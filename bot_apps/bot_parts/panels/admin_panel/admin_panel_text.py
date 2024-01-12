from aiogram.fsm.context import FSMContext

from bot_apps.bot_parts.panels.admin_panel.admin_panel_functions import find_range_value, get_user_info, get_all_tasks, \
    get_task_info, get_task_id, get_return_flag, get_task_distribution, get_reduse_executions, get_profile_link, \
    get_post_link, get_workers, get_task_price, SettingsTaskPrice, find_out_about_price_changes, get_priority_settings, \
    find_out_about_priority_setting, find_out_about_awards_cut_setting, get_settings_awards_cut, \
    get_level_for_change_limits, get_change_tasks_day, get_change_accs_on_task, get_level_for_receiving_limits, \
    get_change_need_tasks, get_change_need_active_accs, get_new_admin, get_remove_admin, get_new_support, \
    get_remove_support, get_new_balance, get_tg_id, get_new_priority, correct_number_for_text_about_delete
from bot_apps.bot_parts.panels.admin_panel.admin_panel_functions import get_tasks_page
from bot_apps.bot_parts.personal_tasks.personal_task_text import text_for_task_actions, text_for_task_comment, \
    text_for_user_links, \
    sorted_actions_dict
from bot_apps.other_apps.wordbank import admin_panel
from databases.database import Database
from databases.dataclasses_storage import AdminPanelMainInfo, UsersList, UserAllInfo, ActionsInfo, TaskAllInfo, \
    UserAccount, UserPayments, UserFines, AllInfoLimits, AwardsCut, UsersPerformTask, SentTasksInfo, UserTasksInfo, \
    AllTasks, RealPricesTask, PriorityChange, AdminInfo, SupportInfo

db = Database()


async def main_text_builder(tg_id: int) -> str:
    """Текст при открыти главного меню"""
    main_info: AdminPanelMainInfo = await db.get_main_info_for_admin_panel(tg_id)
    return admin_panel['main_text'].format(
        main_info.now_time.strftime("%d-%m-%Y"),
        main_info.admin_balance,
        main_info.received_today,
        main_info.spent_on_task,
        main_info.refund_today,
        main_info.earned_by_workers,
        main_info.new_users,
        main_info.new_accounts,
        main_info.new_tasks,
        main_info.sended_tasks,
        main_info.completed_tasks,
        main_info.sended_fines)


def users_menu_text(users_list: list[UsersList], page: int) -> str:
    """Текст при открытии меню с пользователями"""
    limits = find_range_value(page, len(users_list))
    text = admin_panel['users_menu']
    for user in users_list[limits.lower_limit:limits.upper_limit]:
        text += admin_panel['users_info_frame'].format(
            user.tg_id,
            user.username,
            user.registration_date.strftime('%d-%m-%Y %H:%M:%S'),
            user.priority,
            user.level,
            user.number_accounts,
            user.number_completed,
            user.number_add_tasks,
            user.number_active_tasks,
            user.number_fines)
    return text


async def all_user_info_text(state: FSMContext) -> str:
    """Получить всю информацию о пользователе"""
    tg_id = await get_tg_id(state)
    user_info: UserAllInfo = await db.get_all_info_for_user(tg_id)
    user_info.date_join = user_info.date_join.strftime('%d-%m-%Y %H:%M:%S')
    text_list = list(vars(user_info).values())
    text_list[26] = _get_active_tasks_now(user_info)
    text = admin_panel['all_user_info_frame'].format(*text_list)
    await state.update_data(user_info=user_info)
    return text


def _get_active_tasks_now(user_info: UserAllInfo) -> str:
    """Получить текста с активными заданиями юзера"""
    if user_info.number_tasks_active_now:
        return ', '.join([f'<code>{val}</code>' for val in user_info.number_tasks_active_now])
    return '<code>отсутствуют</code>'


