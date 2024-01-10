import asyncio
from dataclasses import dataclass
from datetime import timedelta, datetime
from typing import Literal, Callable, TypedDict

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot_apps.bot_parts.personal_tasks.personal_task_functions import TasksRange
from bot_apps.other_apps.FSM.FSM_states import FSMAdmin
from bot_apps.other_apps.systems_tasks.control_tasks.delete_task import force_delete_task, safely_delete_task
from bot_apps.other_apps.systems_tasks.sending_tasks.sending_tasks import sending_task
from bot_apps.other_apps.systems_tasks.sending_tasks.start_task import admin_additionally_distributed_task
from bot_apps.other_apps.wordbank import admin_panel
from databases.database import Database
from databases.dataclasses_storage import TaskStatus, UsersList, UserAccount, UserFines, AllTasks, UserTasksInfo, \
    TaskAllInfo, UserPayments, SentTasksInfo, UsersPerformTask, RealPricesTask, AwardsCut, PriorityChange, UserAllInfo

db = Database()


@dataclass
class SortedUsers:
    key: str
    reverse: bool
    list: Literal['white_list', 'black_list', 'grey_list']
    time: str


@dataclass
class SortedTasks:
    key: str
    reverse: bool
    list: Literal['active_list', 'history_list', 'all_list']
    time: Literal['day', 'weeek', 'month', 'all_time']


class SettingsTaskPrice(TypedDict):
    subscriptions: float | None
    likes: float | None
    retweets: float | None
    comments: float | None
    commission: float | None


def find_range_value(page: int, length_tasks: int, pg_nm: int = 10):
    """Найти нижний и вернхий предел"""
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
    """Запиcать страничку с юзерами"""
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
        await state.update_data(user_sorting_options=SortedUsers(key='registration_date', reverse=True, list='white_list', time='all_time'))
    data = await state.get_data()
    return data['user_sorting_options']


async def apply_sorting(callback: CallbackQuery, state: FSMContext, reset: bool = False) -> list[UsersList]:
    """Отсортировать список и сохранить"""
    users_list, user_sorting_options, sorted_dict = await _get_all_sorting_options(state)
    sorted_key: str = _get_sorted_key_and_reverse(callback, user_sorting_options, reset)
    sorted_users_list = sorted(users_list, key=sorted_dict[sorted_key], reverse=user_sorting_options.reverse)
    user_sorting_options.key = sorted_key
    await state.update_data(users_list=sorted_users_list)
    await state.update_data(user_sorting_options=user_sorting_options)
    return sorted_users_list


def _get_sorted_key_and_reverse(callback: CallbackQuery, user_sorting_options: SortedUsers, reset: bool = False) -> str:
    """Получить ключ, по которому нужно сортировать и reverse"""
    if reset:
        sorted_key, user_sorting_options.reverse = 'registration_date', True
    else:
        sorted_key = callback.data[17:]
        if sorted_key == user_sorting_options.key:
            user_sorting_options.reverse = not user_sorting_options.reverse
    return sorted_key


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


async def _get_tools_for_sorting_time(callback: CallbackQuery, state: FSMContext) -> tuple[str, dict, dict, SortedUsers]:
    sort_key = callback.data[23:]
    time_dict = {'day': 1, 'week': 7, 'month': 30, 'all_time': 999999999}
    new_time_for_options = {'day': 'week', 'week': 'month', 'month': 'all_time', 'all_time': 'day'}
    user_sorting_options: SortedUsers = await get_user_sorting_options(state)
    return sort_key, time_dict, new_time_for_options, user_sorting_options


async def get_admin_message(state: FSMContext) -> int:
    """Получить интерфейс админа"""
    data = await state.get_data()
    return data['admin_message']


async def get_user_info(state: FSMContext) -> UserAllInfo:
    """Дать информацию о юзере"""
    data = await state.get_data()
    return data['user_info']


async def get_tg_id(state: FSMContext) -> int:
    """Взять tg_id открытого пользователя"""
    data = await state.get_data()
    return data['tg_id']


async def get_new_balance(state: FSMContext) -> int:
    data = await state.get_data()
    return data['new_balance']


