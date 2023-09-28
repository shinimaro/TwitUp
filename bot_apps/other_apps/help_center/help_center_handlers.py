from aiogram import Router
from aiogram.filters import Text
from aiogram.types import CallbackQuery

from bot_apps.limit_filter.limit_filter import MainFiter
from bot_apps.other_apps.help_center.help_center_keyboards import help_center_kb_builder, back_to_help_center_builder
from bot_apps.wordbank.wordlist import help_center

router = Router()



# Открываем хелп центр
@router.callback_query(Text(text=['help_center', 'back_to_help_center']))
async def process_open_help_center(callback: CallbackQuery):
    await callback.message.edit_text(help_center['main_text'],
                                     reply_markup=await help_center_kb_builder())


# Открытие вопрос-ответ
@router.callback_query(Text(text=['question-answer']))
async def process_open_question_answer(callback: CallbackQuery):
    await callback.message.edit_text(help_center['question-answer'],
                                     reply_markup=await back_to_help_center_builder())
