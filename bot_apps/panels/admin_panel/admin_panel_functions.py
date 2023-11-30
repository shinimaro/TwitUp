from dataclasses import dataclass
from typing import Literal

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot_apps.personal_task.personal_task_functions import TasksRange
from databases.database import UsersList, db, UserAllInfo


@dataclass
class SortedUsers:
    key: str
    reverse: bool
    list: Literal['white_list', 'black_list', 'grey_list']
    time: str


def find_range_value(page: int, length_tasks: int):
    """Найти нижний и вернхий предел"""
    pg_nm = 10  # Пагинейшн нумбер
    previous_page = page - 1
    return TasksRange(lower_limit=0, upper_limit=pg_nm) if previous_page == 0 else \
        TasksRange(lower_limit=previous_page * pg_nm,
                   upper_limit=length_tasks if length_tasks - previous_page * pg_nm < pg_nm else previous_page * pg_nm + pg_nm)


async def find_users_page(callback: CallbackQuery, state: FSMContext) -> int:
    """Найти страницу в меню юзеров"""
    if callback.data == 'back_to_users_work':
        data = await state.get_data()
        return data.get('users_list_page', 1)
    return 1


async def initial_users_page(callback: CallbackQuery, state: FSMContext) -> int:
    """Запиать страничку с юзерами"""
    if callback.data.startswith('admin_users_work_page_'):
        page = int(callback.data[22:])
        await state.update_data(users_work_page=page)
        return page
    else:
        data = await state.get_data()
        return data.get('users_work_page', 1)


async def get_users_list_from_state(state: FSMContext) -> list[UsersList]:
    """Взять список с юзерами"""
    data = await state.get_data()
    return data.get('users_list', await db.get_users_list_with_info())


async def get_user_sorting_options(state: FSMContext) -> SortedUsers:
    """Получить применённые опции сортировки"""
    data = await state.get_data()
    if 'user_sorting_options' not in data:
        # await state.update_data(user_sorting_options=SortedUsers(key='registration_date', reverse=True, list='white_list'))
        await state.update_data(user_sorting_options=SortedUsers(key='registration_date', reverse=True, list='white_list', time='all_time'))
    data = await state.get_data()
    return data['user_sorting_options']


async def apply_sorting(callback: CallbackQuery, state: FSMContext, reset: bool = False) -> list[UsersList]:
    """Отсортировать список и сохранить"""
    users_list, user_sorting_options, sorted_dict = await _get_all_sorting_options(state)
    sorted_key = _get_sorted_key_and_reverse(callback, user_sorting_options, reset)
    sorted_users_list = sorted(users_list, key=sorted_dict[sorted_key], reverse=user_sorting_options.reverse)
    user_sorting_options.key = sorted_key
    await state.update_data(users_list=sorted_users_list)
    await state.update_data(user_sorting_options=user_sorting_options)
    return sorted_users_list


async def open_another_users_list(callback: CallbackQuery, state: FSMContext) -> None:
    type_list = callback.data[22:]
    users_list: list[UsersList] = await db.get_users_list_with_info(type_list)
    await state.update_data(users_list=users_list)
    await state.update_data(user_sorting_options=SortedUsers(key='registration_date', reverse=True, list=type_list, time='day'))


async def sorted_users_list_for_time(callback: CallbackQuery, state: FSMContext) -> None:
    """Сортировка по времени"""
    sort_key, time_dict, new_time_for_options, user_sorting_options = await _get_tools_for_sorting_time(callback, state)
    users_list: list[UsersList] = await db.get_users_list_with_info(condition_sort=user_sorting_options.key, time_condition=time_dict[sort_key])
    await state.update_data(users_list=users_list)
    await state.update_data(user_sorting_options=SortedUsers(key=user_sorting_options.key,
                                                             reverse=user_sorting_options.reverse,
                                                             list=user_sorting_options.list,
                                                             time=sort_key))


async def get_admin_message(state: FSMContext) -> int:
    """Получить интерфейс админа"""
    data = await state.get_data()
    return data['admin_message']


async def get_user_info(state: FSMContext) -> UserAllInfo:
    """Дать информацию о юзере"""
    data = await state.get_data()
    return data['user_info']


async def find_tg_id(message: Message, state: FSMContext) -> int:
    """Найти тг_id юзера"""
    tg_id = int(message.text) if message.text.isdigit() else await db.find_tg_id_on_username(message.text)
    await state.update_data(tg_id=tg_id)
    return tg_id


