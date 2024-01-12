from math import ceil
from re import search

from aiogram.types import InlineKeyboardButton as IB
from aiogram.types import InlineKeyboardMarkup as IM
from aiogram.utils.keyboard import InlineKeyboardBuilder as BD

from bot_apps.other_apps.wordbank import BACK_PERSONAL_ACCOUNT, payment, history_task
from bot_apps.other_apps.wordbank import accounts, BACK, FORWARD
from bot_apps.other_apps.wordbank import personal_account, BACK_MAIN_MENU
from databases.database import Database

db = Database()


# Билдер личного кабинета
async def personal_account_builder(tg_id) -> IM:
    personal_account_menu = BD()
    # Если у пользователя ещё нет ни одного аккаунта, сразу выносим кнопку с предложением добавить аккаунт
    if not await db.check_adding_accounts(tg_id):
        personal_account_menu.row(
            IB(text=personal_account['dop_buttons']['add_first_account_button'],
               callback_data='add_first_account'),
            IB(text=personal_account['buttons']['ref_office_button'],
               callback_data='ref_office'),
            *[IB(text=button[1], callback_data=button[0][:-7])
              for button in list(personal_account['buttons'].items())[2:4]], width=2)

    else:
        # Собираем все кнопки, находящиеся в словаре по ключу personal_account['buttons'], которые должны быть в 2 ряда
        personal_account_menu.row(*[IB(text=button[1], callback_data=button[0][:-7])
                                    for button in list(personal_account['buttons'].items())[:4]], width=2)
    # Проверяем несобранный баланс пользователя
    balance = await db.uncollected_balance_check(tg_id)
    # Добавление кнопки для сбора баланса, если есть несобранный баланс
    if balance:
        personal_account_menu.row(
            IB(text=personal_account['buttons']['collect_all_rewards_button'], callback_data=f'collect_all_rewards_{balance}'), width=1)
    # Собираем оставшиеся кнопки, которые должны быть в 1 ряд
    personal_account_menu.row(*[IB(text=button[1], callback_data=button[0][:-7])
                                for button in list(personal_account['buttons'].items())[5:]], width=1)
    personal_account_menu.row(IB(text=BACK_MAIN_MENU,
                                 callback_data='back_to_main_menu'))
    return personal_account_menu.as_markup()


# Клавиатура при открытии пользователем своих аккаунтов, которая показывает кнопки с аккаунтами и пагинацию под ними, если это необходимо
# Использует функцию для билдинга текста с информацией по аккаунтам и, опираясь на полученную информацию, собирает клавиатуру
async def list_account_builder(list_text, tg_id, page=1) -> IM:
    accounts_kb = BD()
    # Если у пользователя нет аккаунтов, то возвращаем пару кнопок
    if list_text['page_1'] == accounts['not_accounts']:
        # Если у пользователя никогда не добавлял аккаунт, предлагаем пройти обучение
        if not await db.check_first_accounts(tg_id):
            accounts_kb.row(
                IB(text=accounts['buttons']['add_first_account_button'],
                   callback_data='add_first_account'))
        # Если пользователь уже добавлял аккаунты, обучение не запускаем
        else:
            accounts_kb.row(
                IB(text=accounts['buttons']['add_account_button'],
                   callback_data='add_account'))
        accounts_kb.row(
            IB(text=BACK,
               callback_data='back_to_personal_account'))

    # Если у пользователя меньше 8 аккаунтов, не добавляем пагинацию
    elif len(list_text) == 1:
        for button in list_text['page_1'][1:]:
            account_name = '@' + search(r'@([a-zA-Z0-9_]+)', button).group(1)
            accounts_kb.row(
                IB(text=f'{account_name}✅' if search(r' Включен', button) else f'{account_name}❌',
                   callback_data=f'account_{account_name}', width=1))
        accounts_kb.row(
            IB(text=accounts['buttons']['add_account_button'],
               callback_data='add_account'),
            IB(text=BACK,
               callback_data='back_to_personal_account'), width=1)

    # Если у пользователя много аккаунтов, то создаём пагинацию на странице
    else:
        # Закидываем все аккаунты пользователя с информацией об их состоянии (включён/выключен)
        for button in list_text[f'page_{page}'][1:]:
            account_name = '@' + search(r'@([a-zA-Z0-9_]+)', button).group(1)
            accounts_kb.row(
                IB(text=f'{account_name}✅' if search(r' Включен', button) else f'{account_name}❌',
                   callback_data=f'account_{account_name}', width=1))

        # Докидываем оставшиеся кнопки для пагинации и выхода из аккаунтов
        accounts_kb.row(
            IB(text=BACK,
               callback_data=f'accounts_page_{page-1}' if page > 1 else 'other_apps'),
            IB(text=f'{page}/{len(list_text)}',
               callback_data='other_apps'),
            IB(text=FORWARD,
               callback_data=f'accounts_page_{page+1}' if page < len(list_text) else 'other_apps', width=3))

        accounts_kb.row(
            IB(text=accounts['buttons']['add_account_button'],
               callback_data='add_account'),
            IB(text=BACK,
               callback_data='back_to_personal_account'), width=1)

    return accounts_kb.as_markup()


