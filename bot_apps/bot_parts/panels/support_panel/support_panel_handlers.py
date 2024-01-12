from aiogram import Router, Bot, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot_apps.bot_parts.panels.admin_panel.admin_panel_functions import get_users_list_from_state, apply_sorting, \
    get_user_sorting_options, find_users_page, open_another_users_list, sorted_users_list_for_time, change_user_balance, \
    change_user_priority, get_tg_id, add_priority_fines, add_stb_fines, get_sent_tasks, get_users_task, \
    sorted_user_accounts, get_user_accounts, get_user_fines, get_user_paymnets, del_fines_id, save_all_tasks, \
    set_initial_options, tasks_sorting, open_other_tasks_list, save_sort_time_task, sorted_task_by_time, \
    save_task_all_info, task_distribution, task_safely_delete, task_add_executions, change_return_flag, \
    task_reduse_executions, save_workers, sorted_task_workers, task_force_delete
from bot_apps.bot_parts.panels.admin_panel.admin_panel_middlewares import UserInDatabase, TaskInDatabase, TaskIsActive
from bot_apps.bot_parts.panels.admin_panel.admin_panel_send_messages import send_message_to_user_from_bot
from bot_apps.bot_parts.panels.admin_panel.admin_panel_text import all_user_info_text, user_tasks_text, \
    all_task_info_text, \
    confirm_safely_delete_text, task_force_delete_text, confirm_force_delete_text, \
    show_workers_text, notification_for_reduce_executions
from bot_apps.bot_parts.panels.support_panel.support_panel_functions import change_active_status, \
    change_default_support, \
    save_users_list, sup_initial_users_page, get_support_message, accept_task
from bot_apps.bot_parts.panels.support_panel.support_panel_keyboards import main_menu_keyboard, sup_users_work_keyboard, \
    sup_sorted_users_menu_keboard, sup_all_info_user_keyboard, sup_back_user_button, \
    sup_coinfirm_change_user_balance_keyboard, sup_coinfirm_change_user_priority_keybaord, \
    sup_change_user_level_keyboard, sup_adding_fines_user_keyboard, sup_confirm_user_message_keyboard, \
    sup_sent_tasks_keyboard, sup_user_tasks_keyboard, sup_user_acounts_keyboard, sup_user_fines_keyboard, \
    sup_user_payments_keyboard, sup_user_remove_fines_keboard, sup_all_tasks_sorting_keyboard, sup_all_tasks_keyboard, \
    sup_all_task_info_keyboard, sup_button_to_task_keyboard, sup_confirm_task_distribution_keyboard, \
    sup_safely_delete_keyboard, sup_force_delete_keyboard, sup_confirm_add_executions_keyboard, \
    sup_reduce_executions_keyboard, sup_confirm_reduse_executions_keboard, sup_show_workers_keyboard, \
    sup_accept_task_id_for_accept, back_to_tasks_user_list
from bot_apps.bot_parts.panels.support_panel.support_panel_middlewares import SupportMidelware, TaskIsNotCompleted
from bot_apps.bot_parts.panels.support_panel.support_panel_text import main_menu_text, change_status_text, \
    change_default_support_text, sup_users_menu_text, sup_get_user_text_dict, sup_coinfirm_change_user_balance_text, \
    sup_change_user_priority_text, sup_priority_fines_text, sup_stb_fines_text, sup_message_from_bot_text, \
    sup_confirm_user_message_text, sup_sent_tasks_user_text, sup_user_tasks_text, sup_user_account_text, \
    sup_user_fines_text, sup_user_payments_text, sup_user_remove_fines_text, sup_all_tasks_text, \
    sup_dop_task_distribution_text, sup_confirm_dop_task_distribution_text, sup_safely_delete_task_text, \
    sup_task_add_executions_text, sup_confirm_add_executions_text, sup_reduce_executions_text, \
    sup_confirm_eduse_executions_text, sup_accept_task_for_accept
from bot_apps.other_apps.FSM.FSM_states import FSMSupport
from bot_apps.other_apps.filters.ban_filters.is_banned import IsBanned
from bot_apps.other_apps.wordbank import support_panel, admin_panel
from config import load_config
from databases.database import Database
from databases.dataclasses_storage import UsersList, SentTasksInfo, UserAccount, UserFines, UserPayments, UserAllInfo, \
    UserTasksInfo

router = Router()
config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
db = Database()
is_banned = IsBanned()