async def get_new_priority(state: FSMContext) -> int:
    data = await state.get_data()
    return data['new_priority']


async def change_user_balance(state: FSMContext) -> None:
    """Имзенить баланс юзера"""
    tg_id = await get_tg_id(state)
    new_balance = await get_new_balance(state)
    await db.change_user_balance(tg_id, new_balance)


async def change_user_priority(state: FSMContext) -> None:
    """Изменить приоритет юзера"""
    tg_id = await get_tg_id(state)
    priority: int = await get_new_priority(state)
    if 0 <= int(priority) <= 100:
        await db.change_user_priority(tg_id, int(priority))


async def add_priority_fines(state: FSMContext, fines_priorirty: str) -> None:
    """Добавить штраф на приоритет пользователю"""
    if fines_priorirty.isdigit() and 0 <= int(fines_priorirty) <= 99:
        await db.adding_priority_fines(await get_tg_id(state), int(fines_priorirty))


async def add_stb_fines(state: FSMContext, fines_stb: str) -> None:
    """Дать штраф юзеру на stb"""
    text = fines_stb.split(',')
    fines_stb = int(text[0])
    victim_user = None if len(text) == 1 else int(text[1])
    await db.adding_stb_fines(await get_tg_id(state), fines_stb, victim_user)


async def get_sent_tasks(state: FSMContext) -> list[SentTasksInfo]:
    """Достать инфу об отправленных тасках юзеру"""
    date = await state.get_data()
    return date['tasks_info']


async def _get_message_text(state: FSMContext) -> str:
    """Достать текст, который отправится юзеру от имени бота"""
    data = await state.get_data()
    return data['message_to_user_from_bot']


async def get_users_task(state: FSMContext) -> list[UserTasksInfo]:
    """Достать таски, созданные юзером"""
    data = await state.get_data()
    return data['user_tasks']


async def get_user_fines(state: FSMContext) -> list[UserFines]:
    """Достать штрафы юзера"""
    data = await state.get_data()
    return data['user_fines']


async def sorted_user_accounts(callback: CallbackQuery) -> list[UserAccount]:
    """Отсортировать список с аккаунтами"""
    filter_dict = {'active_accounts': lambda x: x.account_status == 'active',
                   'inactive_accounts': lambda x: x.account_status == 'inactive',
                   'deleted_accounts': lambda x: x.account_status == 'deleted'}
    user_accounts: list[UserAccount] = await db.get_all_user_accounts(int(callback.from_user.id))  # Да, при каждой сортировке я решил использовать новый список, вместо уже существующего. А что вы мне сделаете, я в другом городе
    return list(filter(filter_dict[callback.data[15:]], user_accounts))


async def get_user_accounts(state: FSMContext) -> list[UserAccount]:
    """Достать аккаунты юзера"""
    data = await state.get_data()
    return data['user_accounts']


async def get_user_paymnets(state: FSMContext) -> list[UserPayments]:
    """Достать пополнения юзера"""
    data = await state.get_data()
    return data['user_payments']


async def _get_all_sorting_options(state) -> tuple[list[UsersList], SortedUsers, dict[str, Callable]]:
    """Выдаёт список для сортировки, данные о прошлых сортировках и ключи для новой"""
    levels_dict = {'champion': 6, 'challenger': 5, 'main': 4, 'prelim': 3, 'vacationers': 2, 'beginner': 1}
    users_list: list[UsersList] = await get_users_list_from_state(state)
    user_sorting_options: SortedUsers = await get_user_sorting_options(state)
    sorted_dict = {
        'registration_date': lambda x: x.registration_date if x.registration_date is not None else float('inf'),
        'number_accounts': lambda x: x.number_accounts if x.number_accounts is not None else float('inf'),
        'number_completed': lambda x: x.number_completed if x.number_completed is not None else float('inf'),
        'number_add_tasks': lambda x: x.number_add_tasks if x.number_add_tasks is not None else float('inf'),
        'level': lambda x: levels_dict[x.level],
        'priority': lambda x: x.priority if x.priority is not None else float('inf'),
        'number_active_tasks': lambda x: x.number_active_tasks if x.number_active_tasks is not None else float('inf'),
        'number_fines': lambda x: x.number_fines if x.number_fines is not None else float('inf')}
    return users_list, user_sorting_options, sorted_dict


