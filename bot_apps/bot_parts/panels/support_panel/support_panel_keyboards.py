from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton as IB
from aiogram.types import InlineKeyboardMarkup as IM
from aiogram.utils.keyboard import InlineKeyboardBuilder as BD

from bot_apps.bot_parts.panels.admin_panel.admin_panel_functions import SortedUsers, get_user_info, get_all_tasks, \
    get_tasks_page, \
    SortedTasks, get_tasks_sorting_options, get_workers
from bot_apps.bot_parts.panels.admin_panel.admin_panel_keyboards import pagination, add_arrow, get_return_stb_sign
from bot_apps.other_apps.wordbank import admin_panel, BACK, support_panel
from databases.database import Database
from databases.dataclasses_storage import SupportInfo, UsersList, UserAllInfo, SentTasksInfo, UserTasksInfo, \
    UserAccount, UserFines, UserPayments, AllTasks, UsersPerformTask

db = Database()


async def main_menu_keyboard(support_id: int) -> IM:
    """Главное меню саппорта"""
    keyboard = BD()
    support_info: SupportInfo = await db.get_info_about_support(support_id)
    keyboard.row(
        IB(text=admin_panel['main_menu_buttons']['users_work_button'],
           callback_data='support_open_users_work'),
        IB(text=admin_panel['main_menu_buttons']['tasks_work_button'],
           callback_data='support_open_tasks_work'),
        IB(text=support_panel['buttons']['start_work_button'], callback_data='support_start_work') if support_info.active_status is False
        else IB(text=support_panel['buttons']['stop_work_button'], callback_data='support_stopped_working'),
        IB(text=support_panel['buttons']['take_main_role_button'], callback_data='support_defaulted_support') if support_info.main_support is False
        else IB(text=support_panel['buttons']['give_main_role_button'], callback_data='support_lifted_defaulted_support'),
        IB(text=admin_panel['main_menu_buttons']['close_menu_button'],
           callback_data='support_close_menu'), width=1)
    return keyboard.as_markup()


def sup_users_work_keyboard(users_list: list[UsersList], page: int) -> IM:
    """Клавиатура под меню с юзерами"""
    users_menu_kb = BD()
    if len(users_list) > 10:
        users_menu_kb.row(*pagination(page, len(users_list), 'users_work', user_word='support'))
    users_menu_kb.row(
        IB(text=admin_panel['buttons']['sorting_button'],
           callback_data='support_sorting_users_list'),
        IB(text=admin_panel['buttons']['reset_sorting_button'],
           callback_data='support_reset_sorting_users_list'),
        IB(text=BACK,
           callback_data='back_to_support_panel'), width=1)
    return users_menu_kb.as_markup()


async def sup_sorted_users_menu_keboard(state: FSMContext) -> IM:
    """Клавиатура под сортировкой юзеров"""
    sorted_users_menu_kb = BD()
    data = await state.get_data()
    sorting_options = data['user_sorting_options'] if 'user_sorting_options' in data else None
    sorted_users_menu_kb.row(
        *[IB(text=text + add_arrow(button, sorting_options),
             callback_data='sup_sorted_users_' + button)
          for button, text in admin_panel['sorted_users_buttons'].items()], width=1)
    sorted_users_menu_kb.row(*_sup_get_list_collor_buttons(sorting_options), width=1)
    sorted_users_menu_kb.row(_sup_get_sort_time_button(sorting_options))
    sorted_users_menu_kb.row(IB(text=BACK, callback_data='support_back_to_users_work_pages'))
    return sorted_users_menu_kb.as_markup()