# Открытие панели саппорта
@router.message(Command(commands='support'), SupportMidelware())
async def open_support_panel(message: Message, state: FSMContext):
    message_id = await message.answer(await main_menu_text(message.from_user.id),
                                      reply_markup=await main_menu_keyboard(message.from_user.id))
    await message.delete()
    await state.update_data(support_id=message.from_user.id)
    await state.update_data(support_message=message_id.message_id)


# Вернуться в панель саппорта
@router.callback_query(F.data == 'back_to_support_panel', SupportMidelware())
async def process_back_support_panel(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FSMSupport.neutral_state)
    await callback.message.edit_text(await main_menu_text(callback.from_user.id),
                                     reply_markup=await main_menu_keyboard(callback.from_user.id))


# Уйти на отдых саппорту | стать активным
@router.callback_query((F.data == "support_stopped_working") | (F.data == 'support_start_work'), SupportMidelware())
async def process_change_active_status(callback: CallbackQuery, state: FSMContext):
    await change_active_status(callback)
    await callback.answer(change_status_text(callback))
    await process_back_support_panel(callback, state)


# Стать саппортом по умолчанию | Перестать быть саппортом по умолчанию
@router.callback_query((F.data == 'support_defaulted_support') | (F.data == 'support_lifted_defaulted_support'), SupportMidelware())
async def process_change_default_support(callback: CallbackQuery, state: FSMContext):
    await change_default_support(callback)
    change_default_support_text(callback)
    await process_back_support_panel(callback, state)


# Открыть список юзеров
async def all_list_users(callback: CallbackQuery, state: FSMContext, page: int = 1):
    await state.set_state(FSMSupport.input_user)
    users_list: list[UsersList] = await get_users_list_from_state(state)
    await callback.message.edit_text(sup_users_menu_text(users_list, page),
                                     reply_markup=sup_users_work_keyboard(users_list, page))


# Саппорт зашёл в меню работы с юзерами
@router.callback_query(F.data == 'support_open_users_work', SupportMidelware())
async def process_open_all_users(callback: CallbackQuery, state: FSMContext):
    await save_users_list(state)
    await state.set_state(FSMSupport.input_user)
    await all_list_users(callback, state)


# Сбросить сортировку
@router.callback_query(F.data == 'support_reset_sorting_users_list', SupportMidelware())
async def process_sorting_user(callback: CallbackQuery, state: FSMContext):
    await apply_sorting(callback, state, reset=True)
    await callback.answer(support_panel['sorting_reset'])
    await all_list_users(callback, state)


# Вернуться в список юзеров
@router.callback_query(F.data == 'support_back_to_users_work', SupportMidelware())
async def back_to_user_work(callback: CallbackQuery, state: FSMContext):
    page = await find_users_page(callback, state)
    await state.set_state(FSMSupport.input_user)
    await all_list_users(callback, state, page)


# Открыть другую страницу с юзерами
@router.callback_query((F.data.startswith('support_work_page_')) | (F.data == 'support_back_to_users_work_pages'), SupportMidelware())
async def open_users_work_page(callback: CallbackQuery, state: FSMContext):
    page = await sup_initial_users_page(callback, state)
    await all_list_users(callback, state, page)


# Саппорт зашёл в сортировку
@router.callback_query(F.data == 'support_sorting_users_list', SupportMidelware())
async def process_sorted_users(callback: CallbackQuery, state: FSMContext):
    await get_user_sorting_options(state)
    await callback.message.edit_text(support_panel['soretd_text'],
                                     reply_markup=await sup_sorted_users_menu_keboard(state))


# Отсортировать список юзеров
@router.callback_query(F.data.startswith('sup_sorted_users_'), SupportMidelware())
async def process_apply_sorting_users_list(callback: CallbackQuery, state: FSMContext):
    await apply_sorting(callback, state)
    await callback.answer(admin_panel['new_sorting'])
    await all_list_users(callback, state)


# Открыть забаненных или других юзеров
@router.callback_query(F.data.startswith('supus_open_users_list_'), SupportMidelware())
async def process_open_users_list_(callback: CallbackQuery, state: FSMContext):
    await open_another_users_list(callback, state)
    await callback.answer(admin_panel['new_list_users'])
    await all_list_users(callback, state)


# Отсечь по времени других юзеров
@router.callback_query(F.data.startswith('supus_sorted_users_for_'), SupportMidelware())
async def sorted_users_for_time(callback: CallbackQuery, state: FSMContext):
    await sorted_users_list_for_time(callback, state)
    await callback.answer(admin_panel['new_sorting'])
    await all_list_users(callback, state)


