import time
from asyncio import sleep

from aiogram import Router, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Text, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot_apps.FSM.FSM_states import FSMAccounts
from bot_apps.databases.database import db
from bot_apps.limit_filter.limit_filter import MainFiter
from bot_apps.personal_office.first_steps.first_steps_keyboards import first_account_builder, add_first_account_builder, \
    before_check_first_account_builder, completion_add_first_account_builder, \
    completion_of_training_builder, button_back_under_ruled_from_training_builder, \
    button_back_under_rules_from_end_training_builder, \
    how_up_to_level_builder, shadow_ban_keyboard_builder, not_add_first_account_builder
from bot_apps.personal_office.personal_office_filters import correct_account
from bot_apps.personal_office.personal_office_parsing import add_new_account
from bot_apps.wordbank.wordlist import accounts, rules
from config import load_config

router = Router()
config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")


# Добавление своего самого первого аккаунта
@router.callback_query(Text(text=['add_first_account', 'back_at_specify_account']))
async def add_first_account(callback: CallbackQuery):
    await callback.message.edit_text(accounts['education_1'],
                                     reply_markup=await first_account_builder())


# Возвращение в меню добавление первого аккаунта (если необходимо удалить сообщение)
@router.callback_query(Text(text=['back_to_first_account']))
async def add_first_account(callback: CallbackQuery):
    await callback.message.delete()
    message_id = await callback.message.answer(accounts['education_1'],
                                               reply_markup=await first_account_builder())
    await db.update_main_interface(callback.from_user.id, message_id.message_id)


# Пользователь учится добавлять аккаунт
@router.callback_query(Text(text=['specify_account', 'change_first_account']))
async def adding_an_account(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    message_id = await callback.message.answer_photo(photo='https://disk.yandex.ru/i/97G2fkTFxPYZKw', caption=accounts['education_2'],
                                                     reply_markup=await add_first_account_builder())
    await db.update_main_interface(callback.from_user.id, message_id.message_id)
    await state.set_state(FSMAccounts.add_first_account)


# Пользователь написал первый аккаунт
@router.message(StateFilter(FSMAccounts.add_first_account))
async def input_first_account(message: Message, state: FSMContext):
    is_correct = await correct_account(message.from_user.id, message.text.strip() if message.text else None)
    try:
        await bot.delete_message(message_id=await db.get_main_interface(message.from_user.id),
                                 chat_id=message.chat.id)
    except TelegramBadRequest:
        pass
    # Если вернулся текст с ошибкой
    if isinstance(is_correct, str):
        message_id = await message.answer_photo(photo='https://disk.yandex.ru/i/97G2fkTFxPYZKw',
                                                caption=is_correct.format(message.text.strip()[:70]),
                                                reply_markup=await add_first_account_builder())
        await db.update_main_interface(message.from_user.id, message_id.message_id)
    # Если пользователь корректно указал аккаунт
    else:
        username = message.text.strip() if not message.text.startswith('https://twitter.com/') else '@' + message.text.strip()[20:]
        await state.set_state(FSMAccounts.accounts_menu)
        message_id = await message.answer(text=accounts['education_3'].format(username[1:]),
                                          reply_markup=await before_check_first_account_builder(),
                                          disable_web_page_preview=True)
        await db.update_main_interface(message.from_user.id, message_id.message_id)
        await state.update_data(account=username)
    await message.delete()


# Пользователь не подписался на аккаунт
@router.callback_query(lambda x: x.data.startswith('try_again_education_'))
async def process_fail_check(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    # check_2 = await func()
    check_2 = True
    await callback.message.edit_text(accounts['examination'].format(data.get('account')))
    await sleep(2)
    # Если аккаунт так и не найден в подписках
    if not check_2:
        await callback.message.edit_text(accounts['fail_check_again'].format(
            data.get('account')[1:] if callback.data[-1] != '3'
            else accounts['final_fail'].format(data.get('account')[1:])),
            reply_markup=await not_add_first_account_builder(int(callback.data[-1]) + 1),
            disable_web_page_preview=True)
    # Если аккаунты был найден в подписках
    else:
        await callback.message.edit_text(accounts['result_check'].format(data.get('account')[1:]),
                                         reply_markup=await completion_add_first_account_builder(),
                                         disable_web_page_preview=True)
        await add_new_account(callback.from_user.id, data.get('account'))
        await state.set_state(FSMAccounts.accounts_menu)


# Пользователь подписался на канал
@router.callback_query(Text(text=['check_first_task']))
async def process_check_first_task(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    # first_check = func()
    await callback.message.edit_text(accounts['examination'].format(data.get('account')))
    # Задержка пока для видимости проверки
    await sleep(3)
    first_check, shadow_ban = True, True
    if not first_check:
        await callback.message.edit_text(accounts['fail_check'].format(data.get('account')[1:]),
                                         reply_markup=await not_add_first_account_builder(),
                                         disable_web_page_preview=True)
    elif not shadow_ban:
        await callback.message.edit_text(accounts['shadow_ban'].format(data.get('account')[1:]),
                                         reply_markup=await shadow_ban_keyboard_builder(),
                                         disable_web_page_preview=True)
    else:
        await callback.message.edit_text(accounts['result_check'].format(data.get('account')[1:]),
                                         reply_markup=await completion_add_first_account_builder(),
                                         disable_web_page_preview=True)
        await add_new_account(callback.from_user.id, data.get('account'))
        await state.set_state(FSMAccounts.accounts_menu)


# Переход обратно в меню с информацией о добавлении первого аккаунта
@router.callback_query(Text(text=['back_check_first_task']))
async def back_check_first_task(callback: CallbackQuery):
    await callback.message.edit_text(accounts['result_check'],
                                     reply_markup=await completion_add_first_account_builder())


# Первое включение всех уведомлений
@router.callback_query(Text(text=['allow_enabling_tasks', 'back_at_end_training_true']))
async def enable_all_notifications(callback: CallbackQuery):
    await db.enable_all_on(callback.from_user.id)
    await callback.message.edit_text(accounts['notifications_enabled'].format(0, 0, 0, 0),
                                     reply_markup=await completion_of_training_builder())


# # Пользователь решил не включать аккаунт в первый раз
# @router.callback_query(Text(text=['not_allow_enabling_tasks', 'back_at_end_training_false']))
# async def not_enable_all_notifications(callback: CallbackQuery):
#     await callback.message.edit_text(accounts['not_notifications_enabled'],
#                                      reply_markup=await completion_of_training_with_setting_builder())
#     await db.enable_all_off(callback.message.message_id)

# Открытие правил пользования сервисов из начала обучения
@router.callback_query(Text(text=['rules_from_training']))
async def open_rules_from_training(callback: CallbackQuery):
    await callback.message.edit_text(text=rules['main_text'],
                                     reply_markup=await button_back_under_ruled_from_training_builder())


# Открытие правил пользования в конце обучения
@router.callback_query(Text(text=['rules_from_end_training_notice', 'rules_from_end_training_without_notice']))
async def open_rules_from_end_training(callback: CallbackQuery):
    await callback.message.edit_text(rules['main_text'],
                                     reply_markup=await button_back_under_rules_from_end_training_builder(
                                         False if callback.data == 'rules_from_end_training_without_notice' else True))


# Блок с конкретным ответом на вопрос, как апнуть уровень аккаунта
@router.callback_query(Text(text=['how_up_level']))
async def open_up_level_instruction(callback: CallbackQuery):
    await callback.message.edit_text(rules['how_up_level'],
                                     reply_markup=await how_up_to_level_builder())
