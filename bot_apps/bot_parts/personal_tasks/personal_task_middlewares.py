from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot_apps.bot_parts.personal_tasks.personal_task_functions import get_task_id
from databases.database import Database

db = Database()


class ActiveTask(BaseFilter):
    """Проверка таска на то, что он активен"""
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        task_id = await get_task_id(state)
        if await db.check_active_task(task_id):
            return True
        return False