# Открытие информации о юзере
@router.message(StateFilter(FSMSupport.input_user), UserInDatabase(), SupportMidelware())
async def open_all_info_about_user(message: Message, state: FSMContext, tg_id: int):
    await message.delete()
    await state.update_data(tg_id=tg_id)
    user_info: UserAllInfo = await db.get_all_info_for_user(tg_id)
    await state.update_data(user_info=user_info)
    await bot.edit_message_text(message_id=await get_support_message(state),
                                chat_id=message.chat.id,
                                text=await all_user_info_text(state),
                                reply_markup=await sup_all_info_user_keyboard(state))


# Вернутся к какому-то пользователю
@router.callback_query(F.data == 'support_back_to_user_info', SupportMidelware())
async def back_open_all_info_about_user(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text=await all_user_info_text(state),
                                     reply_markup=await sup_all_info_user_keyboard(state))
    await state.set_state(FSMSupport.input_user)


# Открытие меню с юзером после каких-то изменений
async def open_all_user_info_after_message(obj: Message | CallbackQuery, state: FSMContext):
    await state.set_state(FSMSupport.input_user)
    await bot.edit_message_text(chat_id=obj.from_user.id,
                                message_id=await get_support_message(state),
                                text=await all_user_info_text(state),
                                reply_markup=await sup_all_info_user_keyboard(state))


# Изменение баланса юзера
@router.callback_query(F.data == 'support_for_user_change_balance', SupportMidelware())
async def user_change_balance(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text=await sup_get_user_text_dict('change_balance', state),
                                     reply_markup=sup_back_user_button())
    await state.set_state(FSMSupport.input_user_balance)


