from aiogram import Router, Bot, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot_apps.FSM.FSM_states import FSMPersonalTask
from bot_apps.filters.ban_filters.is_banned import IsBanned
from bot_apps.personal_task.adding_task.adding_task_handlers import open_page_settings
from bot_apps.personal_task.adding_task.adding_task_text import define_price
from bot_apps.personal_task.personal_task_functions import find_page, get_task_id, check_increase_executions, \
    inirial_task_id, update_state, check_balance_sufficiency, get_sum_penalty, get_sum_refund_with_penalty, \
    duplicate_task_settings, find_history_page, inirial_history_task_id, get_histoy_task_id
from bot_apps.personal_task.personal_task_keyboards import personal_tasks_menu_keyboard, active_task_keyboard, \
    noneactive_task_keyboard, increased_executions_keyboard, add_new_executions_keyboard, \
    warning_before_deletion_keyboard, delete_task_keyboard, del_task_keyboard, editing_duplication_keyboard, \
    active_tasks_menu_keyboard, history_tasks_menu_keyboard, history_task_keyboard, \
    del_task_from_history
from bot_apps.personal_task.personal_task_text import personal_tasks_menu_text, active_tasks_menu_text, \
    active_task_text, increased_executions_text, not_balance_for_increased_executions, add_new_executions_text, \
    prefix_not_enter_number, prefix_not_correct_number, insufficient_balance_for_executions, task_executions_updated, \
    delete_task_text, define_warning_text_before_deletion, delete_task_notification, delete_task_with_penalty, \
    history_tasks_menu_text, history_task_text, collect_fines_text
from bot_apps.wordbank import personal_task
from config import load_config
from databases.database import db, RemainingTaskBalance

router = Router()
config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")

router.callback_query.filter(IsBanned())
router.message.filter(IsBanned())


# Основное меню кабинета с тасками
@router.callback_query((F.data == 'personal_tasks') | (F.data == 'back_to_personal_tasks'))
async def open_personal_tasks(callback: CallbackQuery):
    await callback.message.edit_text(text=await personal_tasks_menu_text(callback.from_user.id),
                                     reply_markup=await personal_tasks_menu_keyboard(callback.from_user.id))


# Меню с активными тасками
@router.callback_query((F.data == 'active_tasks') | (F.data == 'back_to_active_tasks'))
async def open_active_tasks_menu(callback: CallbackQuery, state: FSMContext):
    page = await find_page(callback, state)
    await callback.message.edit_text(text=await active_tasks_menu_text(callback.from_user.id, page),
                                     reply_markup=await active_tasks_menu_keyboard(callback.from_user.id, page))
    await state.clear()


# Переход на другую страницу
@router.callback_query(F.data.startswith('active_task_page_'))
async def open_task_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[17:])
    await callback.message.edit_text(text=await active_tasks_menu_text(callback.from_user.id, page),
                                     reply_markup=await active_tasks_menu_keyboard(callback.from_user.id, page))
    await state.update_data(active_tasks_page=page)


# Пользователь открыл один из активных тасков
@router.callback_query(F.data.startswith('open_active_task_') | (F.data == 'back_to_active_task'))
async def open_active_task(callback: CallbackQuery, state: FSMContext):
    task_id = await inirial_task_id(callback, state)
    await callback.message.edit_text(text=await active_task_text(task_id),
                                     reply_markup=active_task_keyboard(),
                                     disable_web_page_preview=True)


# Увеличить кол-во выполнений таска
@router.callback_query((F.data == 'increased_executions') | (F.data == 'back_to_increased_executions'))
async def increased_executions_on_task(callback: CallbackQuery, state: FSMContext):
    task_id = await get_task_id(state)
    if await check_increase_executions(callback.from_user.id, task_id):  # Проверка на то, что баланса юзера хватит на минималку
        await callback.answer(text=await not_balance_for_increased_executions(callback.from_user.id, task_id), show_alert=True)
    elif await db.check_unfinished_task(task_id):  # Проверка на то, что задание всё ещё активно
        await callback.message.edit_text(text=personal_task['now_increased_executions'],
                                         reply_markup=noneactive_task_keyboard())
    else:  # Если всё ок
        await callback.message.edit_text(text=await increased_executions_text(task_id),
                                         reply_markup=await increased_executions_keyboard(
                                             callback.from_user.id, task_id))
        await state.set_state(FSMPersonalTask.add_executions)