async def get_user_text_dict(text: str, state: FSMContext) -> str:
    """Начальный текст для некоторых меню и полный текст для других"""
    user_info: UserAllInfo = await get_user_info(state)
    text_dict = {'tasks_sent_history': admin_panel['open_tasks_sent_history'].format(user_info.telegram_name),
                 'tasks_personal_history': admin_panel['open_tasks_personal_history'].format(user_info.telegram_name),
                 'all_accounts': admin_panel['open_all_accounts'].format(user_info.telegram_name),
                 'fines_history': admin_panel['open_fines_history'].format(user_info.telegram_name),
                 'payment_history': admin_panel['open_payment_history'].format(user_info.telegram_name),
                 'change_balance': admin_panel['change_user_balance'].format(user_info.telegram_name, user_info.balance),
                 'change_priority': admin_panel['change_user_priority'].format(user_info.telegram_name, user_info.priority),
                 'change_level': admin_panel['change_user_level'].format(user_info.telegram_name, user_info.level),
                 'adding_fines': admin_panel['adding_user_fines'].format(user_info.telegram_name, user_info.fines_on_priority, user_info.sum_of_fines),
                 'remove_fines': admin_panel['remove_user_fines'].format(user_info.telegram_name),
                 'message_from_bot': admin_panel['message_from_bot'].format(user_info.telegram_name)}
    return text_dict[text]


async def coinfirm_change_user_balance_text(state: FSMContext) -> str:
    """Текст под изменением баланса юзера"""
    user_info: UserAllInfo = await get_user_info(state)
    new_balance = await get_new_balance(state)
    return admin_panel['cionfirm_user_balance'].format(
        user_info.telegram_name, new_balance)


async def change_user_priority_text(state: FSMContext) -> str:
    """Текст под изменением приоритета юзера"""
    user_info: UserAllInfo = await get_user_info(state)
    new_proiority = await get_new_priority(state)
    return admin_panel['coinfirm_user_priority'].format(
        user_info.telegram_name, new_proiority)


async def priority_fines_text(state: FSMContext) -> str:
    """Текст под добавлением штрафа на приоритет"""
    user_info: UserAllInfo = await get_user_info(state)
    return admin_panel['input_fines_priority'].format(user_info.telegram_name)


async def stb_fines_text(state: FSMContext) -> str:
    """Текст под добавлением штрафа на STB"""
    user_info: UserAllInfo = await get_user_info(state)
    return admin_panel['input_fines_stb'].format(user_info.telegram_name, user_info.balance, user_info.sum_of_fines, )


async def message_from_bot_text(state: FSMContext) -> str:
    """Текст под указанием сообщения для юзера"""
    user_info: UserAllInfo = await get_user_info(state)
    return admin_panel['message_from_bot'].format(user_info.telegram_name)


async def confirm_user_message_text(state: FSMContext, message: str) -> str:
    """Текст под подтверждением отправки сообщения юзеру"""
    user_info: UserAllInfo = await get_user_info(state)
    return admin_panel['confirm_message_from_bot'].format(user_info.telegram_name, message)


async def sent_tasks_user_text(state: FSMContext, tasks_info: list[SentTasksInfo], page: int = 1) -> str:
    """Текст с заданиями, отправленными юзеру"""
    text = await get_user_text_dict('tasks_sent_history', state)
    limits = find_range_value(page, len(tasks_info))
    for task in tasks_info[limits.lower_limit:limits.upper_limit]:
        text += admin_panel['sent_tasks_user_frame'].format(
            task.task_id,
            admin_panel['executions_status'][task.status],
            task.offer_time.strftime('%d-%m-%Y %H:%M:%S') if task.offer_time else '-',
            task.complete_time.strftime('%d-%m-%Y %H:%M:%S') if task.complete_time else '-')
    return text


async def user_tasks_text(state: FSMContext, user_tasks: list[UserTasksInfo], page: int = 1) -> str:
    """Текст с заданиями, которые создал сам юзер"""
    text = await get_user_text_dict('tasks_personal_history', state)
    limits = find_range_value(page, len(user_tasks))
    for task in user_tasks[limits.lower_limit:limits.upper_limit]:
        text += admin_panel['user_tasks_frame'].format(
            task.task_id,
            task.status.value,
            task.date_of_creation.strftime('%d-%m-%Y %H:%M:%S') if task.date_of_creation else '-',
            task.date_of_completed.strftime('%d-%m-%Y %H:%M:%S') if task.date_of_completed else '-',
            task.count_executions)
    return text

