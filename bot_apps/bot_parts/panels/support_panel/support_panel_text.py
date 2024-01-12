from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot_apps.bot_parts.panels.admin_panel.admin_panel_functions import find_range_value, get_user_info, \
    get_new_balance, \
    get_new_priority, get_all_tasks, get_tasks_page, get_task_info, get_task_distribution, \
    correct_number_for_text_about_delete, get_reduse_executions, get_task_id
from bot_apps.bot_parts.panels.admin_panel.admin_panel_text import correct_left
from bot_apps.bot_parts.panels.support_panel.support_panel_functions import get_task_id_for_accepted
from bot_apps.other_apps.wordbank import support_panel, admin_panel
from databases.database import Database
from databases.dataclasses_storage import SupportPanelInfo, UsersList, UserAllInfo, SentTasksInfo, UserTasksInfo, \
    UserFines, UserPayments, TaskAllInfo, UserAccount, AllTasks

db = Database()


async def main_menu_text(tg_id: int) -> str:
    """Текст под панелью с главным меню"""
    info: SupportPanelInfo = await db.get_info_for_support_panel(tg_id)
    return support_panel['main_text'].format(
        'Активен' if info.status else 'Не активен',
        info.main_support,
        info.active_tasks,
        info.number_offers,
        info.active_workers)


def change_status_text(callback: CallbackQuery) -> str:
    """Уведомление под сменой статуса актива"""
    if callback.data == 'support_stopped_working':
        return support_panel['active_status_false']
    return support_panel['active_status_true']


def change_default_support_text(callback: CallbackQuery) -> str:
    """Уведомление под сменой дефолт саппорта"""
    if callback.data == 'support_defaulted_support':
        return support_panel['defaulted_support']
    return support_panel['not_default_support']


def sup_users_menu_text(users_list: list[UsersList], page: int) -> str:
    """Текст при открытии меню с пользователями"""
    limits = find_range_value(page, len(users_list))
    text = support_panel['users_menu']
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


async def sup_get_user_text_dict(text: str, state: FSMContext) -> str:
    """Начальный текст для некоторых меню и полный текст для других"""
    user_info: UserAllInfo = await get_user_info(state)
    text_dict = {'tasks_sent_history': support_panel['open_tasks_sent_history'].format(user_info.telegram_name),
                 'tasks_personal_history': support_panel['open_tasks_personal_history'].format(user_info.telegram_name),
                 'all_accounts': support_panel['open_all_accounts'].format(user_info.telegram_name),
                 'fines_history': support_panel['open_fines_history'].format(user_info.telegram_name),
                 'payment_history': support_panel['open_payment_history'].format(user_info.telegram_name),
                 'change_balance': support_panel['change_user_balance'].format(user_info.telegram_name, user_info.balance),
                 'change_priority': support_panel['change_user_priority'].format(user_info.telegram_name, user_info.priority),
                 'change_level': support_panel['change_user_level'].format(user_info.telegram_name, user_info.level),
                 'adding_fines': support_panel['adding_user_fines'].format(user_info.telegram_name, user_info.fines_on_priority, user_info.sum_of_fines),
                 'remove_fines': support_panel['remove_user_fines'].format(user_info.telegram_name),
                 'message_from_bot': support_panel['message_from_bot'].format(user_info.telegram_name)}
    return text_dict[text]


async def sup_coinfirm_change_user_balance_text(state: FSMContext) -> str:
    """Текст под изменением баланса юзера"""
    user_info: UserAllInfo = await get_user_info(state)
    new_balance = await get_new_balance(state)
    return support_panel['cionfirm_user_balance'].format(
        user_info.telegram_name, new_balance)


async def sup_change_user_priority_text(state: FSMContext) -> str:
    """Текст под изменением приоритета юзера"""
    user_info: UserAllInfo = await get_user_info(state)
    new_proiority = await get_new_priority(state)
    return support_panel['coinfirm_user_priority'].format(
        user_info.telegram_name, new_proiority)


