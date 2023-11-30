import asyncio
import math

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton as IB
from aiogram.utils.keyboard import InlineKeyboardBuilder as BD

from bot_apps.panels.admin_panel.admin_panel_functions import SortedUsers, get_user_info
from bot_apps.wordbank import admin_panel, BACK, FORWARD
from databases.database import UsersList, db, UserAllInfo


def main_menu_keyboard():
    """Клавиатура под главным меню"""
    main_menu_kb = BD()
    main_menu_kb.row(
        *[IB(text=text, callback_data='admin_' + callback[:-7])
          for callback, text in admin_panel['main_menu_buttons'].items()], width=1)
    return main_menu_kb.as_markup()


def users_work_keyboard(users_list: list[UsersList], page: int):
    """Клавиатура под меню с юзерами"""
    users_menu_kb = BD()
    if len(users_list) > 10:
        users_menu_kb.row(*_pagination(page, len(users_list), 'users_work'))
    users_menu_kb.row(
        IB(text=admin_panel['buttons']['sorting_button'],
           callback_data='admin_sorting_users_list'),
        IB(text=admin_panel['buttons']['reset_sorting_button'],
           callback_data='admin_reset_sorting_users_list'),
        IB(text=BACK,
           callback_data='admin_back_to_admin_main_menu'), width=1)
    return users_menu_kb.as_markup()


async def sorted_users_menu_keboard(state: FSMContext):
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


async def all_info_user_keyboard(state: FSMContext) -> BD:
    """Клавиаутпа при открытии пользователя"""
    all_info_user_kb = BD()
    user_info: UserAllInfo = await get_user_info(state)
    all_info_user_kb.row(
        *[IB(text=text, callback_data='admin_for_user_' + button) for button, text in admin_panel['all_user_info_buttons'].items()], width=1)
    all_info_user_kb.row(IB(text=admin_panel['buttons']['ban_button'], callback_data='admin_ban_user') if user_info.user_status != 'в чёрном списке'
                         else IB(text=admin_panel['buttons']['unban_button'], callback_data='admin_unban_user'))
    all_info_user_kb.row(IB(text=BACK, callback_data='admin_back_to_users_work'))
    return all_info_user_kb.as_markup()


def back_user_button() -> BD:
    back_user_kb = BD()
    back_user_kb.row(
        _get_back_user_button())
    return back_user_kb.as_markup()

def asdasdasd():
    pass

def change_user_level_keyboard() -> BD:
    """Клавиатура под выбором нового аккаунта"""
    change_user_level_kb = BD()
    levels_list = ['champion', 'challenger', 'main', 'prelim', 'vacationers']
    change_user_level_kb.row(
        *[IB(text=button, callback_data=f'admin_for_user_change_level_{button}') for button in levels_list], width=1)
    change_user_level_kb.row(_get_back_user_button())
    return change_user_level_kb.as_markup()


def adding_fines_user_keyboard() -> BD:
    """Клавиатура под выбором типа штрафа"""
    adding_fines_user_kb = BD()
    adding_fines_user_kb.row(
        IB(text=admin_panel['buttons']['fines_on_prioryty'],
           callback_data='admin_for_user_adding_fines_priority'),
        IB(text=admin_panel['buttons']['fines_on_stb'],
           callback_data='admin_for_user_adding_fines_stb'),
        _get_back_user_button(), width=1)
    return adding_fines_user_kb.as_markup()


def confirm_user_message_keyboard() -> BD:
    confirm_user_message_kb = BD()
    confirm_user_message_kb.row(
        IB(text=admin_panel['buttons']['confirm_message'],
           callback_data='admin_for_user_confirm_message'),
        IB(text=admin_panel['buttons']['nonconfirm_message'],
           callback_data='admin_back_to_user_info'), width=1)
    return confirm_user_message_kb.as_markup()

def _get_back_user_button():
    return IB(text=BACK,
              callback_data='admin_back_to_user_info')


def _add_arrow(button: str, sorting_options: SortedUsers) -> str:
    """Приставка для сортировки"""
    if sorting_options and button == sorting_options.key:
        return ' ▲' if not sorting_options.reverse else ' ▼'
    return ''


def _get_list_collor_buttons(sorting_options: SortedUsers) -> str:
    """Дать кнопопки со списками"""
    button_list = [IB(text=text, callback_data='admin_open_users_list_' + button)
                   for button, text in admin_panel['sorted_users_list'].items() if (sorting_options.list != button if sorting_options else button != 'white_list')]
    return button_list


def _get_sort_time_button(sorting_options: SortedUsers) -> str:
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


def _pagination(page: int, len_elems: int, pagination_word: str) -> list[IB]:
    """Настройка пагинации"""
    pages = math.ceil(len_elems / 10)
    buttons = [IB(text=BACK, callback_data=f'admin_{pagination_word}_page_{page - 1}' if page - 1 > 0 else 'other_apps'),
               IB(text=f"{page}/{pages}", callback_data='other_apps'),
               IB(text=FORWARD, callback_data=f'admin_{pagination_word}_page_{page + 1}' if page < pages else 'other_apps')]
    return buttons