async def user_account_text(state: FSMContext, user_accounts: list[UserAccount], page: int = 1) -> str:
    """Текст под аккаунтами юзера"""
    text = await get_user_text_dict('all_accounts', state)
    limits = find_range_value(page, len(user_accounts))
    for account in user_accounts[limits.lower_limit:limits.upper_limit]:
        text += admin_panel['user_account_frame'].format(
            account.account_name,
            admin_panel['accounts_status'][account.account_status],
            account.total_executions,
            account.adding_time.strftime('%d-%m-%Y %H:%M:%S'))
    return text


async def user_fines_text(state: FSMContext, user_fines: list[UserFines], page: int) -> str:
    """Текст под штрафами юзера"""
    text = await get_user_text_dict('fines_history', state)
    limits = find_range_value(page, len(user_fines))
    for fine in user_fines[limits.lower_limit:limits.upper_limit]:
        text += admin_panel['user_fines_frame'].format(
            fine.fines_id,
            fine.fines_type,
            fine.date_added,
            fine.contents_fine,
            correct_left(fine))
    return text


def correct_left(user_fine: UserFines) -> str:
    """Текст о том, сколько осталось до отрбаотки штрафа"""
    if user_fine.stb_left:
        return f'<b>Осталось отработать:</b> <code>{user_fine.stb_left}</code>'
    else:
        time_left_str = str(user_fine.time_left).split(".")[0]
        return f'<b>Осталось до конца:</b> <code>{time_left_str}</code>'


async def user_payments_text(state: FSMContext, user_payments: list[UserPayments], page: int = 1) -> str:
    """Текст о всех пополнениях юзера"""
    text = await get_user_text_dict('payment_history', state)
    limits = find_range_value(page, len(user_payments))
    for payment in user_payments[limits.lower_limit:limits.upper_limit]:
        text += admin_panel['user_payments_frame'].format(
            payment.payment_date.strftime('%d-%m-%Y %H:%M:%S'),
            payment.amount_pay,
            payment.issued_by_stb,
            payment.payment_method)
    return text


async def user_remove_fines_text(state: FSMContext, user_fines: list[UserFines], page: int) -> str:
    """Текст с активными штрафами юзера для выбора того, какой удалить"""
    text = await get_user_text_dict('remove_fines', state)
    limits = find_range_value(page, len(user_fines))
    for fine in user_fines[limits.lower_limit:limits.upper_limit]:
        text += admin_panel['user_fines_frame'].format(
            fine.fines_id,
            fine.fines_type,
            fine.date_added,
            fine.contents_fine,
            correct_left(fine))
    return text


async def all_tasks_text(state: FSMContext) -> str:
    """Текст под открытием всех заданий"""
    all_tasks: list[AllTasks] = await get_all_tasks(state)
    page: int = await get_tasks_page(state)
    text = admin_panel['open_all_tasks']
    limits = find_range_value(page, len(all_tasks))
    for task in all_tasks[limits.lower_limit:limits.upper_limit]:
        text += admin_panel['all_task_frame'].format(
            task.task_id,
            task.date_of_creation.strftime('%d-%m-%Y %H:%M:%S'),
            task.status.value,
            task.completed_tasks,
            task.executions,
            task.completion_percent,
            task.total_pay,
            task.doing_now,
            task.remaining_balance)
    return text


