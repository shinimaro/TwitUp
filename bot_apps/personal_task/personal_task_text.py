import asyncio
import datetime
import time

from aiogram.types import CallbackQuery

from bot_apps.personal_task.adding_task.adding_task_text import final_text_builder, define_price, round_numbers
from bot_apps.personal_task.personal_task_functions import format_date, get_min_price, find_range_value, get_sum_penalty, \
    get_remaining_taks_balance_with_penalty
from bot_apps.wordbank import personal_task
from databases.database import db, ActiveTasks, ActiveTask, CommentParameter, ActionsInfo, InfoIncreasedExecutions, \
    RemainingTaskBalance, HistoryTasks, HistoryTask


async def personal_tasks_menu_text(tg_id: int) -> str:
    """Билдер текста основного меню"""
    return personal_task['main_text'].format(
        await db.check_balance(tg_id),
        await db.get_count_active_tasks(tg_id),
        await db.get_count_all_tasks(tg_id))


async def active_tasks_menu_text(tg_id: int, page: int) -> str:
    """Билдер меню с активными тасками"""
    tasks: dict[int, ActiveTasks] = await db.get_active_tasks_inforamtions(tg_id)
    text = personal_task['active_tasks_startwith']
    tasks_range = find_range_value(page, len(tasks))
    for task_id in list(tasks.keys())[tasks_range.lower_limit:tasks_range.upper_limit]:
        task_info = tasks[task_id]
        text += personal_task['active_tasks_frame'].format(
            task_info.task_number,
            format_date(task_info.date_of_creation),
            task_info.number_actions,
            task_info.status.value,
            task_info.completion_percentage)
    return text


async def history_tasks_menu_text(tg_id: int, page: int):
    """Билдер мнею с тасками в истории"""
    text = personal_task['history_tasks_startwith']
    tasks: dict[int, HistoryTasks] = await db.get_history_tasks_informations(tg_id)
    tasks_range = find_range_value(page, len(tasks))
    for task_id in list(tasks.keys())[tasks_range.lower_limit:tasks_range.upper_limit]:
        task_info = tasks[task_id]
        text += personal_task['history_tasks_frame'].format(
            task_info.task_number,
            format_date(task_info.date_of_creation),
            _get_time_completed_text(task_info),
            task_info.status.value,
            task_info.completed_task,
            task_info.executions,
            task_info.completion_percentage,
            task_info.total_pay,
            _fines_text(task_info),
            _text_for_task_actions(task_info.type_action))
    return text


async def active_task_text(task_id: int) -> str:
    """Билдер текста с информацией об активном задании"""
    task: ActiveTask = await db.get_active_task_info(task_id)
    return personal_task['active_task_info_frame'].format(
        task.task_number,
        format_date(task.date_of_creation),
        _text_for_task_actions(task.actions_info),
        _text_for_user_links(task.actions_info.type_action),
        task.status.value,
        task.number_completed,
        task.executions,
        task.completion_percent,
        task.doing_now,
        task.total_pay,
        task.remaining_balance)


async def history_task_text(task_id: int) -> str:
    """Билдер текста с информацией о задании в истории"""
    task: HistoryTask = await db.get_history_task_info(task_id)
    return personal_task['history_task_info_frame'].format(
        task.task_number,
        format_date(task.date_of_creation),
        _get_time_completed_text(task),
        _text_for_task_actions(task.actions_info),
        _text_for_user_links(task.actions_info.type_action),
        task.status.value,
        task.completed_task,
        task.executions,
        task.completion_percent,
        task.total_pay,
        _fines_text(task))


async def increased_executions_text(task_id: int) -> str:
    """Билдер текста в менюшке ввода дополнительного кол-ва выполнений"""
    info: InfoIncreasedExecutions = await db.info_for_increased_executions(task_id)
    text = personal_task['increased_executions'].format(
        info.executions,
        info.number_completed,
        info.price,
        info.balance)
    return text


async def prefix_not_enter_number(task_id: int) -> str:
    """Приставляет к тексту то, что юзер ввёл не число"""
    return (await increased_executions_text(task_id) +
            personal_task['not_number_prefix'])


async def prefix_not_correct_number(task_id: int) -> str:
    """Приставляет к тексту то, что юзер ввёл больше выполнений, чем может"""
    return (await increased_executions_text(task_id) +
            personal_task['not_correct_executions'])


