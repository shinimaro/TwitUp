from aiogram.types import InlineKeyboardButton as IB
from aiogram.types import InlineKeyboardMarkup as IM
from aiogram.utils.keyboard import InlineKeyboardBuilder as BD

from bot_apps.bot_parts.help_center.help_center_functions import SupportName
from bot_apps.other_apps.wordbank.wordlist import help_center, BACK_MAIN_MENU, BACK
from config.config import load_config

config = load_config()
support_names = SupportName()


# Клавиатура, которая может отправить в вопрос-ответ, либо саппорту
async def help_center_kb_builder() -> IM:
    help_center_kb = BD()
    support = await support_names.get_support_name()
    help_center_kb.row(
        IB(text=help_center['buttons']['question-answer_button'],
           callback_data='question-answer'),
        (IB(text=help_center['buttons']['message_support_button'],
            url=f"tg://resolve?domain={support}")) if support
        else (IB(text=help_center['buttons']['message_support_button'],
                 callback_data='other_apps')),
        IB(text=BACK_MAIN_MENU,
           callback_data='back_to_main_menu'), width=1)
    return help_center_kb.as_markup()


# Клавиатура для возврата обратно в help_center из вопрос-ответ
def back_to_help_center_builder() -> IM:
    back_to_help_center = BD()
    back_to_help_center.row(
        IB(text=BACK,
           callback_data='back_to_help_center'))
    return back_to_help_center.as_markup()