async def sup_priority_fines_text(state: FSMContext) -> str:
    """Текст под добавлением штрафа на приоритет"""
    user_info: UserAllInfo = await get_user_info(state)
    return support_panel['input_fines_priority'].format(user_info.telegram_name)


async def sup_stb_fines_text(state: FSMContext) -> str:
    """Текст под добавлением штрафа на STB"""
    user_info: UserAllInfo = await get_user_info(state)
    return support_panel['input_fines_stb'].format(user_info.telegram_name, user_info.balance, user_info.sum_of_fines, )


async def sup_message_from_bot_text(state: FSMContext) -> str:
    """Текст под указанием сообщения для юзера"""
    user_info: UserAllInfo = await get_user_info(state)
    return support_panel['message_from_bot'].format(user_info.telegram_name)


async def sup_confirm_user_message_text(state: FSMContext, message: str) -> str:
    """Текст под подтверждением отправки сообщения юзеру"""
    user_info: UserAllInfo = await get_user_info(state)
    return support_panel['confirm_message_from_bot'].format(user_info.telegram_name, message)


async def sup_sent_tasks_user_text(state: FSMContext, tasks_info: list[SentTasksInfo], page: int = 1) -> str:
    """Текст с заданиями, отправленными юзеру"""
    text = await sup_get_user_text_dict('tasks_sent_history', state)
    limits = find_range_value(page, len(tasks_info))
    for task in tasks_info[limits.lower_limit:limits.upper_limit]:
        text += admin_panel['sent_tasks_user_frame'].format(
            task.task_id,
            admin_panel['executions_status'][task.status],
            task.offer_time.strftime('%d-%m-%Y %H:%M:%S') if task.offer_time else '-',
            task.complete_time.strftime('%d-%m-%Y %H:%M:%S') if task.complete_time else '-')
    return text


async def sup_user_tasks_text(state: FSMContext, user_tasks: list[UserTasksInfo], page: int = 1) -> str:
    """Текст с заданиями, которые создал сам юзер"""
    text = await sup_get_user_text_dict('tasks_personal_history', state)
    limits = find_range_value(page, len(user_tasks))
    for task in user_tasks[limits.lower_limit:limits.upper_limit]:
        text += admin_panel['user_tasks_frame'].format(
            task.task_id,
            task.status.value,
            task.date_of_creation.strftime('%d-%m-%Y %H:%M:%S') if task.date_of_creation else '-',
            task.date_of_completed.strftime('%d-%m-%Y %H:%M:%S') if task.date_of_completed else '-',
            task.count_executions)
    return text


async def sup_accept_task_for_accept(state: FSMContext) -> str:
    """Клавиатура под подтверждением того, что выполнение этого таска нужно засчитать"""
    task_id = await get_task_id_for_accepted(state)
    return support_panel['coinfirm_accept_task'].format(task_id)


async def sup_user_account_text(state: FSMContext, user_accounts: list[UserAccount], page: int = 1) -> str:
    """Текст под аккаунтами юзера"""
    text = await sup_get_user_text_dict('all_accounts', state)
    limits = find_range_value(page, len(user_accounts))
    for account in user_accounts[limits.lower_limit:limits.upper_limit]:
        text += admin_panel['user_account_frame'].format(
            account.account_name,
            admin_panel['accounts_status'][account.account_status],
            account.total_executions,
            account.adding_time.strftime('%d-%m-%Y %H:%M:%S'))
    return text


async def sup_user_fines_text(state: FSMContext, user_fines: list[UserFines], page: int) -> str:
    """Текст под штрафами юзера"""
    text = await sup_get_user_text_dict('fines_history', state)
    limits = find_range_value(page, len(user_fines))
    for fine in user_fines[limits.lower_limit:limits.upper_limit]:
        text += admin_panel['user_fines_frame'].format(
            fine.fines_id,
            fine.fines_type,
            fine.date_added,
            fine.contents_fine,
            correct_left(fine))
    return text


