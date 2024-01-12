import datetime
import math

from aiogram.types import InlineKeyboardButton as IB
from aiogram.types import InlineKeyboardMarkup as IM
from aiogram.utils.keyboard import InlineKeyboardBuilder as BD

from bot_apps.bot_parts.adding_task.adding_task_text import define_price
from bot_apps.bot_parts.help_center.help_center_functions import SupportName
from bot_apps.bot_parts.personal_tasks.personal_task_functions import TasksRange, find_range_value, format_date
from bot_apps.other_apps.wordbank import BACK_MAIN_MENU, main_menu, personal_task, BACK, FORWARD, add_task, payment, \
    help_center, \
    task_completion
from config import load_config
from databases.database import Database
from databases.dataclasses_storage import ActiveTasks, HistoryTasks

config = load_config()
support_names = SupportName()
db = Database()


async def personal_tasks_menu_keyboard(tg_id: int) -> IM:
    """Клавиатура под главным меню тасков"""
    personal_tasks_menu = BD()
    personal_tasks_menu.row(
        IB(text=main_menu['dop_buttons']['add_task_button'],
           callback_data='add_task'))
    # Если есть хотя бы 1 активный таск
    if await db.get_count_active_tasks(tg_id) > 0:
        personal_tasks_menu.row(
            IB(text=personal_task['buttons']['open_personal_tasks_button'],
               callback_data='active_tasks'))
    # Если в истории заданий уже лежит хотя бы 1 таск
    if await db.get_count_task_on_history(tg_id) > 0:
        personal_tasks_menu.row(
            IB(text=personal_task['buttons']['history_tasks_button'],
               callback_data='history_tasks'))
    personal_tasks_menu.row(_get_back_to_main_menu_button())
    return personal_tasks_menu.as_markup()


async def active_tasks_menu_keyboard(tg_id: int, page: int) -> IM:
    """Клавиатура под активными тасками"""
    tasks: dict[int, ActiveTasks] = await db.get_active_tasks_inforamtions(tg_id)
    return tasks_menu_keyboard(page, tasks, 'active')


async def history_tasks_menu_keyboard(tg_id: int, page: int) -> IM:
    """Клавиатура под историей тасков"""
    tasks: dict[int, HistoryTasks] = await db.get_history_tasks_informations(tg_id)
    return tasks_menu_keyboard(page, tasks, 'history')


def tasks_menu_keyboard(page: int, tasks: dict[int, ActiveTasks | HistoryTasks], pagination_word: str) -> IM:
    """Клавиатура с тасками и пагинацией"""
    active_tasks_menu = BD()
    legth_tasks = len(tasks)
    # Если тасков менее 8, пагинация не создаётся
    if legth_tasks <= 8:
        active_tasks_menu.row(
            *[IB(text=_get_task_name_for_button(task_info.task_number, task_info.date_of_creation),
                 callback_data=f'open_{pagination_word}_task_{task_id}')
              for task_id, task_info in tasks.items()], width=1)

    # Если тасков более 8, создаём пагинейшн
    else:
        active_tasks_menu.row(*_pagination(page, legth_tasks, pagination_word))
        tasks_range: TasksRange = find_range_value(page, legth_tasks)
        active_tasks_menu.row(
            *[IB(text=_get_task_name_for_button(tasks[task_id].task_number, tasks[task_id].date_of_creation),
                 callback_data=f'open_{pagination_word}_task_{task_id}') for task_id in
              list(tasks.keys())[tasks_range.lower_limit:tasks_range.upper_limit]], width=1)

    active_tasks_menu.row(
        IB(text=BACK,
           callback_data='back_to_personal_tasks'),
        _get_back_to_main_menu_button(), width=1)
    return active_tasks_menu.as_markup()


def active_task_keyboard() -> IM:
    """Клавиатура под активным таском"""
    active_task_kb = BD()
    active_task_kb.row(
        IB(text=personal_task['buttons']['increased_executions_button'],
           callback_data='increased_executions'),
        IB(text=personal_task['buttons']['editing_duplication_button'],
           callback_data='editing_duplication'),
        IB(text=personal_task['buttons']['delete_task_button'],
           callback_data='delete_task'),
        IB(text=BACK,
           callback_data='back_to_active_tasks'),
        _get_back_to_main_menu_button(), width=1)
    return active_task_kb.as_markup()


def history_task_keyboard() -> IM:
    """Клавиатура под заданием из истории"""
    history_task_kb = BD()
    history_task_kb.row(
        IB(text=personal_task['buttons']['dublication_task_button'],
           callback_data='dublication_history_task'),
        IB(text=personal_task['buttons']['delete_from_history_button'],
           callback_data='delete_task_from_history'),
        IB(text=BACK,
           callback_data='back_to_history_tasks'),
        _get_back_to_main_menu_button(), width=1)
    return history_task_kb.as_markup()


def del_task_from_history() -> IM:
    """Клавиатура под подтверждением удаления задания"""
    del_task_kb = BD()
    del_task_kb.row(
        IB(text=personal_task['buttons']['delete_from_history_button'],
           callback_data='task_deletion_confirmation'),
        IB(text=BACK,
           callback_data='back_to_history_task'), width=1)
    return del_task_kb.as_markup()


