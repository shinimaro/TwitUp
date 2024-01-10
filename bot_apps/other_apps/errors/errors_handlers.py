from aiogram import Router
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.types import ErrorEvent

from bot_apps.other_apps.filters.ban_filters.they_banned import TheyBanned

router = Router()
they_banned = TheyBanned()


@router.errors()
async def all_errors_from_telegram(exception: ErrorEvent):
    if isinstance(exception.exception, TelegramForbiddenError):
        print('Ошибка зафиксированная в счётчик')
        await they_banned.adding_they_blocked_users(exception.update.message.from_user.id)
    elif isinstance(exception.exception, TelegramBadRequest):
        pass
    elif exception.update.callback_query:
        print(f"Ошибка от {exception.update.callback_query.from_user.id} (@{exception.update.callback_query.from_user.username}) в {exception.update.callback_query.message.date}; Сам текст ошибки: {exception.exception}")
    else:
        print(f"Ошибка от {exception.update.message.from_user.id} (@{exception.update.message.from_user.username}) в {exception.update.message.date}; Сам текст ошибки: {exception.exception}")

