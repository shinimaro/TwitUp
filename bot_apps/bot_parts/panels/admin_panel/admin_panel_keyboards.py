import math

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton as IB
from aiogram.types import InlineKeyboardMarkup as IM
from aiogram.utils.keyboard import InlineKeyboardBuilder as BD

from bot_apps.bot_parts.panels.admin_panel.admin_panel_functions import SortedUsers, get_user_info, get_all_tasks, SortedTasks, \
    get_tasks_sorting_options, get_tasks_page, get_return_flag, get_workers, get_task_price, SettingsTaskPrice, \
    find_out_about_price_changes, get_priority_settings, find_out_about_priority_setting, get_settings_awards_cut, \
    find_out_about_awards_cut_setting
from bot_apps.other_apps.wordbank import admin_panel, BACK, FORWARD
from databases.database import Database
from databases.dataclasses_storage import UsersList, SentTasksInfo, UserTasksInfo, UserFines, AllInfoLimits, \
    UserAllInfo, UserAccount, AllTasks, UsersPerformTask, PriorityChange, UserPayments, AwardsCut, SupportInfo, \
    AdminInfo

db = Database()


def main_menu_keyboard() -> IM:
    """Клавиатура под главным меню"""
    main_menu_kb = BD()
    main_menu_kb.row(
        *[IB(text=text, callback_data='admin_' + callback[:-7])
          for callback, text in admin_panel['main_menu_buttons'].items()], width=1)
    return main_menu_kb.as_markup()


def users_work_keyboard(users_list: list[UsersList], page: int) -> IM:
    """Клавиатура под меню с юзерами"""
    users_menu_kb = BD()
    if len(users_list) > 10:
        users_menu_kb.row(*pagination(page, len(users_list), 'users_work'))
    users_menu_kb.row(
        IB(text=admin_panel['buttons']['sorting_button'],
           callback_data='admin_sorting_users_list'),
        IB(text=admin_panel['buttons']['reset_sorting_button'],
           callback_data='admin_reset_sorting_users_list'),
        IB(text=BACK,
           callback_data='admin_back_to_admin_main_menu'), width=1)
    return users_menu_kb.as_markup()


async def sorted_users_menu_keboard(state: FSMContext) -> IM:
    """Клавиатура под сортировкой юзеров"""
    sorted_users_menu_kb = BD()
    data = await state.get_data()
    sorting_options = data['user_sorting_options'] if 'user_sorting_options' in data else None
    sorted_users_menu_kb.row(
        *[IB(text=text + _add_arrow(button, sorting_options),
             callback_data='admin_sort_users_' + button)
          for button, text in admin_panel['sorted_users_buttons'].items()], width=1)
    sorted_users_menu_kb.row(*_get_list_collor_buttons(sorting_options), width=1)
    sorted_users_menu_kb.row(_get_sort_time_button(sorting_options))
    sorted_users_menu_kb.row(IB(text=BACK, callback_data='admin_back_to_users_work_pages'))
    return sorted_users_menu_kb.as_markup()


def _get_list_collor_buttons(sorting_options: SortedUsers) -> list[IB]:
    """Дать кнопопки со списками"""
    button_list = [IB(text=text, callback_data='admin_open_users_list_' + button)
                   for button, text in admin_panel['sorted_users_list'].items()
                   if (sorting_options.list != button if sorting_options else button != 'white_list')]
    return button_list


def _get_sort_time_button(sorting_options: SortedUsers) -> IB:
    """Получить кнопку с сортировкой по времени"""
    time_dict = {'day': IB(text=admin_panel['sorted_users_time_buttons']['sorted_for_week'],
                           callback_data='admin_sorted_users_for_week'),
                 'week': IB(text=admin_panel['sorted_users_time_buttons']['sorted_for_month'],
                            callback_data='admin_sorted_users_for_month'),
                 'month': IB(text=admin_panel['sorted_users_time_buttons']['sorted_all_time'],
                             callback_data='admin_sorted_users_for_all_time'),
                 'all_time': IB(text=admin_panel['sorted_users_time_buttons']['sorted_for_day'],
                                callback_data='admin_sorted_users_for_day')}
    return time_dict[sorting_options.time]


async def all_info_user_keyboard(state: FSMContext) -> IM:
    """Клавиаура при открытии пользователя"""
    all_info_user_kb = BD()
    user_info: UserAllInfo = await get_user_info(state)
    all_info_user_kb.row(
        *[IB(text=text, callback_data='admin_for_user_' + button) for button, text in admin_panel['all_user_info_buttons'].items()], width=1)
    all_info_user_kb.row(IB(text=admin_panel['buttons']['ban_button'], callback_data='admin_ban_user') if user_info.user_status != 'в чёрном списке'
                         else IB(text=admin_panel['buttons']['unban_button'], callback_data='admin_unban_user'))
    all_info_user_kb.row(IB(text=BACK, callback_data='admin_back_to_users_work'))
    return all_info_user_kb.as_markup()


