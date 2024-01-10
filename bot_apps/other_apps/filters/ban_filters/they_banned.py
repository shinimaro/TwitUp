from datetime import timedelta

from aiogram import Bot
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from bot_apps.bot_parts.main_menu.main_menu_keyboard import welcome_keyboard
from bot_apps.other_apps.wordbank import welcome_message
from config import load_config
from databases.database import Database

db = Database()


config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")


class TheyBanned(BaseFilter):
    they_banned_users = []

    # Загрузка всех, кто забанил нас, при запуске
    @classmethod
    async def loading_they_blocked_users(cls) -> None:
        cls.they_banned_users = await db.get_they_banned_users()

    # Добавление юзера, которому мы не смогли отправить сообщение
    @classmethod
    async def adding_they_blocked_users(cls, user_id) -> None:
        result = await db.they_banned_fill(user_id)
        if result:
            cls.they_banned_users.append(user_id)

    # Юзер нам написал
    @classmethod
    async def user_send_we(cls, user_id) -> bool:
        # Смещаем на 1 единицу каунтер и убираем из списка юзера класса
        last_message: timedelta = await db.del_they_banned_users(user_id)  # Полностью из бан списка его не убираем, т.к. он может снова кинуть нас в бан
        cls.they_banned_users.remove(user_id)
        # Если юзера не писал нам более 3 дней, то поприветствуем его что-ли
        await cls.send_welcome_message(user_id)
        if last_message.total_seconds() >= 3 * 86400:
            return False
        return True

    @staticmethod
    async def send_welcome_message(user_id) -> None:
        # Отправляем приветственное сообщение
        await bot.send_message(
            chat_id=user_id,
            text=welcome_message['welcome_message'],
            reply_markup=welcome_keyboard())

    async def __call__(self, obj: CallbackQuery | Message) -> bool:
        user_id = obj.from_user.id
        if user_id in TheyBanned.they_banned_users:
            return await self.user_send_we(user_id)  # Если мы у юзера долго были в бане, сначало отправляем приветственное сообщение
        else:
            return True