async def all_task_info_text(state: FSMContext) -> str:
    task_info: TaskAllInfo = await get_task_info(state)
    actions_info = sorted_actions_dict(ActionsInfo(type_action=task_info.actions, comment_paremeters=None))
    text = admin_panel['all_task_info_frame'].format(
        task_info.task_id,
        task_info.telegram_id,
        task_info.status.value,
        task_info.round,
        task_info.completed_tasks,
        task_info.executions,
        task_info.completion_percent,
        task_info.doing_now,
        task_info.balance,
        task_info.price,
        task_info.total_pay,
        task_info.remaining_balance,
        text_for_task_actions(actions_info),
        text_for_task_comment(task_info.comment_parameters) if task_info.comment_parameters else '',
        text_for_user_links(actions_info.type_action),
        task_info.total_sent,
        task_info.number_not_viewed,
        task_info.number_more,
        task_info.number_hidden,
        task_info.number_start_task,
        task_info.number_refuse,
        task_info.number_refuse_late,
        task_info.number_scored,
        task_info.number_fully_completed,
        task_info.number_process_subscriptions,
        task_info.number_process_likes,
        task_info.number_process_retweets,
        task_info.number_process_comments,
        task_info.number_waiting_link,
        task_info.date_of_creation.strftime('%d-%m-%Y %H:%M:%S') if task_info.date_of_creation else '-',
        task_info.date_of_completed.strftime('%d-%m-%Y %H:%M:%S') if task_info.date_of_completed else '-',
        str(task_info.completion_in).split(".")[0],
        task_info.average_duration)
    return text


async def dop_task_distribution_text(state: FSMContext) -> str:
    """Текст под дополнительным распределением задания"""
    task_info: TaskAllInfo = await get_task_info(state)
    return admin_panel['open_dop_task_distribution'].format(
        task_info.task_id,
        task_info.total_sent,
        task_info.executions - task_info.completed_tasks)


async def confirm_dop_task_distribution_text(state: FSMContext) -> str:
    """Текст под подтверждением ввёдного доп числа для распределения"""
    task_id = await get_task_id(state)
    number = await get_task_distribution(state)
    return admin_panel['confirtm_dop_distribution'].format(
        task_id,
        number)


async def safely_delete_task_text(state: FSMContext) -> str:
    """Текст под меню с безопасным удалением"""
    task_info: TaskAllInfo = await get_task_info(state)
    return admin_panel['open_task_safely_delete_task'].format(
        task_info.task_id,
        *correct_number_for_text_about_delete(task_info))


async def confirm_safely_delete_text(state: FSMContext) -> str:
    """Уведомление о том, что задание было безопасно удалено"""
    task_id = await get_task_id(state)
    return admin_panel['task_safely_delete'].format(task_id)


async def confirm_add_executions_text(text: str, state: FSMContext) -> str:
    """Подтверждение дополнительного добавления выполнений"""
    task_id = await get_task_id(state)
    return admin_panel['confirm_task_distribution'].format(
        text,
        task_id)


async def confirm_eduse_executions_text(state: FSMContext) -> str:
    """Подтверждение уменьшения выполнений"""
    task_id = await get_task_id(state)
    number = await get_reduse_executions(state)
    return admin_panel['confirm_eduse_executions'].format(
        number,
        task_id)


async def task_force_delete_text(state: FSMContext) -> str:
    """Текст под меню с принудительным удалением задани"""
    task_info: TaskAllInfo = await get_task_info(state)
    return admin_panel['task_force_delete'].format(
        task_info.task_id,
        *correct_number_for_text_about_delete(task_info))


async def confirm_force_delete_text(state: FSMContext) -> str:
    """Уведомление о том, что задание было безопасно удалено"""
    task_id = await get_task_id(state)
    return admin_panel['task_force_delete_notification'].format(task_id)


async def task_add_executions_text(state: FSMContext) -> str:
    """Текст под добавлением какого-то кол-ва выполнений"""
    task_info: TaskAllInfo = await get_task_info(state)
    return admin_panel['task_add_executions'].format(
        task_info.task_id,
        task_info.total_sent)


async def reduce_executions_text(state: FSMContext) -> str:
    """Текст под уменьшением кол-ва выполнений"""
    task_info: TaskAllInfo = await get_task_info(state)
    return admin_panel['process_reduce_executions'].format(
        task_info.task_id,
        task_info.completed_tasks,
        task_info.executions,
        task_info.total_sent)