async def not_balance_for_increased_executions(tg_id: int, task_id: int) -> str:
    """Билдер всплывающего текста о том, что баланса на добавление мин. кол-ва выполнений не хватает"""
    return personal_task['not_balance_for_min_increased_executions'].format(
        await db.check_balance(tg_id),
        await get_min_price(task_id))


async def insufficient_balance_for_executions(tg_id: int, task_id: int, executions: int) -> str:
    """Билдер всплывающего текста о том, что баланса уже не хватает для добавление нужного кол-ва выполнений"""
    return personal_task['not_balance_for_max_increased_executions'].format(
        await db.check_balance(tg_id),
        executions,
        await get_min_price(task_id))


async def task_executions_updated(tg_id: int, executions: int) -> str:
    """Всплывающее сообщение об успешно обновлении задания"""
    return personal_task['task_executions_updated'].format(
        executions,
        await db.check_balance(tg_id))


async def add_new_executions_text(*, tg_id: int, task_id: int, add_executions: int) -> str:
    """Билдер текста перед добавлением нового кол-ва выполнений"""
    balance = await db.check_balance(tg_id)
    actions_list = await db.get_actions_list(task_id)
    price = await define_price(actions_list, add_executions)
    return personal_task['add_new_executions'].format(
        add_executions,
        price,
        balance,
        round_numbers(balance - price),
        await final_text_builder(actions_list))


async def define_warning_text_before_deletion(callback: CallbackQuery, task_id: int) -> str:
    """Определить текст, который будет стоять в предупрежедении перед удалением"""
    task_info: RemainingTaskBalance = await db.get_remaining_task_balance(task_id)
    if task_info.status == 'waiting_start':  # Без предупреждение
        return _warning_delete_note_start_task(task_info)
    elif (callback.data == 'continue_delete_task' or
          await db.check_quantity_delete_task(callback.from_user.id, task_id, 3)):  # Опасное предупреждение
        return _warning_about_rewards_distribution(task_info)
    elif task_info.number_workers < 1:  # Обычное предупреждение без юзеров
        return _warning_delete_task(task_info)
    else:
        return _warning_with_users(task_info)  # Обычное предупреждение с юзерами


async def delete_task_notification(task_id: int) -> str:
    """Уведомление об удалении неначавшегося задания"""
    return personal_task['delete_task_notification'].format(
        round_numbers(await db.check_balance_task(task_id)))


async def delete_task_text(task_id: int) -> str:
    """Текст о том, что задание удалено"""
    return personal_task['delete_task_text'].format(
        round_numbers(await db.check_remaining_task_balance(task_id)))


async def delete_task_with_penalty(task_id: int) -> str:
    """Задание удалено, но часть наград была раздана другим пользователям"""
    return personal_task['delete_task_with_penalty'].format(
        round_numbers(await get_sum_penalty(task_id)),
        await get_remaining_taks_balance_with_penalty(task_id))


def collect_fines_text(sum_fines: float) -> str:
    return personal_task['collection_fines'].format(sum_fines)


def _get_time_completed_text(task_info: HistoryTasks) -> str:
    if task_info.date_of_completed:
        return personal_task['time_completed_for_history'].format(
            format_date(task_info.date_of_completed),
            _get_correct_date(task_info.completion_in))
    return ''


