from aiogram import Bot

from bot_apps.filters.limits_filters.message_limit_filter import MessageFilter
from databases.database import db
from bot_apps.task_push.task_push_keyboards import proposal_for_review_builder
from bot_apps.wordbank import notifications
from config import load_config

config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
message_filter = MessageFilter()


# Функция для проверки того, нужно ли присылать пользователю предложение о том, чтобы оставить отзыв
async def availability_check(tg_id):
    # Проверка на ревью (0.05 секунд)
    if await db.check_availability(tg_id):
        # Отправка уведомления
        await message_filter(user_id=tg_id)
        await bot.send_message(
            chat_id=tg_id,
            text=notifications['proposal_for_review'],
            reply_markup=await proposal_for_review_builder())
        # Отметка о том, что уведомили
        await db.change_offered_reviews(tg_id)
