import time

from aiogram import Router, Bot
from aiogram.filters import Command, Text
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ErrorEvent

from bot_apps.databases.database import db
from bot_apps.other_apps.main_menu.main_menu_functions import delete_old_interface, Antispam
from bot_apps.other_apps.main_menu.main_menu_keyboard import main_menu_builder
from bot_apps.wordbank.wordlist import main_menu
from config import load_config
from bot_apps.limit_filter.limit_filter import MainFiter

router = Router()
config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")

router.callback_query.filter(MainFiter()), router.message.filter(MainFiter())


# Запуск бота пользователем
@router.message(Command('start'), Antispam())
async def process_start_bot(message: Message, state: FSMContext):
    await state.clear()
    await db.adding_user_in_database(message.from_user.id, '@' + message.from_user.username, message.text[9:])
    message_id = await message.answer(main_menu['main_text'], reply_markup=await main_menu_builder(message.from_user.id))
    # Удаление старого сообщения с интерфейсом бота и запись в бд о новом сообщении
    await delete_old_interface(message_id, message.from_user.id, bot, message.message_id)


# Пользователь вернулся в главное меню
@router.callback_query(Text(text=['back_to_main_menu']))
async def process_open_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    # Проверка на то, что у бота есть другие отправленные им сообщения перед главным меню, либо же пользователь долго не открывал главное меню
    if await db.check_answer_message(callback.from_user.id, callback.message.message_id):
        message_id = await callback.message.answer(main_menu['main_text'],
                                                   reply_markup=await main_menu_builder(callback.from_user.id))
        # Удаление старого сообщения с интерфейсом бота и запись в бд о новом сообщении
        await delete_old_interface(message_id, callback.from_user.id, bot, callback.message.message_id)
    else:
        await callback.message.edit_text(main_menu['main_text'],
                                         reply_markup=await main_menu_builder(callback.from_user.id))


# Обработчик любых ошибок (сюда будут приходить все ошибки, которые вылезли при принятии/отправке сообщений)
# @router.errors()
# async def sus(exception: ErrorEvent):
#     print('Ошибка: ', exception.exception, exception)