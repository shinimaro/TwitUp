from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot_apps.bot_parts.panels.admin_panel.admin_panel_functions import get_tg_id
from databases.database import Database

db = Database()


class SupportMidelware(BaseFilter):
    """Мидлваря для пропуска админа в его панель"""
    async def __call__(self, message: Message) -> bool:
        if message.from_user.id in await db.get_support_list():
            await db.update_support_username(message.from_user.id, '@' + message.from_user.username)  # Обновляем name сапорта
            return True
        return False


class TaskIsNotCompleted(BaseFilter):
    """Мидлваря, проверяющая, что задание не было успешно завершено"""
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        tg_id = await get_tg_id(state)
        tasks_msg_id = await db.get_tasks_msg_id_from_task(tg_id, int(message.text))
        check_execution = await db.check_task_on_completed_status(tasks_msg_id)
        return False if check_execution else True