def back_user_button() -> IM:
    back_user_kb = BD()
    back_user_kb.row(
        _get_back_user_button())
    return back_user_kb.as_markup()


def coinfirm_change_user_balance_keyboard() -> IM:
    """Клавиатура под подтверждением нового баланса"""
    user_balance_kb = BD()
    user_balance_kb.row(
        IB(text=admin_panel['buttons']['coinfirm_button'],
           callback_data='admin_coinfirm_change_user_balance'),
        _get_back_user_button(), width=1)
    return user_balance_kb.as_markup()


def coinfirm_change_user_priority_keybaord() -> IM:
    """Клавиатура под подверждением нового приоритета"""
    user_priority_kb = BD()
    user_priority_kb.row(
        IB(text=admin_panel['buttons']['coinfirm_button'],
           callback_data='admin_coinfirm_user_priority'),
        _get_back_user_button(), width=1)
    return user_priority_kb.as_markup()


def change_user_level_keyboard() -> IM:
    """Клавиатура под выбором нового аккаунта"""
    change_user_level_kb = BD()
    levels_list = ['champion', 'challenger', 'main', 'prelim', 'vacationers']
    change_user_level_kb.row(
        *[IB(text=button, callback_data=f'admin_for_user_change_level_{button}') for button in levels_list], width=1)
    change_user_level_kb.row(_get_back_user_button())
    return change_user_level_kb.as_markup()


def adding_fines_user_keyboard() -> IM:
    """Клавиатура под выбором типа штрафа"""
    adding_fines_user_kb = BD()
    adding_fines_user_kb.row(
        IB(text=admin_panel['buttons']['fines_on_prioryty'],
           callback_data='admin_for_user_adding_fines_priority'),
        IB(text=admin_panel['buttons']['fines_on_stb'],
           callback_data='admin_for_user_adding_fines_stb'),
        _get_back_user_button(), width=1)
    return adding_fines_user_kb.as_markup()


def confirm_user_message_keyboard() -> IM:
    confirm_user_message_kb = BD()
    confirm_user_message_kb.row(
        IB(text=admin_panel['buttons']['confirm_message'],
           callback_data='admin_for_user_confirm_message'),
        IB(text=admin_panel['buttons']['nonconfirm_message'],
           callback_data='admin_back_to_user_info'), width=1)
    return confirm_user_message_kb.as_markup()


def sent_tasks_keyboard(task_info: list[SentTasksInfo], page: int = 1) -> IM:
    """Клавиатура под тасками, отправленными пользователю"""
    sent_tasks_kb = BD()
    if len(task_info) > 10:
        sent_tasks_kb.row(*pagination(page, len(task_info), 'sent_tasks_user'))
    sent_tasks_kb.row(_get_back_user_button())
    return sent_tasks_kb.as_markup()


def user_tasks_keyboard(user_tasks: list[UserTasksInfo], page: int = 1) -> IM:
    """Клавиатура под тасками, созданными юзером"""
    user_tasks_kb = BD()
    if len(user_tasks) > 10:
        user_tasks_kb.row(*pagination(page, len(user_tasks), 'user_tasks'))
    user_tasks_kb.row(_get_back_user_button())
    return user_tasks_kb.as_markup()


def user_acounts_keyboard(user_accounts: list[UserAccount], page: int) -> IM:
    """Клавиатура под аккаунтами юзера"""
    user_acounts_kb = BD()
    if len(user_accounts) > 10:
        user_acounts_kb.row(*pagination(page, len(user_accounts), 'user_accounts'))
    user_acounts_kb.row(IB(text=admin_panel['buttons']['only_acitve_accs_button'],
                           callback_data='admin_for_user_active_accounts'),
                        IB(text=admin_panel['buttons']['only_inactive_accs_button'],
                           callback_data='admin_for_user_inactive_accounts'),
                        IB(text=admin_panel['buttons']['only_deleted_accs_button'],
                           callback_data='admin_for_user_deleted_accounts'),
                        IB(text=admin_panel['buttons']['all_accs_button'],
                           callback_data='admin_for_user_all_accounts'), width=1)
    user_acounts_kb.row(_get_back_user_button())

    return user_acounts_kb.as_markup()


