from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot_apps.bot_parts.help_center.help_center_keyboards import help_center_kb_builder, back_to_help_center_builder
from bot_apps.other_apps.filters.ban_filters.is_banned import IsBanned
from bot_apps.other_apps.wordbank.wordlist import help_center

router = Router()
router.callback_query.filter(IsBanned())
router.message.filter(IsBanned())


# Открываем хелп центр
@router.callback_query((F.data == 'help_center') | (F.data == 'back_to_help_center'))
async def process_open_help_center(callback: CallbackQuery):
    await callback.message.edit_text(help_center['main_text'],
                                     reply_markup=await help_center_kb_builder())


# Открытие вопрос-ответ
@router.callback_query(F.data == 'question-answer')
async def process_open_question_answer(callback: CallbackQuery):
    # await callback.message.edit_text(help_center['question-answer'],
    #                                  reply_markup=back_to_help_center_builder())
    await callback.answer(help_center['question-answer_stub'], show_alert=True)