async def del_fines_id(message: Message) -> None:
    if message.text.isdigit():
        await db.delete_user_fines(int(message.text))


async def save_all_tasks(state: FSMContext) -> None:
    """Получить и сохранить список всех аккаунтов"""
    all_tasks: list[AllTasks] = await db.get_all_tasks()
    await state.update_data(all_tasks=all_tasks)
    await save_frozen_tasks_list(state)


async def get_all_tasks(state: FSMContext) -> list[AllTasks]:
    """Дать список всех заданий"""
    data = await state.get_data()
    if 'all_tasks' in data:
        return data['all_tasks']
    else:  # Если админ перешёл из кабинета работы с юзерами
        all_tasks: list[AllTasks] = await db.get_all_tasks()
        return all_tasks
    await get_tg_id()


async def tasks_sorting(callback: CallbackQuery, state: FSMContext, reset: bool = False) -> list[AllTasks]:
    """Отсортировать список с заданиями и сохранить"""
    all_tasks, tasks_sorting_options, sorted_dict = await soring_all_task(state)
    sorted_key = _get_tasks_sorted_key_and_reverse(callback, tasks_sorting_options, reset)
    sorted_tasks_list = sorted(all_tasks, key=sorted_dict[sorted_key], reverse=tasks_sorting_options.reverse)
    tasks_sorting_options.key = sorted_key
    await state.update_data(all_tasks=sorted_tasks_list)
    await state.update_data(tasks_sorting_options=tasks_sorting_options)
    return sorted_tasks_list


async def get_tasks_sorting_options(state: FSMContext) -> SortedTasks:
    """Получить настройки сортировки тасков"""
    data = await state.get_data()
    if 'tasks_sorting_options' not in data:
        await set_initial_options(state)
    data = await state.get_data()
    return data['tasks_sorting_options']


async def set_initial_options(state: FSMContext):
    await state.update_data(
        tasks_sorting_options=SortedTasks(key='date_of_creation', reverse=True, list='all_list', time='all_time'))


async def get_tasks_page(state: FSMContext) -> int:
    """Получить страницу с тасками"""
    data = await state.get_data()
    return data.get('tasks_list_page', 1)


async def soring_all_task(state: FSMContext) -> tuple[list[AllTasks], SortedTasks, dict]:
    """Фанкшин для сортировки"""
    all_tasks: list[AllTasks] = await get_all_tasks(state)
    tasks_sorting_options: SortedTasks = await get_tasks_sorting_options(state)
    sorted_dict = {'date_of_creation': lambda x: x.date_of_creation,
                   'total_executions': lambda x: x.executions if x.executions is not None else float('inf'),
                   'active_workers': lambda x: x.doing_now if x.doing_now is not None else float('inf'),
                   'total_completed': lambda x: x.completed_tasks if x.completed_tasks is not None else float('inf'),
                   'total_pay': lambda x: x.total_pay if x.total_pay is not None else float('inf')}
    return all_tasks, tasks_sorting_options, sorted_dict


async def open_other_tasks_list(state: FSMContext, type_sorted: Literal['active_list', 'history_list', 'all_list']):
    """Отсортировать таски по активным-пассивным и сохранить список всех тасков"""
    sorted_dict = {'active_list': lambda x: x.status in (TaskStatus.WAITING_START, TaskStatus.BULK_MESSAGING, TaskStatus.DOP_BULK_MESSAGING, TaskStatus.ACTIVE),
                   'history_list': lambda x: x.status in (TaskStatus.COMPLETED, TaskStatus.DELETED),
                   'all_list': lambda x: x}
    all_tasks: list[AllTasks] = await get_frozen_tasks_list(state)
    await change_tasks_options(state, type_sorted)
    await state.update_data(all_tasks=list(filter(sorted_dict[type_sorted], all_tasks)))


async def change_tasks_options(state: FSMContext, type_sorted: Literal['active_list', 'history_list', 'all_list']):
    tasks_options: SortedTasks = await get_tasks_sorting_options(state)
    await state.update_data(tasks_sorting_options=SortedTasks(key='date_of_creation', reverse=True, list=type_sorted, time=tasks_options.time))


