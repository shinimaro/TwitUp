from aiogram import Router, Bot, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot_apps.FSM.FSM_states import FSMAdmin
from bot_apps.filters.ban_filters.is_banned import IsBanned
from bot_apps.panels.admin_panel.admin_panel_functions import find_users_page, get_users_list_from_state, apply_sorting, \
    get_user_sorting_options, initial_users_page, open_another_users_list, sorted_users_list_for_time, \
    get_admin_message, find_tg_id, get_tg_id, change_user_priority, change_user_balance, add_priority_fines, \
    add_stb_fines
from bot_apps.panels.admin_panel.admin_panel_keyboards import main_menu_keyboard, users_work_keyboard, \
    sorted_users_menu_keboard, all_info_user_keyboard, change_user_level_keyboard, adding_fines_user_keyboard, \
    back_user_button, confirm_user_message_keyboard
from bot_apps.panels.admin_panel.admin_panel_middlewares import AdminMidelware
from bot_apps.panels.admin_panel.admin_panel_send_messages import send_message_to_user_from_bot
from bot_apps.panels.admin_panel.admin_panel_text import main_text_builder, users_menu_text, all_user_info_text, \
    get_user_text_dict, priority_fines_text, stb_fines_text, message_from_bot_text, confirm_user_message_text, sent_tasks_user_text
from bot_apps.wordbank import admin_panel
from config import load_config
from databases.database import db, UsersList

router = Router()
config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
is_banned = IsBanned()


# Открытие панели админа
@router.message(Command(commands='admin'), AdminMidelware())
async def open_admin_panel(message: Message, state: FSMContext):
    message_id = await message.answer(await main_text_builder(),
                                      reply_markup=main_menu_keyboard())
    await message.delete()
    await state.update_data(admin_message=message_id.message_id)


# Вернуться в панель админа
@router.callback_query(F.data == 'admin_back_to_admin_main_menu')
async def open_back_admin_panel(callback: CallbackQuery):
    await callback.message.edit_text(await main_text_builder(),
                                     reply_markup=main_menu_keyboard())


# Открыть меню с юзерами
@router.callback_query((F.data == 'admin_users_work') | (F.data == 'admin_back_to_users_work'))
async def open_users_work(callback: CallbackQuery, state: FSMContext):
    page = await find_users_page(callback, state)
    users_list: list[UsersList] = await db.get_users_list_with_info()
    await callback.message.edit_text(users_menu_text(users_list, page),
                                     reply_markup=users_work_keyboard(users_list, page))
    await state.update_data(users_list=users_list)
    await state.set_state(FSMAdmin.input_user)


# Открыть меню с юзерами после сортировки с первой страницы
async def open_users_work_after_sorting(callback: CallbackQuery, state: FSMContext, notification: str):
    await callback.answer(notification)
    users_list: list[UsersList] = await get_users_list_from_state(state)
    await callback.message.edit_text(users_menu_text(users_list, 1),
                                     reply_markup=users_work_keyboard(users_list, 1))


# Открыть другую страницу с юзерами
@router.callback_query((F.data.startswith('admin_users_work_page_')) | (F.data == 'admin_back_to_users_work_pages'))
async def open_users_work_page(callback: CallbackQuery, state: FSMContext):
    page = await initial_users_page(callback, state)
    users_list: list[UsersList] = await get_users_list_from_state(state)
    await callback.message.edit_text(users_menu_text(users_list, page),
                                     reply_markup=users_work_keyboard(users_list, page))


# Сбросить сортировку в юзерах
@router.callback_query(F.data == 'admin_reset_sorting_users_list')
async def process_reset_sorting_users(callback: CallbackQuery, state: FSMContext):
    await apply_sorting(callback, state, 'registration_date')
    await open_users_work_after_sorting(callback, state, admin_panel['reset_sorting'])


# Открыть сортировку юзеров
@router.callback_query(F.data == 'admin_sorting_users_list')
async def process_sorting_users_list(callback: CallbackQuery, state: FSMContext):
    await get_user_sorting_options(state)
    await callback.message.edit_text(admin_panel['soretd_text'],
                                     reply_markup=await sorted_users_menu_keboard(state))


# Отсортировать значения
@router.callback_query(F.data.startswith('admin_sort_users_'))
async def process_apply_sorting_users_list(callback: CallbackQuery, state: FSMContext):
    await apply_sorting(callback, state)
    await open_users_work_after_sorting(callback, state, admin_panel['new_sorting'])


# Открыть забаненных или других юзеров
@router.callback_query(F.data.startswith('admin_open_users_list_'))
async def process_open_users_list_(callback: CallbackQuery, state: FSMContext):
    await open_another_users_list(callback, state)
    await open_users_work_after_sorting(callback, state, admin_panel['new_list_users'])


# Отсечь по времени других юзеров
@router.callback_query(F.data.startswith('admin_sorted_users_for_'))
async def sorted_users_for_time(callback: CallbackQuery, state: FSMContext):
    await sorted_users_list_for_time(callback, state)
    await open_users_work_after_sorting(callback, state, admin_panel['new_sorting'])


# Открыть какого-то пользователя
@router.message(StateFilter(FSMAdmin.input_user))
async def open_all_info_about_user(message: Message, state: FSMContext):
    await message.delete()
    tg_id = await find_tg_id(message, state)
    await bot.edit_message_text(message_id=await get_admin_message(state),
                                chat_id=message.chat.id,
                                text=await all_user_info_text(tg_id, state),
                                reply_markup=await all_info_user_keyboard(state))


