from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from databases.database import Database

db = Database()


class IsBanned(BaseFilter):
    is_banned_users = []

    @classmethod
    async def loading_blocked_users(cls) -> None:
        """Загрузка забаненных пользователей при запуске"""
        cls.is_banned_users = await db.get_is_banned_users()

    @classmethod
    async def adding_blocked_users(cls, user_id, reason: str = None, comment: str = None) -> None:
        """Добавление нового забанненого пользователя в бд и в список класса"""
        cls.is_banned_users.append(user_id)
        await db.add_ban_user(user_id, reason, comment)

    @classmethod
    async def del_blocked_users(cls, user_id):
        """Убрать юзера из бана"""
        cls.is_banned_users.remove(user_id)
        await db.del_ban_user(user_id)

    @classmethod
    async def __call__(cls, obj: CallbackQuery | Message) -> bool:
        """Проверка на бан"""
        user_id = obj.from_user.id
        if user_id not in cls.is_banned_users:
            return True
        else:
            return False