async def save_frozen_tasks_list(state: FSMContext) -> None:
    """Сохранить готовый список для даленьейшей сортировки"""
    data = await state.get_data()
    await state.update_data(all_tasks_frozen=data['all_tasks'])


async def get_frozen_tasks_list(state: FSMContext) -> list[AllTasks]:
    """Достать список для сортировки"""
    data = await state.get_data()
    return data['all_tasks_frozen']


async def change_list_to_sorting_options(state: FSMContext, type_sorted: Literal['active_list', 'history_list', 'all_list']) -> None:
    tasks_sorted_options: SortedTasks = await get_tasks_sorting_options(state)
    await state.update_data(tasks_sorted_options=SortedTasks(tasks_sorted_options.key,
                                                             tasks_sorted_options.reverse,
                                                             type_sorted,
                                                             tasks_sorted_options.time))


def _get_tasks_sorted_key_and_reverse(callback: CallbackQuery, tasks_sorting_options: SortedTasks, reset: bool = False) -> str:
    """Получить ключ, по которому нужно сортировать и reverse"""
    if reset:
        sorted_key, tasks_sorting_options.reverse = 'date_of_creation', True
        return sorted_key
    else:
        if callback.data.startswith('admin_sort_tasks_') or callback.data.startswith('supus_sort_tasks_'):
            sorted_key = callback.data[17:]
            if sorted_key == tasks_sorting_options.key:
                tasks_sorting_options.reverse = not tasks_sorting_options.reverse
            return sorted_key
        return tasks_sorting_options.key


async def save_sort_time_task(callback: CallbackQuery, state: FSMContext) -> None:
    """Сохранить новую сортировку по времени в fsm"""
    sort_key = callback.data[23:]
    sorting_option: SortedTasks = await get_tasks_sorting_options(state)
    await state.update_data(tasks_sorting_options=SortedTasks(key=sorting_option.key,
                                                              reverse=sorting_option.reverse,
                                                              list=sorting_option.list,
                                                              time=sort_key))


async def sorted_task_by_time(state: FSMContext) -> None:
    """Отсортировать таск по времени"""
    sorting_option: SortedTasks = await get_tasks_sorting_options(state)
    all_tasks: list[AllTasks] = await get_frozen_tasks_list(state)
    time_sort_dict = {'day': lambda x: datetime.now() - datetime.strptime(x.date_of_creation, '%d-%m-%Y %H:%M:%S') < timedelta(days=1),
                      'week': lambda x:  datetime.now() - datetime.strptime(x.date_of_creation, '%d-%m-%Y %H:%M:%S') < timedelta(days=7),
                      'month': lambda x:  datetime.now() - datetime.strptime(x.date_of_creation, '%d-%m-%Y %H:%M:%S') < timedelta(days=30),
                      'all_time': lambda x: x.date_of_creation}
    new_all_tasks: list[AllTasks] = list(filter(time_sort_dict[sorting_option.time], all_tasks))
    await state.update_data(all_tasks=new_all_tasks)


async def get_task_id(state: FSMContext) -> int:
    """Получить task_id"""
    data = await state.get_data()
    return data['task_id']


async def save_task_all_info(state: FSMContext) -> None:
    """Получить и сохранить всю информацию о задании"""
    task_id = await get_task_id(state)
    task_info: TaskAllInfo = await db.get_all_info_about_task(task_id)
    await state.update_data(task_info=task_info)


async def get_task_info(state: FSMContext) -> TaskAllInfo:
    """Взять всю информацию о задании"""
    data = await state.get_data()
    return data['task_info']


async def get_add_executions(state: FSMContext) -> int:
    """Взять кол-во дополнительного распределния задания"""
    data = await state.get_data()
    return data['add_executions']


async def get_reduse_executions(state: FSMContext) -> int:
    """Получить кол-во снятий с задания"""
    data = await state.get_data()
    return data['reduse_executions']