# Вернутся к какому-то пользователю
@router.callback_query(F.data == 'admin_back_to_user_info')
async def back_open_all_info_about_user(callback: CallbackQuery, state: FSMContext):
    tg_id = await get_tg_id(state)
    await callback.message.edit_text(text=await all_user_info_text(tg_id, state),
                                     reply_markup=await all_info_user_keyboard(state))
    await state.set_state(FSMAdmin.input_user)


# Открытие меню с юзером после каких-то изменений
async def open_all_user_info_after_message(obj: Message | CallbackQuery, state: FSMContext):
    if isinstance(obj, Message):
        await bot.edit_message_text(chat_id=obj.chat.id,
                                    message_id=await get_admin_message(state),
                                    text=await all_user_info_text(obj.from_user.id, state),
                                    reply_markup=await all_info_user_keyboard(state))
    else:
        await obj.message.edit_text(text=await all_user_info_text(obj.from_user.id, state),
                                    reply_markup=await all_info_user_keyboard(state))


# Изменение баланса юзера
@router.callback_query(F.data == 'admin_for_user_change_balance')
async def user_change_balance(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text=await get_user_text_dict('change_balance', state),
                                     reply_markup=back_user_button())
    await state.set_state(FSMAdmin.input_user_balance)


# Ввод нового баланса
@router.message(StateFilter(FSMAdmin.input_user_balance))
async def process_input_user_balance(message: Message, state: FSMContext):
    await change_user_balance(state, message.text)
    await message.delete()
    await open_all_user_info_after_message(message, state)


# Изменения приоритета пользвателя
@router.callback_query(F.data == 'admin_for_user_change_priority')
async def user_change_priority(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text=await get_user_text_dict('change_level', state),
                                     reply_markup=back_user_button())
    await state.set_state(FSMAdmin.input_user_priority)


# Ввод нового приоритета юзера
@router.message(StateFilter(FSMAdmin.input_user_priority))
async def process_input_user_priority(message: Message, state: FSMContext):
    await change_user_priority(state, message.text)
    await message.delete()
    await open_all_user_info_after_message(message, state)


# Изменение уровня пользователя
@router.callback_query(F.data == 'admin_for_user_change_level')
async def change_user_level(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await get_user_text_dict('change_level', state),
                                     reply_markup=change_user_level_keyboard())


# Ввод нового уровня для пользователя
@router.callback_query(F.data.startswith('admin_for_user_change_level_'))
async def process_change_user_level(callback: CallbackQuery, state: FSMContext):
    await db.change_user_level(await get_tg_id(state), callback.data[28:])
    await open_all_user_info_after_message(callback, state)


# Добавить штраф для юзера
@router.callback_query(F.data == 'admin_for_user_adding_fines')
async def adding_new_fines_user(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await get_user_text_dict('adding_fines', state),
                                     reply_markup=adding_fines_user_keyboard())


# Выбор штрафа на приоритет
@router.callback_query(F.data == 'admin_for_user_adding_fines_priority')
async def process_ading_fines_prioryty(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await priority_fines_text(state),
                                     reply_markup=back_user_button())
    await state.set_state(FSMAdmin.input_fines_priority)


# Указание понижение приоритета юзера
@router.message(StateFilter(FSMAdmin.input_fines_priority))
async def process_adding_fines_on_priority(message: Message, state: FSMContext):
    await message.delete()
    await add_priority_fines(state, message.text)
    await open_all_user_info_after_message(message, state)


# Выбор штрафа на сбор STB
@router.callback_query(F.data == 'admin_for_user_adding_fines_stb')
async def process_adding_fines_on_stb(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await stb_fines_text(state),
                                     reply_markup=back_user_button())
    await state.set_state(FSMAdmin.input_fines_stb)


# Указать сколько будем взимать с юзера
@router.message(StateFilter(FSMAdmin.input_fines_stb))
async def process_adding_fines_on_stb(message: Message, state: FSMContext):
    await message.delete()
    await add_stb_fines(state, message.text)
    await open_all_user_info_after_message(message, state)


# Отправить сообщение от имени бота
@router.callback_query(F.data == 'admin_for_user_message_from_bot')
async def new_message_to_user(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await message_from_bot_text(state),
                                     reply_markup=back_user_button())
    await state.set_state(FSMAdmin.input_message_from_bot)


# Указать сообщение для юзера
@router.message(StateFilter(FSMAdmin.input_message_from_bot))
async def process_new_message_user(message: Message, state: FSMContext):
    await message.delete()
    await bot.edit_message_text(chat_id=message.chat.id,
                                message_id=await get_admin_message(state),
                                text=await confirm_user_message_text(state, message.text),
                                reply_markup=confirm_user_message_keyboard(),
                                disable_web_page_preview=True)
    await state.update_data(message_to_user_from_bot=message.text)


# Подтверждение указанного сообщения
@router.callback_query(F.data == 'admin_for_user_confirm_message')
async def process_message_answer(callback: CallbackQuery, state: FSMContext):
    await send_message_to_user_from_bot(state)
    await open_all_user_info_after_message(callback, state)


# Забанить юзера
@router.callback_query(F.data == 'admin_ban_user')
async def process_ban_user(callback: CallbackQuery, state):
    await is_banned.adding_blocked_users(callback.from_user.id)
    await callback.answer(admin_panel['ban_user'])
    await open_all_user_info_after_message(callback, state)


# Разбанить юзера
@router.callback_query(F.data == 'admin_unban_user')
async def process_unban_user(callback: CallbackQuery, state):
    await is_banned.del_blocked_users(callback.from_user.id)
    await callback.answer(admin_panel['unban_user'])
    await open_all_user_info_after_message(callback, state)


# Показать историю отправленных заданий юзеру
@router.callback_query(F.data == 'admin_for_user_tasks_sent_history')
async def process_open_sent_tasks(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await sent_tasks_user_text(callback.from_user.id, state))


    # Стейт с вводом задания


















