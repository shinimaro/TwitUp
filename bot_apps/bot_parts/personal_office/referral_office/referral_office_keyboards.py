from aiogram.types import InlineKeyboardButton as IB
from aiogram.types import InlineKeyboardMarkup as IM
from aiogram.utils.keyboard import InlineKeyboardBuilder as BD

from bot_apps.bot_parts.personal_office.referral_office.refferall_office_link_constructor import ref_link_constructor
from bot_apps.other_apps.wordbank import BACK, referral_office, BACK_PERSONAL_ACCOUNT


# Клавиатура, если пользователь не может пройти в реферальный кабинет
def block_keyboard_builder() -> IM:
    block_keyboard = BD()
    block_keyboard.row(
        IB(text=BACK,
           callback_data='back_to_personal_account'))
    return block_keyboard.as_markup()


# Самая первая клавиатура для начала создания промокода
def create_promocode_kb_builder() -> IM:
    create_promocode_kb = BD()
    create_promocode_kb.row(
        IB(text=referral_office['buttons']['create_promocode_button'],
           callback_data='create_promocode'),
        IB(text=BACK_PERSONAL_ACCOUNT,
           callback_data='back_to_personal_account'), width=1)
    return create_promocode_kb.as_markup()


# Кнопка "назад" под вводом первого промокода
def button_back_under_insert_promocode_builder() -> IM:
    button_back_under_insert_promocode = BD()
    button_back_under_insert_promocode.row(
        IB(text=BACK,
           callback_data='back_to_create_promocode'),
        IB(text=BACK_PERSONAL_ACCOUNT,
           callback_data='back_to_personal_account'), width=1)
    return button_back_under_insert_promocode.as_markup()


# Пользователь задал промокод и нужно спросить, всё ли корректно
def correct_to_inserted_promocode_builder() -> IM:
    correct_to_inserted_promocode = BD()
    correct_to_inserted_promocode.row(
        IB(text=referral_office['buttons']['save_promocode_button'],
           callback_data='save_promocode'),
        IB(text=referral_office['buttons']['change_promocode_button'],
           callback_data='change_promocode'),
        IB(text=BACK_PERSONAL_ACCOUNT,
           callback_data='back_to_personal_account'), width=1)
    return correct_to_inserted_promocode.as_markup()


# Пользователь успешно добавил промокод
async def successful_creation_promocode_builder(tg_id) -> IM:
    successful_creation_promocode = BD()
    promocode = await ref_link_constructor(tg_id)
    successful_creation_promocode.row(
        IB(text=referral_office['buttons']['invite_friends_button'],
           url=promocode),
        IB(text=referral_office['buttons']['go_to_ref_office_button'],
           callback_data='ref_office'),
        IB(text=BACK_PERSONAL_ACCOUNT,
           callback_data='back_to_personal_account'), width=1)
    return successful_creation_promocode.as_markup()


# Клавиатура реферального кабинета
async def ref_office_builder(tg_id) -> IM:
    ref_office = BD()
    promocode = await ref_link_constructor(tg_id)
    ref_office.row(
        IB(text=referral_office['buttons']['invite_friends_button'],
           url=promocode),
        IB(text=referral_office['buttons']['collect_rewards_button'],
           callback_data='collect_referral_rewards'),
        IB(text=referral_office['buttons']['affiliate_statistics_button'],
           callback_data='affiliate_statistics'),
        IB(text=BACK_PERSONAL_ACCOUNT,
           callback_data='back_to_personal_account'), width=1)
    return ref_office.as_markup()


# Клавиатура партнёрской статистики
def affiliate_statistics_builder() -> IM:
    affiliate_statistics_kb = BD()
    affiliate_statistics_kb.row(
        IB(text=BACK,
           callback_data='back_to_ref_office'),
        IB(text=BACK_PERSONAL_ACCOUNT,
           callback_data='back_to_personal_account'), width=1)
    return affiliate_statistics_kb.as_markup()


# Кнопка назад после того, как пользователь решил собрать награды, а их нет
def back_to_ref_office_builder() -> IM:
    back_to_ref_office = BD()
    back_to_ref_office.row(
        IB(text=BACK,
           callback_data='back_to_ref_office'))
    return back_to_ref_office.as_markup()
