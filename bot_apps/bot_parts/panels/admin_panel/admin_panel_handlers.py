from aiogram import Router, Bot, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot_apps.bot_parts.panels.admin_panel.admin_panel_functions import find_users_page, get_users_list_from_state, \
    apply_sorting, \
    get_user_sorting_options, initial_users_page, open_another_users_list, sorted_users_list_for_time, \
    get_admin_message, get_tg_id, change_user_priority, change_user_balance, add_priority_fines, \
    add_stb_fines, get_sent_tasks, get_users_task, sorted_user_accounts, get_user_accounts, get_user_fines, \
    get_user_paymnets, del_fines_id, save_all_tasks, tasks_sorting, open_other_tasks_list, \
    set_initial_options, save_task_all_info, save_sort_time_task, sorted_task_by_time, \
    task_distribution, task_safely_delete, task_add_executions, change_link_to_profile, change_link_to_post, \
    send_task_to_user, task_reduse_executions, change_return_flag, save_workers, sorted_task_workers, \
    initial_task_price, get_correct_task_price_state, save_price_changes, save_new_price_task, \
    initial_priority_settings, set_priority_type, save_priority_changes, apply_priority_changes, initial_awards_cut, \
    save_first_fine, save_subsequent_fines, apply_rule_fines, save_new_raiting_fines, save_new_task_fine_percent, \
    save_change_level, get_need_state_for_change_limits, change_limits_level_tasks, change_limits_level_accounts, \
    save_level_for_receiving_limits, get_need_state_for_change_receiving_limits, change_tasks_receiving_limits, \
    change_active_accs_receiving_limits, adding_new_admin, remove_admin_from_db, add_new_support, \
    remove_supporn_from_db, task_force_delete
from bot_apps.bot_parts.panels.admin_panel.admin_panel_keyboards import main_menu_keyboard, users_work_keyboard, \
    sorted_users_menu_keboard, all_info_user_keyboard, change_user_level_keyboard, adding_fines_user_keyboard, \
    back_user_button, confirm_user_message_keyboard, sent_tasks_keyboard, user_tasks_keyboard, user_acounts_keyboard, \
    user_fines_keyboard, user_payments_keyboard, user_remove_fines_keboard, all_tasks_keyboard, \
    all_tasks_sorting_keyboard, all_task_info_keyboard, button_to_task_keyboard, safely_delete_keyboard, \
    force_delete_keyboard, reduce_executions_keyboard, edit_task_links_keyboard, send_task_keyboard, \
    confirm_add_executions_keyboard, confirm_task_distribution_keyboard, confirm_reduse_executions_keboard, \
    confirm_new_profile_link, confirm_new_post_link, show_workers_keyboard, all_setings_keyboard, \
    price_per_task_keyboard, back_to_price_keyboard, priority_change_keyboard, back_to_rating_change_keyboard, \
    awards_cut_keyboard, back_to_rule_fines_keyboard, setting_raiting_fines_keyboard, back_to_raiting_fines_keyboard, \
    coinfirm_raiting_fines_keyboard, task_fines_keyboard, change_task_fines_keyboard, coinfirm_percent_fines_keyboard, \
    work_with_levels_keyboard, levels_limits_keyboard, change_limits_keyboard, back_to_limits_keyboard, \
    confirm_change_limits_tasks_keyboard, confirm_change_limits_accounts_keyboard, receiving_limits_kebyboard, \
    level_receiving_limits_kebyboard, back_to_receiving_limits_keyboard, confirm_change_need_tasks_keyboard, \
    confirm_change_need_active_accs_keyboard, edit_admin_list_keboard, back_to_admin_list_button, \
    coinfirm_adding_admin_keyboard, remove_admin_keyboard, coinfirm_remove_admin_keyboard, supports_list_keyboard, \
    back_button_to_support_list, coinfirm_support_keyboard, remove_support_keyboard, coinfirm_remove_support_keyboard, \
    defalut_support_keyboard, coinfirm_change_user_balance_keyboard, coinfirm_change_user_priority_keybaord
from bot_apps.bot_parts.panels.admin_panel.admin_panel_middlewares import AdminMidelware, UserInDatabase, \
    TaskInDatabase, \
    ItisMainAdmin, TaskIsActive
from bot_apps.bot_parts.panels.admin_panel.admin_panel_send_messages import send_message_to_user_from_bot
from bot_apps.bot_parts.panels.admin_panel.admin_panel_text import main_text_builder, users_menu_text, \
    all_user_info_text, \
    get_user_text_dict, priority_fines_text, stb_fines_text, message_from_bot_text, confirm_user_message_text, \
    sent_tasks_user_text, user_tasks_text, user_account_text, user_fines_text, user_payments_text, \
    user_remove_fines_text, all_tasks_text, all_task_info_text, dop_task_distribution_text, safely_delete_task_text, \
    confirm_safely_delete_text, task_force_delete_text, task_add_executions_text, reduce_executions_text, \
    notification_for_reduce_executions, edit_task_links_text, change_link_to_profile_text, change_link_to_post_text, \
    sent_task_text, sending_task_notification, confirm_dop_task_distribution_text, confirm_add_executions_text, \
    confirm_force_delete_text, confirm_eduse_executions_text, coinfirm_change_link_to_profile_text, \
    coinfirm_change_link_to_post_text, show_workers_text, price_per_task_text, rating_change_text, rule_fines_text, \
    setting_raiting_fines, confirm_raitin_fines_text, task_fines_text, coinfirm_task_fines_text, work_with_levels_text, \
    limits_levels_text, change_level_limits, confirm_change_limits_tasks_text, confirm_change_limits_accounts_text, \
    receiving_limits_text, change_receiving_limits_text, confirm_change_need_tasks_text, \
    confirm_change_need_active_accs_text, admins_list_text, conifrm_new_admin_text, coinifrn_remove_admin, \
    supports_list_text, coinfirm_add_support_text, coinfirm_remove_support_text, coinfirm_change_user_balance_text, \
    change_user_priority_text
from bot_apps.other_apps.FSM.FSM_states import FSMAdmin
from bot_apps.other_apps.filters.ban_filters.is_banned import IsBanned
from bot_apps.other_apps.wordbank import admin_panel
from config import load_config
from databases.database import Database
from databases.dataclasses_storage import UsersList, UserPayments, UserAccount, UserTasksInfo, UserFines, SentTasksInfo, \
    UserAllInfo

