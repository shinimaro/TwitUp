from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot_apps.bot_parts.panels.admin_panel.admin_panel_functions import get_task_id
from config import load_config
from databases.database import Database

config = load_config()
db = Database()


class AdminMidelware(BaseFilter):
    """Мидлваря для пропуска админа в его панель"""
    async def __call__(self, message: Message) -> bool:
        if message.from_user.id in await db.get_admins_ids():
            await db.update_admin_username(message.from_user.id, '@' + message.from_user.username)  # Обновляем name админа
            return True
        return False


class UserInDatabase(BaseFilter):
    """Мидлваря на то, есть ли юзер в бд"""
    async def __call__(self, message: Message) -> None | dict[str, int]:
        if message.text.isdigit() and await db.check_user_in_db(int(message.text)):
            return {'tg_id': int(message.text)}
        elif message.text.startswith("@"):
            tg_id: int | None = await db.find_tg_id_on_username(message.text)
            return {'tg_id': int(tg_id)} if tg_id else None


class TaskInDatabase(BaseFilter):
    """Проверка таска на то, что он есть в базе данных"""
    async def __call__(self, message: Message) -> bool:
        if message.text.isdigit() and await db.check_task_in_db(int(message.text)):
            return True
        return False


class ItisMainAdmin(BaseFilter):
    """Проверка на то, что это главный админ - Максим"""
    async def __call__(self, callback: CallbackQuery) -> bool:
        if int(callback.from_user.id) == config.tg_bot.main_admin:
            return True
        return False


class TaskIsActive(BaseFilter):
    """Проверка таска на то, что он активный"""
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        task_id = await get_task_id(state)
        if await db.check_active_task(task_id):
            return True
        return False