def user_fines_keyboard(user_fines: list[UserFines], page: int) -> IM:
    """Клавиатура под штрафами юзера"""
    user_fines_kb = BD()
    if len(user_fines) > 10:
        user_fines_kb.row(*pagination(page, len(user_fines), 'user_fines'))
    user_fines_kb.row(IB(text=admin_panel['buttons']['only_active_fines'],
                         callback_data='admin_for_user_active_fines'),
                      IB(text=admin_panel['buttons']['all_fines'],
                         callback_data='admin_for_user_fines_history'), width=1)
    user_fines_kb.row(_get_back_user_button())
    return user_fines_kb.as_markup()


def user_payments_keyboard(user_payments: list[UserPayments], page: int = 1) -> IM:
    """Клавиатура под пополнениями юзера"""
    user_payments_kb = BD()
    if len(user_payments) > 10:
        user_payments_kb.row(*pagination(page, len(user_payments), 'user_payments'))
    user_payments_kb.row(_get_back_user_button())
    return user_payments_kb.as_markup()


def user_remove_fines_keboard(user_fines: list[UserFines], page: int) -> IM:
    user_remove_fines_kb = BD()
    if len(user_fines) > 10:
        user_remove_fines_kb.row(*pagination(page, len(user_fines), 'user_remove_fines'))
    user_remove_fines_kb.row(_get_back_user_button())
    return user_remove_fines_kb.as_markup()


def _get_back_user_button() -> IB:
    return IB(text=BACK,
              callback_data='admin_back_to_user_info')


async def all_tasks_keyboard(state: FSMContext) -> IM:
    """Клавиатура под открытием всех заданий"""
    all_tasks_kb = BD()
    all_tasks: list[AllTasks] = await get_all_tasks(state)
    page: int = await get_tasks_page(state)
    if len(all_tasks) > 10:
        all_tasks_kb.row(*pagination(page, len(all_tasks), 'all_tasks'))
    all_tasks_kb.row(
        IB(text=admin_panel['buttons']['sorting_button'],
           callback_data='admin_sorting_all_tasks'),
        IB(text=admin_panel['buttons']['reset_sorting_button'],
           callback_data='admin_reset_sorting_all_tasks'),
        IB(text=admin_panel['buttons']['update_info'],
           callback_data='admin_update_info_all_tasks'),
        IB(text=BACK,
           callback_data='admin_back_to_admin_main_menu'), width=1)
    return all_tasks_kb.as_markup()


async def all_tasks_sorting_keyboard(state: FSMContext) -> IM:
    """Клавиатура при открытии сортировки"""
    all_tasks_kb = BD()
    sorting_options: SortedTasks = await get_tasks_sorting_options(state)
    all_tasks_kb.row(
        *[IB(text=text + _add_arrow(button, sorting_options),
             callback_data=f'admin_sort_tasks_{button}')
          for button, text in admin_panel['sorted_tasks_buttons'].items()], width=1)
    all_tasks_kb.row(*_get_list_tasks_buttons(sorting_options), width=1)
    all_tasks_kb.row(_get_sort_tasks_time_button(sorting_options))
    all_tasks_kb.row(_get_back_tasks_button())
    return all_tasks_kb.as_markup()


def _get_list_tasks_buttons(sorting_options: SortedTasks) -> list[IB]:
    """Дать кнопопки со списками тасов"""
    button_list = [IB(text=text, callback_data=f'admin_open_tasks_list_{button}')
                   for button, text in admin_panel['sorted_tasks_list'].items()
                   if (sorting_options.list != button if sorting_options else button != 'all_list')]
    return button_list


def _get_back_tasks_button() -> IB:
    return IB(text=BACK,
              callback_data='admin_back_to_all_tasks')


def _add_arrow(button: str, sorting_options: SortedUsers | SortedTasks) -> str:
    """Приставка для сортировки"""
    if sorting_options and button == sorting_options.key:
        return ' ▲' if not sorting_options.reverse else ' ▼'
    return ''


def _get_sort_tasks_time_button(sorting_options: SortedTasks) -> IB:
    """Получить кнопку с сортировкой по времени для тасков"""
    time_dict = {'day': IB(text=admin_panel['sorted_tasks_time_buttons']['sorted_for_week'],
                           callback_data='admin_sorted_tasks_for_week'),
                 'week': IB(text=admin_panel['sorted_tasks_time_buttons']['sorted_for_month'],
                            callback_data='admin_sorted_tasks_for_month'),
                 'month': IB(text=admin_panel['sorted_tasks_time_buttons']['sorted_all_time'],
                             callback_data='admin_sorted_tasks_for_all_time'),
                 'all_time': IB(text=admin_panel['sorted_tasks_time_buttons']['sorted_for_day'],
                                callback_data='admin_sorted_tasks_for_day')}
    return time_dict[sorting_options.time]