async def task_distribution(state: FSMContext) -> str:
    """Дополнительное распределение задания + защита от слишком большого кол-ва распределний"""
    task_info: TaskAllInfo = await get_task_info(state)
    number = await get_task_distribution(state)
    if number < task_info.executions * 3:
        # Распределние задания
        asyncio.get_event_loop().create_task(
            admin_additionally_distributed_task(task_info.task_id, number))
        return admin_panel['dop_distribution'].format(task_info.task_id, number)
    else:
        return admin_panel['not_dop_distribution']


def correct_number_for_text_about_delete(task_info: TaskAllInfo) -> tuple[float, float]:
    """Корректные числа для текста об удалении"""
    return (task_info.remaining_balance - task_info.doing_now * task_info.price,
            task_info.doing_now * task_info.price)


async def task_safely_delete(state: FSMContext) -> None:
    task_id = await get_task_id(state)
    await db.change_task_status_to_deleted(task_id)
    await return_stb_on_author(state)
    await safely_delete_task(task_id)


async def task_force_delete(state: FSMContext) -> None:
    """Принудительное удаление задания"""
    task_id = await get_task_id(state)
    await db.change_task_status_to_deleted(task_id)
    await return_stb_on_author(state)
    await force_delete_task(task_id)


async def return_stb_on_author(state: FSMContext) -> None:
    """Вернуть STB создателю задания"""
    task_id = await get_task_id(state)
    task_info: TaskAllInfo = await db.get_all_info_about_task(task_id)
    sum_refund: float = await db.check_remaining_task_balance(task_id)
    await db.record_of_refund(task_id, sum_refund)
    await db.return_stb_to_author(sum_refund, task_info.telegram_id)


async def get_task_distribution(state: FSMContext) -> int:
    data = await state.get_data()
    return data['task_distribution']


async def task_add_executions(state: FSMContext) -> str:
    """Дополнительное распределение задания"""
    task_info: TaskAllInfo = await get_task_info(state)
    executions: int = await get_add_executions(state)
    if executions <= 200:
        # Добавление баланса и ексекютиноф
        await db.add_executions(task_info.task_id, executions)
        if executions > (task_info.total_sent * 0.3):
            # Дополнительное распределение задания
            return admin_panel['process_task_add_executions_and_distribution'].format(task_info.task_id, executions)
        return admin_panel['process_task_add_executions'].format(task_info.task_id, executions)
    return admin_panel['not_task_add_executions']


async def task_reduse_executions(state: FSMContext) -> str:
    """Снять выполнения с задания"""
    task_info: TaskAllInfo = await get_task_info(state)
    executions: int = await get_reduse_executions(state)
    if executions < task_info.executions:
        await db.reduse_executions(task_info.task_id, executions)
        if await get_return_flag(state):
            # Возврат баланса
            await db.return_stb_for_reduse(task_info.task_id, executions * task_info.price)
            return admin_panel['reduse_executions_and_return'].format(task_info.task_id, executions)
        # Не возврат баланса
        return admin_panel['reduse_executions'].format(task_info.task_id, executions)
    else:
        return admin_panel['not_reduce_executions'].format(task_info.task_id)


async def change_return_flag(state: FSMContext) -> None:
    """Поменять флаг о возвращении STB"""
    data = await state.get_data()
    await state.update_data(return_stb=not data['return_stb'])


async def get_return_flag(state: FSMContext) -> bool:
    """Дать флаг возврата stb"""
    data = await state.get_data()
    return data['return_stb']


async def get_profile_link(state: FSMContext) -> bool:
    """Взять новую ссылку на профиль"""
    data = await state.get_data()
    return data['new_link_profile']


async def get_post_link(state: FSMContext) -> bool:
    """Взять новую ссылку на пост"""
    data = await state.get_data()
    return data['new_link_post']


async def change_link_to_profile(state: FSMContext) -> None:
    """Поменять ссылку на профиль"""
    task_id = await get_task_id(state)
    link = await get_profile_link(state)
    await db.change_link_to_task(task_id, ['subscriptions'], link)


async def change_link_to_post(state: FSMContext) -> None:
    """Поменять ссылку на пост"""
    task_id = await get_task_id(state)
    link = await get_post_link(state)
    await db.change_link_to_task(task_id, ['likes', 'retweets', 'comments'], link)


async def send_task_to_user(tg_id, state: FSMContext) -> None:
    """Отправка задания на выполнение"""
    task_id = await get_task_id(state)
    await sending_task(task_id, {tg_id: 100})