def noneactive_task_keyboard() -> IM:
    """Урезанная клавиатура под уже неактивным таском"""
    noneactive_task_kb = BD()
    noneactive_task_kb.row(
        IB(text=personal_task['buttons']['editing_duplication_button'],
           callback_data=f'editing_duplication'),
        IB(text=BACK,
           callback_data='back_to_active_tasks'),
        _get_back_to_main_menu_button(), width=1)
    return noneactive_task_kb.as_markup()


async def increased_executions_keyboard(tg_id: int, task_id: int) -> IM:
    """Клавиатура под выбором дополнительного кол-ва выполнений"""
    increased_executions_kb = BD()
    max_executions: int = await _get_max_executions(tg_id=tg_id, task_id=task_id)
    if max_executions > 5:  # Максимальная кнопка
        increased_executions_kb.row(
            IB(text=add_task['buttons']['choice_max_button'].format(max_executions),
               callback_data=f'add_new_executions_{max_executions}'))
    if max_executions >= 5:  # Минимальная кнопка
        increased_executions_kb.row(
            IB(text=add_task['buttons']['choice_min_button'],
               callback_data=f'add_new_executions_5'))
    increased_executions_kb.row(
        IB(text=payment['buttons']['pay_button'],
           callback_data='pay_from_active_task_info'),
        IB(text=personal_task['buttons']['back_to_active_task_button'],
           callback_data='back_to_active_task'), width=1)
    return increased_executions_kb.as_markup()


def add_new_executions_keyboard(executions: int) -> IM:
    """Клавиатура под принятием доп. кол-ва обновлений"""
    add_new_executions_kb = BD()
    add_new_executions_kb.row(
        IB(text=personal_task['buttons']['update_executions_button'],
           callback_data=f'update_executions_{executions}'),
        IB(text=personal_task['buttons']['back_to_increased_executions_button'],
           callback_data='back_to_increased_executions'),
        IB(text=personal_task['buttons']['back_to_active_task_button'],
           callback_data='back_to_active_task'), width=1)
    return add_new_executions_kb.as_markup()


def delete_task_keyboard() -> IM:
    """Клавиатура под удалением задания"""
    delete_task_kb = BD()
    delete_task_kb.row(
        IB(text=personal_task['buttons']['delete_active_task_button'],
           callback_data='delete_active_task_button'),
        IB(text=BACK,
           callback_data='back_to_active_task'), width=1)
    return delete_task_kb.as_markup()


async def warning_before_deletion_keyboard() -> IM:
    """Клавиатура под предупрежеднием о частом удалении заданий"""
    warning_before_deletion_kb = BD()
    warning_before_deletion_kb.row(
        IB(text=help_center['buttons']['message_support_button'],
           url=f"tg://resolve?domain={await support_names.get_support_name()}"),
        IB(text=personal_task['buttons']['continue_delete_task_button'],
           callback_data='continue_delete_task'),
        IB(text=BACK,
           callback_data='back_to_active_task'), width=1)
    return warning_before_deletion_kb.as_markup()


async def del_task_keyboard(tg_id: int, task_id: int) -> IM:
    """Клавиатура после того, как юзер удалил задание"""
    del_task_kb = BD()
    if await db.get_count_active_tasks(tg_id) > 0:
        del_task_kb.row(
            IB(text=personal_task['buttons']['open_personal_tasks_button'],
               callback_data='back_to_active_tasks'))
    del_task_kb.row(
        IB(text=personal_task['buttons']['open_deleted_task_button'],
           callback_data=f'open_history_task_{task_id}'),
        _get_back_to_main_menu_button(), width=1)
    return del_task_kb.as_markup()


def editing_duplication_keyboard() -> IM:
    editing_duplication_kb = BD()
    editing_duplication_kb.row(
        IB(text=personal_task['buttons']['dublication_task_button'],
           callback_data='dublication_active_task'),
        IB(text=BACK,
           callback_data='back_to_active_task'), width=1)
    return editing_duplication_kb.as_markup()


def collect_fines_keyboard(send_id: int) -> IM:
    """Клавиатура под сообщением о сборе штрафов"""
    collect_fines_kb = BD()
    collect_fines_kb.row(
        IB(text=task_completion['buttons']['collect_reward_button'],
           callback_data=f'collect_fines_{send_id}'))
    return collect_fines_kb.as_markup()


def _get_task_name_for_button(task_number: int, date_add: datetime.datetime) -> str:
    """Дать нужное название для кнопки с таском"""
    return f'Задание №{task_number} - {format_date(date_add)}'


def _pagination(page: int, legth_tasks: int, pagination_word: str) -> list[IB]:
    """Настройка пагинации"""
    pages = math.ceil(legth_tasks / 8)
    buttons = [IB(text=BACK, callback_data=f'{pagination_word}_task_page_{page - 1}' if page - 1 > 0 else 'other_apps'),
               IB(text=f"{page}/{pages}", callback_data='other_apps'),
               IB(text=FORWARD, callback_data=f'{pagination_word}_task_page_{page + 1}' if page < pages else 'other_apps')]
    return buttons


def _get_back_to_main_menu_button() -> IB:
    """Дать кнопку с главным меню"""
    return IB(text=BACK_MAIN_MENU,
              callback_data='back_to_main_menu')


async def _get_max_executions(*, tg_id: int, task_id: int) -> int:
    """Посчитать максимальное кол-во выполнений"""
    list_actions: list[str] = await db.get_actions_list(task_id)
    prices: int | float = await define_price(list_actions)
    balance: int | float = await db.check_balance(tg_id)
    return int(balance // prices)