def all_task_info_keyboard() -> IM:
    """Клавиатура под открытием все информации о задании"""
    all_task_info_kb = BD()
    all_task_info_kb.row(*[IB(text=text, callback_data=f'admin_for_task_{button}')
                           for button, text in admin_panel['all_task_info_buttons'].items()], width=1)
    all_task_info_kb.row(IB(text=admin_panel['buttons']['update_info'], callback_data='admin_task_update_info'))
    all_task_info_kb.row(_get_back_tasks_button())
    return all_task_info_kb.as_markup()


def button_to_task_keyboard() -> IM:
    """Кнопка для вовзращения назад к заданию"""
    button_to_task_kb = BD()
    button_to_task_kb.row(_get_back_task_button())
    return button_to_task_kb.as_markup()


def safely_delete_keyboard() -> IM:
    """Кнопка под безопасным удалением задания"""
    safely_delete_kb = BD()
    safely_delete_kb.row(IB(text=admin_panel['buttons']['confirm_delete'],
                            callback_data='admin_confirm_task_safely_delete'))
    safely_delete_kb.row(_get_back_task_button())
    return safely_delete_kb.as_markup()


def force_delete_keyboard() -> IM:
    """Принудительное удаление задания"""
    force_delete_kb = BD()
    force_delete_kb.row(IB(text=admin_panel['buttons']['confirm_delete'],
                           callback_data='admin_confirm_task_force_delete'))
    force_delete_kb.row(_get_back_task_button())
    return force_delete_kb.as_markup()


async def reduce_executions_keyboard(state: FSMContext) -> IM:
    """Кнопка под уменьшением кол-ва заданий"""
    reduce_executions_kb = BD()
    reduce_executions_kb.row(
        IB(text=admin_panel['buttons']['return_stb_button'] + await _get_return_stb_sign(state),
           callback_data='admin_for_task_reduce_return_stb'))
    reduce_executions_kb.row(_get_back_task_button())
    return reduce_executions_kb.as_markup()


async def _get_return_stb_sign(state: FSMContext) -> str:
    """Дополнение для кнопки с вовзратом stb юзеру"""
    return_flag = await get_return_flag(state)
    return ' ❌' if not return_flag else ' ✅'


def confirm_add_executions_keyboard() -> IM:
    """Подтверждение увеличения кол-ва выполнений"""
    confirm_add_executions_kb = BD()
    confirm_add_executions_kb.row(
        IB(text=admin_panel['buttons']['confirm_button'],
           callback_data='admin_confirm_task_add_executions'))
    confirm_add_executions_kb.row(_get_back_task_button())
    return confirm_add_executions_kb.as_markup()


def confirm_reduse_executions_keboard() -> IM:
    """Подтверждение уменьшения кол-ва выполнений"""
    reduse_executions_kb = BD()
    reduse_executions_kb.row(
        IB(text=admin_panel['buttons']['confirm_button'],
           callback_data='admin_confirm_task_reduse_executions'))
    reduse_executions_kb.row(_get_back_task_button())
    return reduse_executions_kb.as_markup()


def confirm_task_distribution_keyboard() -> IM:
    confirm_task_distribution_kb = BD()
    confirm_task_distribution_kb.row(
        IB(text=admin_panel['buttons']['confirm_button'],
           callback_data='admin_confirm_task_distribution'))
    confirm_task_distribution_kb.row(_get_back_task_button())
    return confirm_task_distribution_kb.as_markup()


def confirm_new_profile_link() -> IM:
    """Клавиатура под подтверждением новой ссылки на профиль"""
    confirm_new_profile_kb = BD()
    confirm_new_profile_kb.row(
        IB(text=admin_panel['buttons']['confirm_button'],
           callback_data='admin_new_link_to_profile'))
    confirm_new_profile_kb.row(_get_back_task_button())
    return confirm_new_profile_kb.as_markup()


def confirm_new_post_link() -> IM:
    """Клавиатура под подтверждением новой ссылки на профиль"""
    confirm_new_post_kb = BD()
    confirm_new_post_kb.row(
        IB(text=admin_panel['buttons']['confirm_button'],
           callback_data='admin_new_link_to_post'))
    confirm_new_post_kb.row(_get_back_task_button())
    return confirm_new_post_kb.as_markup()


def edit_task_links_keyboard() -> IM:
    """Клавиатура под сменой ссылок"""
    edit_task_links_kb = BD()
    edit_task_links_kb.row(
        IB(text=admin_panel['buttons']['change_profile_link_button'],
           callback_data='admin_for_task_change_link_profile'),
        IB(text=admin_panel['buttons']['change_post_link_button'],
           callback_data='admin_for_task_change_link_post'), width=1)
    edit_task_links_kb.row(_get_back_task_button())
    return edit_task_links_kb.as_markup()


