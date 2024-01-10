from aiogram import Router, Bot, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot_apps.bot_parts.adding_task.adding_task_filters import is_correct_profile_link, is_correct_post_link, \
    is_correct_words_or_tags, is_correct_note
from bot_apps.bot_parts.adding_task.adding_task_keyboards import select_actions_builder, \
    setup_all_components_builder, \
    back_button_to_setting_task_builder, comment_parameters_builder, comment_criteria_builder, \
    select_minimum_parameters_builder, back_to_checking_comment_builder, add_note_in_comment_builder, \
    do_you_really_want_to_leave_builder, add_number_user_builder, final_add_task_builder, add_task_keyboad_builder, \
    not_money_keyboard_builder, not_payments_builder, not_existing_link_builder
from bot_apps.bot_parts.adding_task.adding_task_text import task_setting_text_builder, \
    text_under_comment_parameters_builder, text_under_adding_one_parameter_builder, define_price, final_text_builder, \
    no_money_text_builder, count_commission
from bot_apps.bot_parts.main_menu.main_menu_functions import delete_old_interface
from bot_apps.other_apps.FSM.FSM_states import FSMAddTask
from bot_apps.other_apps.filters.ban_filters.is_banned import IsBanned
from bot_apps.other_apps.systems_tasks.sending_tasks.start_task import start_tasks
from bot_apps.other_apps.wordbank import add_task
from config.config import load_config
from databases.database import Database

router = Router()
config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
db = Database()

router.callback_query.filter(IsBanned())
router.message.filter(IsBanned())


# Пользователь решил добавить новое задание
@router.callback_query(F.data == 'add_task')
async def add_new_task(callback: CallbackQuery, state: FSMContext):
    # Задаются все нужные объекты
    await state.set_state(FSMAddTask.add_task)
    await state.update_data(setting_actions=[])  # Список, содержащий действия, которые нужны пользователю
    await state.update_data(accepted={'profile_link': False, 'post_link': False, 'comment_parameters': {}})  # Словарь для сохранения ссылок и настроек пользователя
    # Проверка на то, что пользователь переходит из уведомления о завершении задания (в этом случае необходимо менять основной интерфейс)
    if await db.get_main_interface(callback.from_user.id) != callback.message.message_id:
        message_id = await callback.message.answer(add_task['start_text'], reply_markup=select_actions_builder())
        # Удаление старого сообщения с интерфейсом бота и запись в бд о новом сообщении
        await delete_old_interface(message_id, callback.from_user.id, bot, callback.message.message_id)
    else:
        await callback.message.edit_text(add_task['start_text'],
                                         reply_markup=select_actions_builder())


# Пользователь выбрал одно из действий, либо перешёл обратно к выбору действий
@router.callback_query(F.data.startswith('add_new_'), StateFilter(FSMAddTask.add_task))
async def user_select_action(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    # Если ключ уже есть в списке, то убираем его
    if callback.data[8:] in data['setting_actions']:
        data['setting_actions'].remove(callback.data[8:])
    else:
        data['setting_actions'].append(callback.data[8:])
    await callback.message.edit_text(add_task['start_text'],
                                     reply_markup=select_actions_builder(data.get('setting_actions')))


# Пользователь вернулся к выбору действий
@router.callback_query(F.data == 'back_to_setting_task')
async def user_back_select_action(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(add_task['start_text'],
                                     reply_markup=select_actions_builder(data.get('setting_actions')))


# Пользователь выбрал нужные ему действия и открыл страницу настроек
@router.callback_query((F.data == 'accept_settings_task') | (F.data == 'back_accept_setting_task'))
async def open_page_settings(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FSMAddTask.add_task)
    data = await state.get_data()
    # Если пользователь не выбрал ни одно действие
    if not data['setting_actions']:
        await callback.answer(add_task['not_select_setting'], show_alert=True)
    # Если пользователь выбрал действия
    else:
        await callback.message.edit_text(await task_setting_text_builder(data.get('setting_actions'), data.get('accepted')), disable_web_page_preview=True,
                                         reply_markup=setup_all_components_builder(data.get('setting_actions'), data.get('accepted')))


# Пользователь задаёт один из параметров
@router.callback_query(F.data.startswith('add_in_task_'))
async def user_sets_preferences(callback: CallbackQuery, state: FSMContext):
    # Пользователь задаёт ссылку на профиль
    if callback.data[12:] == 'profile_link':
        await state.set_state(FSMAddTask.add_profile_link)
        await callback.message.edit_text(add_task['add_link_profile'], disable_web_page_preview=True,
                                         reply_markup=back_button_to_setting_task_builder())
    # Пользователь задаёт ссылку на пост
    elif callback.data[12:] == 'post_link':
        await state.set_state(FSMAddTask.add_post_link)
        await callback.message.edit_text(add_task['add_link_post'],
                                         reply_markup=back_button_to_setting_task_builder())
    # Пользователь задаёт параметры комментария
    else:
        data = await state.get_data()
        await callback.message.edit_text(await text_under_comment_parameters_builder(data['accepted']['comment_parameters']),
                                         reply_markup=comment_parameters_builder(data.get('accepted')))


# Пользователь вводит ссылку на аккаунт/юзернейм
@router.message(StateFilter(FSMAddTask.add_profile_link))
async def insert_link_profile(message: Message, state: FSMContext):
    await message.delete()
    data = await state.get_data()
    is_correct = await is_correct_profile_link(message.text)
    # Пользователь ввёл неправильные данные и вернулся текст ошибки, а не введённый аккаунт
    if len(is_correct.split()) != 1:
        await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                    chat_id=message.chat.id,
                                    text=is_correct.format(message.text),
                                    reply_markup=back_button_to_setting_task_builder())
    # Пользователь ввёл верные данные
    else:
        await state.set_state(FSMAddTask.add_task)
        data['accepted']['profile_link'] = is_correct
        await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                    chat_id=message.chat.id,
                                    text=await task_setting_text_builder(data.get('setting_actions'), data.get('accepted')), disable_web_page_preview=True,
                                    reply_markup=setup_all_components_builder(
                data.get('setting_actions'), data.get('accepted')))


