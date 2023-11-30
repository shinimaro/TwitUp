from bot_apps.panels.support_panel.notification import send_notification_to_support
from bot_apps.wordbank import notifications_to_support
from config import load_config
from databases.database import db

config = load_config()


async def check_over_refusal(tasks_msg_id: int) -> None:
    """Проверка на то, не слишком ли много отказов у задания"""
    task_id: int = await db.get_task_id_from_tasks_messages(tasks_msg_id)
    if await db.failure_rate_check(task_id):
        await send_notification_to_support(notifications_to_support['over_refusal'].format(task_id))
