import time

from aiogram import Router, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Text, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot_apps.FSM.FSM_states import FSMAddTask
from bot_apps.adding_task.adding_task_filters import is_correct_profile_link, is_correct_post_link, \
    is_correct_words_or_tags, is_correct_note
from bot_apps.adding_task.adding_task_keyboards import select_actions_builder, setup_all_components_builder, \
    back_button_to_setting_task_builder, comment_parameters_builder, comment_criteria_builder, \
    select_minimum_parameters_builder, back_to_checking_comment_builder, add_note_in_comment_builder, \
    do_you_really_want_to_leave_builder, add_number_user_builder, final_add_task_builder, add_task_keyboad_builder, \
    not_money_keyboard_builder, not_payments_builder
from bot_apps.adding_task.adding_task_text import task_setting_text_builder, \
    text_under_comment_parameters_builder, text_under_adding_one_parameter_builder, define_price, final_text_builder, \
    no_money_text_builder
from bot_apps.databases.database import db
from bot_apps.other_apps.main_menu.main_menu_functions import delete_old_interface
from bot_apps.wordbank import add_task
from config.config import load_config

# Обозначение нужных классов
router = Router()
config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")


# Пользователь решил добавить новое задание
@router.callback_query(Text(text=['add_task']))
async def add_new_task(callback: CallbackQuery, state: FSMContext):
    # Задаются все нужные объекты
    await state.set_state(FSMAddTask.add_task)
    await state.update_data(setting_actions=[])  # Список, содержащий действия, которые нужны пользователю
    await state.update_data(accepted={'profile_link': False, 'post_link': False, 'comment_parameters': {}})  # Словарь для сохранения ссылок и настроек пользователя
    # Проверка на то, что пользователь переходит из уведомления о завершении задания (в этом случае необходимо менять основной интерфейс)
    if await db.get_main_interface(callback.from_user.id) != callback.message.message_id:
        message_id = await callback.message.answer(add_task['start_text'], reply_markup=await select_actions_builder())
        # Удаление старого сообщения с интерфейсом бота и запись в бд о новом сообщении
        await delete_old_interface(message_id, callback.from_user.id, bot, callback.message.message_id)
    else:
        await callback.message.edit_text(add_task['start_text'],
                                         reply_markup=await select_actions_builder())


# Пользователь выбрал одно из действий, либо перешёл обратно к выбору действий
@router.callback_query(lambda x: x.data.startswith('add_new_'), StateFilter(FSMAddTask.add_task))
async def user_select_action(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    # Если ключ уже есть в списке, то убираем его
    if callback.data[8:] in data['setting_actions']:
        data['setting_actions'].remove(callback.data[8:])
    else:
        data['setting_actions'].append(callback.data[8:])
    await callback.message.edit_text(add_task['start_text'],
                                     reply_markup=await select_actions_builder(data.get('setting_actions')))


# Пользователь вернулся к выбору действий
@router.callback_query(Text(text=['back_to_setting_task']))
async def user_back_select_action(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(add_task['start_text'],
                                     reply_markup=await select_actions_builder(data.get('setting_actions')))


# Пользователь выбрал нужные ему действия и открыл страницу настроек
@router.callback_query(Text(text=['accept_settings_task', 'back_accept_setting_task']))
async def open_page_settings(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FSMAddTask.add_task)
    data = await state.get_data()
    # Если пользователь не выбрал ни одно действие
    if not data['setting_actions']:
        await callback.answer(add_task['not_select_setting'], show_alert=True)
    # Если пользователь выбрал действия
    else:
        await callback.message.edit_text(await task_setting_text_builder(data.get('setting_actions'), data.get('accepted')), disable_web_page_preview=True,
                                         reply_markup=await setup_all_components_builder(data.get('setting_actions'), data.get('accepted')))


# Пользователь задаёт один из параметров
@router.callback_query(lambda x: x.data.startswith('add_in_task_'))
async def user_sets_preferences(callback: CallbackQuery, state: FSMContext):
    # Пользователь задаёт ссылку на профиль
    if callback.data[12:] == 'profile_link':
        await state.set_state(FSMAddTask.add_profile_link)
        await callback.message.edit_text(add_task['add_link_profile'], disable_web_page_preview=True,
                                         reply_markup=await back_button_to_setting_task_builder())
    # Пользователь задаёт ссылку на пост
    elif callback.data[12:] == 'post_link':
        await state.set_state(FSMAddTask.add_post_link)
        await callback.message.edit_text(add_task['add_link_post'],
                                         reply_markup=await back_button_to_setting_task_builder())
    # Пользователь задаёт параметры комментария
    else:
        data = await state.get_data()
        await callback.message.edit_text(await text_under_comment_parameters_builder(data['accepted']['comment_parameters']),
                                         reply_markup=await comment_parameters_builder(data.get('accepted')))


# Пользователь вводит ссылку на аккаунт/юзернейм
@router.message(StateFilter(FSMAddTask.add_profile_link))
async def insert_link_profile(message: Message, state: FSMContext):
    await message.delete()
    data = await state.get_data()
    is_correct = await is_correct_profile_link(message.text)
    # Пользователь ввёл неправильные данные и вернулся текст ошибки, а не введённый аккаунт
    if len(is_correct.split()) != 1:
        # Защита от ошибки изменения сообщения на тот же самый текст
        try:
            await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                        chat_id=message.chat.id,
                                        text=is_correct.format(message.text),
                                        reply_markup=await back_button_to_setting_task_builder())
        except TelegramBadRequest:
            pass
    # Пользователь ввёл верные данные
    else:
        await state.set_state(FSMAddTask.add_task)
        data['accepted']['profile_link'] = is_correct
        await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                    chat_id=message.chat.id,
                                    text=await task_setting_text_builder(data.get('setting_actions'), data.get('accepted')), disable_web_page_preview=True,
                                    reply_markup=await setup_all_components_builder(
                data.get('setting_actions'), data.get('accepted')))


