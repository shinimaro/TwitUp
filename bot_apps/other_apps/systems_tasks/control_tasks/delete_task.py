import asyncio

from aiogram import Bot

from bot_apps.bot_parts.task_push.task_push_keyboards import ok_button_two_builder, finally_task_builder
from bot_apps.other_apps.filters.limits_filters.callback_limit_filter import CallbackFilter
from bot_apps.other_apps.wordbank import task_completion
from config import load_config
from databases.database import Database
from databases.dataclasses_storage import InfoForDeleteTask

config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
db = Database()
callback_filter = CallbackFilter()


async def force_delete_task(task_id: int) -> None:
    """Функция, которая удаляет задание принудительно с помощью сапорта"""
    info_dict: dict[int, InfoForDeleteTask] = await db.info_for_delete_messages(task_id)
    tasks = []
    for key in info_dict:
        if info_dict[key]['status'] in 'offer':
            tasks.extend([_delete_message(info_dict[key], key)])
        elif info_dict[key]['status'] == 'offer_more':
            tasks.extend([_edit_message_after_offer_more(info_dict[key], key, task_completion['admin_force_deletion_message_note_reward'])])
        else:
            tasks.extend([_force_deletion_message_with_reward(info_dict[key], key)])
    await asyncio.gather(*tasks)


async def safely_delete_task(task_id: int) -> None:
    """Функция, "безопасно" удаляющая задание"""
    info_dict: dict[int, InfoForDeleteTask] = await db.info_for_delete_messages(task_id)
    tasks = []
    for key in info_dict:
        if info_dict[key]['status'] in 'offer':
            tasks.extend([_delete_message(info_dict[key], key)])
        elif info_dict[key]['status'] == 'offer_more':
            tasks.extend([_edit_message_after_offer_more(info_dict[key], key, task_completion['delete_task'])])
    await asyncio.gather(*tasks)


async def _delete_message(info_dict: InfoForDeleteTask, tasks_msg_id: int) -> None:
    """Удаление сообщения о задании"""
    await db.add_del_time_in_task(tasks_msg_id)
    await db.add_deleted_status(tasks_msg_id)
    await bot.delete_message(
        chat_id=info_dict['telegram_id'],
        message_id=info_dict['message_id'])


async def _edit_message_after_offer_more(info_dict: InfoForDeleteTask, tasks_msg_id: int, text: str) -> None:
    """Удаление без наград (когда только открыл подробнее)"""
    await db.add_del_time_in_task(tasks_msg_id)
    await db.add_deleted_status(tasks_msg_id)
    await callback_filter(user_id=info_dict['telegram_id'])
    await bot.edit_message_text(
        chat_id=info_dict['telegram_id'],
        message_id=info_dict['message_id'],
        text=text,
        reply_markup=ok_button_two_builder(tasks_msg_id))


async def _force_deletion_message_with_reward(info_dict: InfoForDeleteTask, tasks_msg_id: int) -> None:
    """Удаление с получением наград (когда выполнял задание)"""
    await db.account_initialization(tasks_msg_id)  # Если у юзера не было на этот момент выбрано аккаунта, то выбираем самый первый акк юзера для зачисления туда награды
    await db.task_completed(tasks_msg_id, not_checking_flag=True)  # Засчитать задание и указать, что после его перепроверять не нужно
    await callback_filter(user_id=info_dict['telegram_id'])
    await bot.edit_message_text(
        chat_id=info_dict['telegram_id'],
        message_id=info_dict['message_id'],
        text=task_completion['force_deletion_message_with_reward'],
        reply_markup=finally_task_builder(tasks_msg_id))