# Ввод нового баланса
@router.message(StateFilter(FSMSupport.input_user_balance), SupportMidelware())
async def process_input_user_balance(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(new_balance=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_support_message(state),
                                text=await sup_coinfirm_change_user_balance_text(state),
                                reply_markup=sup_coinfirm_change_user_balance_keyboard())


# Подтверждение ввода баланса
@router.callback_query(F.data == 'support_coinfirm_change_user_balance', SupportMidelware())
async def coinfirm_change_user_balance(callback: CallbackQuery, state: FSMContext):
    await change_user_balance(state)
    await callback.answer(admin_panel['user_balance_changes'])
    await open_all_user_info_after_message(callback, state)


# Изменения приоритета пользвателя
@router.callback_query(F.data == 'support_for_user_change_priority', SupportMidelware())
async def user_change_priority(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text=await sup_get_user_text_dict('change_priority', state),
                                     reply_markup=sup_back_user_button())
    await state.set_state(FSMSupport.input_user_priority)


# Ввод нового приоритета юзера
@router.message(StateFilter(FSMSupport.input_user_priority), SupportMidelware())
async def process_input_user_priority(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(new_priority=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_support_message(state),
                                text=await sup_change_user_priority_text(state),
                                reply_markup=sup_coinfirm_change_user_priority_keybaord())


# Подтверждение изменения приоритета
@router.callback_query(F.data == 'support_coinfirm_user_priority', SupportMidelware())
async def coinifrm_change_priority(callback: CallbackQuery, state: FSMContext):
    await change_user_priority(state)
    await callback.answer(admin_panel['user_priority_changes'])
    await open_all_user_info_after_message(callback, state)


# Изменение уровня пользователя
@router.callback_query(F.data == 'support_for_user_change_level', SupportMidelware())
async def change_user_level(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await sup_get_user_text_dict('change_level', state),
                                     reply_markup=sup_change_user_level_keyboard())


# Ввод нового уровня для пользователя
@router.callback_query(F.data.startswith('supus_for_user_change_level_'), SupportMidelware())
async def process_change_user_level(callback: CallbackQuery, state: FSMContext):
    await db.change_user_level(await get_tg_id(state), callback.data[28:])
    await open_all_user_info_after_message(callback, state)


# Добавить штраф для юзера
@router.callback_query(F.data == 'support_for_user_adding_fines', SupportMidelware())
async def adding_new_fines_user(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await sup_get_user_text_dict('adding_fines', state),
                                     reply_markup=sup_adding_fines_user_keyboard())


# Выбор штрафа на приоритет
@router.callback_query(F.data == 'support_for_user_adding_fines_priority', SupportMidelware())
async def process_ading_fines_prioryty(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await sup_priority_fines_text(state),
                                     reply_markup=sup_back_user_button())
    await state.set_state(FSMSupport.input_fines_priority)


# Указание понижение приоритета юзера
@router.message(StateFilter(FSMSupport.input_fines_priority), SupportMidelware())
async def process_adding_fines_on_priority(message: Message, state: FSMContext):
    await message.delete()
    await add_priority_fines(state, message.text)
    await open_all_user_info_after_message(message, state)


# Выбор штрафа на сбор STB
@router.callback_query(F.data == 'support_for_user_adding_fines_stb', SupportMidelware())
async def process_adding_fines_on_stb(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await sup_stb_fines_text(state),
                                     reply_markup=sup_back_user_button())
    await state.set_state(FSMSupport.input_fines_stb)


# Указать сколько будем взимать с юзера
@router.message(StateFilter(FSMSupport.input_fines_stb), SupportMidelware())
async def process_adding_fines_on_stb(message: Message, state: FSMContext):
    await message.delete()
    await add_stb_fines(state, message.text)
    await open_all_user_info_after_message(message, state)


# Отправить сообщение от имени бота
@router.callback_query(F.data == 'support_for_user_message_from_bot', SupportMidelware())
async def new_message_to_user(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await sup_message_from_bot_text(state),
                                     reply_markup=sup_back_user_button())
    await state.set_state(FSMSupport.input_message_from_bot)


# Указать сообщение для юзера
@router.message(StateFilter(FSMSupport.input_message_from_bot), SupportMidelware())
async def process_new_message_user(message: Message, state: FSMContext):
    await message.delete()
    await bot.edit_message_text(chat_id=message.chat.id,
                                message_id=await get_support_message(state),
                                text=await sup_confirm_user_message_text(state, message.text),
                                reply_markup=sup_confirm_user_message_keyboard(),
                                disable_web_page_preview=True)
    await state.update_data(message_to_user_from_bot=message.text)


# Подтверждение указанного сообщения
@router.callback_query(F.data == 'support_for_user_confirm_message', SupportMidelware())
async def process_message_answer(callback: CallbackQuery, state: FSMContext):
    await send_message_to_user_from_bot(state)
    await open_all_user_info_after_message(callback, state)


# Забанить юзера
@router.callback_query(F.data == 'support_ban_user', SupportMidelware())
async def process_ban_user(callback: CallbackQuery, state):
    await is_banned.adding_blocked_users(await get_tg_id(state), 'support_ban')
    await callback.answer(admin_panel['ban_user'])
    await open_all_user_info_after_message(callback, state)


# Разбанить юзера
@router.callback_query(F.data == 'support_unban_user', SupportMidelware())
async def process_unban_user(callback: CallbackQuery, state):
    await is_banned.del_blocked_users(await get_tg_id(state))
    await callback.answer(admin_panel['unban_user'])
    await open_all_user_info_after_message(callback, state)


# Показать историю отправленных заданий юзеру
@router.callback_query((F.data == 'support_for_user_tasks_sent_history') | (F.data == 'support_back_to_tasks_sent_history'), SupportMidelware())
async def process_open_sent_tasks(callback: CallbackQuery, state: FSMContext):
    tasks_info: list[SentTasksInfo] = await db.get_info_about_sent_tasks(callback.from_user.id)
    await state.update_data(tasks_info=tasks_info)
    await open_sent_tasks_to_user(callback, state)


# Открыть другую страницу с заданиями
@router.callback_query(F.data.startswith('supus_sent_tasks_user_page_'), SupportMidelware())
async def process_open_page_sent_tasks_user(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[27:])
    await open_sent_tasks_to_user(callback, state, page)


# Ввод задания, которое нужно засчитать
@router.callback_query(F.data == 'support_accept_execution', SupportMidelware())
async def support_accept_execution(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(support_panel['input_task_id_for_accept'],
                                     reply_markup=back_to_tasks_user_list())
    await state.set_state(FSMSupport.input_task_id_for_accept)


# Сапорт вводить задание для засчитывания
@router.message(StateFilter(FSMSupport.input_task_id_for_accept), TaskIsNotCompleted(), SupportMidelware())
async def support_input_task_id_for_accept(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(task_for_accept=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_support_message(state),
                                text=await sup_accept_task_for_accept(state),
                                reply_markup=sup_accept_task_id_for_accept())


# Подтверждение засчитывания этого таска
@router.callback_query(F.data == 'support_accept_task_id_for_accept', SupportMidelware())
async def support_accept_task_id_for_accept(callback: CallbackQuery, state: FSMContext):
    await accept_task(state)
    await callback.answer(support_panel['task_accepted'])
    await open_sent_tasks_to_user(callback, state)


# Открыть список с отправленными тасками юзеру
async def open_sent_tasks_to_user(callback: CallbackQuery, state: FSMContext, page=1):
    await state.set_state(FSMSupport.input_task_id)
    tasks_info: list[SentTasksInfo] = await get_sent_tasks(state)
    await bot.edit_message_text(chat_id=callback.from_user.id,
                                message_id=await get_support_message(state),
                                text=await sup_sent_tasks_user_text(state, tasks_info, page),
                                reply_markup=sup_sent_tasks_keyboard(tasks_info, page))


# Открыть личные задания юзера
@router.callback_query(F.data == 'support_for_user_task_personal_history', SupportMidelware())
async def process_open_user_tasks(callback: CallbackQuery, state: FSMContext):
    user_tasks: list[UserTasksInfo] = await db.get_info_abuot_user_tasks(callback.from_user.id)
    await callback.message.edit_text(await sup_user_tasks_text(state, user_tasks),
                                     reply_markup=sup_user_tasks_keyboard(user_tasks))
    await state.update_data(user_tasks=user_tasks)
    await state.set_state(FSMSupport.input_task_id)


# Открыть страницу с личными заданиями юзера
@router.callback_query(F.data.startswith('supus_user_tasks_page_'), SupportMidelware())
async def process_open_page_user_tasks(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[22:])
    user_tasks: list[UserTasksInfo] = await get_users_task(state)
    await callback.message.edit_text(await user_tasks_text(state, user_tasks, page),
                                     reply_markup=sup_user_tasks_keyboard(user_tasks, page))


# Открыть все аккаунты юзера
@router.callback_query(F.data == 'support_for_user_all_accounts', SupportMidelware())
async def open_user_accounts(callback: CallbackQuery, state: FSMContext):
    user_accounts: list[UserAccount] = await db.get_all_user_accounts(callback.from_user.id)
    await state.update_data(user_accounts=user_accounts)
    await state.set_state(FSMSupport.input_task_id)
    await open_list_user_accounts(callback, state)


# Открыть другую страницу со всеми аккаунтами
@router.callback_query((F.data == 'supus_for_user_active_accounts') | (F.data == 'supus_for_user_inactive_accounts') |
                       (F.data == 'supus_for_user_deleted_accounts'), SupportMidelware())
async def process_sorted_user_accounts(callback: CallbackQuery, state: FSMContext):
    user_accounts: list[UserAccount] = await sorted_user_accounts(callback)
    await state.update_data(user_accounts=user_accounts)
    await callback.answer(admin_panel['new_sorting'])
    await open_list_user_accounts(callback, state)


# Перейти на другую страницу в аккаунтах
@router.callback_query(F.data.startswith('supus_user_accounts_page_'), SupportMidelware())
async def process_open_user_accounts_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[25:])
    await open_list_user_accounts(callback, state, page)


# Открытие списка аккаунтов юзера
async def open_list_user_accounts(callback: CallbackQuery, state: FSMContext, page: int = 1):
    await state.set_state(FSMSupport.input_user)
    user_accounts: list[UserAccount] = await get_user_accounts(state)
    await callback.message.edit_text(await sup_user_account_text(state, user_accounts, page),
                                     reply_markup=sup_user_acounts_keyboard(user_accounts, page))


# Открыть список штрафов
@router.callback_query(F.data == 'support_for_user_fines_history', SupportMidelware())
async def open_all_user_fines(callback: CallbackQuery, state: FSMContext):
    user_fines: list[UserFines] = await db.get_all_fines_user(callback.from_user.id)
    await state.update_data(user_fines=user_fines)
    await open_user_fines_list(callback, state)


# Открыть другую страницу штрафов
@router.callback_query(F.data.startswith("supus_user_fines_page_"), SupportMidelware())
async def open_user_fine_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[22:])
    await open_user_fines_list(callback, state, page)


# Открыть только активные штрафы
@router.callback_query(F.data == 'support_for_user_active_fines', SupportMidelware())
async def open_active_fines_user(callback: CallbackQuery, state: FSMContext):
    user_fines: list[UserFines] = await db.get_only_active_fines_user(callback.from_user.id)
    await callback.answer(admin_panel['new_sorting'])
    await state.update_data(user_fines=user_fines)
    await open_user_fines_list(callback, state)


# Открыть список штрафов юзера
async def open_user_fines_list(callback: CallbackQuery, state: FSMContext, page: int = 1):
    user_fines: list[UserFines] = await get_user_fines(state)
    await callback.message.edit_text(await sup_user_fines_text(state, user_fines, page),
                                     reply_markup=sup_user_fines_keyboard(user_fines, page))


# Открыть пополнения юзера
@router.callback_query(F.data == 'support_for_user_payment_history', SupportMidelware())
async def open_all_user_payments(callback: CallbackQuery, state: FSMContext):
    user_payments: list[UserPayments] = await db.get_all_payments_user(callback.from_user.id)
    await callback.message.edit_text(await sup_user_payments_text(state, user_payments),
                                     reply_markup=sup_user_payments_keyboard(user_payments))
    await state.update_data(user_payments=user_payments)


# Открыть другую страницу с пополнениями юзера
@router.callback_query(F.data.startswith('supus_user_payments_page_'), SupportMidelware())
async def open_all_user_payments_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[25:])
    user_payments: list[UserPayments] = await get_user_paymnets(state)
    await callback.message.edit_text(await sup_user_payments_text(state, user_payments, page),
                                     reply_markup=sup_user_payments_keyboard(user_payments, page))


# Открыть меню для удаления каких-то штрафов юзера
@router.callback_query(F.data == 'support_for_user_remove_fines', SupportMidelware())
async def process_remove_user_fines(callback: CallbackQuery, state: FSMContext):
    user_fines: list[UserFines] = await db.get_only_active_fines_user(callback.from_user.id)
    await state.update_data(user_fines=user_fines)
    await state.set_state(FSMSupport.input_fines_id)
    await open_user_remove_fines_list(callback, state)


# Открыть другую страницу со штрафами для удаления
@router.callback_query(F.data.startswith('supus_user_remove_fines_page_'), SupportMidelware())
async def open_remove_user_fines_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[29:])
    await open_user_remove_fines_list(callback, state, page)