async def sup_user_payments_text(state: FSMContext, user_payments: list[UserPayments], page: int = 1) -> str:
    """Текст о всех пополнениях юзера"""
    text = await sup_get_user_text_dict('payment_history', state)
    limits = find_range_value(page, len(user_payments))
    for payment in user_payments[limits.lower_limit:limits.upper_limit]:
        text += admin_panel['user_payments_frame'].format(
            payment.payment_date.strftime('%d-%m-%Y %H:%M:%S'),
            payment.amount_pay,
            payment.issued_by_stb,
            payment.payment_method)
    return text


async def sup_user_remove_fines_text(state: FSMContext, user_fines: list[UserFines], page: int) -> str:
    """Текст с активными штрафами юзера для выбора того, какой удалить"""
    text = await sup_get_user_text_dict('remove_fines', state)
    limits = find_range_value(page, len(user_fines))
    for fine in user_fines[limits.lower_limit:limits.upper_limit]:
        text += admin_panel['user_fines_frame'].format(
            fine.fines_id,
            fine.fines_type,
            fine.date_added,
            fine.contents_fine,
            correct_left(fine))
    return text


async def sup_all_tasks_text(state: FSMContext) -> str:
    """Текст под открытием всех заданий"""
    all_tasks: list[AllTasks] = await get_all_tasks(state)
    page: int = await get_tasks_page(state)
    text = support_panel['open_all_tasks']
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


async def sup_dop_task_distribution_text(state: FSMContext) -> str:
    """Текст под дополнительным распределением задания"""
    task_info: TaskAllInfo = await get_task_info(state)
    return support_panel['open_dop_task_distribution'].format(
        task_info.task_id,
        task_info.total_sent,
        task_info.executions - task_info.completed_tasks)


async def sup_confirm_dop_task_distribution_text(state: FSMContext) -> str:
    """Текст под подтверждением ввёдного доп числа для распределения"""
    task_id = await get_task_id(state)
    number = await get_task_distribution(state)
    return support_panel['confirtm_dop_distribution'].format(
        task_id,
        number)


async def sup_safely_delete_task_text(state: FSMContext) -> str:
    """Текст под меню с безопасным удалением"""
    task_info: TaskAllInfo = await get_task_info(state)
    return support_panel['open_task_safely_delete_task'].format(
        task_info.task_id,
        *correct_number_for_text_about_delete(task_info))


async def task_force_delete_text(state: FSMContext) -> str:
    """Текст под меню с принудительным удалением задани"""
    task_info: TaskAllInfo = await get_task_info(state)
    return admin_panel['task_force_delete'].format(
        task_info.task_id,
        *correct_number_for_text_about_delete(task_info))


async def sup_task_add_executions_text(state: FSMContext) -> str:
    """Текст под добавлением какого-то кол-ва выполнений"""
    task_info: TaskAllInfo = await get_task_info(state)
    return support_panel['task_add_executions'].format(
        task_info.task_id,
        task_info.total_sent)


async def sup_confirm_add_executions_text(text: str, state: FSMContext) -> str:
    """Подтверждение дополнительного добавления выполнений"""
    task_id = await get_task_id(state)
    return support_panel['confirm_task_distribution'].format(
        text,
        task_id)


async def sup_reduce_executions_text(state: FSMContext) -> str:
    """Текст под уменьшением кол-ва выполнений"""
    task_info: TaskAllInfo = await get_task_info(state)
    return support_panel['process_reduce_executions'].format(
        task_info.task_id,
        task_info.completed_tasks,
        task_info.executions,
        task_info.total_sent)


async def sup_confirm_eduse_executions_text(state: FSMContext) -> str:
    """Подтверждение уменьшения выполнений"""
    task_id = await get_task_id(state)
    number = await get_reduse_executions(state)
    return support_panel['confirm_eduse_executions'].format(
        number,
        task_id)
