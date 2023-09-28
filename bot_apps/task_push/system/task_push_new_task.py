import asyncio
import time

from aiogram import Router, Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Text
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot_apps.databases.database import db
from bot_apps.task_push.task_push_keyboards import new_task_keyboard_builder
from bot_apps.wordbank import task_completion
from config import load_config

router = Router()
config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")


@router.message(Text(text=['q']))
async def sus(message: Message):
    await message.delete()
    tg_id_list = [message.from_user.id]
    tasks = []
    task_id = 26

    while tg_id_list:
        batch_size = min(30, len(tg_id_list))
        batch_tg_ids = tg_id_list[:batch_size]
        tg_id_list = tg_id_list[batch_size:]

        info_dict = await db.get_all_completed_and_price(task_id)

        batch_tasks = [send_message_to_worker(tg_id, task_id, int(info_dict["price"]) if info_dict["price"].is_integer() else round(info_dict["price"], 2),
                                              info_dict['count_complete']) for tg_id in batch_tg_ids]
        tasks.extend(batch_tasks)

    await asyncio.gather(*tasks)


async def send_message_to_worker(tg_id, task_id, price, count_complete):
    try:
        tasks_msg_id = await db.create_task_message(tg_id, task_id)
        message_id = await bot.send_message(
            chat_id=tg_id,
            text=task_completion['task_notification'].format(price, count_complete),
            reply_markup=await new_task_keyboard_builder(tasks_msg_id),
            disable_web_page_preview=True)
        await db.add_info_task_message(tasks_msg_id, message_id.message_id)
    except TelegramForbiddenError:
        pass




