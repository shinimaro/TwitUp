from aiogram import Bot

from config import load_config
from databases.database import Database

config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
db = Database()


async def send_notification_to_admin(text: str, specific_tg_id: int = None) -> None:
    """Функция для срочного уведомления админам, которая не будет проходить через фильтр сообщений"""
    for admin_id in await db.get_admins_ids() if not specific_tg_id else specific_tg_id:
        await bot.send_message(
            text=text,
            chat_id=admin_id)