async def save_workers(state: FSMContext) -> None:
    """Сохранить список с воркерами задания"""
    task_id = await get_task_id(state)
    workers_list: list[UsersPerformTask] = await db.get_user_performing_task(task_id)
    await state.update_data(workers_list=workers_list)
    await state.update_data(frozen_workers_list=workers_list)


async def get_workers(state: FSMContext) -> list[UsersPerformTask]:
    """Дать список с воркерами задания"""
    data = await state.get_data()
    return data['workers_list']


async def _get_frozen_workers(state: FSMContext) -> list[UsersPerformTask]:
    """Дать список со всеми воркерами"""
    data = await state.get_data()
    return data['frozen_workers_list']


async def sorted_task_workers(callback: CallbackQuery, state: FSMContext) -> None:
    """Отсортировать список воркеров"""
    sorted_key = callback.data[21:]
    sorted_dict = {'not_started_list': lambda x: x.status in ('offer', 'offer_more', 'deleted'),
                   'started_list': lambda x: x.status in list(admin_panel['executions_status'].keys())[2:10],
                   'completed_list': lambda x: x.status == 'completed',
                   'not_completed_list': lambda x: x.status in list(admin_panel['executions_status'].keys())[11:-1],
                   'all_list': lambda x: x.status}
    workers_list: list[UsersPerformTask] = await _get_frozen_workers(state)
    await state.update_data(workers_list=list(filter(sorted_dict[sorted_key], workers_list)))


async def initial_task_price(state: FSMContext) -> None:
    """Задать начальные настройки цен за таски"""
    await state.update_data(task_price={
        'subscriptions': None,
        'likes': None,
        'retweets': None,
        'comments': None,
        'commission': None})


async def get_task_price(state: FSMContext) -> SettingsTaskPrice:
    """Дать настройки цен за таск"""
    data = await state.get_data()
    return data['task_price']


def get_correct_task_price_state(callback: CallbackQuery):
    fsm_dict = {'subscriptions': FSMAdmin.input_price_to_subscriptions,
                'likes': FSMAdmin.input_price_to_likes,
                'retweets': FSMAdmin.input_price_to_retweets,
                'comments': FSMAdmin.input_price_to_comments,
                'commission': FSMAdmin.input_price_to_commission}
    return fsm_dict[callback.data[19:]]


async def save_price_changes(text: str, state: FSMContext) -> None:
    task_price: SettingsTaskPrice = await get_task_price(state)
    change: str = (await state.get_state())[24:]
    task_price[change] = float(text)
    await state.update_data(task_price=task_price)


async def find_out_about_price_changes(state: FSMContext) -> bool:
    """Узнать о том, были ли какие-то изменения в прайсе"""
    task_price: SettingsTaskPrice = await get_task_price(state)
    result = [value for value in task_price.values() if value is not None]
    return True if result else False


async def save_new_price_task(state: FSMContext) -> None:
    """Сохрание изменений в цене за задания"""
    task_price: SettingsTaskPrice = await get_task_price(state)
    real_price: RealPricesTask = await db.get_prices_for_tasks()
    finally_dict = {
        'subscriptions': task_price['subscriptions'] if task_price['subscriptions'] else real_price.subscriptions,
        'likes': task_price['likes'] if task_price['likes'] else real_price.likes,
        'retweets': task_price['retweets'] if task_price['retweets'] else real_price.retweets,
        'comments': task_price['comments'] if task_price['comments'] else real_price.comments,
        'commission': task_price['commission'] if task_price['commission'] else real_price.commission}
    await db.save_task_price_changes(finally_dict)


async def initial_priority_settings(state: FSMContext) -> None:
    """Инициализация настроек по изменению рейтингов"""
    await state.update_data(priority_settings={
        'completing_task': None,
        're_execution': None,
        'max_re_execution': None,
        'complete_others': None,
        'downtime_more_20_min': None,
        'ignore_more_20_min': None,
        'ignore_more_40_min': None,
        'ignore_more_60_min': None,
        'refuse': None,
        'refuse_late': None,
        'scored_on_task': None,
        'ignore_many_times': None,
        'hidden_many_times': None,
        'refuse_many_times': None,
        'scored_many_times': None})