def _get_correct_date(date: datetime.timedelta):
    """Показывает в виде текста, за сколько завершилось задание"""
    hours = str(date.seconds // 3600)
    minutes = str((date.seconds % 3600) // 60)
    text = []
    if date.days > 0:
        days = str(date.days)
        date_dict = {'1': 'день', '2': 'дня', '3': 'дня', '4': 'дня',
                     'exceptions': ['11', '12', '13', '14']}
        text = f"{days} {'дней' if days in date_dict['exceptions'] else date_dict.get(days[-1], 'дней')}"

    if int(hours) > 0:
        hurs_dict = {'1': 'час', '2': 'часа', '3': 'часа', '4': 'часа',
                     'exceptions': ['11', '12', '13', '14']}
        text.append(f"{hours} {'часов' if hours in hurs_dict['exceptions'] else hurs_dict.get(hours[-1], 'часов')}")
    if int(minutes) > 0:
        minute_dict = {'1': 'минуту', '2': 'минуты', '3': 'минуты', '4': 'минуты',
                       'exceptions': ['11', '12', '13', '14']}
        text.append(f"{minutes} {'минут' if minutes in minute_dict['exceptions'] else minute_dict.get(minutes[-1], 'минут')}")
    return ' '.join(text)


def _fines_text(task_info: HistoryTasks | HistoryTask) -> str:
    """Текст со штрафом в истории заданий"""
    return personal_task['fines_text'].format(task_info.fines) if task_info.fines else ''


def _warning_delete_note_start_task(task_info: RemainingTaskBalance) -> str:
    """Вопрос перед удалением таска, кторый ещё не был стартанут"""
    return personal_task['warnings']['delete_task_warning_1'].format(
        personal_task['warnings']['balance_prefix'].format(
            task_info.balance_task))


def _warning_delete_task(task_info: RemainingTaskBalance) -> str:
    """Текст с предупреждением перед удалением без пользователей, делающих таск"""
    return personal_task['warnings']['delete_task_warning_2'].format(
        task_info.number_sent_users) + _prefix_warning_delete(
        task_info.remaining_task_balance)


def _warning_with_users(task_info: RemainingTaskBalance) -> str:
    """Текст с обычным предупреждением с пользователями, которые делают таск"""
    return personal_task['warnings']['delete_task_warning_3'].format(
        task_info.number_rewards,
        task_info.number_workers) + _prefix_warning_delete(
        task_info.remaining_task_balance)


def _warning_about_rewards_distribution(task_info: RemainingTaskBalance) -> str:
    """Текст с предупреждением, что сейчас награды юзерам раздадим и всё"""
    dop_text = personal_task['warnings']['dop_text_for_warning_5'].format(task_info.number_rewards, task_info.number_workers) if task_info.number_workers else ''
    send_rewards = round_numbers(task_info.balance_task / 100 * 30)
    remaining_task_balance = task_info.remaining_task_balance - send_rewards
    return personal_task['warnings']['delete_task_warning_5'].format(
        send_rewards, dop_text) + _prefix_warning_delete(remaining_task_balance)


def _prefix_warning_delete(remaining_task_balance: int | float):
    """Билдер префикса к предупреждению об удалении"""
    return personal_task['warnings']['balance_prefix'].format(round_numbers(remaining_task_balance))


def _text_for_task_actions(actions_info: ActionsInfo) -> str:
    """Билдер текста действий в задании с ссылкой"""
    actions_info = _sorted_actions_dict(actions_info)
    text = ''
    for key, action in enumerate(actions_info.type_action, start=1):
        text += f"<b>{key}.</b> {personal_task['text_for_actions'][action].format(actions_info.type_action[action])}\n"
    if actions_info.comment_paremeters:
        text += _text_for_task_comment(actions_info.comment_paremeters)
    return text


def _text_for_task_comment(comment_parameter: CommentParameter) -> str:
    """Билдер текста для комментария"""
    text = '\n<b>Комментарий должен:</b>\n'
    for key, value in comment_parameter.items():
        text += personal_task['text_for_comment_parameters'][key].format(value) + '\n' if value else ''
    return text


def _sorted_actions_dict(actions_dict: ActionsInfo) -> ActionsInfo:
    """Отсортировать словарь с типами тасков"""
    words_actions = {1: 'subscriptions', 2: 'likes', 3: 'retweets', 4: 'comments'}
    sorted_words_actions = dict(sorted(actions_dict.type_action.items(), key=lambda item: words_actions.get(item[1], float('inf'))))
    return ActionsInfo(type_action=sorted_words_actions, comment_paremeters=actions_dict.comment_paremeters)


def _text_for_user_links(type_action: ActionsInfo.type_action) -> str:
    """Билдер с указанными ссылками пользователя"""
    text = ''
    for link in type_action.values():  # Предпологается, что дикт отсортирован
        link = 'example/status/' if link is None else link
        if '/status/' not in link:
            text += f'<b>1.</b> Ссылка на профиль {link}\n'
        else:
            if '/status/' in link and not text:
                text += f'<b>1.</b> Ссылка на пост - {link}\n'
            else:
                text += f'<b>2.</b> Ссылка на пост - {link}\n'
            break
    return text