router = Router()
config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
db = Database()
is_banned = IsBanned()


# Открытие панели админа
@router.message(Command(commands='admin'), AdminMidelware())
async def open_admin_panel(message: Message, state: FSMContext):
    message_id = await message.answer(await main_text_builder(message.from_user.id),
                                      reply_markup=main_menu_keyboard())
    await message.delete()
    await state.update_data(admin_message=message_id.message_id)


# Вернуться в панель админа
@router.callback_query(F.data == 'admin_back_to_admin_main_menu')
async def open_back_admin_panel(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FSMAdmin.neutral_state)
    await callback.message.edit_text(await main_text_builder(callback.from_user.id),
                                     reply_markup=main_menu_keyboard())


# Открыть меню с юзерами
@router.callback_query((F.data == 'admin_users_work'))
async def open_users_work(callback: CallbackQuery, state: FSMContext):
    users_list: list[UsersList] = await db.get_users_list_with_info()
    await state.update_data(users_list=users_list)
    await state.set_state(FSMAdmin.input_user)
    await open_users_list(callback, state)


# Вернуться в список юзеров
@router.callback_query(F.data == 'admin_back_to_users_work')
async def back_to_user_work(callback: CallbackQuery, state: FSMContext):
    page = await find_users_page(callback, state)
    await state.set_state(FSMAdmin.input_user)
    await open_users_list(callback, state, page)


# Открыть другую страницу с юзерами
@router.callback_query((F.data.startswith('admin_users_work_page_')) | (F.data == 'admin_back_to_users_work_pages'))
async def open_users_work_page(callback: CallbackQuery, state: FSMContext):
    page = await initial_users_page(callback, state)
    await open_users_list(callback, state, page)


# Открыть меню с юзерами после сортировки с первой страницы
async def open_users_work_after_sorting(callback: CallbackQuery, state: FSMContext, notification: str):
    await callback.answer(notification)
    await open_users_list(callback, state)


# Открыть список юзеров
async def open_users_list(callback: CallbackQuery, state: FSMContext, page: int = 1):
    await state.set_state(FSMAdmin.input_user)
    users_list: list[UsersList] = await get_users_list_from_state(state)
    await callback.message.edit_text(users_menu_text(users_list, page),
                                     reply_markup=users_work_keyboard(users_list, page))


# Сбросить сортировку в юзерах
@router.callback_query(F.data == 'admin_reset_sorting_users_list')
async def process_reset_sorting_users(callback: CallbackQuery, state: FSMContext):
    await apply_sorting(callback, state, reset=True)
    await open_users_work_after_sorting(callback, state, admin_panel['reset_sorting'])


# Открыть сортировку юзеров
@router.callback_query(F.data == 'admin_sorting_users_list')
async def process_sorting_users_list(callback: CallbackQuery, state: FSMContext):
    await get_user_sorting_options(state)
    await callback.message.edit_text(admin_panel['soretd_text'],
                                     reply_markup=await sorted_users_menu_keboard(state))


# Отсортировать список юзеров
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
@router.message(StateFilter(FSMAdmin.input_user), UserInDatabase())
async def open_all_info_about_user(message: Message, state: FSMContext, tg_id: int):
    await message.delete()
    await state.update_data(tg_id=tg_id)
    user_info: UserAllInfo = await db.get_all_info_for_user(tg_id)
    await state.update_data(user_info=user_info)
    await bot.edit_message_text(message_id=await get_admin_message(state),
                                chat_id=message.chat.id,
                                text=await all_user_info_text(state),
                                reply_markup=await all_info_user_keyboard(state))


# Вернутся к какому-то пользователю
@router.callback_query(F.data == 'admin_back_to_user_info')
async def back_open_all_info_about_user(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text=await all_user_info_text(state),
                                     reply_markup=await all_info_user_keyboard(state))
    await state.set_state(FSMAdmin.input_user)


