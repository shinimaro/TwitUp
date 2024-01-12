from aiogram import Router, Bot, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot_apps.bot_parts.adding_task.adding_task_text import round_numbers
from bot_apps.bot_parts.personal_office.referral_office.referral_office_keyboards import create_promocode_kb_builder, \
    button_back_under_insert_promocode_builder, correct_to_inserted_promocode_builder, \
    successful_creation_promocode_builder, ref_office_builder, affiliate_statistics_builder, block_keyboard_builder, \
    back_to_ref_office_builder
from bot_apps.bot_parts.personal_office.referral_office.refferal_office_text import ref_office_text_builder, \
    affiliate_statistics_text_builder
from bot_apps.bot_parts.personal_office.referral_office.refferall_office_link_constructor import ref_link_no_text
from bot_apps.bot_parts.personal_office.referral_office.refferral_office_filters import correct_promocode
from bot_apps.other_apps.FSM.FSM_states import FSMPromocode, FSMAccounts
from bot_apps.other_apps.filters.ban_filters.is_banned import IsBanned
from bot_apps.other_apps.wordbank import referral_office
from config import load_config
from databases.database import Database

config = load_config()
router = Router()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
db = Database()
router.callback_query.filter(IsBanned())
router.message.filter(IsBanned())


# Начало создания промокода
@router.callback_query((F.data == 'not_promocode') | (F.data == 'back_to_create_promocode'))
async def process_add_promocode(callback: CallbackQuery, state: FSMContext):
    if not await db.check_pass_ref_office(callback.from_user.id):
        await callback.message.edit_text(referral_office['preliminary_text'],
                                         reply_markup=block_keyboard_builder())
    else:
        await callback.message.edit_text(referral_office['creation_promocode']['firs_text'],
                                         reply_markup=create_promocode_kb_builder())
        await state.set_state(FSMAccounts.accounts_menu)


# Пользователь собирается вводить промокод
@router.callback_query((F.data == 'create_promocode') | (F.data == 'change_promocode'))
async def process_create_promocode(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(referral_office['creation_promocode']['what_the_name'],
                                     reply_markup=button_back_under_insert_promocode_builder())
    await state.set_state(FSMPromocode.create_promocode)


# Пользователь ввёл промокод
@router.message(StateFilter(FSMPromocode.create_promocode))
async def process_insert_promocode(message: Message, state: FSMContext):
    await message.delete()
    is_correct_promomode = await correct_promocode(message.text.strip() if message.text else None)
    # Если функция вернула текст с ошибкой
    if isinstance(is_correct_promomode, str):
        await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                    chat_id=message.chat.id, text=is_correct_promomode,
                                    reply_markup=button_back_under_insert_promocode_builder())
    # Если пользователь ввёл корректный промокод
    else:
        await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                    chat_id=message.chat.id,
                                    text=referral_office['creation_promocode']['insert_name'].format(message.text.strip()),
                                    reply_markup=correct_to_inserted_promocode_builder())
        await state.update_data(promocode=message.text.strip())


# Пользователь сохранил промокод
@router.callback_query(F.data == 'save_promocode')
async def process_save_new_promocode(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await db.save_new_promocode(callback.from_user.id, data.get('promocode'))
    await callback.message.edit_text(referral_office['creation_promocode']['save_name'].format(
        data.get('promocode'), await ref_link_no_text(callback.from_user.id)),
        reply_markup=await successful_creation_promocode_builder(callback.from_user.id))
    await state.set_state(FSMAccounts.accounts_menu)


# Пользователь открыл реферальный кабинет
@router.callback_query((F.data == 'ref_office') | (F.data == 'back_to_ref_office'))
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
@router.callback_query(F.data == 'affiliate_statistics')
async def process_open_affiliate_statistics(callback: CallbackQuery):
    await callback.message.edit_text(await affiliate_statistics_text_builder(callback.from_user.id),
                                     reply_markup=affiliate_statistics_builder())


# Пользователь решил собрать все реферальные награды
@router.callback_query(F.data == 'collect_referral_rewards')
async def collection_referral_rewards(callback: CallbackQuery, state: FSMContext):
    # У пользователя нет реферальных наград
    if not await db.check_referral_rewards(callback.from_user.id):
        await callback.message.edit_text(referral_office['not_tokens'],
                                         reply_markup=back_to_ref_office_builder())
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
            await callback.answer(referral_office['part_awards_collected'].format(round_numbers(result),
                                                                                  balance), show_alert=True)
            await process_open_ref_office(callback, state)
        # Пользователь может собрать все реферальные награды
        else:
            balance = await db.collection_of_referral_rewards(callback.from_user.id)
            await callback.answer(referral_office['awards_collected'].format(balance[0],
                                                                             balance[1]), show_alert=True)
            await process_open_ref_office(callback, state)