# Клавиатура под аккаунтом при его открытии (с кнопками для работы с ним)
def keyboard_under_account_builder(account_name, page=None, status='active') -> IM:
    keyboard_under_account = BD()
    # Собираем
    for key, value in accounts['buttons']['buttons_for_account'].items():
        if key == 'disable_button' and status == 'inactive':
            key, value = 'enable_button', 'Включить в работу'
        keyboard_under_account.row(IB(text=value, callback_data=key[:-6]+account_name), width=1)
    keyboard_under_account.row(IB(text=BACK, callback_data=f'accounts_page_{page}' if page else f'accounts'), width=1)
    return keyboard_under_account.as_markup()


# Кнопка для возвращения назад под меню ввода аккаунта (после его настройки например)
def back_button_builder() -> IM:
    back_button = BD()
    back_button.row(
        IB(text=BACK,
           callback_data='back_to_accounts'))
    return back_button.as_markup()


# Клавиатура для добавления нового аккаунта
def add_account_builder() -> IM:
    add_account = BD()
    add_account.row(
        IB(text=accounts['buttons']['confirm_button'], callback_data='confirm_add'),
        IB(text=accounts['buttons']['not_add_button'], callback_data='not_add'))
    add_account.row(IB(text=BACK, callback_data='back_to_accounts'))
    return add_account.as_markup()


# Пользователь зафейлил проверку
def not_add_account_builder(attempt=1) -> IM:
    not_add_account = BD()
    # Если пользователь не зафейлил попытку 3 раза
    # Если пользователь зафейлил 3 раза, бот сообщает о том, что всё, бро, попробуй снова попозже
    if attempt != 3:
        not_add_account.row(
            IB(text=accounts['buttons']['try_again_button'],
               callback_data='try_again_' + str(attempt)), width=1)
    not_add_account.row(
        IB(text=accounts['buttons']['back_to_accounts_button'],
           callback_data='back_to_accounts'), width=1)
    return not_add_account.as_markup()


# Пользователь зафейлил проверку при переименовании
def not_rename_account_builder(account_name) -> IM:
    keyboard = BD()
    keyboard.row(IB(text=accounts['buttons']['try_again_button'],
                    callback_data='try_rename_again'),
                 _get_back_to_account_button(account_name), width=1)
    return keyboard.as_markup()


# Клавиатура под сообщением о теневом бане
def shadow_ban_builder() -> IM:
    shadow_ban_kb = BD()
    shadow_ban_kb.row(
        IB(text=accounts['buttons']['new_account_button'],
           callback_data='add_account'),
        IB(text=accounts['buttons']['back_to_accounts_button'],
           callback_data='back_to_accounts'),
        IB(text=BACK_PERSONAL_ACCOUNT,
           callback_data='back_to_personal_account'), width=1)
    return shadow_ban_kb.as_markup()