def send_task_keyboard() -> IM:
    send_task_kb = BD()
    send_task_kb.row(
        IB(text=admin_panel['buttons']['send_task_me_button'],
           callback_data='admin_for_task_send_me'))
    send_task_kb.row(_get_back_task_button())
    return send_task_kb.as_markup()


async def show_workers_keyboard(state: FSMContext, page: int) -> IM:
    """Клавиатура под воркерами задания"""
    show_workers_kb = BD()
    workers: list[UsersPerformTask] = await get_workers(state)
    if len(workers) > 10:
        show_workers_kb.row(*pagination(page, len(workers), 'task_workers'))
    show_workers_kb.row(
        *[IB(text=text, callback_data=f'admin_sorted_workers_{button}')
          for button, text in admin_panel['workers_list'].items()], width=1)
    show_workers_kb.row(IB(text=admin_panel['buttons']['update_info'],
                           callback_data='admin_update_info_about_workers'))
    show_workers_kb.row(_get_back_task_button())
    return show_workers_kb.as_markup()


def _get_back_task_button() -> IB:
    """Получить кнопку для вовзрата к выбранному заданию"""
    return IB(text=BACK, callback_data='admin_back_to_task')


def pagination(page: int, len_elems: int, pagination_word: str, user_word: str = 'admin', pg_elem: int = 10) -> list[IB]:
    """Настройка пагинации"""
    pages = math.ceil(len_elems / pg_elem)
    buttons = [IB(text=BACK, callback_data=f'{user_word}_{pagination_word}_page_{page - 1}' if page - 1 > 0 else 'other_apps'),
               IB(text=f"{page}/{pages}", callback_data='other_apps'),
               IB(text=FORWARD, callback_data=f'{user_word}_{pagination_word}_page_{page + 1}' if page < pages else 'other_apps')]
    return buttons



def all_setings_keyboard() -> IM:
    """Клавиатура под открытием всех настроек"""
    all_setings_kb = BD()
    all_setings_kb.row(
        *[IB(text=text, callback_data=f'admin_setting_{button}')
          for button, text in admin_panel['all_settings_buttons'].items()], width=1)
    all_setings_kb.row(IB(text=BACK, callback_data='admin_back_to_admin_main_menu'))
    return all_setings_kb.as_markup()


async def price_per_task_keyboard(state) -> IM:
    """Клавиатура под указанием нового прайса"""
    price_per_task_kb = BD()
    price_per_task_kb.row(
        *[IB(text=text + await _attach_tick(button, state),
             callback_data=f'admin_price_{button}')
          for button, text in admin_panel['actions_status'].items()], width=1)
    if await find_out_about_price_changes(state):
        price_per_task_kb.row(IB(text=admin_panel['buttons']['save_chenges_button'],
                                 callback_data='admin_save_new_task_price'))
    price_per_task_kb.row(_get_back_all_settings_back())
    return price_per_task_kb.as_markup()


def back_to_price_keyboard() -> IM:
    back_to_price_kb = BD()
    back_to_price_kb.row(IB(text=BACK, callback_data='admin_back_to_task_price'))
    return back_to_price_kb.as_markup()


async def priority_change_keyboard(state: FSMContext) -> IM:
    """Клавиатура под изменением приоритета"""
    priority_change_kb = BD()
    priority_change_kb.row(
        *[IB(text=text + await _attach_tick_2(button, state),
             callback_data=f'admin_change_priority_for_{button}')
          for button, text in admin_panel['priority_buttons'].items()], width=1)
    if await find_out_about_priority_setting(state):
        priority_change_kb.row(IB(text=admin_panel['buttons']['save_chenges_button'],
                                  callback_data='admin_save_new_change_priority'))
    priority_change_kb.row(_get_back_all_settings_back())
    return priority_change_kb.as_markup()


async def _attach_tick(button: str, state: FSMContext) -> str:
    """Поставить соответствующую метку на клавиатуре с прайсом"""
    task_price: SettingsTaskPrice = await get_task_price(state)
    if task_price[button[7:]]:
        return ' ✅'
    return ''


async def _attach_tick_2(button: str, state: FSMContext) -> str:
    """Приписюнить метку на клваиатуре с рейтингом"""
    priority_settings: PriorityChange = await get_priority_settings(state)
    if priority_settings[button]:
        return ' ✅'
    return ''


def back_to_rating_change_keyboard() -> IM:
    back_to_rating_change_kb = BD()
    back_to_rating_change_kb.row(
        IB(text=BACK,
           callback_data='back_to_rating_change'))
    return back_to_rating_change_kb.as_markup()