# Пользователь вводит ссылку на пост
@router.message(StateFilter(FSMAddTask.add_post_link))
async def insert_post_link(message: Message, state: FSMContext):
    await message.delete()
    data = await state.get_data()
    is_correct = await is_correct_post_link(message.text)
    # Если пользователь ввёл некорректную ссылку
    if not is_correct:
        # Защита от ошибки изменения сообщения на тот же самый текст
        try:
            await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                        chat_id=message.chat.id,
                                        text=add_task['not_correct_link_post'].format(message.text if message.text else ''),
                                        reply_markup=await back_button_to_setting_task_builder())
        except TelegramBadRequest:
            pass
    # Если пользователь ввёл корректную ссылку
    else:
        await state.set_state(FSMAddTask.add_task)
        data['accepted']['post_link'] = message.text.lower()
        await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                    chat_id=message.chat.id,
                                    text=await task_setting_text_builder(data.get('setting_actions'),
                                                                         data.get('accepted')),
                                    disable_web_page_preview=True,
                                    reply_markup=await setup_all_components_builder(data.get('setting_actions'), data.get('accepted')))


# Пользователь вернулся в главное меню настройки комментариев
@router.callback_query(Text(text=['back_to_comment_parameters']))
async def back_to_comment_parameters(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(await text_under_comment_parameters_builder(data['accepted']['comment_parameters']),
                                     reply_markup=await comment_parameters_builder(data.get('accepted')))
    await state.set_state(FSMAddTask.add_task)


# Пользователь переходит в меню для добавления критерия проверки комментария
@router.callback_query(Text(text=['add_checking_comment', 'back_to_checking_comment']))
async def open_add_checking_comment(callback: CallbackQuery, state: FSMContext):
    # Если пользователь вернулся во время того, как задать какой-нибудь параметр
    data = await state.get_data()
    if callback.data != 'add_checking_comment':
        await state.set_state(FSMAddTask.add_task)
    # Предварительно создаём словарь с выбором одного из значений для проверки комментария
    if 'one_value' not in data['accepted']['comment_parameters']:
        data['accepted']['comment_parameters']['one_value'] = {}
    await callback.message.edit_text(text=await text_under_adding_one_parameter_builder(data['accepted']['comment_parameters']['one_value']),
                                     reply_markup=await comment_criteria_builder(data.get('accepted')))


# Пользователь решил выбрать количество слов в комментарии
async def add_many_words_parameter(callback: CallbackQuery):
    await callback.message.edit_text(add_task['add_minimum_words'],
                                     reply_markup=await select_minimum_parameters_builder())


# Пользователь решил выбрать количество тэгов в комментарии
async def add_many_tags_parameter(callback: CallbackQuery):
    await callback.message.edit_text(add_task['add_minimum_tags'],
                                     reply_markup=await select_minimum_parameters_builder('tags'))


# Пользователь решил написать ключевые слова и тэги по которым будет проходить проверка комментария
async def add_key_tags_and_words(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FSMAddTask.add_comment_parameters)
    await callback.message.edit_text(add_task['add_tags/words'],
                                     reply_markup=await back_to_checking_comment_builder())


# Переключатель для открытия выбора одной из 3 ключевых настроек комментария для его проверки
@router.callback_query(lambda x: x.data.startswith('add_in_comment_'))
async def add_parameter_in_comment(callback: CallbackQuery, state: FSMContext):
    setting = callback.data[15:]
    # Пользователь хочет указать количество слов
    if setting == 'number_words':
        await add_many_words_parameter(callback)
    # Пользователь хочет указать количество тэгов
    elif setting == 'number_tags':
        await add_many_tags_parameter(callback)
    # Пользователь хочет указать ключевые слова и тэги
    else:
        await add_key_tags_and_words(callback, state)


# Пользователь выбирает минимальное количество слов или тэгов
@router.callback_query(lambda x: x.data.startswith('minimum_words_') or x.data.startswith('minimum_tags_'))
async def add_minimum_value(callback: CallbackQuery, state: FSMContext):
    value = callback.data.replace('minimum_words_', '').replace('minimum_tags_', '')
    data = await state.get_data()
    # Обновление минимального количества слов
    if callback.data.startswith('minimum_words_'):
        data['accepted']['comment_parameters']['one_value'] = {'words': value, 'tags': False, 'tags/words': False}
        await back_to_comment_parameters(callback, state)
    # Обновление минимального количества тэгов
    else:
        data['accepted']['comment_parameters']['one_value'] = {'words': False, 'tags': value, 'tags/words': False}
        await back_to_comment_parameters(callback, state)


# Пользователь вводит ключевые слова/теги
@router.message(StateFilter(FSMAddTask.add_comment_parameters))
async def add_key_word(message: Message, state: FSMContext):
    await message.delete()
    data = await state.get_data()
    is_correct = await is_correct_words_or_tags(message.text, True if data['accepted']['comment_parameters'].get('only_english', None) else False)
    # Если функция вернула не словарь с тегами и наборами слов, а текст с ошибкой
    if isinstance(is_correct, str):
        # Защита от ошибки изменения сообщения на тот же самый текст
        try:
            await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                        chat_id=message.chat.id,
                                        text=is_correct, reply_markup=await back_to_checking_comment_builder())
        except TelegramBadRequest:
            pass
    else:
        data['accepted']['comment_parameters']['one_value'] = {'words': False, 'tags': False, 'tags/words': is_correct}
        await state.set_state(FSMAddTask.add_task)
        await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                    chat_id=message.chat.id,
                                    text=await text_under_comment_parameters_builder(data['accepted']['comment_parameters']),
                                    reply_markup=await comment_parameters_builder(data.get('accepted')))


