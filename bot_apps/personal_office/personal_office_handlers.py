from asyncio import sleep

from aiogram import Router, Bot, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot_apps.FSM.FSM_states import FSMAccounts
from bot_apps.filters.ban_filters.is_banned import IsBanned
from databases.database import db
from bot_apps.other_apps.main_menu.main_menu_functions import delete_old_interface
from bot_apps.personal_office.personal_office_filters import correct_account
from bot_apps.personal_office.personal_office_keyboards import personal_account_builder, list_account_builder, \
    keyboard_under_account_builder, account_delete_builder, back_button_builder, add_account_builder, \
    not_add_account_builder, account_added_successfully_builder, payment_keyboard_builder, \
    button_back_personal_office_builder, history_keyboard_builder, history_account_keyboard_builder, \
    list_tasks_keyboards, pay_from_add_task_builder, shadow_ban_builder
from bot_apps.personal_office.personal_office_parsing import add_new_account
from bot_apps.personal_office.personal_office_text import personal_account_text_builder, accounts_text_builder, \
    history_account_builder, tasks_list_text_builder
from bot_apps.wordbank.wordlist import accounts, rules, statistic, payment, history_task
from config import load_config
from parsing.other_parsing.parsing_our_subscribers import AllOurUsers

from parsing.other_parsing.parsing_shadowban import parsing_shadowban

config = load_config()
router = Router()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
all_our_users = AllOurUsers()
router.callback_query.filter(IsBanned())
router.message.filter(IsBanned())