def _sup_get_sort_time_button(sorting_options: SortedUsers) -> IB:
    """Получить кнопку с сортировкой по времени"""
    time_dict = {'day': IB(text=admin_panel['sorted_users_time_buttons']['sorted_for_week'],
                           callback_data='supus_sorted_users_for_week'),
                 'week': IB(text=admin_panel['sorted_users_time_buttons']['sorted_for_month'],
                            callback_data='supus_sorted_users_for_month'),
                 'month': IB(text=admin_panel['sorted_users_time_buttons']['sorted_all_time'],
                             callback_data='supus_sorted_users_for_all_time'),
                 'all_time': IB(text=admin_panel['sorted_users_time_buttons']['sorted_for_day'],
                                callback_data='supus_sorted_users_for_day')}
    return time_dict[sorting_options.time]


def _sup_get_list_collor_buttons(sorting_options: SortedUsers) -> list[IB]:
    """Дать кнопопки со списками"""
    button_list = [IB(text=text, callback_data='supus_open_users_list_' + button)
                   for button, text in admin_panel['sorted_users_list'].items()
                   if (sorting_options.list != button if sorting_options else button != 'white_list')]
    return button_list


async def sup_all_info_user_keyboard(state: FSMContext) -> IM:
    """Клавиаура при открытии пользователя"""
    all_info_user_kb = BD()
    user_info: UserAllInfo = await get_user_info(state)
    all_info_user_kb.row(
        *[IB(text=text, callback_data='support_for_user_' + button) for button, text in admin_panel['all_user_info_buttons'].items()], width=1)
    all_info_user_kb.row(IB(text=admin_panel['buttons']['ban_button'], callback_data='support_ban_user') if user_info.user_status != 'в чёрном списке'
                         else IB(text=admin_panel['buttons']['unban_button'], callback_data='support_unban_user'))
    all_info_user_kb.row(IB(text=BACK, callback_data='support_back_to_users_work'))
    return all_info_user_kb.as_markup()


def sup_back_user_button() -> IM:
    back_user_kb = BD()
    back_user_kb.row(
        _sup_get_back_user_button())
    return back_user_kb.as_markup()


def sup_coinfirm_change_user_balance_keyboard() -> IM:
    """Клавиатура под подтверждением нового баланса"""
    user_balance_kb = BD()
    user_balance_kb.row(
        IB(text=admin_panel['buttons']['coinfirm_button'],
           callback_data='support_coinfirm_change_user_balance'),
        _sup_get_back_user_button(), width=1)
    return user_balance_kb.as_markup()


def sup_coinfirm_change_user_priority_keybaord() -> IM:
    """Клавиатура под подверждением нового приоритета"""
    user_priority_kb = BD()
    user_priority_kb.row(
        IB(text=admin_panel['buttons']['coinfirm_button'],
           callback_data='support_coinfirm_user_priority'),
        _sup_get_back_user_button(), width=1)
    return user_priority_kb.as_markup()


def sup_change_user_level_keyboard() -> IM:
    """Клавиатура под выбором нового аккаунта"""
    change_user_level_kb = BD()
    levels_list = ['champion', 'challenger', 'main', 'prelim', 'vacationers']
    change_user_level_kb.row(
        *[IB(text=button, callback_data=f'supus_for_user_change_level_{button}') for button in levels_list], width=1)
    change_user_level_kb.row(_sup_get_back_user_button())
    return change_user_level_kb.as_markup()


def sup_adding_fines_user_keyboard() -> IM:
    """Клавиатура под выбором типа штрафа"""
    adding_fines_user_kb = BD()
    adding_fines_user_kb.row(
        IB(text=admin_panel['buttons']['fines_on_prioryty'],
           callback_data='support_for_user_adding_fines_priority'),
        IB(text=admin_panel['buttons']['fines_on_stb'],
           callback_data='support_for_user_adding_fines_stb'),
        _sup_get_back_user_button(), width=1)
    return adding_fines_user_kb.as_markup()


def sup_confirm_user_message_keyboard() -> IM:
    confirm_user_message_kb = BD()
    confirm_user_message_kb.row(
        IB(text=admin_panel['buttons']['confirm_message'],
           callback_data='support_for_user_confirm_message'),
        IB(text=admin_panel['buttons']['nonconfirm_message'],
           callback_data='support_back_to_user_info'), width=1)
    return confirm_user_message_kb.as_markup()


