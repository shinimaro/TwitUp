import datetime
from dataclasses import dataclass
from typing import Literal

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot_apps.bot_parts.adding_task.adding_task_text import define_price, round_numbers
from databases.database import Database
from databases.dataclasses_storage import LinkAction, CommentParameter

db = Database()


@dataclass(frozen=True, slots=True)
class TasksRange:
    upper_limit: int
    lower_limit: int


@dataclass(frozen=True, slots=True)
class TaskSettingParameters:
    actions: list[Literal['subscriptions', 'likes', 'retweets', 'comments']]
    links: LinkAction
    comment_paremeters: CommentParameter | None


def format_date(date: datetime.datetime) -> str:
    """Форматирует дату в удобочитаемый вид"""
    months_dict = {1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля', 5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа', 9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'}
    return f"{date.date().day} {months_dict[date.date().month]} в {date.time().hour}:{'0' + str(date.time().minute) if date.time().minute < 10 else date.time().minute}"


def find_range_value(page: int, length_tasks: int) -> TasksRange:
    """Найти начальное значение и итоговую страницу, т.к. активные таски могут постоянно удаляться из активных"""
    pg_nm = 8  # Пагинейшн нумбер
    previous_page = page - 1
    # Если нужна первая страница
    if previous_page == 0:
        tasks_range = TasksRange(lower_limit=0, upper_limit=pg_nm)
    # Если не хватает тасков, чтобы перейти на нужную страницу, переходим на страницу ниже
    elif length_tasks <= previous_page * pg_nm:
        tasks_range = TasksRange(lower_limit=length_tasks // pg_nm * pg_nm if length_tasks // pg_nm != 0 else 0,
                                 upper_limit=length_tasks)
    # Если всё ок и тасков хватает для нужной страницы
    else:
        tasks_range = TasksRange(lower_limit=previous_page * pg_nm,
                                 upper_limit=length_tasks if length_tasks - previous_page * pg_nm < pg_nm else previous_page * pg_nm + pg_nm)
    return tasks_range


async def find_page(callback: CallbackQuery, state: FSMContext) -> int:
    """Фанкшин для поиска нужной страницы при открытии активных тасков"""
    if callback.data == 'back_to_active_tasks':
        data = await state.get_data()
        return data.get('active_tasks_page', 1)
    return 1


async def find_history_page(callback: CallbackQuery, state: FSMContext) -> int:
    """Фанкшин для поиска нужной страницы при открытии истории тасков"""
    if callback.data == 'back_to_history_tasks':
        data = await state.get_data()
        return data.get('history_tasks_page', 1)
    return 1


async def initial_task_id(callback: CallbackQuery, state: FSMContext) -> int:
    """Фанкшн для иницилизации task_id"""
    if callback.data.startswith('open_active_task_'):  # Записать новый task_id
        task_id = int(callback.data[17:])
        await state.update_data(active_task_id=task_id)
    else:
        task_id = await get_task_id(state)  # Взять готовый
    return task_id


async def inirial_history_task_id(callback: CallbackQuery, state: FSMContext) -> int:
    """Инициализация task_id в истории"""
    if callback.data.startswith('open_history_task_'):  # Записать новый task_id
        task_id = int(callback.data[18:])
        await state.update_data(history_task_id=task_id)
    else:
        task_id = await get_histoy_task_id(state)  # Взять готовый
    return task_id


async def get_task_id(state: FSMContext) -> int:
    """Фанкшин для поиска task_id"""
    data = await state.get_data()
    return data['active_task_id']


async def get_histoy_task_id(state: FSMContext) -> int:
    """Фанкшин для поиска task_id в истории"""
    data = await state.get_data()
    return data.get('history_task_id')


async def check_increase_executions(tg_id: int, task_id: int) -> bool:
    """Проверить, хватает ли баланса пользователя на добавление минимального кол-ва выполнений"""
    need_balance: int | float = await get_min_price(task_id)
    balance: int | float = await db.check_balance(tg_id)
    return need_balance > balance


async def get_min_price(task_id: int) -> int | float:
    """Посчитать цену 5 выполнений"""
    actions_list: list[str] = await db.get_actions_list(task_id)
    return await define_price(actions_list, count=5)


async def update_state(state: FSMContext) -> None:
    """Убрать из state состояние и оставить task_id"""
    data = await state.get_data()
    key = data.get('active_task_id')
    await state.clear()
    await state.update_data(active_task_id=key)


async def check_balance_sufficiency(task_id: int, executions) -> bool:
    """Проверка, что баланса юзера хватит на оплату задания"""
    tg_id = await db.get_telegram_id_from_tasks(task_id)
    balance = await db.check_balance(tg_id)
    need_balance = await define_price(await db.get_actions_list(task_id), int(executions))
    return balance >= need_balance


async def get_remaining_taks_balance_with_penalty(task_id: int) -> float:
    """Найти баланс задания, учитвая штраф"""
    return round_numbers(await db.check_balance_task(task_id) - await get_sum_penalty(task_id))


async def get_sum_penalty(task_id: int) -> float | int:
    """Найти велечину штрафа в STB"""
    sum_fines = await db.get_fines_task_persent()
    return await db.check_balance_task(task_id) / 100 * sum_fines


async def get_sum_refund_with_penalty(task_id):
    """Получить оставшийся баланс задания с учётом штрафа"""
    emaining_balance = await db.check_remaining_task_balance(task_id)
    return max(emaining_balance - await get_sum_penalty(task_id), 0)


async def distribution_active_tasks_pages(tg_id: int, state: FSMContext) -> int | None:
    """Определяет, какую страницу активных тасков открыть после удаления задания"""
    if await db.get_count_active_tasks(tg_id) > 0:
        data = await state.get_data()
        get_page = data.get('active_tasks_page')
        return get_page if get_page else 1
    else:
        return None


async def duplicate_task_settings(task_id: int) -> dict:
    """Дублирует настройки задания для его создания"""
    all_task_parameters: TaskSettingParameters = await collect_all_task_parameters(task_id)
    data = {'accepted': {'profile_link': False, 'post_link': False, 'comment_parameters': {}},
            'setting_actions': all_task_parameters.actions}
    data['accepted']['profile_link'] = all_task_parameters.links.account_link
    data['accepted']['post_link'] = all_task_parameters.links.post_link
    if all_task_parameters.comment_paremeters:
        data['accepted']['comment_parameters']['one_value'] = {
            'words': all_task_parameters.comment_paremeters.get('words_count'),
            'tags': all_task_parameters.comment_paremeters.get('tags_count'),
            'tags/words': all_task_parameters.comment_paremeters.get('words_tags')}
        data['accepted']['comment_parameters']['note'] = all_task_parameters.comment_paremeters.get('note')
        data['accepted']['comment_parameters']['only_english'] = all_task_parameters.comment_paremeters.get('english')
    return data


# Собрать параметры с таска
async def collect_all_task_parameters(task_id: int) -> TaskSettingParameters:
    return TaskSettingParameters(
        actions=await db.get_actions_list(task_id),
        links=await db.get_links_on_task(task_id),
        comment_paremeters=await db.get_comment_parameters(task_id))
