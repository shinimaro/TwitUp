from aiogram import Bot
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from bot_apps.other_apps.main_menu.main_menu_keyboard import welcome_keyboard
from bot_apps.wordbank import welcome_message
from config import load_config
from databases.database import db


config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")


class TheyBanned(BaseFilter):
    they_banned_users = []

    # Загрузка всех, кто забанил нас, при запуске
    async def loading_they_blocked_users(self) -> None:
        TheyBanned.is_banned_users = await db.get_they_banned_users()

    # Добавление юзера, которому мы не смогли отправить сообщение
    async def adding_they_blocked_users(self, user_id) -> None:
        result = await db.they_banned_fill(user_id)
        if result:
            TheyBanned.they_banned_users.append(user_id)

    # Юзер нам написал
    async def user_send_we(self, user_id):
        # Смещаем на 1 единицу каунтер и убираем из список
        await db.del_they_banned_users(user_id)
        TheyBanned.they_banned_users.remove(user_id)
        # Если долго не писал нам, то поприветствуем его что-ли
        # if await db.check_wait_time(user_id):
        #     await self.send_welcome_message(user_id)

    async def send_welcome_message(self, user_id):
        # Отправляем приветственное сообщение
        await bot.send_message(
            chat_id=user_id,
            text=welcome_message['welcome_message'],
            reply_markup=await welcome_keyboard()
        )


    async def __call__(self, obj: CallbackQuery | Message) -> bool:
        user_id = obj.from_user.id
        if user_id in TheyBanned.they_banned_users:
            await self.user_send_we(user_id)
            return False
        else:
            return True