def sup_sent_tasks_keyboard(task_info: list[SentTasksInfo], page: int = 1) -> IM:
    """Клавиатура под тасками, отправленными пользователю"""
    sent_tasks_kb = BD()
    if len(task_info) > 10:
        sent_tasks_kb.row(*pagination(page, len(task_info), 'sent_tasks_user', user_word='supus'))
    sent_tasks_kb.row(IB(text=admin_panel['buttons']['accept_execution_button'],
                         callback_data='support_accept_execution'),
                      _sup_get_back_user_button(), width=1)
    return sent_tasks_kb.as_markup()


def sup_accept_task_id_for_accept() -> IM:
    """Клавиатура под подтверждением таска, выполнение которого нужно принять"""
    keyboard = BD()
    keyboard.row(
        IB(text=admin_panel['buttons']['coinfirm_button'],
           callback_data='support_accept_task_id_for_accept'),
        IB(text=BACK,
           callback_data='support_back_to_tasks_sent_history'), width=1)
    return keyboard.as_markup()


def back_to_tasks_user_list() -> IM:
    """Вернуться к списку тасков отправленных юзеру"""
    keyboard = BD()
    keyboard.row(
        IB(text=BACK,
           callback_data='support_back_to_tasks_sent_history'))
    return keyboard.as_markup()


def sup_user_tasks_keyboard(user_tasks: list[UserTasksInfo], page: int = 1) -> IM:
    """Клавиатура под тасками, созданными юзером"""
    user_tasks_kb = BD()
    if len(user_tasks) > 10:
        user_tasks_kb.row(*pagination(page, len(user_tasks), 'user_tasks', user_word='supus'))
    user_tasks_kb.row(_sup_get_back_user_button())
    return user_tasks_kb.as_markup()


def sup_user_acounts_keyboard(user_accounts: list[UserAccount], page: int) -> IM:
    """Клавиатура под аккаунтами юзера"""
    user_acounts_kb = BD()
    if len(user_accounts) > 10:
        user_acounts_kb.row(*pagination(page, len(user_accounts), 'user_accounts', user_word='supus'))
    user_acounts_kb.row(IB(text=admin_panel['buttons']['only_acitve_accs_button'],
                           callback_data='supus_for_user_active_accounts'),
                        IB(text=admin_panel['buttons']['only_inactive_accs_button'],
                           callback_data='supus_for_user_inactive_accounts'),
                        IB(text=admin_panel['buttons']['only_deleted_accs_button'],
                           callback_data='supus_for_user_deleted_accounts'),
                        IB(text=admin_panel['buttons']['all_accs_button'],
                           callback_data='support_for_user_all_accounts'), width=1)
    user_acounts_kb.row(_sup_get_back_user_button())

    return user_acounts_kb.as_markup()


def sup_user_fines_keyboard(user_fines: list[UserFines], page: int) -> IM:
    """Клавиатура под штрафами юзера"""
    user_fines_kb = BD()
    if len(user_fines) > 10:
        user_fines_kb.row(*pagination(page, len(user_fines), 'user_fines', user_word='supus'))
    user_fines_kb.row(IB(text=admin_panel['buttons']['only_active_fines'],
                         callback_data='support_for_user_active_fines'),
                      IB(text=admin_panel['buttons']['all_fines'],
                         callback_data='support_for_user_fines_history'), width=1)
    user_fines_kb.row(_sup_get_back_user_button())
    return user_fines_kb.as_markup()


def sup_user_payments_keyboard(user_payments: list[UserPayments], page: int = 1) -> IM:
    """Клавиатура под пополнениями юзера"""
    user_payments_kb = BD()
    if len(user_payments) > 10:
        user_payments_kb.row(*pagination(page, len(user_payments), 'user_payments', user_word='supus'))
    user_payments_kb.row(_sup_get_back_user_button())
    return user_payments_kb.as_markup()


