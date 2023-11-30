from aiogram.utils.keyboard import InlineKeyboardBuilder as BD
from aiogram.types import InlineKeyboardButton as IB

from bot_apps.wordbank.wordlist import help_center, BACK_MAIN_MENU, BACK
from config.config import load_config
from random import choice
config = load_config()


# Клавиатура, которая может отправить в вопрос-ответ, либо саппорту
async def help_center_kb_builder():
    help_center_kb = BD()
    help_center_kb.row(
        IB(text=help_center['buttons']['question-answer_button'],
           callback_data='question-answer'),
        IB(text=help_center['buttons']['message_support_button'],
           url=f"tg://resolve?domain={choice(list(config.tg_bot.support_ids))}"),
        IB(text=BACK_MAIN_MENU,
           callback_data='back_to_main_menu'), width=1)
    return help_center_kb.as_markup()


# Клавиатура для возврата обратно в help_center из вопрос-ответ
async def back_to_help_center_builder():
    back_to_help_center = BD()
    back_to_help_center.row(
        IB(text=BACK,
           callback_data='back_to_help_center'))
    return back_to_help_center.as_markup()