# Пользователь убирает все заданные ключевые параметры
@router.callback_query(Text(text=['delete_comment_key_parameters']))
async def delete_comment_parameters(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    data['accepted']['comment_parameters']['one_value'] = {}
    await callback.message.edit_text(
        text=await text_under_adding_one_parameter_builder(data['accepted']['comment_parameters']['one_value']),
        reply_markup=await comment_criteria_builder(data.get('accepted')))


# Пользователь добавляет примечание к комментарию
@router.callback_query(Text(text=['add_note']))
async def add_note_in_comment(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FSMAddTask.add_note)
    data = await state.get_data()
    await callback.message.edit_text(add_task['add_note'],
                                     reply_markup=await add_note_in_comment_builder(data.get('accepted')))


# Пользователь ввёл примечание к комментарию
@router.message(StateFilter(FSMAddTask.add_note))
async def insert_note_in_comment(message: Message, state: FSMContext):
    await message.delete()
    data = await state.get_data()
    is_correct = await is_correct_note(message.text)
    # Если вернулось сообщение с текстом ошибки
    if isinstance(is_correct, str):
        # Защита от ошибки изменения сообщения на тот же самый текст
        try:
            await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                        chat_id=message.chat.id,
                                        text=is_correct, reply_markup=await add_note_in_comment_builder(data.get('accepted')))
        except TelegramBadRequest:
            pass
    # Если вернулся словарь с заполненными ключевыми словами/тегами
    else:
        await state.set_state(FSMAddTask.add_task)
        data['accepted']['comment_parameters']['note'] = is_correct['correct_note']
        await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                    chat_id=message.chat.id,
                                    text=await text_under_comment_parameters_builder(data['accepted']['comment_parameters']),
                                    reply_markup=await comment_parameters_builder(data.get('accepted')))