async def awards_cut_keyboard(state: FSMContext) -> IM:
    """Клавиатура под порезами"""
    awards_cut_kb = BD()
    setting_awards_cut: AwardsCut = await get_settings_awards_cut(state)
    awards_cut_kb.row(
        IB(text=admin_panel['buttons']['first_fine_button'] + (' ✅' if setting_awards_cut.first_fine else ''),
           callback_data='admin_rule_fines_change_first_fine'),
        IB(text=admin_panel['buttons']['subsequent_fines_button'] + (' ✅' if setting_awards_cut.subsequent_fines else ''),
           callback_data='admin_rule_fines_change_subsequent_fines'), width=1)
    if await find_out_about_awards_cut_setting(state):
        awards_cut_kb.row(IB(text=admin_panel['buttons']['save_chenges_button'],
                             callback_data='admin_conifrm_rule_fines'))
    awards_cut_kb.row(_get_back_all_settings_back())
    return awards_cut_kb.as_markup()


def back_to_rule_fines_keyboard() -> IM:
    """Клавиатура под изменением штрафа-пореза"""
    back_to_rule_fines_kb = BD()
    back_to_rule_fines_kb.row(
        IB(text=BACK,
           callback_data='admin_back_to_rule_fines'))
    return back_to_rule_fines_kb.as_markup()


def setting_raiting_fines_keyboard() -> IM:
    """Клавиатура под штраф на макс. рейтинг"""
    setting_raiting_fines_kb = BD()
    setting_raiting_fines_kb.row(
        IB(text=admin_panel['buttons']['change_sum_fines'],
           callback_data='admin_change_raiting_fines'))
    setting_raiting_fines_kb.row(_get_back_all_settings_back())
    return setting_raiting_fines_kb.as_markup()


def back_to_raiting_fines_keyboard() -> IM:
    """Клавиатура под вводом нового макс. понижения приоритета"""
    back_to_raiting_fines_kb = BD()
    back_to_raiting_fines_kb.row(
        IB(text=BACK,
           callback_data='back_to_setting_raiting_fines'))
    return back_to_raiting_fines_kb.as_markup()


def coinfirm_raiting_fines_keyboard() -> IM:
    coinfirm_raiting_fines_kb = BD()
    coinfirm_raiting_fines_kb.row(
        IB(text=admin_panel['buttons']['confirm_message'],
           callback_data='admin_coinfirm_raiting_fines'),
        IB(text=admin_panel['buttons']['nonconfirm_message'],
           callback_data='back_to_setting_raiting_fines'), width=1)
    return coinfirm_raiting_fines_kb.as_markup()


def task_fines_keyboard() -> IM:
    """Клавиатура под штрафом за частое удаление заданий"""
    task_fines_kb = BD()
    task_fines_kb.row(IB(text=admin_panel['buttons']['change_percent_fines'],
                         callback_data='admin_change_percent_task_fines'))
    task_fines_kb.row(_get_back_all_settings_back())
    return task_fines_kb.as_markup()


def change_task_fines_keyboard() -> IM:
    change_task_fines_kb = BD()
    change_task_fines_kb.row(
        IB(text=BACK,
           callback_data='back_to_task_fines'))
    return change_task_fines_kb.as_markup()


def coinfirm_percent_fines_keyboard() -> IM:
    """Подтвердить новый штраф за частое удаление задания"""
    coinfirm_percent_fines_kb = BD()
    coinfirm_percent_fines_kb.row(
        IB(text=admin_panel['buttons']['confirm_message'],
           callback_data='admin_coinfirm_task_fines'),
        IB(text=admin_panel['buttons']['nonconfirm_message'],
           callback_data='back_to_task_fines'), width=1)
    return coinfirm_percent_fines_kb.as_markup()


def work_with_levels_keyboard() -> IM:
    """Кнопки под редактирование лимитов уровней"""
    work_with_levels_kb = BD()
    work_with_levels_kb.row(
        IB(text=admin_panel['buttons']['levels_limits_button'],
           callback_data='admin_open_levels_limits'),
        IB(text=admin_panel['buttons']['receiving_limits_button'],
           callback_data='admin_open_receiving_limits'), width=1)
    work_with_levels_kb.row(_get_back_all_settings_back())
    return work_with_levels_kb.as_markup()


async def levels_limits_keyboard() -> IM:
    """Клавиатура под инфой о лимитах уровней"""
    levels_limits_kb = BD()
    all_limits: AllInfoLimits = await db.get_all_info_levels_limits()
    levels = list(all_limits.keys())
    levels_limits_kb.row(
        *[IB(text=f'Изменить уровень {level}', callback_data=f'admin_open_limits_level_{level}') for level in levels], width=1)
    levels_limits_kb.row(IB(text=BACK, callback_data='back_to_work_with_levels'))
    return levels_limits_kb.as_markup()


