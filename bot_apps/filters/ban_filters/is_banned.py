from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from databases.database import db


class IsBanned(BaseFilter):
    is_banned_users = []

    # Загрузка забаненных пользователей при запуске
    async def loading_blocked_users(self) -> None:
        IsBanned.is_banned_users = await db.get_is_banned_users()

    # Добавление нового забанненого пользователя в бд и в список класса
    async def adding_blocked_users(self, user_id, reason: str = None, comment: str = None) -> None:
        IsBanned.is_banned_users.append(user_id)
        await db.ban_user(user_id, reason, comment)

    # Убрать юзера из бана
    async def del_blocked_users(self, user_id):
        IsBanned.is_banned_users.remove(user_id)
        await db.del_ban_user(user_id)

    # Проверка на бан
    async def __call__(self, obj: CallbackQuery | Message) -> bool:
        user_id = obj.from_user.id
        if user_id not in IsBanned.is_banned_users:
            return True
        else:
            return False


