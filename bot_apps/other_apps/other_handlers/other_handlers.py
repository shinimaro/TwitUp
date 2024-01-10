from aiogram import Router, F
from aiogram.types import CallbackQuery

router = Router()


# Пропуск кнопок, которые не должны никак реагировать, чтобы они не грузились, например, кнопки на пагинации
@router.callback_query(F.data == 'other_apps')
async def other_answer(callback: CallbackQuery):
    await callback.answer()


# Закрыть сообщение, которое просто надо закрыть
@router.callback_query(F.data == 'close')
async def close_message(callback: CallbackQuery):
    await callback.message.delete()