def change_limits_keyboard(level: str) -> IM:
    """Выбор того, что изменить в лимитах уровня"""
    change_limits_kb = BD()
    change_limits_kb.row(
        IB(text=admin_panel['buttons']['change_limit_tasks_button'],
           callback_data=f'admin_change_limit_tasks_{level}'),
        IB(text=admin_panel['buttons']['change_limit_accounts_button'],
           callback_data=f'admin_change_limit_accounts_{level}'),
        IB(text=BACK,
           callback_data='back_to_levels_limits'), width=1)
    return change_limits_kb.as_markup()


def back_to_limits_keyboard() -> IM:
    back_to_limits_kb = BD()
    back_to_limits_kb.row(
        IB(text=BACK,
           callback_data='back_to_limits_level'))
    return back_to_limits_kb.as_markup()


def confirm_change_limits_tasks_keyboard() -> IM:
    """Подтвердить изменения тасков в день"""
    limits_tasks_kb = BD()
    limits_tasks_kb.row(
        IB(text=admin_panel['buttons']['coinfirm_button'],
           callback_data='admin_coinfirm_changes_for_limits_tasks'),
        IB(text=BACK,
           callback_data='back_to_limits_level'), width=1)
    return limits_tasks_kb.as_markup()


def confirm_change_limits_accounts_keyboard() -> IM:
    """Подтвердить изменение кол-ва макс. аккаунтов на таск"""
    limits_accounts_kb = BD()
    limits_accounts_kb.row(
        IB(text=admin_panel['buttons']['coinfirm_button'],
           callback_data='admin_coinfirm_changes_for_limits_accounts'),
        IB(text=BACK,
           callback_data='back_to_limits_level'), width=1)
    return limits_accounts_kb.as_markup()


def receiving_limits_kebyboard() -> IM:
    """Клавиатура под лимитами уровней для их достижения"""
    receiving_limits_kb = BD()
    levels = ['champion', 'challenger', 'main', 'prelim']
    receiving_limits_kb.row(
        *[IB(text=f'Изменить уровень {level}',
             callback_data=f'admin_change_receiving_limits_{level}') for level in levels],
        IB(text=BACK,
           callback_data='back_to_work_with_levels'), width=1)
    return receiving_limits_kb.as_markup()


def level_receiving_limits_kebyboard() -> IM:
    """Клавиатура под изменениями лимитов уровня для его получения"""
    level_receiving_limits_kb = BD()
    level_receiving_limits_kb.row(
        IB(text=admin_panel['buttons']['change_need_tasks'],
           callback_data='admin_change_need_tasks_for_level'),
        IB(text=admin_panel['buttons']['change_need_active_accounts'],
           callback_data='admin_change_need_active_accounts_for_level'),
        IB(text=BACK,
           callback_data='back_to_open_receiving_limits'), width=1)
    return level_receiving_limits_kb.as_markup()


def back_to_receiving_limits_keyboard() -> IM:
    back_to_limits_kb = BD()
    back_to_limits_kb.row(
        IB(text=BACK,
           callback_data='back_to_change_receiving_limits'))
    return back_to_limits_kb.as_markup()


def confirm_change_need_tasks_keyboard() -> IM:
    """Подтверждение изменения необходимого кол-ва выполненных тасков для уровня"""
    need_tasks_kb = BD()
    need_tasks_kb.row(
        IB(text=admin_panel['buttons']['coinfirm_button'],
           callback_data='admin_confirm_change_need_tasks'),
        IB(text=BACK,
           callback_data='back_to_open_receiving_limits'), width=1)
    return need_tasks_kb.as_markup()


def confirm_change_need_active_accs_keyboard() -> IM:
    """Подтверждение изменения необходимого кол-ва активных акков для уровня"""
    need_active_accs_kb = BD()
    need_active_accs_kb.row(
        IB(text=admin_panel['buttons']['coinfirm_button'],
           callback_data='admin_confirm_change_need_active_accs'),
        IB(text=BACK,
           callback_data='back_to_open_receiving_limits'), width=1)
    return need_active_accs_kb.as_markup()


def edit_admin_list_keboard() -> IM:
    """Клавиатура под списком админов"""
    admin_list_kb = BD()
    admin_list_kb.row(
        IB(text=admin_panel['buttons']['add_admin_button'],
           callback_data='admin_adding_admin'),
        IB(text=admin_panel['buttons']['remove_admin_button'],
           callback_data='admin_remove_admin'),
        _get_back_all_settings_back(), width=1)
    return admin_list_kb.as_markup()