# Пользователь указал кол-во дополнительных выполнений через кнопку
@router.callback_query(F.data.startswith('add_new_executions_'))
async def add_new_executions_via_button(callback: CallbackQuery, state: FSMContext):
    task_id = await get_task_id(state)
    add_executions = int(callback.data[19:])
    if not await check_balance_sufficiency(task_id, add_executions):
        await callback.answer(personal_task['not_correct_executions'])
    else:
        await add_new_executions(callback.from_user.id, task_id, add_executions)


# Пользователь указал кол-во дополнительных выполнений в виде сообщения
@router.message(StateFilter(FSMPersonalTask.add_executions))
async def add_new_executions_via_message(message: Message, state: FSMContext):
    await message.delete()
    task_id = await get_task_id(state)
    if message.text.isdigit():  # Если цифры
        if not await check_balance_sufficiency(task_id, message.text):
            await not_correct_executions(message, task_id)
        else:
            await add_new_executions(message.from_user.id, task_id, int(message.text))
            await update_state(state)
    else:
        await bot.edit_message_text(  # Если не цифры
            chat_id=message.from_user.id,
            message_id=await db.get_main_interface(message.from_user.id),
            text=await prefix_not_enter_number(task_id),
            reply_markup=await increased_executions_keyboard(message.from_user.id, task_id))


# Пользователь указал больше выполнений, чем ему позволяет его баланс
async def not_correct_executions(message: Message, task_id: int):
    await bot.edit_message_text(
        chat_id=message.from_user.id,
        message_id=await db.get_main_interface(message.from_user.id),
        text=await prefix_not_correct_number(task_id),
        reply_markup=await increased_executions_keyboard(message.from_user.id, task_id))


# Обновление выполнений
async def add_new_executions(tg_id: int, task_id: int, add_executions: int):
    await bot.edit_message_text(chat_id=tg_id,
                                message_id=await db.get_main_interface(tg_id),
                                text=await add_new_executions_text(
                                    tg_id=tg_id, task_id=task_id, add_executions=add_executions),
                                reply_markup=add_new_executions_keyboard(add_executions))


# Обновление кол-ва выполнений
@router.callback_query(F.data.startswith('update_executions_'))
async def update_executions_active_task(callback: CallbackQuery, state: FSMContext):
    task_id = await get_task_id(state)
    executions = int(callback.data[18:])
    if not await check_balance_sufficiency(task_id, executions):
        await callback.answer(await insufficient_balance_for_executions(
            callback.from_user.id, task_id, executions), show_alert=True)
    else:
        await db.update_task_executions(
            task_id, executions, await define_price(await db.get_actions_list(task_id), executions))
        await callback.answer(await task_executions_updated(
            callback.from_user.id, executions), show_alert=True)
        await open_active_task(callback, state)


# Удаление задания
@router.callback_query((F.data == 'delete_task') | (F.data == 'continue_delete_task'))
async def delete_active_task(callback: CallbackQuery, state: FSMContext):
    task_id = await get_task_id(state)
    if callback.data == 'delete_task' and await db.check_quantity_delete_task(callback.from_user.id, task_id):
        await callback.message.edit_text(personal_task['warnings']['delete_task_warning_4'],
                                         reply_markup=warning_before_deletion_keyboard())
    else:
        await callback.message.edit_text(await define_warning_text_before_deletion(callback, task_id),
                                         reply_markup=delete_task_keyboard())