# Открытие меню с юзером после каких-то изменений
async def open_all_user_info_after_message(obj: Message | CallbackQuery, state: FSMContext):
    await state.set_state(FSMAdmin.input_user)
    await bot.edit_message_text(chat_id=obj.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await all_user_info_text(state),
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
    await message.delete()
    await state.update_data(new_balance=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await coinfirm_change_user_balance_text(state),
                                reply_markup=coinfirm_change_user_balance_keyboard())


# Подтверждение ввода баланса
@router.callback_query(F.data == 'admin_coinfirm_change_user_balance')
async def coinfirm_change_user_balance(callback: CallbackQuery, state: FSMContext):
    await change_user_balance(state)
    await callback.answer(admin_panel['user_balance_changes'])
    await open_all_user_info_after_message(callback, state)


# Изменения приоритета пользвателя
@router.callback_query(F.data == 'admin_for_user_change_priority')
async def user_change_priority(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text=await get_user_text_dict('change_priority', state),
                                     reply_markup=back_user_button())
    await state.set_state(FSMAdmin.input_user_priority)


# Ввод нового приоритета юзера
@router.message(StateFilter(FSMAdmin.input_user_priority))
async def process_input_user_priority(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(new_priority=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await change_user_priority_text(state),
                                reply_markup=coinfirm_change_user_priority_keybaord())


# Подтверждение изменения приоритета
@router.callback_query(F.data == 'admin_coinfirm_user_priority')
async def coinifrm_change_priority(callback: CallbackQuery, state: FSMContext):
    await change_user_priority(state)
    await callback.answer(admin_panel['user_priority_changes'])
    await open_all_user_info_after_message(callback, state)


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
    await is_banned.adding_blocked_users(callback.from_user.id, 'admin_ban')
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
    tasks_info: list[SentTasksInfo] = await db.get_info_about_sent_tasks(callback.from_user.id)
    await callback.message.edit_text(await sent_tasks_user_text(state, tasks_info),
                                     reply_markup=sent_tasks_keyboard(tasks_info))
    await state.update_data(tasks_info=tasks_info)
    await state.set_state(FSMAdmin.input_task_id)


# Открыть другую страницу с заданиями
@router.callback_query(F.data.startswith('admin_sent_tasks_user_page_'))
async def process_open_page_sent_tasks_user(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[27:])
    tasks_info = await get_sent_tasks(state)
    await callback.message.edit_text(await sent_tasks_user_text(state, tasks_info, page),
                                     reply_markup=sent_tasks_keyboard(tasks_info, page))


# Открыть личные задания юзера
@router.callback_query(F.data == 'admin_for_user_task_personal_history')
async def process_open_user_tasks(callback: CallbackQuery, state: FSMContext):
    user_tasks: list[UserTasksInfo] = await db.get_info_abuot_user_tasks(callback.from_user.id)
    await callback.message.edit_text(await user_tasks_text(state, user_tasks),
                                     reply_markup=user_tasks_keyboard(user_tasks))
    await state.update_data(user_tasks=user_tasks)
    await state.set_state(FSMAdmin.input_task_id)


# Открыть страницу с личными заданиями юзера
@router.callback_query(F.data.startswith('admin_user_tasks_page_'))
async def process_open_page_user_tasks(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[22:])
    user_tasks: list[UserTasksInfo] = await get_users_task(state)
    await callback.message.edit_text(await user_tasks_text(state, user_tasks, page),
                                     reply_markup=user_tasks_keyboard(user_tasks, page))


# Открыть все аккаунты юзера
@router.callback_query(F.data == 'admin_for_user_all_accounts')
async def open_user_accounts(callback: CallbackQuery, state: FSMContext):
    user_accounts: list[UserAccount] = await db.get_all_user_accounts(callback.from_user.id)
    await state.update_data(user_accounts=user_accounts)
    await state.set_state(FSMAdmin.input_task_id)
    await open_list_user_accounts(callback, state)


# Открыть другую страницу со всеми аккаунтами
@router.callback_query((F.data == 'admin_for_user_active_accounts') | (F.data == 'admin_for_user_inactive_accounts') |
                       (F.data == 'admin_for_user_deleted_accounts'))
async def process_sorted_user_accounts(callback: CallbackQuery, state: FSMContext):
    user_accounts: list[UserAccount] = await sorted_user_accounts(callback)
    await state.update_data(user_accounts=user_accounts)
    await callback.answer(admin_panel['new_sorting'])
    await open_list_user_accounts(callback, state)


# Перейти на другую страницу в аккаунтах
@router.callback_query(F.data.startswith('admin_user_accounts_page_'))
async def process_open_user_accounts_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[25:])
    await open_list_user_accounts(callback, state, page)


# Открытие списка аккаунтов юзера
async def open_list_user_accounts(callback: CallbackQuery, state: FSMContext, page: int = 1):
    await state.set_state(FSMAdmin.input_user)
    user_accounts: list[UserAccount] = await get_user_accounts(state)
    await callback.message.edit_text(await user_account_text(state, user_accounts, page),
                                     reply_markup=user_acounts_keyboard(user_accounts, page))


# Открыть список штрафов
@router.callback_query(F.data == 'admin_for_user_fines_history')
async def open_all_user_fines(callback: CallbackQuery, state: FSMContext):
    user_fines: list[UserFines] = await db.get_all_fines_user(callback.from_user.id)
    await state.update_data(user_fines=user_fines)
    await open_user_fines_list(callback, state)


# Открыть другую страницу штрафов
@router.callback_query(F.data.startswith("admin_user_fines_page_"))
async def open_user_fine_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[22:])
    await open_user_fines_list(callback, state, page)


# Открыть только активные штрафы
@router.callback_query(F.data == 'admin_for_user_active_fines')
async def open_active_fines_user(callback: CallbackQuery, state: FSMContext):
    user_fines: list[UserFines] = await db.get_only_active_fines_user(callback.from_user.id)
    await callback.answer(admin_panel['new_sorting'])
    await state.update_data(user_fines=user_fines)
    await open_user_fines_list(callback, state)


# Открыть список штрафов юзера
async def open_user_fines_list(callback: CallbackQuery, state: FSMContext, page: int = 1):
    user_fines: list[UserFines] = await get_user_fines(state)
    await callback.message.edit_text(await user_fines_text(state, user_fines, page),
                                     reply_markup=user_fines_keyboard(user_fines, page))


# Открыть пополнения юзера
@router.callback_query(F.data == 'admin_for_user_payment_history')
async def open_all_user_payments(callback: CallbackQuery, state: FSMContext):
    user_payments: list[UserPayments] = await db.get_all_payments_user(callback.from_user.id)
    await callback.message.edit_text(await user_payments_text(state, user_payments),
                                     reply_markup=user_payments_keyboard(user_payments))
    await state.update_data(user_payments=user_payments)


# Открыть другую страницу с пополнениями юзера
@router.callback_query(F.data.startswith('admin_user_payments_page_'))
async def open_all_user_payments_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[25:])
    user_payments: list[UserPayments] = await get_user_paymnets(state)
    await callback.message.edit_text(await user_payments_text(state, user_payments, page),
                                     reply_markup=user_payments_keyboard(user_payments, page))


# Открыть меню для удаления каких-то штрафов юзера
@router.callback_query(F.data == 'admin_for_user_remove_fines')
async def process_remove_user_fines(callback: CallbackQuery, state: FSMContext):
    user_fines: list[UserFines] = await db.get_only_active_fines_user(callback.from_user.id)
    await state.update_data(user_fines=user_fines)
    await state.set_state(FSMAdmin.input_fines_id)
    await open_user_remove_fines_list(callback, state)


# Открыть другую страницу со штрафами для удаления
@router.callback_query(F.data.startswith('admin_user_remove_fines_page_'))
async def open_remove_user_fines_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[29:])
    await open_user_remove_fines_list(callback, state, page)


# Удалить какой-то штраф
@router.message(StateFilter(FSMAdmin.input_fines_id))
async def remove_user_fines(message: Message, state: FSMContext):
    await message.delete()
    await del_fines_id(message)
    await open_user_remove_fines_list(message, state, dop_text=admin_panel['fines_remove'].format(message.text))


# Открыть список с активными штрафами для удаления
async def open_user_remove_fines_list(obj: CallbackQuery | Message, state: FSMContext, page: int = 1, dop_text: str = ''):
    user_fines: list[UserFines] = await get_user_fines(state)
    await bot.edit_message_text(chat_id=obj.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await user_remove_fines_text(state, user_fines, page) + dop_text,
                                reply_markup=user_remove_fines_keboard(user_fines, page))