def back_to_admin_list_button() -> IM:
    """Кнопка для вовзрата назад к списку админов"""
    back_to_admin_list_kb = BD()
    back_to_admin_list_kb.row(
        IB(text=BACK,
           callback_data='back_to_admin_list'))
    return back_to_admin_list_kb.as_markup()


def coinfirm_adding_admin_keyboard() -> IM:
    """Подтверждение добавления нового админа"""
    coinfirm_adding_admin_kb = BD()
    coinfirm_adding_admin_kb.row(
        IB(text=admin_panel['buttons']['coinfirm_button'],
           callback_data='admin_coinfirm_to_adding_admin'),
        IB(text=BACK,
           callback_data='back_to_admin_list'), width=1)
    return coinfirm_adding_admin_kb.as_markup()


async def remove_admin_keyboard() -> IM:
    """Клавиатура для выбора админа для удаления"""
    remove_admin_kb = BD()
    admins: list[AdminInfo] = await db.get_info_about_admins()
    remove_admin_kb.row(
        *[IB(text=f'Удалить админа {admin.telegram_id}',
             callback_data=f'admin_remove_to_admin_{admin.telegram_id}') for admin in admins], width=1)
    remove_admin_kb.row(IB(text=BACK, callback_data='back_to_admin_list'))
    return remove_admin_kb.as_markup()


def coinfirm_remove_admin_keyboard() -> IM:
    """Подтверждение удаления админа"""
    coinfirm_remove_admin_kb = BD()
    coinfirm_remove_admin_kb.row(
        IB(text=admin_panel['buttons']['coinfirm_button'],
           callback_data='admin_coinfirm_to_remove_admin'),
        IB(text=BACK,
           callback_data='back_to_admin_list'), width=1)
    return coinfirm_remove_admin_kb.as_markup()


def supports_list_keyboard() -> IM:
    """Список саппортов"""
    supports_list_kb = BD()
    supports_list_kb.row(
        IB(text=admin_panel['buttons']['add_support_button'],
           callback_data='admin_add_support'),
        IB(text=admin_panel['buttons']['remove_support_button'],
           callback_data='admin_remove_support'),
        IB(text=admin_panel['buttons']['default_support_button'],
           callback_data='admin_assign_default_support'),
        _get_back_all_settings_back(), width=1)
    return supports_list_kb.as_markup()


def _get_back_all_settings_back() -> IB:
    """Кнопка для вовзрата во все настройки"""
    return IB(text=BACK, callback_data='admin_back_to_all_settings')


def back_button_to_support_list() -> IM:
    """Клавиатура для возврата к списку саппортов"""
    support_list_kb = BD()
    support_list_kb.row(
        _get_button_back_to_support_list())
    return support_list_kb.as_markup()


def coinfirm_support_keyboard() -> IM:
    """Подтвердить добавление саппорта"""
    coinfirm_support_kb = BD()
    coinfirm_support_kb.row(
        IB(text=admin_panel['buttons']['coinfirm_button'], callback_data='admin_coinfirm_adding_support'),
        _get_button_back_to_support_list(), width=1)
    return coinfirm_support_kb.as_markup()


async def remove_support_keyboard() -> IM:
    """Список саппортов для удаления"""
    remove_support_kb = BD()
    supports: list[SupportInfo] = await db.get_info_about_supports()
    remove_support_kb.row(
        *[IB(text=f'Удалить саппорта {support.telegram_id}',
             callback_data=f'admin_remove_support_{support.telegram_id}') for support in supports],
        _get_button_back_to_support_list(), width=1)
    return remove_support_kb.as_markup()


def coinfirm_remove_support_keyboard() -> IM:
    """Потдверждение удаления саппорта"""
    remove_support_kb = BD()
    remove_support_kb.row(
        IB(text=admin_panel['buttons']['coinfirm_button'],
           callback_data='admin_coinfirm_remove_support'),
        _get_button_back_to_support_list(), width=1)
    return remove_support_kb.as_markup()


async def defalut_support_keyboard() -> IM:
    """Список саппортов для того, чтобы назначить его саппортом по умолчанию"""
    remove_support_kb = BD()
    supports: list[SupportInfo] = await db.get_info_about_supports()
    remove_support_kb.row(
        *[IB(text=f'Назначить саппортом по умлочанию {support.telegram_id}',
             callback_data=f'admin_assign_default_support_{support.telegram_id}') for support in supports],
        _get_button_back_to_support_list(), width=1)
    return remove_support_kb.as_markup()


def _get_button_back_to_support_list() -> IB:
    """Кнопка для возврата к списку саппортов"""
    return IB(text=BACK, callback_data='back_edit_support_list')