async def get_tg_id(state: FSMContext) -> int:
    """Взять tg_id"""
    data = await state.get_data()
    return data['tg_id']


async def change_user_balance(state: FSMContext, balance: str) -> None:
    """Имзенить баланс юзера"""
    tg_id = await get_tg_id(state)
    if balance.isdigit():
        await db.change_user_balance(tg_id, int(balance))


async def change_user_priority(state: FSMContext, priority: str) -> None:
    """Изменить приоритет юзера"""
    tg_id = await get_tg_id(state)
    if priority.isdigit() and 0 <= int(priority) <= 100:
        await db.change_user_priority(tg_id, int(priority))


async def add_priority_fines(state: FSMContext, fines_priorirty: str) -> None:
    """Добавить штраф на приоритет пользователю"""
    if fines_priorirty.isdigit() and 0 <= int(fines_priorirty) <= 99:
        await db.adding_priority_fines(await get_tg_id(state), int(fines_priorirty))


async def add_stb_fines(state: FSMContext, fines_stb: str) -> None:
    """Дать штраф юзеру на stb"""
    text = fines_stb.split(',')
    fines_stb = text[0]
    victim_user = None if len(text) == 1 else text[1]
    await db.adding_stb_fines(await get_tg_id(state), int(fines_stb), int(victim_user))


async def _get_message_text(state: FSMContext) -> str:
    data = await state.get_data()
    return data['message_to_user_from_bot']






async def _get_tools_for_sorting_time(callback: CallbackQuery, state: FSMContext) -> tuple[str, dict, dict, SortedUsers]:
    sort_key = callback.data[23:]
    time_dict = {'day': 1, 'week': 7, 'month': 30, 'all_time': 999999999}
    new_time_for_options = {'day': 'week', 'week': 'month', 'month': 'all_time', 'all_time': 'day'}
    user_sorting_options: SortedUsers = await get_user_sorting_options(state)
    return sort_key, time_dict, new_time_for_options, user_sorting_options


def _get_sorted_key_and_reverse(callback: CallbackQuery, user_sorting_options: SortedUsers, reset: bool = False) -> str:
    """Получить ключ, по которому нужно сортировать и reverse"""
    if reset:
        sorted_key, user_sorting_options.reverse = 'registration_date', True
    else:
        sorted_key = callback.data[17:]
        if sorted_key == user_sorting_options.key:
            user_sorting_options.reverse = not user_sorting_options.reverse
    return sorted_key


async def _get_all_sorting_options(state) -> tuple[list[UsersList], SortedUsers, dict]:
    """Выдаёт список для сортировки, данные о прошлых сортировках и ключи для новой"""
    levels_dict = {'champion': 1, 'challenger': 2, 'main': 3, 'prelim': 4, 'vacationers': 5}
    users_list: list[UsersList] = await get_users_list_from_state(state)
    user_sorting_options: SortedUsers = await get_user_sorting_options(state)
    # sorted_dict = {'registration_date': lambda x: x.registration_date, 'number_accounts': lambda x: x.number_accounts,
    #                'number_completed': lambda x: x.number_completed, 'number_add_tasks': lambda x: x.number_add_tasks,
    #                'level': lambda x: levels_dict[x], 'priority': lambda x: x.priority,
    #                'number_active_tasks': lambda x: x.number_active_tasks, 'number_fines': lambda x: x.number_fines}
    sorted_dict = {
        'registration_date': lambda x: x.registration_date if x.registration_date is not None else float('inf'),
        'number_accounts': lambda x: x.number_accounts if x.number_accounts is not None else float('inf'),
        'number_completed': lambda x: x.number_completed if x.number_completed is not None else float('inf'),
        'number_add_tasks': lambda x: x.number_add_tasks if x.number_add_tasks is not None else float('inf'),
        'level': lambda x: levels_dict[x] if x in levels_dict else float('inf'),
        'priority': lambda x: x.priority if x.priority is not None else float('inf'),
        'number_active_tasks': lambda x: x.number_active_tasks if x.number_active_tasks is not None else float('inf'),
        'number_fines': lambda x: x.number_fines if x.number_fines is not None else float('inf')
    }

    return users_list, user_sorting_options, sorted_dict