# Пользователь вводит ссылку на пост
@router.message(StateFilter(FSMAddTask.add_post_link))
async def insert_post_link(message: Message, state: FSMContext):
    await message.delete()
    data = await state.get_data()
    is_correct = await is_correct_post_link(message.text)
    # Если пользователь ввёл некорректную ссылку
    if not is_correct:
        await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                    chat_id=message.chat.id,
                                    text=add_task['not_correct_link_post'].format(message.text if message.text else ''),
                                    reply_markup=back_button_to_setting_task_builder())
    # Если пользователь ввёл корректную ссылку
    else:
        await state.set_state(FSMAddTask.add_task)
        link = message.text.lower()
        data['accepted']['post_link'], data['accepted']['profile_link'] = link, link[:message.text.find('/status/')]
        await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                    chat_id=message.chat.id,
                                    text=await task_setting_text_builder(data.get('setting_actions'),
                                                                         data.get('accepted')),
                                    disable_web_page_preview=True,
                                    reply_markup=setup_all_components_builder(data.get('setting_actions'), data.get('accepted')))


# Пользователь вернулся в главное меню настройки комментариев
@router.callback_query(F.data == 'back_to_comment_parameters')
async def back_to_comment_parameters(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(await text_under_comment_parameters_builder(data['accepted']['comment_parameters']),
                                     reply_markup=comment_parameters_builder(data.get('accepted')))
    await state.set_state(FSMAddTask.add_task)


# Пользователь переходит в меню для добавления критерия проверки комментария
@router.callback_query((F.data == 'add_checking_comment') | (F.data == 'back_to_checking_comment'))
async def open_add_checking_comment(callback: CallbackQuery, state: FSMContext):
    # Если пользователь вернулся во время того, как задать какой-нибудь параметр
    data = await state.get_data()
    if callback.data != 'add_checking_comment':
        await state.set_state(FSMAddTask.add_task)
    # Предварительно создаём словарь с выбором одного из значений для проверки комментария
    if 'one_value' not in data['accepted']['comment_parameters']:
        data['accepted']['comment_parameters']['one_value'] = {}
    await callback.message.edit_text(text=await text_under_adding_one_parameter_builder(data['accepted']['comment_parameters']['one_value']),
                                     reply_markup=comment_criteria_builder(data.get('accepted')))


# Пользователь решил выбрать количество слов в комментарии
async def add_many_words_parameter(callback: CallbackQuery):
    await callback.message.edit_text(add_task['add_minimum_words'],
                                     reply_markup=select_minimum_parameters_builder())


# Пользователь решил выбрать количество тэгов в комментарии
async def add_many_tags_parameter(callback: CallbackQuery):
    await callback.message.edit_text(add_task['add_minimum_tags'],
                                     reply_markup=select_minimum_parameters_builder('tags'))


# Пользователь решил написать ключевые слова и тэги по которым будет проходить проверка комментария
async def add_key_tags_and_words(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FSMAddTask.add_comment_parameters)
    await callback.message.edit_text(add_task['add_tags/words'],
                                     reply_markup=back_to_checking_comment_builder())


# Переключатель для открытия выбора одной из 3 ключевых настроек комментария для его проверки
@router.callback_query(F.data.startswith('add_in_comment_'))
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
@router.callback_query(F.data.startswith('minimum_words_') | F.data.startswith('minimum_tags_'))
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
        await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                    chat_id=message.chat.id,
                                    text=is_correct, reply_markup=back_to_checking_comment_builder())
    else:
        data['accepted']['comment_parameters']['one_value'] = {'words': False, 'tags': False, 'tags/words': is_correct}
        await state.set_state(FSMAddTask.add_task)
        await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                    chat_id=message.chat.id,
                                    text=await text_under_comment_parameters_builder(data['accepted']['comment_parameters']),
                                    reply_markup=comment_parameters_builder(data.get('accepted')))