# Расскрыть все задания пользователей
@router.callback_query(F.data == 'admin_tasks_work')
async def open_all_tasks(callback: CallbackQuery, state: FSMContext):
    await save_all_tasks(state)
    await set_initial_options(state)
    await state.set_state(FSMAdmin.input_task_id)
    await open_tasks_list(callback, state)


# Вернуться ко всем заданиям юзеров
@router.callback_query(F.data == 'admin_back_to_all_tasks')
async def process_back_to_all_tasks(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FSMAdmin.input_task_id)
    await open_tasks_list(callback, state)


# Обновить информацию
@router.callback_query(F.data == 'admin_update_info_all_tasks')
async def process_update_all_tasks(callback: CallbackQuery, state: FSMContext):
    await callback.answer(admin_panel['update_data'])
    await save_all_tasks(state)
    await tasks_sorting(callback, state)
    await open_tasks_list(callback, state)


# Открыть другую страницу со всеми заданиями
@router.callback_query(F.data.startswith('admin_all_tasks_page_'))
async def open_all_tasks_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[21:])
    await state.update_data(tasks_list_page=page)
    await open_tasks_list(callback, state)


# Сбросить сортировку
@router.callback_query(F.data == 'admin_reset_sorting_all_tasks')
async def reset_sortins_all_tasks(callback: CallbackQuery, state: FSMContext):
    await tasks_sorting(callback, state, reset=True)
    await callback.answer(admin_panel['reset_sorting'])
    await open_tasks_list(callback, state)