# Пользователь решил удалить добавленное примечание к комментарию
@router.callback_query(Text(text=['delete_note']))
async def delete_adding_note(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.set_state(FSMAddTask.add_task)
    data['accepted']['comment_parameters'].pop('note')
    await callback.message.edit_text(await text_under_comment_parameters_builder(data['accepted']['comment_parameters']),
                                     reply_markup=await comment_parameters_builder(data.get('accepted')))


# Пользователь решил включить только "английский язык"
@router.callback_query(Text(text=['only_english']))
async def change_only_english(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if 'only_english' not in data['accepted']['comment_parameters'] or not data['accepted']['comment_parameters']['only_english']:
        # Проверка на то, если пользователь добавлял ранее проверку для комментария, нет ли там русских букв
        # Вывести в отдельную проверку
        if 'one_value' in data['accepted']['comment_parameters'] and data['accepted']['comment_parameters']['one_value'].get('tags/words', None):
            for i in ''.join(data['accepted']['comment_parameters']['one_value']['tags/words']['words'] + data['accepted']['comment_parameters']['one_value']['tags/words']['tags']):
                if i.lower() in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя':
                    await callback.answer(add_task['not_only_english'], show_alert=True)
                    return
        data['accepted']['comment_parameters']['only_english'] = True
        await callback.answer(add_task['on_only_english'])

    else:
        data['accepted']['comment_parameters']['only_english'] = False
        await callback.answer(add_task['off_only_english'])

    await callback.message.edit_text(await text_under_comment_parameters_builder(data['accepted']['comment_parameters']),
                                     reply_markup=await comment_parameters_builder(data.get('accepted')))


# Пользователь решил выйти из меню настройки заданий, но уже задал какие-то настройки
@router.callback_query(Text(text=['exactly_to_back_main_menu']))
async def exactly_back_to_main_menu(callback: CallbackQuery):
    await callback.message.edit_text(text=add_task['you_really_leave'],
                                     reply_markup=await do_you_really_want_to_leave_builder())


# Пользователь указал все нужные ему настройки для своих заданий и нажимает "продолжить"
@router.callback_query(Text(text=['accept_all_settings', 'back_accept_all_setting']))
async def accept_all_settings(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    balance = await db.check_payment(callback.from_user.id)
    # Если пользователь ни разу не пополнял свой аккаунт
    if not balance:
        await state.update_data(text=add_task['first_pay'].format(await define_price(data), await define_price(data, 50)))
        await callback.message.edit_text(add_task['first_pay'].format(await define_price(data), await define_price(data, 50)),
                                         reply_markup=await not_payments_builder())

    # Если баланса пользователя не хватит на оплату минимального количества выполнений
    elif balance - await define_price(data, 5) < 0:
        text = await no_money_text_builder(data, balance)
        await state.update_data(text=text)
        await callback.message.edit_text(text=text, reply_markup=await not_money_keyboard_builder())

    # Если баланса пользователя хватает на оплату минимального количества выполнений
    else:
        balance = int(balance) if balance.is_integer() else round(balance, 2)
        await state.set_state(FSMAddTask.add_quantity_users)
        await state.update_data(text=add_task['add_number_users'].format(await define_price(data), balance))
        await callback.message.edit_text(add_task['add_number_users'].format(await define_price(data), balance),
                                         reply_markup=await add_number_user_builder(balance, data))


# Пользователь вводит количество тех, кто должен выполнить задание
@router.message(StateFilter(FSMAddTask.add_quantity_users))
@router.callback_query(lambda x: x.data.startswith('choice_execute_'))
async def insert_number_users(message_from_user: Message | CallbackQuery, state: FSMContext):
    data = await state.get_data()
    # Если пользователь ввёл число
    try:
        # Функция работает как с сообщениями, так и с колбеками (ввод минимального и максимального количества выполнений)
        # Заставил функцию работать с 2 типами сообщений, т.к. логика всё равно у хендлера одна и делить её на 2 разных хендлера, мне показалось не очень удобным
        if isinstance(message_from_user, Message):
            await message_from_user.delete()
            telegram_id = message_from_user.from_user.id
            chat_id = message_from_user.chat.id
            number_users = int(message_from_user.text)
        else:
            telegram_id = message_from_user.from_user.id
            chat_id = message_from_user.message.chat.id
            number_users = int(message_from_user.data[15:])

        data['number_users'] = number_users
        balance = await db.check_balance(telegram_id)
        balance = int(balance) if balance.is_integer() else round(balance, 2)
        need = await define_price(data, number_users)
        prices = await final_text_builder(data)
        # Если пользователь ввёл менее 5 выполнений
        if number_users < 5:
            await bot.edit_message_text(message_id=await db.get_main_interface(telegram_id),
                                        chat_id=chat_id,
                                        text=add_task['fail_add_number_users'],
                                        reply_markup=await add_number_user_builder(balance, data))
        # Если баланса не хватает для оплаты задания
        elif balance < need:
            await bot.edit_message_text(message_id=await db.get_main_interface(telegram_id),
                                        chat_id=chat_id,
                                        text=await no_money_text_builder(data, balance, balance_flag=True),
                                        reply_markup=await not_money_keyboard_builder(balance_flag=True))
        # Если баланса хватает на оплату задания и всё ок
        else:
            await bot.edit_message_text(message_id=await db.get_main_interface(telegram_id),
                                        chat_id=chat_id,
                                        text=add_task['final_confirmation'].format(need, balance, prices),
                                        reply_markup=await final_add_task_builder())
            await state.update_data(number_users=number_users)
            await state.set_state(FSMAddTask.add_task)

    # Если пользователь ввёл не число
    except ValueError or TypeError:
        # Защита от ошибки изменения сообщения на тот же самый текст
        try:
            await bot.edit_message_text(message_id=await db.get_main_interface(telegram_id),
                                        chat_id=chat_id,
                                        text=data.get('text') + '\n\n<code>Упс, кажется, ты ввёл не число</code>',
                                        reply_markup=await add_number_user_builder(await db.check_balance(telegram_id), data))
        except TelegramBadRequest:
            pass


# # Пользователь добавил новое задание
@router.callback_query(Text(text=['add_finally_task']))
async def add_finally_task(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    # Проверка баланса перед тем, как добавить задание (чтоб юзер с нескольких интерфейсов не открыл меню добавления задания и не добавил сразу их несколько
    balance = await db.check_balance(int(callback.from_user.id))
    need = await define_price(data, data['number_users'])
    if balance < need:
        await callback.message.edit_text(add_task['fail_add_task'].format(round(balance, 2), round(need - balance, 2)),
                                         reply_markup=await not_money_keyboard_builder(balance_flag=True))
    else:
        await db.add_new_task(int(callback.from_user.id),
                              float(await define_price(data, data['number_users'])),
                              await define_price(data),
                              data['number_users'],
                              data['setting_actions'],
                              data['accepted'])
        # Добавление всех необходимых данных для создания таска в базе данных
        await callback.message.edit_text(add_task['add_task'].format(f"{data.get('number_users')}/{data.get('number_users')}"),
                                         reply_markup=await add_task_keyboad_builder())