# Пользователь вошёл в личный кабинет
@router.callback_query((F.data == 'personal_account') | (F.data == 'back_to_personal_account'))
async def process_open_personal_account(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(await personal_account_text_builder(callback.from_user.id),
                                     reply_markup=await personal_account_builder(callback.from_user.id))
    await state.clear()


# Возвращение в личный кабинет во время обучения
@router.callback_query(F.data == 'back_to_personal_account_after_education')
async def back_to_personal_account(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    message_id = await callback.message.answer(await personal_account_text_builder(callback.from_user.id),
                                               reply_markup=await personal_account_builder(callback.from_user.id))
    await db.update_main_interface(callback.from_user.id, message_id.message_id)
    await state.clear()


# Пользователь открыл меню с аккаунтами
@router.callback_query(F.data == 'accounts')
async def process_open_accounts(callback: CallbackQuery, state: FSMContext):
    accounts_dict = await db.get_accounts(callback.from_user.id)
    accounts_list = await accounts_text_builder(accounts_dict)
    await callback.message.edit_text(text=''.join(accounts_list['page_1']),
                                     reply_markup=await list_account_builder(accounts_list, int(callback.from_user.id)),
                                     disable_web_page_preview=True)
    await state.set_state(FSMAccounts.accounts_menu)
    await state.update_data(accounts_list=accounts_list)


# Пользователь перебирает свои аккаунты
@router.callback_query(F.data.startswith('accounts_page_'), StateFilter(FSMAccounts.accounts_menu))
async def pagination_accounts(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = callback.data[14:] if callback.data.startswith('accounts_page_') else data.get('page')
    page = page if f'page_{page}' in data.get('accounts_list') else str(int(page)-1)
    await callback.message.edit_text(text=''.join(data.get('accounts_list')[f'page_{page}']),
                                     reply_markup=await list_account_builder(data.get('accounts_list'),
                                                                             int(callback.from_user.id), int(page)),
                                     disable_web_page_preview=True)
    await state.update_data(page=callback.data[14:] if callback.data.startswith('accounts_page_') else data.get('page'))


# Пользователь открыл один из аккаунтов
@router.callback_query(F.data.startswith('account_') | F.data.startswith('back_to_account_'),  StateFilter(FSMAccounts.accounts_menu))
async def open_account(callback: CallbackQuery, state: FSMContext):
    # Изменение имени в связи с тем, что другие хендлеры могут пользоваться этой функцией
    name = callback.data[8:] if callback.data.startswith('account_') else callback.data.replace('disable_', '').replace('enable_', '').replace('back_to_account_', '').replace('rewards_account_', '')
    info_dict = await db.get_account_info(name, int(callback.from_user.id))
    data = await state.get_data()
    await callback.message.edit_text(
        accounts['account_info'].format(f'<a href="https://twitter.com/{name[1:]}">{name}</a>',
                                        info_dict['status'],
                                        int(info_dict['account_balance']) if info_dict['account_balance'].is_integer() else round(info_dict['account_balance'], 2),
                                        int(info_dict['earned']) if float(info_dict['earned']).is_integer() else round(info_dict['earned'], 2),
                                        info_dict['type'].get('subscriptions', 0), info_dict['type'].get('likes', 0),
                                        info_dict['type'].get('retweets', 0), info_dict['type'].get('comments', 0)),
        reply_markup=await keyboard_under_account_builder(name, data.get('page'), info_dict['status']),
        disable_web_page_preview=True)


# Пользователь собирает награды на одном из своих аккаунтов
@router.callback_query(F.data.startswith('rewards_account_'),  StateFilter(FSMAccounts.accounts_menu))
async def get_rewards(callback: CallbackQuery, state: FSMContext):
    collect, balance = await db.collect_rewards(callback.from_user.id, callback.data[16:])
    # Если у пользователя есть несобранный баланс, то говорим, что он собрал его на такую-то сумму
    if balance:
        await callback.answer(accounts['get_rewards'].format(
            int(collect) if collect.is_integer() else round(collect, 2),
            int(balance) if balance.is_integer() else round(balance, 2),
            show_alert=True))
        await open_account(callback, state)
    # Если у пользователя нет баланса, то говорим, что нечего собирать
    else:
        await callback.answer(accounts['not_rewards'], show_alert=True)


# Пользователь выключил/включил аккаунт
@router.callback_query(F.data.startswith('disable_') | F.data.startswith('enable_'),  StateFilter(FSMAccounts.accounts_menu))
async def change_status(callback: CallbackQuery, state: FSMContext):
    # Меняем статус аккаунта в базе данных
    await db.change_status_account(callback.from_user.id, callback.data.replace('disable_', '').replace('enable_', ''),
                                   'inactive' if callback.data.startswith('disable') else 'active')
    # Обновляем информацию
    accounts_dict = await db.get_accounts(callback.from_user.id)
    accounts_list = await accounts_text_builder(accounts_dict)
    await state.update_data(accounts_list=accounts_list)
    await open_account(callback, state)
    await db.off_all_notifications(callback.from_user.id)


# Пользователь решил удалить аккаунт (предварительный вопрос, точно ли он хочет это сделать)
@router.callback_query((F.data.startswith('delete_account_')), StateFilter(FSMAccounts.accounts_menu))
async def wants_to_delete_account(callback: CallbackQuery):
    await callback.message.edit_text(accounts['question_delete_button'],
                                     reply_markup=await account_delete_builder(callback.data[15:]))


# Пользователь подтвердил удаление аккаунта
@router.callback_query((F.data.startswith('confirm_delete_')), StateFilter(FSMAccounts.accounts_menu))
async def delete_account(callback: CallbackQuery, state: FSMContext):
    await db.delete_acc_in_db(callback.from_user.id, callback.data[15:])
    await callback.answer(accounts['account_delete'])
    data = await state.get_data()
    if data.get('page'):
        accounts_dict = await db.get_accounts(callback.from_user.id)
        accounts_list = await accounts_text_builder(accounts_dict)
        await state.update_data(accounts_list=accounts_list)
        await pagination_accounts(callback, state)
    else:
        await process_open_accounts(callback, state)
    await db.off_all_notifications(callback.from_user.id)


# Возвращение к аккаунтам
@router.callback_query(F.data == 'back_to_accounts')
async def process_back_to_accounts(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FSMAccounts.accounts_menu)
    data = await state.get_data()
    if data.get('page'):
        await pagination_accounts(callback, state)
    else:
        await process_open_accounts(callback, state)


# Пользователя добавляет новый аккаунт и ему показывается сообщение о том, что нужно ввести
@router.callback_query(F.data == 'add_account')
# Пользователь решил поменять название аккаунта на другой
@router.callback_query(F.data == 'not_add')
async def process_add_account(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(accounts['add_account'],
                                     reply_markup=await back_button_builder())
    await state.set_state(FSMAccounts.add_account)


# Пользователь ввёл аккаунт
@router.message(StateFilter(FSMAccounts.add_account))
async def adding_account(message: Message, state: FSMContext):
    await message.delete()
    # Проверка введённого аккаунта на корректность
    is_correct = await correct_account(message.from_user.id, message.text.strip() if message.text else '')
    # Если вернулся текст ошибки вместо удовлетворительного ответа
    if isinstance(is_correct, str):
        await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                    chat_id=message.chat.id, text=is_correct,
                                    reply_markup=await back_button_builder())
    # Если аккаунт оказался корректен
    else:
        username = message.text.strip() if not message.text.startswith('https://twitter.com/') else '@' + message.text.strip()[20:]
        await bot.edit_message_text(message_id=await db.get_main_interface(message.from_user.id),
                                    chat_id=message.chat.id,
                                    text=accounts['new_account'].format(username[1:]),
                                    reply_markup=await add_account_builder(),
                                    disable_web_page_preview=True)
        await state.set_state(FSMAccounts.check_account)
        await state.update_data(account=username)


# Проверка только что добавленного аккаунта
@router.callback_query(F.data == 'confirm_add')
async def process_check_account(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(accounts['examination'].format(data.get('account')))
    await sleep(2)
    # all_users = await all_our_users.get_all_our_users()
    # Если не удалось найти аккаунт в подписках нашего твиттер аккаунта
    # if not data.get('account') in all_users:
    result = True
    if not result:
        await callback.message.edit_text(accounts['fail_check'].format(data.get('account')[1:]),
                                         reply_markup=await not_add_account_builder(),
                                         disable_web_page_preview=True)
    # Если аккаунт найден, то бот открывает функция для его проверки на теневой бан
    elif await parsing_shadowban(data['account']) is False:
        await callback.message.edit_text(accounts['shadow_ban'].format(data.get('account')[1:]),
                                         reply_markup=await shadow_ban_builder(),
                                         disable_web_page_preview=True)

    # Если аккаунт найден в подписках
    else:
        result = await add_new_account(callback.from_user.id, data.get('account'))
        if result:
            await callback.message.edit_text(accounts['account_added_2'].format(data.get('account')),
                                             reply_markup=await account_added_successfully_builder())
        await db.off_all_notifications(callback.from_user.id)


# Пользователь зафейлил проверку, т.к. бот не нашёл его в подписках аккаунта
@router.callback_query(F.data.startswith('try_again_'))
async def try_again_check_account(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(accounts['examination'].format(data.get('account')))
    await sleep(1.5)
    all_users = await all_our_users.get_all_our_users()
    # Если аккаунт не найден, то будет новое сообщение о том, что
    if not data.get('account') in all_users:
        await callback.message.edit_text(accounts['fail_check_again'].format(
            data.get('account')[1:] if callback.data[-1] != '3'
            else accounts['final_fail'].format(data.get('account')[1:])),
            reply_markup=await not_add_account_builder(int(callback.data[-1]) + 1),
            disable_web_page_preview=True)

    # Аккаунт найден в подписках
    else:
        await process_check_account(callback, state)


# Открытие правил пользования сервисов
@router.callback_query(F.data == 'rules')
async def process_open_rules(callback: CallbackQuery):
    await callback.message.edit_text(text=rules['main_text'],
                                     reply_markup=await button_back_personal_office_builder())


# Собрать все награды сразу
# Кнопка появляется, если у пользователя есть несобранные награды с аккаунтов
@router.callback_query(F.data.startswith('collect_all_rewards_'))
async def process_collect_all_rewards(callback: CallbackQuery, state: FSMContext):
    await callback.answer(accounts['collect_all_rewards'].format(callback.data[20:]), show_alert=True)
    await db.collection_of_all_awards(callback.from_user.id)
    await process_open_personal_account(callback, state)


# Пользователь открыл свою личную статистику
@router.callback_query(F.data == 'statistics')
async def process_open_personal_statistics(callback: CallbackQuery):
    statistic_dict = await db.statistic_info(callback.from_user.id)
    await callback.message.edit_text(text=statistic['main_text'].format(statistic_dict.get('total_earned', 0),
                                                                        int(statistic_dict['subscriptions']) if float(statistic_dict['subscriptions']).is_integer() else round(statistic_dict['subscriptions'], 2),
                                                                        int(statistic_dict['likes']) if float(statistic_dict['likes']).is_integer() else round(statistic_dict['likes'], 2),
                                                                        int(statistic_dict['retweets']) if float(statistic_dict['retweets']).is_integer() else round(statistic_dict['retweets'], 2),
                                                                        int(statistic_dict['comments']) if float(statistic_dict['comments']).is_integer() else round(statistic_dict['comments'], 2),
                                                                        statistic_dict.get('earned_referrals')),
                                     reply_markup=await button_back_personal_office_builder())


# # Пользователь перешёл в меню повышения уровня аккаунта
# @router.callback_query(lambda x: x.data.startswith('up_level_'))
# async def process_open_up_level_account(callback: CallbackQuery):
#     # await db.connect()
#     account_info_dict = await db.account_all_info(callback.from_user.id, callback.data[9:])
#     # await db.disconnect()
#     await callback.message.edit_text(accounts['all_account_info'].format(account_info_dict['account_name'],
#                                                                          account_info_dict.get('level', 0), account_info_dict.get('date_of_registration'),
#                                                                          account_info_dict.get('followers', 0), account_info_dict.get('subscribers', 0),
#                                                                          account_info_dict.get('posts', 0), account_info_dict.get('retweets', 0),
#                                                                          account_info_dict.get('post_per_day', 0), account_info_dict.get('average_likes', 0),
#                                                                          account_info_dict.get('average_comments', 0)),
#                                      reply_markup=await up_level_account_kb_builder(callback.data[9:]))


# # Пользователь нажал "обновить информацию об аккаунте"
# @router.callback_query(lambda x: x.data.startswith('update_account_info_'))
# async def process_update_account_info(callback: CallbackQuery):
#     # await db.connect()
#     check_date_of_update = await db.check_to_update(callback.data[20:])
#     # await db.disconnect()
#     # Аккаунт уже обновлялся недавно, т.е., функция вернула оставшееся время до обновления в виде int | float, а не True
#     if not isinstance(check_date_of_update, bool):
#         await callback.answer(check_date_of_update, show_alert=True)
#     # Обновляем всю информацию об аккаунте
#     else:
#         # Здесь уже происходит функция для обновления аккаунта
#         await callback.answer('Парсинг аккаунта')


# Пользователь открывает свою историю заданий
@router.callback_query((F.data == 'task_history') | (F.data == 'history_accounts'))
async def open_task_history(callback: CallbackQuery, state: FSMContext):
    # Сбор всех аккаунтов, с которых были сделаны задания
    accounts_list = await db.check_completed_task(callback.from_user.id)
    await state.update_data(accounts_history=accounts_list)
    # Если не было сделано каких-то заданий
    if not accounts_list:
        await callback.message.edit_text(history_task['user_not_account'],
                                         reply_markup=await button_back_personal_office_builder())
    # Если были сделаны задания
    else:
        await callback.message.edit_text(history_task['history_start'],
                                         reply_markup=await history_keyboard_builder(accounts_list))


# Пользователь вернулся к истории аккаунтов
@router.callback_query(F.data == 'back_to_history')
async def open_back_to_history(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(history_task['history_start'],
                                     reply_markup=await history_keyboard_builder(data.get('accounts_history'),
                                                                                 data.get('history_page', 1)))


# Пользователь ходит по аккаунтам в истории аккаунтов
@router.callback_query(F.data.startswith('history_page_'))
async def open_history_page(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.update_data(history_page=int(callback.data[13:]))
    await callback.message.edit_text(history_task['history_start'],
                                     reply_markup=await history_keyboard_builder(data.get('accounts_history'), int(callback.data[13:])))


# Пользователь перешёл на историю одного из аккаунтов
@router.callback_query(F.data.startswith('history_account_'))
async def open_history_account(callback: CallbackQuery, state: FSMContext):
    account = callback.data[16:]
    dict_history = await history_account_builder(callback.from_user.id, account)
    await callback.message.edit_text(dict_history[account]['page_1'], disable_web_page_preview=True,
                                     reply_markup=await history_account_keyboard_builder(dict_history, account))
    await state.update_data(dict_history=dict_history)
    await state.update_data(account=account)


# Пользователь ходит по истории заданий одного аккаунта
@router.callback_query(F.data.startswith('history_to_account_page_'))
async def open_page_to_history_account(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = callback.data[24:]
    await state.update_data(page=page)
    account = data.get('account')
    await callback.message.edit_text(data['dict_history'][account][f'page_{page}'], disable_web_page_preview=True,
                                     reply_markup=await history_account_keyboard_builder(data['dict_history'], account, int(page)))


# Пользователь решил посмотреть всю историю списком
@router.callback_query(F.data == 'history_list')
async def open_history_list(callback: CallbackQuery, state: FSMContext):
    all_task = await db.all_completed_tasks(callback.from_user.id)
    await state.update_data(all_task=all_task)
    await callback.message.edit_text(await tasks_list_text_builder(all_task),
                                     reply_markup=await list_tasks_keyboards(all_task), disable_web_page_preview=True)


# Пользователь ходит по истории заданий
@router.callback_query(F.data.startswith('history_list_page_'))
async def open_history_list_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data[18:])
    data = await state.get_data()
    await callback.message.edit_text(await tasks_list_text_builder(data.get('all_task'), page), disable_web_page_preview=True,
                                     reply_markup=await list_tasks_keyboards(data.get('all_task'), page))


# Пользователь пополняет свой баланс из личного кабинета
@router.callback_query((F.data == 'pay') | (F.data == 'pay_from_add_task'))
async def process_start_pay(callback: CallbackQuery, state: FSMContext):
    # Записать функцию, которая будет выдавать курс доллара и по-прошествию дня, добавлять новый курс
    # dollar = func()
    # stb = config.stb_curs
    dollar, stb = 100, 50
    # Если пользователь ни разу не пополнял аккаунт (не придумали ещё с Максимом)
    # Пока разницы нет, но в будущем она будет
    if callback.data == 'pay_from_add_task' or not await db.check_payment(callback.from_user.id):
        text = payment['main_text'].format(dollar, stb)
        reply_markup = await payment_keyboard_builder() if callback.data == 'pay' else await pay_from_add_task_builder()
    else:
        text = payment['main_text'].format(dollar, stb)
        reply_markup = await payment_keyboard_builder()

    # Проверка на то, что пользователь переходит из уведомления о завершении задания (в этом случае необходимо менять основной интерфейс)
    if await db.get_main_interface(callback.from_user.id) != callback.message.message_id:
        message_id = await callback.message.answer(text=text, reply_markup=reply_markup)
        # Удаление старого сообщения с интерфейсом бота и запись в бд о новом сообщении
        await delete_old_interface(message_id, callback.from_user.id, bot, callback.message.message_id)
    else:
        await callback.message.edit_text(text=text, reply_markup=reply_markup)


# Пользователь делает первое пополнение из добавления задания
@router.callback_query(F.data == 'first_pay_from_add_task')
async def first_pay_from_add_task(callback: CallbackQuery):
    # Записать функцию, которая будет выдавать курс доллара и по-прошествию дня, добавлять новый курс
    # dollar = func()
    # stb = config.stb_curs
    dollar, stb = 100, 50
    # Пользователь ни разу не пополнял аккаунт (не придумали ещё с Максимом)
    await callback.message.edit_text(payment['main_text'].format(dollar, stb),
                                     reply_markup=await pay_from_add_task_builder(first_pay=True))


# Пользователь делает новое пополнение из добавления аккаунта
@router.callback_query(F.data == 'pay_from_add_task')
async def pay_pay_from_add_task(callback: CallbackQuery, state: FSMContext):
    # Записать функцию, которая будет выдавать курс доллара и по-прошествию дня, добавлять новый курс
    # dollar = func()
    # stb = config.stb_curs
    dollar, stb = 100, 50
    # Пользователь ни разу не пополнял аккаунт (не придумали ещё с Максимом)
    await callback.message.edit_text(payment['main_text'].format(dollar, stb),
                                     reply_markup=await pay_from_add_task_builder())


# Пропуск кнопок, которые не должны никак реагировать, чтобы они не грузились
@router.callback_query(F.data == 'other_apps')
async def other_answer(callback: CallbackQuery):
    await callback.answer()


# Закрыть сообщение, которое просто надо закрыть
@router.callback_query(F.data == 'close')
async def close_message(callback: CallbackQuery):
    await callback.message.delete()
