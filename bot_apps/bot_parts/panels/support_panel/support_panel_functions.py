from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot_apps.bot_parts.panels.admin_panel.admin_panel_functions import get_tg_id
from bot_apps.bot_parts.task_push.task_push_keyboards import finally_task_builder
from bot_apps.bot_parts.task_push.task_push_text import issuance_of_reward
from config import load_config
from databases.database import Database
from databases.dataclasses_storage import UsersList

db = Database()
config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")

async def change_active_status(callback: CallbackQuery) -> None:
    """Поменять статус саппорта"""
    flag = False if callback.data == 'support_stopped_working' else True
    await db.change_support_status(callback.from_user.id, flag)


async def change_default_support(callback: CallbackQuery) -> None:
    """Взять на себя статус дефолт саппорта, либо снять с себя эти полномочия"""
    if callback.data == 'support_defaulted_support':
        await db.defaulted_support(callback.from_user.id)
    else:
        await db.update_default_support(callback.from_user.id)


async def save_users_list(state: FSMContext) -> None:
    """Сохранить список юзеров"""
    users_list: list[UsersList] = await db.get_users_list_with_info()
    await state.update_data(users_list=users_list)


async def sup_initial_users_page(callback: CallbackQuery, state: FSMContext) -> int:
    """Запиcать страничку с юзерами"""
    if callback.data.startswith('support_users_work_page_'):
        page = int(callback.data[22:])
        await state.update_data(users_work_page=page)
        return page
    else:
        data = await state.get_data()
        return data.get('users_work_page', 1)


async def get_support_message(state: FSMContext) -> int:
    data = await state.get_data()
    return data['support_message']


async def get_task_id_for_accepted(state: FSMContext) -> int:
    """Взять таск, выполнение которого нужно засчитать"""
    data = await state.get_data()
    return data['task_for_accept']


async def accept_task(state: FSMContext) -> None:
    """Засчитать выполнение задания"""
    task_id = await get_task_id_for_accepted(state)
    tg_id = await get_tg_id(state)
    tasks_msg_id = await db.get_tasks_msg_id_from_task(tg_id, task_id)
    await db.roll_back_all_changes_for_not_completed_task(tasks_msg_id, tg_id)  # Откатить все изменения, связанные с этим таском (изменение приоритета, штрафы на рейтинг)
    await db.task_completed(tasks_msg_id)
    await bot.send_message(chat_id=tg_id,
                           text=await issuance_of_reward(tasks_msg_id, accepted_support=True),
                           reply_markup=finally_task_builder(tasks_msg_id))
    # result_back_stb: int | None = await db.roll_back_fines(tasks_msg_id, tg_id)
    # if result_back_stb:
    #     await bot.send_message(chat_id=tg_id,
    #                            text='',
    #                            reply_markup='')