# Пользователь убирает все заданные ключевые параметры
@router.callback_query(F.data == 'delete_comment_key_parameters')
async def delete_comment_parameters(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    data['accepted']['comment_parameters']['one_value'] = {}
    await callback.message.edit_text(
        text=await text_under_adding_one_parameter_builder(data['accepted']['comment_parameters']['one_value']),
        reply_markup=comment_criteria_builder(data.get('accepted')))


# Пользователь добавляет примечание к комментарию
@router.callback_query(F.data == 'add_note')
async def add_note_in_comment(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FSMAddTask.add_note)
    data = await state.get_data()
    await callback.message.edit_text(add_task['add_note'],
                                     reply_markup=add_note_in_comment_builder(data.get('accepted')))


# Пользователь ввёл примечание к комментарию
@router.message(StateFilter(FSMAddTask.add_note))
async def insert_note_in_comment(message: Message, state: FSMContext):
    await message.delete()
    data = await state.get_data()
    is_correct = await is_correct_note(message.text)
    # Если вернулось сообщение с текстом ошибки
    if isinstance(is_correct, str):
        await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                    chat_id=message.chat.id,
                                    text=is_correct, reply_markup=add_note_in_comment_builder(data.get('accepted')))
    # Если вернулся словарь с заполненными ключевыми словами/тегами
    else:
        await state.set_state(FSMAddTask.add_task)
        data['accepted']['comment_parameters']['note'] = is_correct['correct_note']
        await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                    chat_id=message.chat.id,
                                    text=await text_under_comment_parameters_builder(data['accepted']['comment_parameters']),
                                    reply_markup=comment_parameters_builder(data.get('accepted')))


# Пользователь решил удалить добавленное примечание к комментарию
@router.callback_query(F.data == 'delete_note')
async def delete_adding_note(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.set_state(FSMAddTask.add_task)
    data['accepted']['comment_parameters'].pop('note')
    await callback.message.edit_text(await text_under_comment_parameters_builder(data['accepted']['comment_parameters']),
                                     reply_markup=comment_parameters_builder(data.get('accepted')))


# Пользователь решил включить только "английский язык"
@router.callback_query(F.data == 'only_english')
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
                                     reply_markup=comment_parameters_builder(data.get('accepted')))


# Пользователь решил выйти из меню настройки заданий, но уже задал какие-то настройки
@router.callback_query(F.data == 'exactly_to_back_main_menu')
async def exactly_back_to_main_menu(callback: CallbackQuery):
    await callback.message.edit_text(text=add_task['you_really_leave'],
                                     reply_markup=do_you_really_want_to_leave_builder())