# Удалить какой-то штраф
@router.message(StateFilter(FSMSupport.input_fines_id), SupportMidelware())
async def remove_user_fines(message: Message, state: FSMContext):
    await message.delete()
    await del_fines_id(message)
    await open_user_remove_fines_list(message, state, dop_text=admin_panel['fines_remove'].format(message.text))


# Открыть список с активными штрафами для удаления
async def open_user_remove_fines_list(obj: CallbackQuery | Message, state: FSMContext, page: int = 1, dop_text: str = ''):
    user_fines: list[UserFines] = await get_user_fines(state)
    await bot.edit_message_text(chat_id=obj.from_user.id,
                                message_id=await get_support_message(state),
                                text=await sup_user_remove_fines_text(state, user_fines, page) + dop_text,
                                reply_markup=sup_user_remove_fines_keboard(user_fines, page))


# Расскрыть все задания пользователей
@router.callback_query(F.data == 'support_open_tasks_work', SupportMidelware())
async def open_all_tasks(callback: CallbackQuery, state: FSMContext):
    await save_all_tasks(state)
    await set_initial_options(state)
    await state.set_state(FSMSupport.input_task_id)
    await open_tasks_list(callback, state)


# Вернуться ко всем заданиям юзеров
@router.callback_query(F.data == 'support_back_to_all_tasks', SupportMidelware())
async def process_back_to_all_tasks(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FSMSupport.input_task_id)
    await open_tasks_list(callback, state)


