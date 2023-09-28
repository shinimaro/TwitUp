from aiogram import Router, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Text, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot_apps.FSM.FSM_states import FSMAccounts, FSMPromocode
from bot_apps.limit_filter.limit_filter import MainFiter
from bot_apps.personal_office.referral_office.referral_office_keyboards import create_promocode_kb_builder, \
    button_back_under_insert_promocode_builder, correct_to_inserted_promocode_builder, \
    successful_creation_promocode_builder, ref_office_builder, affiliate_statistics_builder, block_keyboard_builder, \
    back_to_ref_office_builder
from bot_apps.personal_office.referral_office.refferal_office_text import ref_office_text_builder, \
    affiliate_statistics_text_builder
from bot_apps.personal_office.referral_office.refferall_office_link_constructor import ref_link_no_text
from bot_apps.personal_office.referral_office.refferral_office_filters import correct_promocode
from bot_apps.wordbank.wordlist import referral_office
from config import load_config
from bot_apps.databases.database import db

config = load_config()
router = Router()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")


# Начало создания промокода
@router.callback_query(Text(text=['not_promocode', 'back_to_create_promocode']))
async def process_add_promocode(callback: CallbackQuery, state: FSMContext):
    # if not await db.check_pass_ref_office(callback.from_user.id):
    #     await callback.message.edit_text(referral_office['preliminary_text'],
    #                                      reply_markup=await block_keyboard_builder())
    # else:
    await callback.message.edit_text(referral_office['creation_promocode']['firs_text'],
                                     reply_markup=await create_promocode_kb_builder())
    await state.set_state(FSMAccounts.accounts_menu)


# Пользователь собирается вводить промокод
@router.callback_query(Text(text=['create_promocode', 'change_promocode']))
async def process_create_promocode(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(referral_office['creation_promocode']['what_the_name'],
                                     reply_markup=await button_back_under_insert_promocode_builder())
    await state.set_state(FSMPromocode.create_promocode)


# Пользователь ввёл промокод
@router.message(StateFilter(FSMPromocode.create_promocode))
async def process_insert_promocode(message: Message, state: FSMContext):
    await message.delete()
    is_correct_promomode = await correct_promocode(message.text.strip() if message.text else None)
    # Если функция вернула текст с ошибкой
    if isinstance(is_correct_promomode, str):
        # Защита от ошибки изменения сообщения на тот же самый текст
        try:
            await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                        chat_id=message.chat.id, text=is_correct_promomode,
                                        reply_markup=await button_back_under_insert_promocode_builder())
        except TelegramBadRequest:
            pass
    # Если пользователь ввёл корректный промокод
    else:
        await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                    chat_id=message.chat.id,
                                    text=referral_office['creation_promocode']['insert_name'].format(message.text.strip()),
                                    reply_markup=await correct_to_inserted_promocode_builder())
        await state.update_data(promocode=message.text.strip())


# Пользователь сохранил промокод
@router.callback_query(Text(text=['save_promocode']))
async def process_save_new_promocode(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await db.save_new_promocode(callback.from_user.id, data.get('promocode'))
    await callback.message.edit_text(referral_office['creation_promocode']['save_name'].format(
        data.get('promocode'), await ref_link_no_text(callback.from_user.id)),
        reply_markup=await successful_creation_promocode_builder(callback.from_user.id))
    await state.set_state(FSMAccounts.accounts_menu)


# Пользователь открыл реферальный кабинет
@router.callback_query(Text(text=['ref_office', 'back_to_ref_office']))
async def process_open_ref_office(callback: CallbackQuery, state: FSMContext):
    promocode = await db.get_promocode(callback.from_user.id)
    # Если у пользователя нет промокода, запускается процесс, в котором мы предлагаем ему создать его
    if not promocode:
        await process_add_promocode(callback, state)
    # Если у пользователя есть промокод, открываем реферальный кабинет
    else:
        await callback.message.edit_text(await ref_office_text_builder(callback.from_user.id),
                                         reply_markup=await ref_office_builder(callback.from_user.id))


# Открываем нформацию с партнёрской статистикой
@router.callback_query(Text(text=['affiliate_statistics']))
async def process_open_affiliate_statistics(callback: CallbackQuery):
    await callback.message.edit_text(await affiliate_statistics_text_builder(callback.from_user.id),
                                     reply_markup=await affiliate_statistics_builder())


# Пользователь решил собрать все реферальные награды
@router.callback_query(Text(text=['collect_referral_rewards']))
async def collection_referral_rewards(callback: CallbackQuery, state: FSMContext):
    # У пользователя нет реферальных наград
    if not await db.check_referral_rewards(callback.from_user.id):
        await callback.message.edit_text(referral_office['not_tokens'],
                                         reply_markup=await back_to_ref_office_builder())
    # У пользователя есть реферальные награды
    else:
        result = await db.check_referral_reward(int(callback.from_user.id))
        # Пользователь не может собрать реферальные награды
        if not result:
            await callback.answer(referral_office['not_awards_collected'],
                                  show_alert=True)
        # Пользователь может собрать часть реферальных наград
        elif isinstance(result, float):
            balance = await db.collect_part_of_referral_rewards(callback.from_user.id, result)
            await callback.answer(referral_office['part_awards_collected'].format(
                int(result) if result.is_integer() else round(result, 2),
                int(balance) if balance.is_integer() else round(balance, 2)),
                show_alert=True)
            await process_open_ref_office(callback, state)
        # Пользователь может собрать все реферальные награды
        else:
            balance = await db.collection_of_referral_rewards(callback.from_user.id)
            await callback.answer(referral_office['awards_collected'].format(int(balance[0]) if balance[0].is_integer() else round(balance[0], 2),
                                                                             int(balance[1]) if balance[1].is_integer() else round(balance[1], 2)),
                                  show_alert=True)
            await process_open_ref_office(callback, state)