# Открыть сортировку
@router.callback_query(F.data == 'admin_sorting_all_tasks')
async def process_sorting_all_tasks(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(admin_panel['soretd_text'],
                                     reply_markup=await all_tasks_sorting_keyboard(state))


# Отсортировать по какому-то значению
@router.callback_query(F.data.startswith('admin_sort_tasks_'))
async def sort_all_tasks(callback: CallbackQuery, state: FSMContext):
    await tasks_sorting(callback, state)
    await callback.answer(admin_panel['new_sorting'])
    await open_tasks_list(callback, state)


# Открыть список каких-то тасков (активных, завершённых)
@router.callback_query(F.data.startswith('admin_open_tasks_list_'))
async def process_open_other_tasks_list(callback: CallbackQuery, state: FSMContext):
    await open_other_tasks_list(state, callback.data[22:])
    await open_tasks_list(callback, state)


# Отсортировать таски по времени
@router.callback_query(F.data.startswith("admin_sorted_tasks_for_"))
async def sort_task_for_time(callback: CallbackQuery, state: FSMContext):
    await save_sort_time_task(callback, state)
    await sorted_task_by_time(state)
    await open_tasks_list(callback, state)


# Открыть список с заданиями
async def open_tasks_list(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await all_tasks_text(state),
                                     reply_markup=await all_tasks_keyboard(state))


# Открыть какое-то задание
@router.message(StateFilter(FSMAdmin.input_task_id), TaskInDatabase())
async def process_open_all_task_info(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(task_id=int(message.text))
    await state.set_state(FSMAdmin.input_task_id)
    await save_task_all_info(state)
    await open_all_task_info(message, state)


# Обновить инфрормацию о задании
async def update_tasks_info(callback: CallbackQuery, state: FSMContext):
    await save_task_all_info(state)
    await open_all_task_info(callback, state)


# Вернуться к выбранному заданию
@router.callback_query(F.data == 'admin_back_to_task')
async def process_back_to_task(callback: CallbackQuery, state: FSMContext):
    await open_all_task_info(callback, state)


# Обновить какое-то задание
@router.callback_query(F.data == 'admin_task_update_info')
async def process_update_task_info(callback: CallbackQuery, state: FSMContext):
    await save_task_all_info(state)
    await open_all_task_info(callback, state)


# Отобрать ещё воркеров к какому-то заданию
@router.callback_query(F.data == 'admin_for_task_dop_task_distribution', TaskIsActive())
async def dop_task_distribution(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await dop_task_distribution_text(state),
                                     reply_markup=button_to_task_keyboard())
    await state.set_state(FSMAdmin.input_dop_distribution)


# Распределение задания
@router.message(StateFilter(FSMAdmin.input_dop_distribution))
async def process_task_distribution(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(task_distribution=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await confirm_dop_task_distribution_text(state),
                                reply_markup=confirm_task_distribution_keyboard())


# Подтвердить дополнительное распределние задания
@router.callback_query(F.data == 'admin_confirm_task_distribution', TaskIsActive())
async def process_confirm_task_distribution(callback: CallbackQuery, state: FSMContext):
    notification = await task_distribution(state)
    await callback.answer(notification, show_alert=True)
    await update_tasks_info(callback, state)


# Безопасно удалить задание
@router.callback_query(F.data == 'admin_for_task_safely_delete', TaskIsActive())
async def proces_task_safely_delete(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await safely_delete_task_text(state),
                                     reply_markup=safely_delete_keyboard())


# Подтвердить безопасное удаление задания
@router.callback_query(F.data == 'admin_confirm_task_safely_delete', TaskIsActive())
async def process_task_safely_delete(callback: CallbackQuery, state: FSMContext):
    await callback.answer(await confirm_safely_delete_text(state), show_alert=True)
    await task_safely_delete(state)
    await update_tasks_info(callback, state)


# Удалить задание принудительно
@router.callback_query(F.data == 'admin_for_task_force_delete', TaskIsActive())
async def process_task_force_delete(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await task_force_delete_text(state),
                                     reply_markup=force_delete_keyboard())


# Подтверждение принудительного удаления
@router.callback_query(F.data == 'admin_confirm_task_force_delete', TaskIsActive())
async def process_task_force_delete(callback: CallbackQuery, state: FSMContext):
    await callback.answer(await confirm_force_delete_text(state), show_alert=True)
    await task_force_delete(state)
    await update_tasks_info(callback, state)


# Добавить выполнений к заданию
@router.callback_query(F.data == 'admin_for_task_add_executions', TaskIsActive())
async def process_open_task_add_executions(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await task_add_executions_text(state),
                                     reply_markup=button_to_task_keyboard())
    await state.set_state(FSMAdmin.input_add_executions)


# Ввод дополнительного кол-ва выполнений
@router.message(StateFilter(FSMAdmin.input_add_executions))
async def process_open_task_add_executions(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(add_executions=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await confirm_add_executions_text(message.text, state),
                                reply_markup=confirm_add_executions_keyboard())


# Подтверждение дополнительного кол-ва выполнений
@router.callback_query(F.data == 'admin_confirm_task_add_executions', TaskIsActive())
async def confirm_task_add_executions(callback: CallbackQuery, state: FSMContext):
    notification = await task_add_executions(state)
    await callback.answer(notification, show_alert=True)
    await update_tasks_info(callback, state)


# Уменьшить кол-во выполнений
@router.callback_query(F.data == 'admin_for_task_reduce_executions', TaskIsActive())
async def process_task_reduce_executions(callback: CallbackQuery, state: FSMContext):
    await state.update_data(return_stb=False)
    await callback.message.edit_text(await reduce_executions_text(state),
                                     reply_markup=await reduce_executions_keyboard(state))
    await state.set_state(FSMAdmin.input_reduce_exections)


# Указание того, что нужно все выполнения снятые перевести автору
@router.callback_query(F.data == 'admin_for_task_reduce_return_stb')
async def process_task_return_stb(callback: CallbackQuery, state: FSMContext):
    await change_return_flag(state)
    await callback.answer(await notification_for_reduce_executions(state))
    await callback.message.edit_text(await reduce_executions_text(state),
                                     reply_markup=await reduce_executions_keyboard(state))


# Ввод числа, на сколько нужно уменьшить кол-во выполнений
@router.message(StateFilter(FSMAdmin.input_reduce_exections))
async def process_task_reduse_executions(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(reduse_executions=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await confirm_eduse_executions_text(state),
                                reply_markup=confirm_reduse_executions_keboard())


# Потдверждение уменьшения кол-ва выполнений
@router.callback_query(F.data == 'admin_confirm_task_reduse_executions', TaskIsActive())
async def confirn_task_reduse_executions(callback: CallbackQuery, state: FSMContext):
    notification = await task_reduse_executions(state)
    await callback.answer(notification, show_alert=True)
    await update_tasks_info(callback, state)


# Редактирование ссылок
@router.callback_query(F.data == 'admin_for_task_edit_links', TaskIsActive())
async def process_edit_task_links(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await edit_task_links_text(state),
                                     reply_markup=edit_task_links_keyboard(),
                                     disable_web_page_preview=True)


# Смена ссылки на профиль
@router.callback_query(F.data == 'admin_for_task_change_link_profile')
async def tasks_change_on_profile(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(admin_panel['process_change_profile_link'],
                                     reply_markup=button_to_task_keyboard())
    await state.set_state(FSMAdmin.input_link_to_profile)


# Смена ссылки на пост
@router.callback_query(F.data == 'admin_for_task_change_link_post')
async def tasks_change_on_post(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(admin_panel['process_change_post_link'],
                                     reply_markup=button_to_task_keyboard())
    await state.set_state(FSMAdmin.input_link_to_post)


# Ввод ссылки на профиль
@router.message(StateFilter(FSMAdmin.input_link_to_profile))
async def change_link_task_to_profile(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(new_link_profile=message.text)
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await change_link_to_profile_text(state),
                                reply_markup=confirm_new_profile_link())


# Ввод ссылки на пост
@router.message(StateFilter(FSMAdmin.input_link_to_post))
async def change_link_task_to_post(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(new_link_post=message.text)
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await change_link_to_post_text(state),
                                reply_markup=confirm_new_post_link())


# Подтверждение ссылки на профиль
@router.callback_query(F.data == 'admin_new_link_to_profile', TaskIsActive())
async def confirm_link_task_to_profile(callback: CallbackQuery, state: FSMContext):
    await change_link_to_profile(state)
    await callback.answer(await coinfirm_change_link_to_profile_text(state), show_alert=True)
    await update_tasks_info(callback, state)


# Подтверждение ссылки на пост
@router.callback_query(F.data == 'admin_new_link_to_post', TaskIsActive())
async def confirm_link_task_to_post(callback: CallbackQuery, state: FSMContext):
    await change_link_to_post(state)
    await callback.answer(await coinfirm_change_link_to_post_text(state), show_alert=True)
    await update_tasks_info(callback, state)


# Взять задание на выполнение
@router.callback_query(F.data == 'admin_for_task_send_task', TaskIsActive())
async def process_send_task(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await sent_task_text(state),
                                     reply_markup=send_task_keyboard())
    await state.set_state(FSMAdmin.input_user_to_send)


# Выслать это задание админу
@router.callback_query(F.data == 'admin_for_task_send_me')
# Проверить работу
async def process_task_send_me(callback: CallbackQuery, state: FSMContext):
    await send_task_to_user(callback.from_user.id, state)
    await open_all_task_info(callback, state)


# Выслать это задание кому-то другому
@router.message(StateFilter(FSMAdmin.input_user_to_send), UserInDatabase())
async def process_task_send_user(message: Message, state: FSMContext):
    await message.delete()
    await send_task_to_user(int(message.text), state)
    await sending_task_notification(int(message.text), state)
    await open_all_task_info(message, state)


# Открыть всю информацию о задании
async def open_all_task_info(obj: CallbackQuery | Message, state: FSMContext):
    await state.set_state(FSMAdmin.input_task_id)
    await bot.edit_message_text(chat_id=obj.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await all_task_info_text(state),
                                reply_markup=all_task_info_keyboard(),
                                disable_web_page_preview=True)


# Открыть тех, кто делают задание
@router.callback_query((F.data == 'admin_for_task_show_workers') | (F.data == 'admin_update_info_about_workers'))
async def open_show_workers_for_task(callback: CallbackQuery, state: FSMContext):
    await save_workers(state)
    await state.set_state(FSMAdmin.input_user)
    await open_workers_list(callback, state)


# Перейти на другую страницу воркеров
@router.callback_query(F.data.startswith('admin_task_workers_page_'))
async def open_other_page_workers(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[24:])
    await open_workers_list(callback, state, page)


# Отфильтровать воркеров
@router.callback_query(F.data.startswith("admin_sorted_workers_"))
async def process_sorted_workers(callback: CallbackQuery, state: FSMContext):
    await sorted_task_workers(callback, state)
    await open_workers_list(callback, state)


# Открыть список воркеров
async def open_workers_list(callback: CallbackQuery, state: FSMContext, page: int = 1):
    await callback.message.edit_text(await show_workers_text(state, page),
                                     reply_markup=await show_workers_keyboard(state, page))


# Открыть настройки
@router.callback_query((F.data == 'admin_main_settings') | (F.data == 'admin_back_to_all_settings'))
async def open_all_setings(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FSMAdmin.neutral_state)
    await callback.message.edit_text(admin_panel['all_setting_task'],
                                     reply_markup=all_setings_keyboard())


# Открыть цены за задание
@router.callback_query(F.data == 'admin_setting_price_per_task')
async def open_price_per_task(callback: CallbackQuery, state: FSMContext):
    await initial_task_price(state)
    await open_price_list(callback, state)


@router.callback_query(F.data == 'admin_back_to_task_price')
async def process_back_to_task_price(callback: CallbackQuery, state: FSMContext):
    await open_price_list(callback, state)


# Поставить новую цену за какое-то задание
@router.callback_query(F.data.startswith('admin_price_change_'))
async def process_change_price(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(admin_panel['input_value'],
                                     reply_markup=back_to_price_keyboard())
    await state.set_state(get_correct_task_price_state(callback))


# Ввод нового ценника за задание
@router.message(StateFilter(FSMAdmin.input_price_to_subscriptions))
@router.message(StateFilter(FSMAdmin.input_price_to_likes))
@router.message(StateFilter(FSMAdmin.input_price_to_retweets))
@router.message(StateFilter(FSMAdmin.input_price_to_comments))
@router.message(StateFilter(FSMAdmin.input_price_to_commission))
async def change_task_price(message: Message, state: FSMContext):
    await message.delete()
    await save_price_changes(message.text, state)
    await open_price_list(message, state)


# Подтверждение изменений в цене за таск
@router.callback_query(F.data == 'admin_save_new_task_price')
async def process_save_new_price(callback: CallbackQuery, state: FSMContext):
    await save_new_price_task(state)
    await initial_task_price(state)
    await callback.answer(admin_panel['task_price_changes'], show_alert=True)
    await open_price_list(callback, state)


# Открыть список с ценами за задание
async def open_price_list(obj: CallbackQuery | Message, state: FSMContext):
    await bot.edit_message_text(chat_id=obj.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await price_per_task_text(state),
                                reply_markup=await price_per_task_keyboard(state))


# Открыть изменения таска
@router.callback_query(F.data == 'admin_setting_rating_change')
async def process_rating_change(callback: CallbackQuery, state: FSMContext):
    await initial_priority_settings(state)
    await open_all_rating_settings(callback, state)


@router.callback_query(F.data == 'back_to_rating_change')
async def process_back_to_rating_change(callback: CallbackQuery, state: FSMContext):
    await open_all_rating_settings(callback, state)


# Выбор типа действия за которое меняется приоритет
@router.callback_query(F.data.startswith('admin_change_priority_for_'))
async def pricess_change_priority(callback: CallbackQuery, state: FSMContext):
    await set_priority_type(callback, state)
    await state.set_state(FSMAdmin.input_priority_change)
    await callback.message.edit_text(admin_panel['input_change_priority'],
                                     reply_markup=back_to_rating_change_keyboard())


# Ввод изменения приоритета
@router.message(StateFilter(FSMAdmin.input_priority_change))
async def input_new_value_for_priority(message: Message, state: FSMContext):
    await message.delete()
    await save_priority_changes(message.text, state)
    await open_all_rating_settings(message, state)


# Сохранить изменения
@router.callback_query(F.data == 'admin_save_new_change_priority')
async def save_new_change_priority(callback: CallbackQuery, state: FSMContext):
    await apply_priority_changes(state)
    await initial_priority_settings(state)
    await callback.answer(admin_panel['priority_changes'], show_alert=True)
    await open_all_rating_settings(callback, state)


# Открытие интерфейса с изменениями рейтинга
async def open_all_rating_settings(obj: CallbackQuery | Message, state: FSMContext):
    await bot.edit_message_text(chat_id=obj.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await rating_change_text(state),
                                reply_markup=await priority_change_keyboard(state))


# Открытие штрафов за невыполнение правил сервиса
@router.callback_query(F.data == 'admin_setting_rule_fines')
async def open_setting_rule_fines(callback: CallbackQuery, state: FSMContext):
    await initial_awards_cut(state)
    await open_rule_fines(callback, state)


@router.callback_query(F.data == 'admin_back_to_rule_fines')
async def process__back_to_rule_fine(callback: CallbackQuery, state: FSMContext):
    await open_rule_fines(callback, state)


# Открытие первого пореза-штрафа
@router.callback_query(F.data == 'admin_rule_fines_change_first_fine')
async def process_change_first_fine(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(admin_panel['input_value'],
                                     reply_markup=back_to_rule_fines_keyboard())
    await state.set_state(FSMAdmin.input_first_fine)


# Ввод новой суммы первого штрафа
@router.message(StateFilter(FSMAdmin.input_first_fine))
async def process_save_first_fine(message: Message, state: FSMContext):
    await message.delete()
    await save_first_fine(message.text, state)
    await open_rule_fines(message, state)


# Открытие второго пореза-штрафа
@router.callback_query(F.data == 'admin_rule_fines_change_subsequent_fines')
async def process_change_subsequent_fines(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(admin_panel['input_value'],
                                     reply_markup=back_to_rule_fines_keyboard())
    await state.set_state(FSMAdmin.input_subsequent_fines)


# Ввод новой суммы второго штрафа
@router.message(StateFilter(FSMAdmin.input_subsequent_fines))
async def process_save_first_fine(message: Message, state: FSMContext):
    await message.delete()
    await save_subsequent_fines(message.text, state)
    await open_rule_fines(message, state)


# Потверждение изменений в штрафах
@router.callback_query(F.data == 'admin_conifrm_rule_fines')
async def conifrm_rule_fine(callback: CallbackQuery, state: FSMContext):
    await apply_rule_fines(state)
    await initial_awards_cut(state)
    await open_rule_fines(callback, state)


# Открыть штрафы на порез
async def open_rule_fines(obj: CallbackQuery | Message, state: FSMContext):
    await bot.edit_message_text(chat_id=obj.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await rule_fines_text(state),
                                reply_markup=await awards_cut_keyboard(state))


# Открыть максимальное понижение рейтинга
@router.callback_query((F.data == 'admin_setting_raiting_fines') | (F.data == 'back_to_setting_raiting_fines'))
async def process_fines_on_priority(callback: CallbackQuery):
    await callback.message.edit_text(await setting_raiting_fines(),
                                     reply_markup=setting_raiting_fines_keyboard())


# Изменить макс. понижение рейтинга
@router.callback_query(F.data == 'admin_change_raiting_fines')
async def process_change_raiting_fines(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(admin_panel['new_raiting_fines'],
                                     reply_markup=back_to_raiting_fines_keyboard())
    await state.set_state(FSMAdmin.input_fines_prority)


# Ввод нового штрафа
@router.message(StateFilter(FSMAdmin.input_fines_prority))
async def change_raitin_fines(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(fines_raiting=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_admin_message(state),
                                text=confirm_raitin_fines_text(message.text),
                                reply_markup=coinfirm_raiting_fines_keyboard())


# Сохранить новый штраф на постоянное понижение
@router.callback_query(F.data == 'admin_coinfirm_raiting_fines')
async def coinfirm_raiting_fines(callback: CallbackQuery, state: FSMContext):
    await save_new_raiting_fines(state)
    await process_fines_on_priority(callback)


# Открыть меню со штрафом за частое удаление заданий
@router.callback_query((F.data == 'admin_setting_task_fines') | (F.data == 'back_to_task_fines'))
async def open_task_fines(callback: CallbackQuery):
    await callback.message.edit_text(await task_fines_text(),
                                     reply_markup=task_fines_keyboard())


# Смена процента штрафа
@router.callback_query(F.data == 'admin_change_percent_task_fines')
async def process_change_percent_task(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(admin_panel['new_task_fines'],
                                     reply_markup=change_task_fines_keyboard())
    await state.set_state(FSMAdmin.input_task_fines)


# Указать новый процент штрафа
@router.message(StateFilter(FSMAdmin.input_task_fines))
async def change_percent_fines_task(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(percent_task_fines=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_admin_message(state),
                                text=coinfirm_task_fines_text(message.text),
                                reply_markup=coinfirm_percent_fines_keyboard())


# Подтвердить новый штраф за частое удаление тасков
@router.callback_query(F.data == 'admin_coinfirm_task_fines')
async def coinfirm_percent_fines_task(callback: CallbackQuery, state: FSMContext):
    await save_new_task_fine_percent(state)
    await open_task_fines(callback)


# Открытие меню с информацией об уровнях
@router.callback_query((F.data == 'admin_setting_work_with_levels') | (F.data == 'back_to_work_with_levels'))
async def open_work_with_levels(callback: CallbackQuery):
    await callback.message.edit_text(await work_with_levels_text(),
                                     reply_markup=work_with_levels_keyboard())


# Открытие лимитов уровней
@router.callback_query((F.data == 'admin_open_levels_limits') | (F.data == 'back_to_levels_limits'))
async def process_open_levels_limits(callback: CallbackQuery):
    await callback.message.edit_text(await limits_levels_text(),
                                     reply_markup=await levels_limits_keyboard())


# Изменение лимитов какого-то уровня
@router.callback_query(F.data.startswith('admin_open_limits_level_') | (F.data == 'back_to_limits_level'))
async def process_open_limits_level(callback: CallbackQuery, state: FSMContext):
    level = await save_change_level(callback, state)
    await callback.message.edit_text(await change_level_limits(level),
                                     reply_markup=change_limits_keyboard(level))
    await state.set_state(FSMAdmin.neutral_state)


# Админ выбрал изменить лимиты кол-во заданий
@router.callback_query(F.data.startswith("admin_change_limit_tasks_") | (F.data.startswith('admin_change_limit_accounts_')))
async def process_change_limit_tasks(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(admin_panel['input_value'],
                                     reply_markup=back_to_limits_keyboard())
    await state.set_state(get_need_state_for_change_limits(callback))


# Изменить лимиты тасков на аккаунт в день
@router.message(StateFilter(FSMAdmin.input_level_limits_tasks))
async def change_level_limits_tasks(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(change_tasks_day=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await confirm_change_limits_tasks_text(state),
                                reply_markup=confirm_change_limits_tasks_keyboard())


# Подтверждение изменения лимитов тасков в день
@router.callback_query(F.data == 'admin_coinfirm_changes_for_limits_tasks')
async def change_limits_tasks(callback: CallbackQuery, state: FSMContext):
    await change_limits_level_tasks(state)
    await callback.answer(admin_panel['changes_for_limits_tasks_on_day'])
    await process_open_levels_limits(callback)


# Изменить кол-во аккаунтов на задание
@router.message(StateFilter(FSMAdmin.input_level_limits_accounts))
async def change_level_limits_accounts(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(change_accs_on_task=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await confirm_change_limits_accounts_text(state),
                                reply_markup=confirm_change_limits_accounts_keyboard())


# Подтверждение изменения лимитов тасков в день
@router.callback_query(F.data == 'admin_coinfirm_changes_for_limits_accounts')
async def change_limits_tasks(callback: CallbackQuery, state: FSMContext):
    await change_limits_level_accounts(state)
    await callback.answer(admin_panel['changes_for_limits_accounts_on_day'])
    await process_open_levels_limits(callback)


# Открытие лимитов уровней для их получения
@router.callback_query((F.data == 'admin_open_receiving_limits') | (F.data == 'back_to_open_receiving_limits'))
async def change_receiving_limits(callback: CallbackQuery):
    await callback.message.edit_text(await receiving_limits_text(),
                                     reply_markup=receiving_limits_kebyboard())


# Открытие лимитов для получения какого-то уровня
@router.callback_query((F.data.startswith('admin_change_receiving_limits_')) | (F.data == 'back_to_change_receiving_limits'))
async def change_level_receiving_limits(callback: CallbackQuery, state: FSMContext):
    await save_level_for_receiving_limits(callback, state)
    await callback.message.edit_text(await change_receiving_limits_text(state),
                                     reply_markup=level_receiving_limits_kebyboard())


# Изменить какой-то параметер для получения уровня
@router.callback_query((F.data == 'admin_change_need_tasks_for_level') | (F.data == 'admin_change_need_active_accounts_for_level'))
async def change_needs_for_up_level(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(admin_panel['input_value'],
                                     reply_markup=back_to_receiving_limits_keyboard())
    await state.set_state(get_need_state_for_change_receiving_limits(callback))


# Ввод нового необходимого кол-ва тасков для получения уровня
@router.message(StateFilter(FSMAdmin.input_need_for_level_tasks))
async def coinfirm_change_need_tasks_for_up_level(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(need_tasks_for_level=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await confirm_change_need_tasks_text(state),
                                reply_markup=confirm_change_need_tasks_keyboard())


# Ввод нового необходимого кол-ва активных аккаунтов для получения уровня
@router.message(StateFilter(FSMAdmin.input_need_for_level_accounts))
async def coinfirm_change_need_active_accs_for_up_level(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(need_active_accs_for_level=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await confirm_change_need_active_accs_text(state),
                                reply_markup=confirm_change_need_active_accs_keyboard())


# Подтверждение изменения кол-ва выполненных тасков для получения уровня
@router.callback_query(F.data == 'admin_confirm_change_need_tasks')
async def coinfirm_change_need_tasks(callback: CallbackQuery, state: FSMContext):
    await change_tasks_receiving_limits(state)
    await callback.answer(admin_panel['change_need_tasks_for_level'])
    await change_receiving_limits(callback)


# Подтверждение изменения кол-ва активных аккаунтов для получения уровня
@router.callback_query(F.data == 'admin_confirm_change_need_active_accs')
async def coinfirm_change_need_tasks(callback: CallbackQuery, state: FSMContext):
    await change_active_accs_receiving_limits(state)
    await callback.answer(admin_panel['change_need_avtive_accs_for_level'])
    await change_receiving_limits(callback)


# Редактирование списка админов
@router.callback_query((F.data == 'admin_setting_edit_admin_list') | (F.data == 'back_to_admin_list'), ItisMainAdmin())
async def process_edit_admin_list(callback: CallbackQuery):
    await callback.message.edit_text(await admins_list_text(),
                                     reply_markup=edit_admin_list_keboard())


# Добавление нового админуса
@router.callback_query(F.data == 'admin_adding_admin')
async def process_adding_admin(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(admin_panel['new_admin'],
                                     reply_markup=back_to_admin_list_button())
    await state.set_state(FSMAdmin.input_new_admin)


# Ввод нового админа
@router.message(StateFilter(FSMAdmin.input_new_admin))
async def process_adding_new_admin(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(new_admin=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await conifrm_new_admin_text(state),
                                reply_markup=coinfirm_adding_admin_keyboard())


# Подтверждение добавления нового админа
@router.callback_query(F.data == 'admin_coinfirm_to_adding_admin')
async def coinfirm_new_admin(callback: CallbackQuery, state: FSMContext):
    await adding_new_admin(state)
    await callback.answer(admin_panel['new_admin_notification'])
    await process_edit_admin_list(callback)


# Удаление админа
@router.callback_query(F.data == 'admin_remove_admin')
async def process_remove_admin(callback: CallbackQuery):
    await callback.message.edit_text(admin_panel['remove_admin'],
                                     reply_markup=await remove_admin_keyboard())


# Выбор админа для удаления
@router.callback_query(F.data.startswith("admin_remove_to_admin_"))
async def process_select_admin_for_remove(callback: CallbackQuery, state: FSMContext):
    await state.update_data(remove_admin=int(callback.data[22:]))
    await callback.message.edit_text(await coinifrn_remove_admin(state),
                                     reply_markup=coinfirm_remove_admin_keyboard())


# Подтверждение удаления админа
@router.callback_query(F.data == 'admin_coinfirm_to_remove_admin')
async def process_coinfirm_remove_admin(callback: CallbackQuery, state: FSMContext):
    await remove_admin_from_db(state)
    await callback.answer(admin_panel['remove_admin_notification'])
    await process_edit_admin_list(callback)


# Открыть список саппортом
@router.callback_query((F.data == 'admin_setting_edit_support_list') | (F.data == 'back_edit_support_list'))
async def process_open_support_list(callback: CallbackQuery):
    await callback.message.edit_text(await supports_list_text(),
                                     reply_markup=supports_list_keyboard())


# Добавить нового саппорта
@router.callback_query(F.data == 'admin_add_support')
async def process_admin_add_support(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(admin_panel['new_supports'],
                                     reply_markup=back_button_to_support_list())
    await state.set_state(FSMAdmin.input_new_support)


# Ввод нового саппорта
@router.message(StateFilter(FSMAdmin.input_new_support))
async def process_add_new_support(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(new_support=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_admin_message(state),
                                text=await coinfirm_add_support_text(state),
                                reply_markup=coinfirm_support_keyboard())


# Подтверждение добавления нового саппорта
@router.callback_query(F.data == 'admin_coinfirm_adding_support')
async def process_coinfirm_add_support(callback: CallbackQuery, state: FSMContext):
    await add_new_support(state)
    await callback.answer(admin_panel['support_adding'])
    await process_open_support_list(callback)


# Удалить саппорта
@router.callback_query(F.data == 'admin_remove_support')
async def process_remove_support(callback: CallbackQuery):
    await callback.message.edit_text(admin_panel['remove_support'],
                                     reply_markup=await remove_support_keyboard())


# Выбрать саппорта для удаления
@router.callback_query(F.data.startswith("admin_remove_support_"))
async def select_support_for_remove(callback: CallbackQuery, state: FSMContext):
    await state.update_data(remove_support=int(callback.data[21:]))
    await callback.message.edit_text(await coinfirm_remove_support_text(state),
                                     reply_markup=coinfirm_remove_support_keyboard())


# Потдверждение удаления саппорта
@router.callback_query(F.data == 'admin_coinfirm_remove_support')
async def process_coinirm_remove_support(callback: CallbackQuery, state: FSMContext):
    await remove_supporn_from_db(state)
    await callback.answer(admin_panel['remove_support_notification'])
    await process_open_support_list(callback)


# Назначение саппорта по умолчанию
@router.callback_query(F.data == 'admin_assign_default_support')
async def process_assign_default_support(callback: CallbackQuery):
    await callback.message.edit_text(admin_panel['assign_default_support'],
                                     reply_markup=await defalut_support_keyboard())


# Назначение нового сапорта
@router.callback_query(F.data.startswith("admin_assign_default_support_"))
async def new_default_support(callback: CallbackQuery):
    await db.select_default_support(int(callback.data[29:]))
    await callback.answer(admin_panel['selected_default_support'])
    await process_open_support_list(callback)


# Закрытие админом меню админа
@router.callback_query(F.data == 'admin_close_menu')
async def process_close_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FSMAdmin.neutral_state)
    await callback.message.delete()