# Клавиатура после добавления нового аккаунта (под его статистикой)
def account_added_successfully_builder() -> IM:
    account_added_successfully = BD()
    account_added_successfully.row(
        IB(text=accounts['buttons']['buttons_education']['new_account_button'],
           callback_data='add_account'),
        IB(text=accounts['buttons']['back_to_accounts_button'],
           callback_data='back_to_accounts'),
        IB(text=BACK_PERSONAL_ACCOUNT,
           callback_data='back_to_personal_account'), width=1)
    return account_added_successfully.as_markup()


# Клавиатура для удаления аккаунта
def account_delete_builder(account_name) -> IM:
    delete_account = BD()
    delete_account.row(
        IB(text=accounts['buttons']['confirm_delete_button'],
           callback_data='confirm_delete_' + account_name),
        _get_back_to_account_button(account_name), width=1)
    return delete_account.as_markup()


# Клавиатура для вовзращения к аккаунту
def back_to_account_kb(account_name) -> IM:
    keyboard = BD()
    keyboard.row(_get_back_to_account_button(account_name))
    return keyboard.as_markup()


# Клавиатура после ввода нового имени аккаунта
def insert_new_account_name(account_name) -> IM:
    keyboard = BD()
    keyboard.row(
        IB(text=accounts['buttons']['confirm_button'],
           callback_data='coinfirm_rename_twitter_account'),
        IB(text=accounts['buttons']['change_name_button'],
           callback_data=f'change_new_account_name_{account_name}'))
    keyboard.row(_get_back_to_account_button(account_name))
    return keyboard.as_markup()


# Клавиатура для возврата к аккаунту
def back_to_account_afret_rename(account_name) -> IM:
    keyboard = BD()
    keyboard.row(IB(text=accounts['buttons']['back_to_account_button'],
                    callback_data=f'back_to_account_{account_name}'))
    return keyboard.as_markup()


def _get_back_to_account_button(account_name) -> IB:
    return IB(text=BACK,
              callback_data=f'back_to_account_{account_name}')


# Кнопка, переводящая обратно в личный кабинет
def button_back_personal_office_builder() -> IM:
    button_back_under_ruled = BD()
    button_back_under_ruled.row(
        IB(text=BACK_PERSONAL_ACCOUNT,
           callback_data='back_to_personal_account'))
    return button_back_under_ruled.as_markup()


# Клавиатура для пополнения личного кабинета
async def payment_keyboard_builder(tg_id, data: str) -> IM:
    payment_keyboard = BD()
    if not await db.check_generated_wallet(tg_id):
        payment_keyboard.row(
            IB(text=payment['buttons']['generation_wallet_button'],
               callback_data='generation_wallet'))
    else:
        payment_keyboard.row(
            IB(text=payment['buttons']['go_to_generation_wallet_button'],
               callback_data='go_to_generation_wallet'))

    if data == 'pay':
        payment_keyboard.row(
            IB(text=BACK_PERSONAL_ACCOUNT,
               callback_data='back_to_personal_account'), width=1)
    elif data == 'first_pay_from_add_task':
        payment_keyboard.row(
            IB(text=payment['buttons']['pay_from_add_task']['first_pay_from_add_task_button'],
               callback_data='back_accept_setting_task'))
    else:
        payment_keyboard.row(
            IB(text=payment['buttons']['pay_from_add_task']['first_pay_from_add_task_button'],
               callback_data='back_accept_all_setting'))
    return payment_keyboard.as_markup()


def payment_completed_builder() -> IM:
    keyboard = BD()
    keyboard.row(
        IB(text=payment['buttons']['pay_completed_button'],
           callback_data='close'))
    return keyboard.as_markup()


def back_to_payment() -> IM:
    keyboard = BD()
    keyboard.row(
        IB(text=BACK,
           callback_data='back_to_pay'))
    return keyboard.as_markup()


def back_to_payment_and_generate() -> IM:
    keyboard = BD()
    keyboard.row(
        IB(text=payment['buttons']['generation_wallet_button'],
           callback_data='generation_wallet'),
        IB(text=BACK,
           callback_data='back_to_pay'), width=1)
    return keyboard.as_markup()


