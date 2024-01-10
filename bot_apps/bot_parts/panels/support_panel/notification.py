from aiogram import Bot

from bot_apps.bot_parts.help_center.help_center_functions import SupportName
from config import load_config

config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
support_names = SupportName()


async def send_notification_to_support(text: str, get_support_id=False) -> None | int:
    """Функция для срочного уведомления саппорту по умолчанию, которая не будет проходить через фильтр сообщений"""
    support_id = await support_names.get_support_id()
    await bot.send_message(
        text=text,
        chat_id=support_id)
    if get_support_id:
        return support_id

