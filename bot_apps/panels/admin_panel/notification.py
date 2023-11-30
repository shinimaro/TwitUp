from aiogram import Bot

from config import load_config

config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")


# Функция для срочного уведомления админам, которая не будет проходить через фильтр сообщений
async def send_notification_to_admin(text: str) -> None:
    for id in config.tg_bot.admin_ids.values():
        await bot.send_message(
            text=text,
            chat_id=id)