def sup_user_remove_fines_keboard(user_fines: list[UserFines], page: int) -> IM:
    user_remove_fines_kb = BD()
    if len(user_fines) > 10:
        user_remove_fines_kb.row(*pagination(page, len(user_fines), 'user_remove_fines', user_word='supus'))
    user_remove_fines_kb.row(_sup_get_back_user_button())
    return user_remove_fines_kb.as_markup()


def _sup_get_back_user_button() -> IB:
    return IB(text=BACK,
              callback_data='support_back_to_user_info')


async def sup_all_tasks_keyboard(state: FSMContext) -> IM:
    """Клавиатура под открытием всех заданий"""
    all_tasks_kb = BD()
    all_tasks: list[AllTasks] = await get_all_tasks(state)
    page: int = await get_tasks_page(state)
    if len(all_tasks) > 10:
        all_tasks_kb.row(*pagination(page, len(all_tasks), 'all_tasks', user_word='supus'))
    all_tasks_kb.row(
        IB(text=admin_panel['buttons']['sorting_button'],
           callback_data='support_sorting_all_tasks'),
        IB(text=admin_panel['buttons']['reset_sorting_button'],
           callback_data='support_reset_sorting_all_tasks'),
        IB(text=admin_panel['buttons']['update_info'],
           callback_data='support_update_info_all_tasks'),
        IB(text=BACK,
           callback_data='back_to_support_panel'), width=1)
    return all_tasks_kb.as_markup()


async def sup_all_tasks_sorting_keyboard(state: FSMContext) -> IM:
    """Клавиатура при открытии сортировки"""
    all_tasks_kb = BD()
    sorting_options: SortedTasks = await get_tasks_sorting_options(state)
    all_tasks_kb.row(
        *[IB(text=text + add_arrow(button, sorting_options),
             callback_data=f'supus_sort_tasks_{button}')
          for button, text in admin_panel['sorted_tasks_buttons'].items()], width=1)
    all_tasks_kb.row(*_sup_get_list_tasks_buttons(sorting_options), width=1)
    all_tasks_kb.row(_sup_get_sort_tasks_time_button(sorting_options))
    all_tasks_kb.row(_sup_get_back_tasks_button())
    return all_tasks_kb.as_markup()


def _sup_get_list_tasks_buttons(sorting_options: SortedTasks) -> list[IB]:
    """Дать кнопопки со списками тасов"""
    button_list = [IB(text=text, callback_data=f'supus_open_tasks_list_{button}')
                   for button, text in admin_panel['sorted_tasks_list'].items()
                   if (sorting_options.list != button if sorting_options else button != 'all_list')]
    return button_list


def _sup_get_sort_tasks_time_button(sorting_options: SortedTasks) -> IB:
    """Получить кнопку с сортировкой по времени для тасков"""
    time_dict = {'day': IB(text=admin_panel['sorted_tasks_time_buttons']['sorted_for_week'],
                           callback_data='supus_sorted_tasks_for_week'),
                 'week': IB(text=admin_panel['sorted_tasks_time_buttons']['sorted_for_month'],
                            callback_data='supus_sorted_tasks_for_month'),
                 'month': IB(text=admin_panel['sorted_tasks_time_buttons']['sorted_all_time'],
                             callback_data='supus_sorted_tasks_for_all_time'),
                 'all_time': IB(text=admin_panel['sorted_tasks_time_buttons']['sorted_for_day'],
                                callback_data='supus_sorted_tasks_for_day')}
    return time_dict[sorting_options.time]


def sup_all_task_info_keyboard() -> IM:
    """Клавиатура под открытием все информации о задании"""
    all_task_info_kb = BD()
    all_task_info_kb.row(*[IB(text=text, callback_data=f'supus_for_task_{button}')
                           for button, text in support_panel['all_task_info_buttons'].items()], width=1)
    all_task_info_kb.row(IB(text=admin_panel['buttons']['update_info'], callback_data='support_task_update_info'))
    all_task_info_kb.row(_sup_get_back_tasks_button())
    return all_task_info_kb.as_markup()