# Пользователь указал все нужные ему настройки для своих заданий и нажимает "продолжить"
@router.callback_query((F.data == 'accept_all_settings') | (F.data == 'back_accept_all_setting'))
async def accept_all_settings(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    balance = await db.check_payment(callback.from_user.id)
    # Если пользователь ни разу не пополнял свой аккаунт
    if not balance:
        await state.update_data(text=add_task['first_pay'].format(await define_price(data['setting_actions']), await define_price(data['setting_actions'], 50)))
        await callback.message.edit_text(add_task['first_pay'].format(await define_price(data['setting_actions']), await define_price(data['setting_actions'], 50)),
                                         reply_markup=not_payments_builder())

    # Если баланса пользователя не хватит на оплату минимального количества выполнений
    elif balance - await define_price(data['setting_actions'], 5) < 0:
        text = await no_money_text_builder(data, balance)
        await state.update_data(text=text)
        await callback.message.edit_text(text=text, reply_markup=not_money_keyboard_builder())

    # Если баланса пользователя хватает на оплату минимального количества выполнений
    else:
        await state.set_state(FSMAddTask.add_quantity_users)
        await state.update_data(text=add_task['add_number_users'].format(await define_price(data['setting_actions']), balance))
        await callback.message.edit_text(add_task['add_number_users'].format(await define_price(data['setting_actions']), balance),
                                         reply_markup=await add_number_user_builder(balance, data))


# Пользователь вводит количество тех, кто должен выполнить задание
@router.message(StateFilter(FSMAddTask.add_quantity_users))
@router.callback_query(F.data.startswith('choice_execute_'))
async def insert_number_users(message_from_user: Message | CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if isinstance(message_from_user, Message):
        await message_from_user.delete()
        telegram_id = message_from_user.from_user.id
        chat_id = message_from_user.chat.id
        number_users = message_from_user.text
    else:
        telegram_id = message_from_user.from_user.id
        chat_id = message_from_user.message.chat.id
        number_users = message_from_user.data[15:]
    if number_users.isdigit():
        number_users = int(number_users)
        data['number_users'] = number_users
        balance = await db.check_balance(telegram_id)
        need = await define_price(data['setting_actions'], number_users)
        prices = await final_text_builder(data['setting_actions'])
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
                                        reply_markup=not_money_keyboard_builder(balance_flag=True))
        # Если баланса хватает на оплату задания и всё ок
        else:
            text = add_task['final_confirmation'].format(need, balance, round(balance-need, 2), prices)
            await bot.edit_message_text(message_id=await db.get_main_interface(telegram_id),
                                        chat_id=chat_id,
                                        text=text,
                                        reply_markup=final_add_task_builder())
            await state.update_data(number_users=number_users)
            await state.set_state(FSMAddTask.add_task)

    # Если пользователь ввёл не число
    else:
        await bot.edit_message_text(message_id=await db.get_main_interface(telegram_id),
                                    chat_id=chat_id,
                                    text=data.get('text') + '\n\n<code>Упс, кажется, ты ввёл не число</code>',
                                    reply_markup=await add_number_user_builder(await db.check_balance(telegram_id), data))


# Пользователь добавил новое задание
@router.callback_query(F.data == 'add_finally_task')
async def add_finally_task(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    # Проверка баланса перед тем, как добавить задание (чтоб юзер с нескольких интерфейсов не открыл меню добавления задания и не добавил сразу их несколько
    balance = await db.check_balance(int(callback.from_user.id))
    need = await define_price(data['setting_actions'], data['number_users'])
    # Ещё раз перепроверяем, что баланса хватает
    if balance < need:
        await callback.message.edit_text(add_task['fail_add_task'].format(round(balance, 2), round(need - balance, 2)),
                                         reply_markup=not_money_keyboard_builder(balance_flag=True))
    else:
        post_flag = True if data['accepted']['post_link'] else False  # Флаг, который укажет, ввёл юзер ссылку на профиль или на пост
        await callback.message.edit_text(add_task['check_new_task'])
        link = data['accepted']['post_link'] if post_flag else data['accepted']['profile_link']
        what_check = 'post' if post_flag else 'profile'
        # check_link: bool = await existence_parser(link, what_check)
        check_link = True
        # Если существование поста/аккаунта не было подтверждено
        if not check_link:
            text = add_task['not_existing_link'].format('поста' if post_flag else 'профиля',
                                                        (f"Ссылка на профиль: {data['accepted']['profile_link']}\n" if data['accepted']['profile_link'] else '') +
                                                        (f"Ссылка на пост: {data['accepted']['post_link']}\n" if data['accepted']['post_link'] else ''))
            await callback.message.edit_text(text, reply_markup=not_existing_link_builder(), disable_web_page_preview=True)
        # Если всё ок и ссылки существуют
        else:
            task_id = await db.add_new_task(callback.from_user.id,
                                            float(await define_price(data['setting_actions'], data['number_users']) - await count_commission(data['setting_actions'], data['number_users'])),
                                            await define_price(data['setting_actions'], data['number_users']),
                                            await count_commission(data['setting_actions'], data['number_users']),
                                            float(await define_price(data['setting_actions']) - await count_commission(data['setting_actions'])),
                                            data['number_users'],
                                            data['setting_actions'],
                                            data['accepted'],
                                            True if data['number_users'] > 100 else False)
            # Добавление всех необходимых данных для создания таска в базе данных
            await callback.message.edit_text(add_task['adding_task'],
                                             reply_markup=add_task_keyboad_builder(task_id))
            # Стартуем размещение задания
            await start_tasks(task_id, circular=True if data['number_users'] > 100 else False)