async def notification_for_reduce_executions(state: FSMContext) -> str:
    """Увдеомление при уменьшении кол-ва выполнений"""
    value = await get_return_flag(state)
    return admin_panel['stb_return'] if value else admin_panel['not_stb_return']


async def edit_task_links_text(state: FSMContext) -> str:
    """Текст под меню изменения ссылок"""
    task_info: TaskAllInfo = await get_task_info(state)
    return admin_panel['process_edit_task_link'].format(
        task_info.task_id,
        text_for_user_links(ActionsInfo(type_action=task_info.actions, comment_paremeters=None).type_action))


async def change_link_to_profile_text(state: FSMContext) -> str:
    """Текст после смены ссылки на профиль"""
    task_info: TaskAllInfo = await get_task_info(state)
    link = await get_profile_link(state)
    return admin_panel['change_link_to_profile'].format(
        task_info.task_id,
        task_info.actions_link.account_link if task_info.actions_link.account_link else '-',
        link)


async def change_link_to_post_text(state: FSMContext) -> str:
    """Текст после смены ссылки на пост"""
    task_info: TaskAllInfo = await get_task_info(state)
    link = await get_post_link(state)
    return admin_panel['change_link_to_post'].format(
        task_info.task_id,
        task_info.actions_link.post_link if task_info.actions_link.post_link else '-',
        link)


async def coinfirm_change_link_to_profile_text(state: FSMContext) -> str:
    """Подтвердить смену ссылку на профиль"""
    task_id = await get_task_id(state)
    link = await get_profile_link(state)
    return admin_panel['coinfirm_change_link_to_profile'].format(
        task_id,
        link)


async def coinfirm_change_link_to_post_text(state: FSMContext) -> str:
    """Потвердить смену ссылки на пост"""
    task_id = await get_task_id(state)
    link = await get_post_link(state)
    return admin_panel['coinfirm_change_link_to_post'].format(
        task_id,
        link)


async def sent_task_text(state: FSMContext) -> str:
    """Текст под меню отправки задания на прохождение"""
    task_info: TaskAllInfo = await get_task_info(state)
    return admin_panel['process_sent_task'].format(
        task_info.task_id,
        task_info.executions - task_info.completed_tasks,
        task_info.doing_now)


async def sending_task_notification(tg_id: int, state: FSMContext) -> str:
    """Сообщение о том, что задание было отправлено другому юзеру"""
    task_id = await get_task_id(state)
    return admin_panel['task_sending'].format(
        task_id,
        tg_id)


async def show_workers_text(state: FSMContext, page: int) -> str:
    taks_info: TaskAllInfo = await get_task_info(state)
    workers: list[UsersPerformTask] = await get_workers(state)
    limits = find_range_value(page, len(workers))
    text = admin_panel['all_task_frame'].format(
        taks_info.task_id,
        taks_info.date_of_creation,
        taks_info.status.value,
        taks_info.completed_tasks,
        taks_info.executions,
        taks_info.completion_percent,
        taks_info.total_pay,
        taks_info.doing_now,
        taks_info.remaining_balance)
    for worker in workers[limits.lower_limit:limits.upper_limit]:
        text += admin_panel['user_perform_frame'].format(
            worker.tg_id,
            worker.telegram_name,
            admin_panel['executions_status'][worker.status],
            worker.date_of_sent.strftime('%d-%m-%Y %H:%M:%S') if worker.date_of_sent else '-')
    return text + admin_panel['interaction_text']


async def price_per_task_text(state: FSMContext) -> str:
    """Текст под указанием нового прайса"""
    task_price: SettingsTaskPrice = await get_task_price(state)
    real_price: RealPricesTask = await db.get_prices_for_tasks()
    text = admin_panel['price_per_task'].format(
        real_price.subscriptions,
        real_price.likes,
        real_price.retweets,
        real_price.comments,
        real_price.commission)
    if await find_out_about_price_changes(state):
        text += '<b>Милорд, вы указали следующие изменения</b>\n'
        index = 1
        for type_task, price in task_price.items():
            if price:
                text += admin_panel['actions_dict'][type_task].format(index, price)
                index += 1
        return f'{text}\n<b>Сохранить изменения?</b>'
    else:
        return f'{text}<b>Укажите, что вы хотите изменить</b>👇'