async def get_priority_settings(state: FSMContext) -> PriorityChange:
    """Взять настройки рейтинга"""
    data = await state.get_data()
    return data['priority_settings']


async def find_out_about_priority_setting(state: FSMContext) -> bool:
    """Узнать о том, были ли какие-то изменения в рейтинге"""
    priority_settings: PriorityChange = await get_priority_settings(state)
    result = [value for value in priority_settings.values() if value is not None]
    return True if result else False


async def set_priority_type(callback: CallbackQuery, state: FSMContext) -> None:
    """Сохранить то, что админ хотел сохранить"""
    change = callback.data[26:]
    await state.update_data(change_priority_type=change)


async def get_priority_type(state: FSMContext) -> str:
    """Открыть то, что юзер хотел сохранить"""
    data = await state.get_data()
    return data['change_priority_type']


async def save_priority_changes(text: str, state: FSMContext) -> None:
    """Сохранить изменение в приоритетах"""
    change = await get_priority_type(state)
    priority_settings: PriorityChange = await get_priority_settings(state)
    if int(text) < 100:
        priority_settings[change] = int(text)
        await state.update_data(priority_settings=priority_settings)


async def apply_priority_changes(state: FSMContext) -> None:
    """Применить все изменения к изменениям приоритета"""
    priority_settings: PriorityChange = await get_priority_settings(state)
    priority_changes: PriorityChange = await db.get_priority_change()
    finally_dict = {setting: value if value else priority_changes[setting] for setting, value in priority_settings.items()}
    await db.save_priority_changes(finally_dict)


async def initial_awards_cut(state: FSMContext) -> None:
    """Сделать датакласс, хранящий настройки о порезах"""
    await state.update_data(settings_awards_cut=AwardsCut(
        first_fine=None,
        subsequent_fines=None))


async def get_settings_awards_cut(state: FSMContext) -> AwardsCut:
    """Получить настройки порезв"""
    data = await state.get_data()
    return data['settings_awards_cut']


async def find_out_about_awards_cut_setting(state: FSMContext) -> bool:
    """Узнать, есть ли какие-то введённые штрафы-порезы"""
    settings_awards_cut: AwardsCut = await get_settings_awards_cut(state)
    if settings_awards_cut.first_fine or settings_awards_cut.subsequent_fines:
        return True
    return False


async def save_first_fine(text: str, state: FSMContext) -> None:
    """Сохранить первый штраф-порез"""
    settings: AwardsCut = await get_settings_awards_cut(state)
    await state.update_data(settings_awards_cut=AwardsCut(first_fine=int(text),
                                                          subsequent_fines=settings.subsequent_fines))


async def save_subsequent_fines(text: str, state: FSMContext) -> None:
    """Сохранить второй штраф-порез"""
    settings: AwardsCut = await get_settings_awards_cut(state)
    await state.update_data(settings_awards_cut=AwardsCut(first_fine=settings.first_fine,
                                                          subsequent_fines=int(text)))


async def apply_rule_fines(state: FSMContext) -> None:
    """Сохранить изменения штрафов"""
    settings: AwardsCut = await get_settings_awards_cut(state)
    awards_cut: AwardsCut = await db.get_info_awards_cut()
    await db.save_new_awards_cut(
        settings.first_fine if settings.first_fine else awards_cut.first_fine,
        settings.subsequent_fines if settings.subsequent_fines else awards_cut.subsequent_fines)


async def get_sum_fines(state: FSMContext) -> int:
    """Достать сумму штрафа на понижение рейтинга"""
    data = await state.get_data()
    return data['fines_raiting']


async def save_new_raiting_fines(state: FSMContext) -> None:
    fines_raiting: int = await get_sum_fines(state)
    await db.save_sum_temporary_fines(fines_raiting)


async def get_percent_task_fines(state: FSMContext) -> int:
    data = await state.get_data()
    return data['percent_task_fines']


async def save_new_task_fine_percent(state: FSMContext) -> None:
    percent = await get_percent_task_fines(state)
    await db.change_fines_task_persent(percent)


