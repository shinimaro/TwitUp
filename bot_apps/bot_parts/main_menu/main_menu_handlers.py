from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot_apps.bot_parts.main_menu.main_menu_functions import delete_old_interface, Antispam
from bot_apps.bot_parts.main_menu.main_menu_keyboard import main_menu_builder
from bot_apps.bot_parts.main_menu.main_menu_text import main_info_about_user
from bot_apps.other_apps.filters.ban_filters.is_banned import IsBanned
from bot_apps.other_apps.filters.ban_filters.they_banned import TheyBanned
from bot_apps.other_apps.filters.limits_filters.callback_limit_filter import CallbackFilter
from bot_apps.other_apps.filters.limits_filters.message_limit_filter import MessageFilter
from bot_apps.other_apps.wordbank import main_menu
from config import load_config
from databases.database import Database

router = Router()
config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
they_banned = TheyBanned()
db = Database()

# Фильтры на бан
router.callback_query.filter(IsBanned())
router.message.filter(IsBanned())
router.message.filter(TheyBanned())
router.callback_query.filter(TheyBanned())
# Фильтры на предотвращение отправки большого кол-ва сообщений
router.callback_query.filter(CallbackFilter())
router.message.filter(MessageFilter())


# Запуск бота пользователем
@router.message(Command(commands='start'), Antispam())
async def process_start_bot(message: Message, state: FSMContext):
    await state.clear()
    await db.adding_user_in_database(message.from_user.id, '@' + message.from_user.username, message.text[9:])
    message_id = await message.answer(await main_info_about_user(message.from_user.id),
                                      reply_markup=await main_menu_builder(message.from_user.id))
    # Удаление старого сообщения с интерфейсом бота и запись в бд о новом сообщении
    await delete_old_interface(message_id, message.from_user.id, bot, message.message_id)


# Пользователь вернулся в главное меню
@router.callback_query(F.data == 'back_to_main_menu')
async def process_open_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    # Проверка на то, что у бота есть другие отправленные им сообщения перед главным меню, либо же пользователь долго не открывал главное меню
    if await db.check_answer_message(callback.from_user.id, callback.message.message_id):
        message_id = await callback.message.answer(await main_info_about_user(callback.from_user.id),
                                                   reply_markup=await main_menu_builder(callback.from_user.id))
        # Удаление старого сообщения с интерфейсом бота и запись в бд о новом сообщении
        await delete_old_interface(message_id, callback.from_user.id, bot, callback.message.message_id)
    else:
        await callback.message.edit_text(await main_info_about_user(callback.from_user.id),
                                         reply_markup=await main_menu_builder(callback.from_user.id))


# Пользователь открыл лайтпеппер в главном меню
@router.callback_query(F.data == 'twittup_litepepper')
async def process_open_litepepper(callback: CallbackQuery):
    await callback.answer(main_menu['litepepper_stub'], show_alert=True)
