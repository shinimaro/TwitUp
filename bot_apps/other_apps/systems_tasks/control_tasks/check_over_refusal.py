from bot_apps.bot_parts.panels.support_panel.notification import send_notification_to_support
from bot_apps.other_apps.wordbank import notifications_to_support
from config import load_config
from databases.database import Database

config = load_config()
db = Database()


async def check_over_refusal(tasks_msg_id: int) -> None:
    """Проверка на то, не слишком ли много отказов у задания"""
    task_id: int = await db.get_task_id_from_tasks_messages(tasks_msg_id)
    if (not await db.check_support_alert_about_over_refusal(task_id)
            and await db.failure_rate_check(task_id)):
        support_id = await send_notification_to_support(notifications_to_support['over_refusal'].format(task_id),
                                                        get_support_id=True)
        await db.support_notification_record(support_id, task_id)
