import asyncio

from aiogram.fsm.context import FSMContext

from bot_apps.panels.admin_panel.admin_panel_functions import find_range_value, get_user_info
from bot_apps.wordbank import admin_panel
from databases.database import db, AdminPanelMainInfo, UsersList, UserAllInfo, SentTasksInfo


async def main_text_builder() -> str:
    """Текст при открыти главного меню"""
    main_info: AdminPanelMainInfo = await db.get_main_info_for_admin_panel()
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


def users_menu_text(users_list: list[UsersList], page: int = 1) -> str:
    """Текст при открытии меню с пользователями"""
    limits = find_range_value(page, len(users_list))
    text = admin_panel['users_menu']
    for user in users_list[limits.lower_limit:limits.upper_limit]:
        text += admin_panel['users_info_frame'].format(
            user.tg_id,
            user.username,
            user.registration_date,
            user.priority,
            user.level,
            user.number_accounts,
            user.number_completed,
            user.number_add_tasks,
            user.number_active_tasks,
            user.number_fines)
    return text


async def all_user_info_text(tg_id: int, state: FSMContext) -> str:
    """Получить всю информацию о пользователе"""
    user_info: UserAllInfo = await db.get_all_info_for_user(tg_id)
    user_info.number_tasks_active_now = _get_active_tasks_now(user_info)
    text = admin_panel['all_user_info_frame'].format(*vars(user_info).values())
    await state.update_data(user_info=user_info)
    return text





async def get_user_text_dict(text: str, state: FSMContext) -> str:
    """Начальный текст для некоторых меню и полный текст для других"""
    user_info: UserAllInfo = await get_user_info(state)
    text_dict = {'tasks_sent_history': admin_panel['open_tasks_sent_history'].format(user_info.telegram_name),
                 'task_personal_history': admin_panel['open_task_personal_history'].format(user_info.telegram_name),
                 'all_accounts': admin_panel['open_all_accounts'].format(user_info.telegram_name),
                 'fines_history': admin_panel['open_fines_history'].format(user_info.telegram_name),
                 'change_balance': admin_panel['change_user_balance'].format(user_info.telegram_name, user_info.balance),
                 'change_priority': admin_panel['change_user_priority'].format(user_info.telegram_name, user_info.priority),
                 'change_level': admin_panel['change_user_level'].format(user_info.telegram_name, user_info.level),
                 'adding_fines': admin_panel['adding_user_fines'].format(user_info.telegram_name, user_info.fines_on_priority, user_info.sum_of_fines),
                 'remove_fines': admin_panel['remove_user_fines'].format(user_info.telegram_name),
                 'message_from_bot': admin_panel['message_from_bot'].format(user_info.telegram_name)}
    return text_dict[text]


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
    user_info: UserAllInfo = await get_user_info(state)
    return admin_panel['confirm_message_from_bot'].format(user_info.telegram_name, message)


async def sent_tasks_user_text(tg_id: int, state: FSMContext) -> str:
    tasks_info: tuple[SentTasksInfo] = await db.get_info_about_sent_tasks(tg_id)
    user_info: tuple[UserAllInfo] = await get_user_info(state)
    text: WorkersInfo = ''
    for task in tasks_info:
        text += admin_panel['sent_tasks_user_frame'].format(
            task.task_id,
            admin_panel['executions_status'][task.status],
            task.offer_time,
            task.complete_time)
    return admin_panel['open_tasks_sent_history'].format(user_info.telegram_name, text)


def _get_active_tasks_now(user_info: UserAllInfo) -> str:
    """Получить текста с активными заданиями юзера"""
    if user_info.number_tasks_active_now:
        return ', '.join([f'<code>{val}</code>' for val in user_info.number_tasks_active_now])
    return 'отсутствуют'
