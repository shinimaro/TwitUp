from aiogram import Bot
from aiogram.fsm.context import FSMContext

from bot_apps.filters.limits_filters.message_limit_filter import MessageFilter
from bot_apps.panels.admin_panel.admin_panel_functions import _get_message_text, get_user_info
from config import load_config
from databases.database import UserAllInfo

message_filter = MessageFilter()
config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")


async def send_message_to_user_from_bot(state: FSMContext) -> None:
    """Отправить уведомление юзеру от имени бота"""
    text = await _get_message_text(state)
    user_info: UserAllInfo = await get_user_info(state)
    await message_filter(user_id=user_info.telegram_id)
    await bot.send_message(chat_id=user_info.telegram_id,
                           text=text)