async def rating_change_text(state: FSMContext) -> str:
    """Текст под изменением приоритета за действия"""
    priority_change: PriorityChange = await db.get_priority_change()
    priority_settings: PriorityChange = await get_priority_settings(state)
    text = admin_panel['change_raiting'].format(
        priority_change['completing_task'],
        priority_change['re_execution'],
        priority_change['max_re_execution'],
        priority_change['complete_others'],
        priority_change['downtime_more_20_min'],
        priority_change['ignore_more_20_min'],
        priority_change['ignore_more_40_min'],
        priority_change['ignore_more_60_min'],
        priority_change['refuse'],
        priority_change['refuse_late'],
        priority_change['scored_on_task'],
        priority_change['ignore_many_times'],
        priority_change['hidden_many_times'],
        priority_change['refuse_many_times'],
        priority_change['scored_many_times'])

    if await find_out_about_priority_setting(state):
        text += '<b>Милорд, вы указали следующие изменения</b>\n'
        index = 1
        for type_setting, price in priority_settings.items():
            if price:
                text += admin_panel['priority_change'][type_setting].format(index, price)
                index += 1
        return f'{text}\n<b>Сохранить изменения?</b>'
    else:
        return f'{text}<b>Укажите параметр, который хотите изменить👇</b>'


async def rule_fines_text(state: FSMContext):
    """Текст под штрафом-порезом"""
    awards_cut: AwardsCut = await db.get_info_awards_cut()
    settings_awards_cut: AwardsCut = await get_settings_awards_cut(state)
    text = admin_panel['awards_cut'].format(
        awards_cut.first_fine,
        awards_cut.subsequent_fines)
    if await find_out_about_awards_cut_setting(state):
        text += '<b>Милорд, вы указали следующие изменения</b>\n'
        if settings_awards_cut.first_fine:
            text += admin_panel['first_fines'].format(settings_awards_cut.first_fine)
        if settings_awards_cut.subsequent_fines:
            text += admin_panel['subsequent_fines'].format(settings_awards_cut.subsequent_fines)
        return f'{text}\n<b>Сохранить изменения?</b>'
    else:
        return f"{text}<b>Укажите процент штрафа, который хотите изменить👇</b>"


async def setting_raiting_fines() -> str:
    """Текст под максимальным уменьшением рейтинга"""
    raiting_fines: int = await db.get_rating_fines()
    return admin_panel['raiting_fines'].format(
        raiting_fines)


def confirm_raitin_fines_text(text: str) -> str:
    """Подтверждение понижения макс. рейтинга"""
    return admin_panel['conifrm_raiting_fines'].format(text)


async def task_fines_text() -> str:
    """Текст под изменением штрафа за макс приоритет"""
    return admin_panel['task_fines'].format(
        await db.get_fines_task_persent())


def coinfirm_task_fines_text(text: str) -> str:
    """Подтверждение изменения штрафа за частое удаление тасков"""
    return admin_panel['confirm_task_fines'].format(text)


async def work_with_levels_text() -> str:
    """Открытие всей инфы об уровнях"""
    all_limits: AllInfoLimits = await db.get_all_info_levels_limits()
    levels_order = list(all_limits.keys())
    levels_parameters = ['tasks_per_day', 'max_accs_on_taks', 'need_task_for_level', 'need_accs_for_level']
    text = admin_panel['work_with_levels'].format(
        *[all_limits[level][field] for level in levels_order for field in levels_parameters])
    return text


async def limits_levels_text() -> str:
    """Текст под инфой о лимитах уровней"""
    all_limits: AllInfoLimits = await db.get_all_info_levels_limits()
    levels_order = list(all_limits.keys())
    levels_parameters = ['tasks_per_day', 'max_accs_on_taks']
    return admin_panel['levels_limits'].format(
        *[all_limits[level][field] for level in levels_order for field in levels_parameters])