# Окончательное удаление задания
@router.callback_query((F.data == 'delete_active_task_button'))
async def confirmation_delete_active_task(callback: CallbackQuery, state: FSMContext):
    task_id = await get_task_id(state)
    task_info: RemainingTaskBalance = await db.get_remaining_task_balance(task_id)
    if task_info.status == 'waiting_start':
        await callback.message.edit_text(await delete_task_notification(task_id), reply_markup=await del_task_keyboard(callback.from_user.id, task_id))
        sum_refund = await db.check_balance_task(task_id)
        # await db.del_task_from_db(task_id)
    else:
        await db.change_task_status_to_deleted(task_id)
        if await db.check_quantity_delete_task(callback.from_user.id, task_id, 3):  # Если уже 3 и более тасков рано удалено
            sum_refund = await get_sum_refund_with_penalty(task_id)
            # Хз, надо ли раздавать подобным образом или это всё будет через сообщение со сбором
            # await db.distribution_some_awards(task_id, await get_sum_penalty(task_id))  # Раздача штрафа воркерсам
            await db.penalty_for_frequent_deletion(task_id, await get_sum_penalty(task_id))  # Запись о штрафе
            await callback.message.edit_text(text=await delete_task_with_penalty(task_id), reply_markup=await del_task_keyboard(callback.from_user.id, task_id))
        else:
            sum_refund = await db.check_remaining_task_balance(task_id)
            await callback.message.edit_text(text=await delete_task_text(task_id), reply_markup=await del_task_keyboard(callback.from_user.id, task_id))
        # Запуск функции, удаляющей таск у воркеров
    await db.change_task_status_to_deleted(task_id)
    await db.return_some_balanc_from_task(task_id, sum_refund)
    await db.record_of_refund(task_id, sum_refund)


    # Меню дублирования задания
@router.callback_query(F.data == 'editing_duplication')
async def editing_duplication_menu(callback: CallbackQuery):
    await callback.message.edit_text(personal_task['editing_duplication_menu'],
                                     reply_markup=editing_duplication_keyboard())


# Дублирование задания
@router.callback_query((F.data == 'dublication_active_task') | F.data == 'dublication_history_task')
async def dublication_task(callback: CallbackQuery, state: FSMContext):
    task_id = await get_task_id(state) if callback.data == 'dublication_active_task' else await get_histoy_task_id(state)
    await state.update_data(await duplicate_task_settings(task_id))
    await open_page_settings(callback, state)


# Открытие истории заданий
@router.callback_query((F.data == 'history_tasks') | (F.data == 'back_to_history_tasks'))
async def open_history_tasks(callback: CallbackQuery, state: FSMContext):
    page = await find_history_page(callback, state)
    await callback.message.edit_text(await history_tasks_menu_text(callback.from_user.id, page),
                                     reply_markup=await history_tasks_menu_keyboard(callback.from_user.id, page),
                                     disable_web_page_preview=True)


# Открытие какое-то страницы в истории
@router.callback_query(F.data.startswith('history_task_page_'))
async def open_page_history_tasks(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[18:])
    await callback.message.edit_text(text=await history_tasks_menu_text(callback.from_user.id, page),
                                     reply_markup=await history_tasks_menu_keyboard(callback.from_user.id, page),
                                     disable_web_page_preview=True)
    await state.update_data(history_tasks_page=page)


# Открытие задания в истории
@router.callback_query((F.data.startswith('open_history_task_')) | (F.data == 'back_to_history_task'))
async def open_task_in_history(callback: CallbackQuery, state: FSMContext):
    task_id = await inirial_history_task_id(callback, state)
    await callback.message.edit_text(text=await history_task_text(task_id),
                                     reply_markup=history_task_keyboard(),
                                     disable_web_page_preview=True)


# Пользователь собирается удалить задание из истории
@router.callback_query(F.data == 'delete_task_from_history')
async def delete_task_from_history(callback: CallbackQuery):
    await callback.message.edit_text(personal_task['check_want_del_task'],
                                     reply_markup=del_task_from_history())


# Пользователь подтвердил удаление задания из истории
@router.callback_query(F.data == 'task_deletion_confirmation')
async def task_deletion_confirmation(callback: CallbackQuery, state: FSMContext):
    task_id = await get_histoy_task_id(state)
    await db.del_task_from_history(task_id)
    await callback.answer(personal_task['delete_task_from_history'])
    await open_history_tasks(callback, state)


# Собрать штрафы
@router.callback_query(F.data.startswith('collect_fines_'))
async def process_collection_fines(callback: CallbackQuery):
    sum_fines: float = await db.collection_fines(int(callback.data[14:]))
    await callback.answer(collect_fines_text(sum_fines), show_alert=True)
    await callback.message.delete()
