from aiogram import Bot

from config import load_config

config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")


# Функция для срочного уведомления саппортам, которая не будет проходить через фильтр сообщений
async def send_notification_to_support(text: str) -> None:
    pass
    # await config.tg_bot.support_ids()
    # await bot.send_message(
    #     text=text,
    #     chat_id=config.tg_bot.support_id)