async def save_change_level(callback: CallbackQuery, state: FSMContext) -> str:
    """Сохранить указанные левел для изменения лимитов и вернуть"""
    if callback.data.startswith('admin_open_limits_level_'):
        await state.update_data(limits_level=callback.data[24:])
    data = await state.get_data()
    return data['limits_level']


async def get_level_for_change_limits(state: FSMContext) -> str:
    data = await state.get_data()
    return data['limits_level']


def get_need_state_for_change_limits(callback: CallbackQuery):
    if callback.data.startswith("admin_change_limit_tasks_"):
        return FSMAdmin.input_level_limits_tasks
    return FSMAdmin.input_level_limits_accounts


async def get_change_tasks_day(state: FSMContext) -> int:
    data = await state.get_data()
    return data['change_tasks_day']


async def get_change_accs_on_task(state: FSMContext) -> int:
    data = await state.get_data()
    return data['change_accs_on_task']


async def change_limits_level_tasks(state: FSMContext) -> None:
    """Изменить лимиты тасков в день"""
    level = await get_level_for_change_limits(state)
    new_limit = await get_change_tasks_day(state)
    await db.add_new_limits_tasks(level, new_limit)


async def change_limits_level_accounts(state: FSMContext) -> None:
    level = await get_level_for_change_limits(state)
    new_executions = await get_change_accs_on_task(state)
    await db.add_new_limits_accounts(level, new_executions)


async def save_level_for_receiving_limits(callback: CallbackQuery, state: FSMContext) -> None:
    """Сохранить уровень для изменения лимитов для его получения"""
    if callback.data.startswith('admin_change_receiving_limits_'):
        await state.update_data(level_change=callback.data[30:])


async def get_level_for_receiving_limits(state: FSMContext) -> str:
    """Получить уровень, на котором нужно изменить лимиты для его получения"""
    data = await state.get_data()
    return data['level_change']


def get_need_state_for_change_receiving_limits(callback: CallbackQuery):
    """Получить нужное состояние под изменением лимитов для получения уровня"""
    if callback.data == "admin_change_need_tasks_for_level":
        return FSMAdmin.input_need_for_level_tasks
    return FSMAdmin.input_need_for_level_accounts


async def get_change_need_tasks(state: FSMContext) -> int:
    data = await state.get_data()
    return data['need_tasks_for_level']


async def get_change_need_active_accs(state: FSMContext) -> int:
    data = await state.get_data()
    return data['need_active_accs_for_level']


async def change_tasks_receiving_limits(state: FSMContext) -> None:
    """Изменить необходимое кол-во выполненных тасков для получения уровня"""
    level = await get_level_for_receiving_limits(state)
    need_tasks = await get_change_need_tasks(state)
    await db.change_need_tasks_for_level(level, need_tasks)


async def change_active_accs_receiving_limits(state: FSMContext) -> None:
    """Изменить необходимое кол-во активных аккаунтов для получения уровня"""
    level = await get_level_for_receiving_limits(state)
    need_active_accs = await get_change_need_active_accs(state)
    await db.change_need_active_accs_for_level(level, need_active_accs)


async def get_new_admin(state: FSMContext) -> int:
    data = await state.get_data()
    return data['new_admin']


async def adding_new_admin(state: FSMContext) -> None:
    """Добавить нового админа"""
    admin_id = await get_new_admin(state)
    await db.adding_admin(admin_id)


async def get_remove_admin(state: FSMContext) -> int:
    data = await state.get_data()
    return data['remove_admin']


async def remove_admin_from_db(state: FSMContext) -> None:
    """Удаление админа"""
    admin_id = await get_remove_admin(state)
    await db.remove_admin(admin_id)


async def get_new_support(state: FSMContext) -> int:
    data = await state.get_data()
    return data['new_support']


async def add_new_support(state: FSMContext) -> None:
    """Добавление саппорта в базу данных"""
    support_id = await get_new_support(state)
    await db.add_new_supprt(support_id)


async def get_remove_support(state: FSMContext) -> int:
    data = await state.get_data()
    return data['remove_support']


async def remove_supporn_from_db(state: FSMContext) -> None:
    """Удаление саппорта из базы данных"""
    support_id = await get_remove_support(state)
    await db.remove_support(support_id)
