import asyncio
from typing import TypedDict

from aiogram import Router, Bot, F
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import Message

from bot_apps.other_apps.filters.ban_filters.they_banned import TheyBanned
from bot_apps.other_apps.filters.limits_filters.message_limit_filter import MessageFilter
from bot_apps.bot_parts.task_push.task_push_keyboards import new_task_keyboard_builder
from bot_apps.other_apps.wordbank import task_completion
from config import load_config
from databases.database import Database


router = Router()
config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
db = Database()
message_filter = MessageFilter()
they_banned = TheyBanned()


class TaskInfo(TypedDict):
    count_complete: int
    price: int | float


# @router.message(F.text == 'a')
# async def sus(message: Message):
#     a = await db.user_executions_info(1338827549)
#     print(a)

# @router.message(F.text == 'q')
#     task_id = 24
#     workers = {message.from_user.id: 2}
# @router.message(F.text == 'q')
# async def sending_task(message: Message) -> None:
    # task_id = 35
    # workers = {message.from_user.id: 2}
async def sending_task(task_id: int, workers: dict[int, int]) -> None:
    tasks = []
    # Взятие некоторой информации по заданию
    task_info: TaskInfo = await db.get_all_completed_and_price(task_id)
    # Создание тасков
    for worker in workers:
        tasks_msg_id = await db.create_task_message(worker, task_id, workers[worker])
        tasks.extend([send_message_to_worker(worker, tasks_msg_id,
                                             task_info['price'],
                                             task_info['count_complete'])])
    # Запускаем отправку
    await asyncio.gather(*tasks)


# Отправка пользователю сообщения о таске
async def send_message_to_worker(tg_id, tasks_msg_id, price, count_complete):
    try:
        # Отправка таска
        await message_filter(user_id=tg_id)
        message_id = await bot.send_message(
            chat_id=tg_id,
            text=task_completion['task_notification'].format(price, count_complete),
            reply_markup=new_task_keyboard_builder(tasks_msg_id),
            disable_web_page_preview=True)
    except TelegramForbiddenError:
        # Если не получилось отправить, удаляем сообщение из бд
        await db.delete_task_message(tasks_msg_id)
        await they_banned.adding_they_blocked_users(tg_id)
    else:
        # Если всё ок, дополняется запись в бд о таске
        await db.add_info_task_message(tasks_msg_id, message_id.message_id)
        # Проверка на новичка
        await db.definition_of_beginners(tasks_msg_id)
        #  Проверка на то, был ли юзер в приоритетной очереди
        await db.check_user_priority_queue(tg_id)