# Клавиатура, при открытии истории заданий, которая показывает список аккаунтов (за образец взята функция list_account_builder)
# В отличие от клавиатуры работы с заданиями, эта клавиатура
def history_keyboard_builder(account_list, page=1) -> IM:
    history_keyboard = BD()
    # Если пользователь сделал менее 8 заданий
    if len(account_list) <= 8:
        for account in account_list:
            history_keyboard.row(
                IB(text=account,
                   callback_data=f'history_account_{account}', width=1))
        history_keyboard.row(
            IB(text=history_task['buttons']['history_list_button'],
               callback_data='history_list'),
            IB(text=BACK_PERSONAL_ACCOUNT,
               callback_data='back_to_personal_account'), width=1)

    # Если у пользователя много аккаунтов, то создаём пагинацию на странице
    else:
        # Превращение account_list в нормальный словарь
        pagus = 1
        main_dict = {f'page_{pagus}': []}
        for account in account_list:
            if len(main_dict[f'page_{pagus}']) > 8:
                pagus += 1
                main_dict[f'page_{pagus}'] = []
            main_dict[f'page_{pagus}'].append(account)

        # Закидываем все аккаунты пользователя
        for account in main_dict[f'page_{page}']:
            history_keyboard.row(
                IB(text=account,
                   callback_data=f'history_account_{account}', width=1))
        # Докидываем оставшиеся кнопки для пагинации и выхода из статистики
        history_keyboard.row(
            IB(text=BACK,
               callback_data=f'history_page_{page - 1}' if page > 1 else 'other_apps'),
            IB(text=f'{page}/{len(main_dict)}',
               callback_data='other_apps'),
            IB(text=FORWARD,
               callback_data=f'history_page_{page + 1}' if page < len(main_dict) else 'other_apps', width=3))

        history_keyboard.row(
            IB(text=history_task['buttons']['history_list_button'],
               callback_data='history_list'),
            IB(text=BACK_PERSONAL_ACCOUNT,
               callback_data='back_to_personal_account'), width=1)
    return history_keyboard.as_markup()


# Билдер пагинации для просмотра истории на конкретном аккаунте
def history_account_keyboard_builder(history_dict, account, page=1) -> IM:
    history_account_keyboard = BD()
    if len(history_dict[account]) == 1:
        history_account_keyboard.row(
            IB(text=BACK,
               callback_data='back_to_history'),
            IB(text=BACK_PERSONAL_ACCOUNT,
               callback_data='back_to_personal_account'), width=1)

    else:
        history_account_keyboard.row(
            IB(text=BACK,
               callback_data=f'history_to_account_page_{page - 1}' if page > 1 else 'other_apps'),
            IB(text=f'{page}/{len(history_dict[account])}',
               callback_data='other_apps'),
            IB(text=FORWARD,
               callback_data=f'history_to_account_page_{page + 1}' if page < len(history_dict[account]) else 'other_apps', width=3))

        history_account_keyboard.row(
            IB(text=BACK,
               callback_data='back_to_history'),
            IB(text=BACK_PERSONAL_ACCOUNT,
               callback_data='back_to_personal_account'), width=1)
    return history_account_keyboard.as_markup()


# Клавиатура под показом заданий списком
def list_tasks_keyboards(all_task, page=1) -> IM:
    list_tasks = BD()
    if len(all_task) < 8:
        list_tasks.row(
            IB(text=history_task['buttons']['history_accounts_button'],
               callback_data='history_accounts'),
            IB(text=BACK_PERSONAL_ACCOUNT,
               callback_data='back_to_personal_account'), width=1)

    else:
        list_tasks.row(
            IB(text=BACK,
               callback_data=f'history_list_page_{page - 1}' if page > 1 else 'other_apps'),
            IB(text=f'{page}/{ceil(len(all_task)/8)}',
               callback_data='other_apps'),
            IB(text=FORWARD,
               callback_data=f'history_list_page_{page + 1}' if page < ceil(len(all_task)/8) else 'other_apps', width=3))

        list_tasks.row(
            IB(text=history_task['buttons']['history_accounts_button'],
               callback_data='history_accounts'),
            IB(text=BACK_PERSONAL_ACCOUNT,
               callback_data='back_to_personal_account'), width=1)
    return list_tasks.as_markup()