# Обновить информацию
@router.callback_query(F.data == 'support_update_info_all_tasks', SupportMidelware())
async def process_update_all_tasks(callback: CallbackQuery, state: FSMContext):
    await callback.answer(admin_panel['update_data'])
    await save_all_tasks(state)
    await tasks_sorting(callback, state)
    await open_tasks_list(callback, state)


# Открыть другую страницу со всеми заданиями
@router.callback_query(F.data.startswith('supus_all_tasks_page_'), SupportMidelware())
async def open_all_tasks_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[21:])
    await state.update_data(tasks_list_page=page)
    await open_tasks_list(callback, state)


# Сбросить сортировку
@router.callback_query(F.data == 'support_reset_sorting_all_tasks', SupportMidelware())
async def reset_sortins_all_tasks(callback: CallbackQuery, state: FSMContext):
    await tasks_sorting(callback, state, reset=True)
    await callback.answer(admin_panel['reset_sorting'])
    await open_tasks_list(callback, state)


# Открыть сортировку
@router.callback_query(F.data == 'support_sorting_all_tasks', SupportMidelware())
async def process_sorting_all_tasks(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(admin_panel['soretd_text'],
                                     reply_markup=await sup_all_tasks_sorting_keyboard(state))


# Отсортировать по какому-то значению
@router.callback_query(F.data.startswith('supus_sort_tasks_'), SupportMidelware())
async def sort_all_tasks(callback: CallbackQuery, state: FSMContext):
    await tasks_sorting(callback, state)
    await callback.answer(admin_panel['new_sorting'])
    await open_tasks_list(callback, state)


# Открыть список каких-то тасков (активных, завершённых)
@router.callback_query(F.data.startswith('supus_open_tasks_list_'), SupportMidelware())
async def process_open_other_tasks_list(callback: CallbackQuery, state: FSMContext):
    await open_other_tasks_list(state, callback.data[22:])
    await open_tasks_list(callback, state)


# Отсортировать таски по времени
@router.callback_query(F.data.startswith("supus_sorted_tasks_for_"), SupportMidelware())
async def sort_task_for_time(callback: CallbackQuery, state: FSMContext):
    await save_sort_time_task(callback, state)
    await sorted_task_by_time(state)
    await open_tasks_list(callback, state)


# Открыть список с заданиями
async def open_tasks_list(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await sup_all_tasks_text(state),
                                     reply_markup=await sup_all_tasks_keyboard(state))


# Открыть какое-то задание
@router.message(StateFilter(FSMSupport.input_task_id), TaskInDatabase(), SupportMidelware())
async def process_open_all_task_info(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(task_id=int(message.text))
    await state.set_state(FSMSupport.input_task_id)
    await save_task_all_info(state)
    await open_all_task_info(message, state)


async def update_tasks_info(callback: CallbackQuery, state: FSMContext):
    await save_task_all_info(state)
    await open_all_task_info(callback, state)


# Вернуться к выбранному заданию
@router.callback_query(F.data == 'support_back_to_task', SupportMidelware())
async def process_back_to_task(callback: CallbackQuery, state: FSMContext):
    await open_all_task_info(callback, state)


# Обновить какое-то задание
@router.callback_query(F.data == 'support_task_update_info', SupportMidelware())
async def process_update_task_info(callback: CallbackQuery, state: FSMContext):
    await save_task_all_info(state)
    await open_all_task_info(callback, state)


# Отобрать ещё воркеров к какому-то заданию
@router.callback_query((F.data == 'supus_for_task_dop_task_distribution'), TaskIsActive(), SupportMidelware())
async def dop_task_distribution(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await sup_dop_task_distribution_text(state),
                                     reply_markup=sup_button_to_task_keyboard())
    await state.set_state(FSMSupport.input_dop_distribution)


# Распределение задания
@router.message(StateFilter(FSMSupport.input_dop_distribution), SupportMidelware())
async def process_task_distribution(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(task_distribution=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_support_message(state),
                                text=await sup_confirm_dop_task_distribution_text(state),
                                reply_markup=sup_confirm_task_distribution_keyboard())


# Подтвердить дополнительное распределние задания
@router.callback_query(F.data == 'support_confirm_task_distribution', TaskIsActive(), SupportMidelware())
async def process_confirm_task_distribution(callback: CallbackQuery, state: FSMContext):
    notification = await task_distribution(state)
    await callback.answer(notification, show_alert=True)
    await update_tasks_info(callback, state)


# Безопасно удалить задание
@router.callback_query(F.data == 'supus_for_task_safely_delete', TaskIsActive(), SupportMidelware())
async def proces_task_safely_delete(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await sup_safely_delete_task_text(state),
                                     reply_markup=sup_safely_delete_keyboard())


# Подтвердить безопасное удаление задания
@router.callback_query(F.data == 'support_confirm_task_safely_delete', TaskIsActive(), SupportMidelware())
async def process_task_safely_delete(callback: CallbackQuery, state: FSMContext):
    await callback.answer(await confirm_safely_delete_text(state), show_alert=True)
    await task_safely_delete(state)
    await update_tasks_info(callback, state)


# Удалить задание принудительно
@router.callback_query(F.data == 'supus_for_task_force_delete', TaskIsActive(), SupportMidelware())
async def process_task_force_delete(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await task_force_delete_text(state),
                                     reply_markup=sup_force_delete_keyboard())


# Подтверждение принудительного удаления
@router.callback_query(F.data == 'support_confirm_task_force_delete', TaskIsActive(), SupportMidelware())
async def process_task_force_delete(callback: CallbackQuery, state: FSMContext):
    await callback.answer(await confirm_force_delete_text(state), show_alert=True)
    await task_force_delete(state)
    await update_tasks_info(callback, state)


# Добавить выполнений к заданию
@router.callback_query(F.data == 'supus_for_task_add_executions', TaskIsActive(), SupportMidelware())
async def process_open_task_add_executions(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await sup_task_add_executions_text(state),
                                     reply_markup=sup_button_to_task_keyboard())
    await state.set_state(FSMSupport.input_add_executions)


# Ввод дополнительного кол-ва выполнений
@router.message(StateFilter(FSMSupport.input_add_executions), SupportMidelware())
async def process_open_task_add_executions(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(add_executions=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_support_message(state),
                                text=await sup_confirm_add_executions_text(message.text, state),
                                reply_markup=sup_confirm_add_executions_keyboard())


# Подтверждение дополнительного кол-ва выполнений
@router.callback_query(F.data == 'support_confirm_task_add_executions', TaskIsActive(), SupportMidelware())
async def confirm_task_add_executions(callback: CallbackQuery, state: FSMContext):
    notification = await task_add_executions(state)
    await callback.answer(notification, show_alert=True)
    await update_tasks_info(callback, state)


# Уменьшить кол-во выполнений
@router.callback_query(F.data == 'supus_for_task_reduce_executions', TaskIsActive(), SupportMidelware())
async def process_task_reduce_executions(callback: CallbackQuery, state: FSMContext):
    await state.update_data(return_stb=False)
    await callback.message.edit_text(await sup_reduce_executions_text(state),
                                     reply_markup=await sup_reduce_executions_keyboard(state))
    await state.set_state(FSMSupport.input_reduce_exections)


# Указание того, что нужно все выполнения снятые перевести автору
@router.callback_query(F.data == 'support_for_task_reduce_return_stb', SupportMidelware())
async def process_task_return_stb(callback: CallbackQuery, state: FSMContext):
    await change_return_flag(state)
    await callback.answer(await notification_for_reduce_executions(state))
    await callback.message.edit_text(await sup_reduce_executions_text(state),
                                     reply_markup=await sup_reduce_executions_keyboard(state))


# Ввод числа, на сколько нужно уменьшить кол-во выполнений
@router.message(StateFilter(FSMSupport.input_reduce_exections), SupportMidelware())
async def process_task_reduse_executions(message: Message, state: FSMContext):
    await message.delete()
    await state.update_data(reduse_executions=int(message.text))
    await bot.edit_message_text(chat_id=message.from_user.id,
                                message_id=await get_support_message(state),
                                text=await sup_confirm_eduse_executions_text(state),
                                reply_markup=sup_confirm_reduse_executions_keboard())


# Потдверждение уменьшения кол-ва выполнений
@router.callback_query(F.data == 'support_confirm_task_reduse_executions', TaskIsActive(), SupportMidelware())
async def confirn_task_reduse_executions(callback: CallbackQuery, state: FSMContext):
    notification = await task_reduse_executions(state)
    await callback.answer(notification, show_alert=True)
    await update_tasks_info(callback, state)


# Открыть всю информацию о задании
async def open_all_task_info(obj: CallbackQuery | Message, state: FSMContext):
    await state.set_state(FSMSupport.input_task_id)
    await bot.edit_message_text(chat_id=obj.from_user.id,
                                message_id=await get_support_message(state),
                                text=await all_task_info_text(state),
                                reply_markup=sup_all_task_info_keyboard(),
                                disable_web_page_preview=True)


# Открыть тех, кто делают задание
@router.callback_query((F.data == 'supus_for_task_show_workers') | (F.data == 'support_update_info_about_workers'), SupportMidelware())
async def open_show_workers_for_task(callback: CallbackQuery, state: FSMContext):
    await save_workers(state)
    await state.set_state(FSMSupport.input_user)
    await open_workers_list(callback, state)


# Перейти на другую страницу воркеров
@router.callback_query(F.data.startswith('supus_task_workers_page_'), SupportMidelware())
async def open_other_page_workers(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[24:])
    await open_workers_list(callback, state, page)


# Отфильтровать воркеров
@router.callback_query(F.data.startswith("supus_sorted_workers_"), SupportMidelware())
async def process_sorted_workers(callback: CallbackQuery, state: FSMContext):
    await sorted_task_workers(callback, state)
    await open_workers_list(callback, state)


# Открыть список воркеров
async def open_workers_list(callback: CallbackQuery, state: FSMContext, page: int = 1):
    await callback.message.edit_text(await show_workers_text(state, page),
                                     reply_markup=await sup_show_workers_keyboard(state, page))


# Закрытие меню саппорта
@router.callback_query(F.data == 'support_close_menu', SupportMidelware())
async def process_close_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FSMSupport.neutral_state)
    await callback.message.delete()