def sup_button_to_task_keyboard() -> IM:
    """Кнопка для вовзращения назад к заданию"""
    button_to_task_kb = BD()
    button_to_task_kb.row(_sup_get_back_task_button())
    return button_to_task_kb.as_markup()


def sup_confirm_task_distribution_keyboard() -> IM:
    confirm_task_distribution_kb = BD()
    confirm_task_distribution_kb.row(
        IB(text=admin_panel['buttons']['confirm_button'],
           callback_data='support_confirm_task_distribution'))
    confirm_task_distribution_kb.row(_sup_get_back_task_button())
    return confirm_task_distribution_kb.as_markup()


def sup_safely_delete_keyboard() -> IM:
    """Кнопка под безопасным удалением задания"""
    safely_delete_kb = BD()
    safely_delete_kb.row(IB(text=admin_panel['buttons']['confirm_delete'],
                            callback_data='support_confirm_task_safely_delete'))
    safely_delete_kb.row(_sup_get_back_task_button())
    return safely_delete_kb.as_markup()


def sup_force_delete_keyboard() -> IM:
    """Принудительное удаление задания"""
    force_delete_kb = BD()
    force_delete_kb.row(IB(text=admin_panel['buttons']['confirm_delete'],
                           callback_data='support_confirm_task_force_delete'))
    force_delete_kb.row(_sup_get_back_task_button())
    return force_delete_kb.as_markup()


def sup_confirm_add_executions_keyboard() -> IM:
    """Подтверждение увеличения кол-ва выполнений"""
    confirm_add_executions_kb = BD()
    confirm_add_executions_kb.row(
        IB(text=admin_panel['buttons']['confirm_button'],
           callback_data='support_confirm_task_add_executions'))
    confirm_add_executions_kb.row(_sup_get_back_task_button())
    return confirm_add_executions_kb.as_markup()


async def sup_reduce_executions_keyboard(state: FSMContext) -> IM:
    """Кнопка под уменьшением кол-ва заданий"""
    reduce_executions_kb = BD()
    reduce_executions_kb.row(
        IB(text=admin_panel['buttons']['return_stb_button'] + await get_return_stb_sign(state),
           callback_data='support_for_task_reduce_return_stb'))
    reduce_executions_kb.row(_sup_get_back_task_button())
    return reduce_executions_kb.as_markup()


def sup_confirm_reduse_executions_keboard() -> IM:
    """Подтверждение уменьшения кол-ва выполнений"""
    reduse_executions_kb = BD()
    reduse_executions_kb.row(
        IB(text=admin_panel['buttons']['confirm_button'],
           callback_data='support_confirm_task_reduse_executions'))
    reduse_executions_kb.row(_sup_get_back_task_button())
    return reduse_executions_kb.as_markup()


async def sup_show_workers_keyboard(state: FSMContext, page: int) -> IM:
    """Клавиатура под воркерами задания"""
    show_workers_kb = BD()
    workers: list[UsersPerformTask] = await get_workers(state)
    if len(workers) > 10:
        show_workers_kb.row(*pagination(page, len(workers), 'task_workers', user_word='supus'))
    show_workers_kb.row(
        *[IB(text=text, callback_data=f'supus_sorted_workers_{button}')
          for button, text in admin_panel['workers_list'].items()], width=1)
    show_workers_kb.row(IB(text=admin_panel['buttons']['update_info'],
                           callback_data='support_update_info_about_workers'))
    show_workers_kb.row(_sup_get_back_task_button())
    return show_workers_kb.as_markup()


def _sup_get_back_tasks_button() -> IB:
    return IB(text=BACK,
              callback_data='support_back_to_all_tasks')


def _sup_get_back_task_button() -> IB:
    """Получить кнопку для вовзрата к выбранному заданию"""
    return IB(text=BACK, callback_data='support_back_to_task')
