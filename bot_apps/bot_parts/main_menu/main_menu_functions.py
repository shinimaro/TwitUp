from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import BaseFilter
from aiogram.types import Message

from databases.database import Database

db = Database()


# Функция, которая находит старое сообщение с основным интерфейсом бота и удаляет его, записывая новое
async def delete_old_interface(message: Message, tg_id: int, bot: Bot, dop_message_id=None):
    main_interface = await db.get_main_interface(tg_id)
    # Если старое сообщение обнаружено
    if main_interface:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=main_interface)
        except TelegramBadRequest:
            pass
    else:
        # Запись о новом сообщении в бд
        await db.add_main_interface(tg_id, message.message_id)
    # Если нужно удалить существующее сообщение
    if dop_message_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=dop_message_id)
        except TelegramBadRequest:
            pass

        # Обновить существующую запись
        await db.update_main_interface(tg_id, message.message_id)


# Мидлваря для предотвращения спама командами
class Antispam(BaseFilter):
    async def __call__(self, message: Message):
        time = await db.get_time_add_main_interface(int(message.from_user.id))
        if not time or (datetime.now().astimezone() - time).total_seconds() > 2:
            return True
        else:
            return False