async def change_level_limits(level: str) -> str:
    """Админ выбирает, что ему изменить"""
    all_limits: AllInfoLimits = await db.get_all_info_levels_limits()
    return admin_panel['change_level_limits'].format(
        level,
        all_limits[level]['tasks_per_day'],
        all_limits[level]['max_accs_on_taks'])


async def confirm_change_limits_tasks_text(state: FSMContext) -> str:
    """Подтверждение изменения тасков на акк в день"""
    level = await get_level_for_change_limits(state)
    tasks_day = await get_change_tasks_day(state)
    return admin_panel['confirm_change_limits_tasks'].format(
        level,
        tasks_day)


async def confirm_change_limits_accounts_text(state: FSMContext) -> str:
    """Подтверждение изменения макс. выполнений на таск"""
    level = await get_level_for_change_limits(state)
    executions = await get_change_accs_on_task(state)
    return admin_panel['confirm_change_limits_accounts'].format(
        level,
        executions)


async def receiving_limits_text() -> str:
    """Информация о лимитах для достижения уровня"""
    all_limits: AllInfoLimits = await db.get_all_info_levels_limits()
    levels = ['champion', 'challenger', 'main', 'prelim']
    parameters_level = ['need_task_for_level', 'need_accs_for_level']
    return admin_panel['receiving_limits'].format(
        *(all_limits[level][parameter] for level in levels for parameter in parameters_level))


async def change_receiving_limits_text(state: FSMContext) -> str:
    """Меню перед изменением лимитов уровня для его получения"""
    all_limits: AllInfoLimits = await db.get_all_info_levels_limits()
    level = await get_level_for_receiving_limits(state)
    return admin_panel['level_receiving_limits'].format(
        level,
        all_limits[level]['need_task_for_level'],
        all_limits[level]['need_accs_for_level'])


async def confirm_change_need_tasks_text(state: FSMContext) -> str:
    """Подтверждение изменения необходимого кол-ва выполненных тасков для получения уровня"""
    level = await get_level_for_receiving_limits(state)
    number_tasks = await get_change_need_tasks(state)
    return admin_panel['confirm_change_need_tasks'].format(
        level,
        number_tasks)


async def confirm_change_need_active_accs_text(state: FSMContext) -> str:
    """Подтверждение изменения необходимого кол-ва выполненных тасков для получения уровня"""
    level = await get_level_for_receiving_limits(state)
    number_tasks = await get_change_need_active_accs(state)
    return admin_panel['confirm_change_need_active_accs'].format(
        level,
        number_tasks)


async def admins_list_text() -> str:
    admins: list[AdminInfo] = await db.get_info_about_admins()
    text = admin_panel['opening_admin_list']
    for admin in admins:
        text += admin_panel['admin_info_frame'].format(admin.telegram_id,
                                                       admin.telegram_name,
                                                       admin.admin_balance)
    return text


async def conifrm_new_admin_text(state: FSMContext) -> str:
    """Достать указанного админа"""
    return admin_panel['confirm_admin'].format(
        await get_new_admin(state))


async def coinifrn_remove_admin(state: FSMContext) -> str:
    """Тект под подверждение удаления админа"""
    admin_id = await get_remove_admin(state)
    return admin_panel['coinfirm_remove_admin'].format(admin_id)


async def supports_list_text() -> str:
    """Список саппортов"""
    supports: list[SupportInfo] = await db.get_info_about_supports()
    text = admin_panel['supports_list']
    for support in supports:
        text += admin_panel['support_frame'].format(
            support.telegram_id,
            support.telegram_name,
            support.support_balance,
            'Активен' if support.active_status else 'Отдыхает',
            admin_panel['default_support'] if support.main_support else '')
    return text


async def coinfirm_add_support_text(state: FSMContext) -> str:
    """Подтверждение добалвения нового саппорта"""
    return admin_panel['coinfirm_add_support'].format(
        await get_new_support(state))


async def coinfirm_remove_support_text(state: FSMContext) -> str:
    """Подтверждение удаления саппорта"""
    return admin_panel['coinfirm_remove_support'].format(
        await get_remove_support(state))
