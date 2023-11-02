from math import ceil
from re import search

from aiogram.types import InlineKeyboardButton as IB
from aiogram.utils.keyboard import InlineKeyboardBuilder as BD

from databases.database import db
from bot_apps.wordbank.wordlist import BACK_PERSONAL_ACCOUNT, payment, history_task
from bot_apps.wordbank.wordlist import accounts, BACK, FORWARD
from bot_apps.wordbank.wordlist import personal_account, BACK_MAIN_MENU


# Билдер личного кабинета
async def personal_account_builder(tg_id):
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
async def list_account_builder(list_text, tg_id, page=1):
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
async def keyboard_under_account_builder(account_name, page=None, status='active'):
    keyboard_under_account = BD()
    # Собираем
    for key, value in accounts['buttons']['buttons_for_account'].items():
        if key == 'disable_button' and status == 'inactive':
            key, value = 'enable_button', 'Включить в работу'
        elif key == 'up_level_button':
            keyboard_under_account.row(
                IB(text=value,
                   url='https://twitter.com/' + account_name[1:]), width=1)
            continue
        keyboard_under_account.row(
            IB(text=value,
               callback_data=key[:-6]+account_name), width=1)
    keyboard_under_account.row(
        IB(text=BACK,
           callback_data=f'accounts_page_{page}' if page else f'accounts'),
        IB(text=BACK_PERSONAL_ACCOUNT,
           callback_data='back_to_personal_account'), width=1)
    return keyboard_under_account.as_markup()


# # Клавиатура под меню для повышения уровня аккаунта
# async def up_level_account_kb_builder(acc_name):
#     up_level_account_kb = BD()
#     up_level_account_kb.row(
#         IB(text=accounts['buttons']['update_account_info_button'],
#            callback_data=f'update_account_info_{acc_name}'),
#         IB(text=BACK,
#            callback_data=f'back_to_account_{acc_name}'),
#         IB(text=BACK_PERSONAL_ACCOUNT,
#            callback_data='back_to_personal_account'), width=1)
#     return up_level_account_kb.as_markup()


# Кнопка для возвращения назад под меню ввода аккаунта (после его настройки например)
async def back_button_builder():
    back_button = BD()
    back_button.row(
        IB(text=BACK,
           callback_data='back_to_accounts'))
    return back_button.as_markup()


# Клавиатура для добавления нового аккаунта
async def add_account_builder():
    add_account = BD()
    add_account.row(
        IB(text=accounts['buttons']['confirm_button'],
           callback_data='confirm_add'),
        IB(text=accounts['buttons']['not_add_button'],
           callback_data='not_add'))
    add_account.row(
        IB(text=BACK,
           callback_data='back_to_accounts'))
    return add_account.as_markup()


# Пользователь зафейлил проверку
async def not_add_account_builder(attempt=1):
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


# Клавиатура после добавления нового аккаунта (под его статистикой)
async def account_added_successfully_builder():
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
async def account_delete_builder(account_name):
    delete_account = BD()
    delete_account.row(
        IB(text=accounts['buttons']['confirm_delete_button'],
           callback_data='confirm_delete_' + account_name),
        IB(text=BACK,
           callback_data='back_to_account_' + account_name),
        IB(text=BACK_PERSONAL_ACCOUNT,
           callback_data='back_to_personal_account'), width=1)
    return delete_account.as_markup()


# Кнопка, переводящая обратно в личный кабинет
async def button_back_personal_office_builder():
    button_back_under_ruled = BD()
    button_back_under_ruled.row(
        IB(text=BACK_PERSONAL_ACCOUNT,
           callback_data='back_to_personal_account'))
    return button_back_under_ruled.as_markup()


# Клавиатура для пополнения личного кабинета
async def payment_keyboard_builder():
    payment_keyboard = BD()
    payment_keyboard.row(
        *[IB(text=text, callback_data=button[:-7])
          for button, text in payment['buttons']['pay_method'].items()], width=1)
    payment_keyboard.row(
        IB(text=BACK_PERSONAL_ACCOUNT,
           callback_data='back_to_personal_account'))
    return payment_keyboard.as_markup()


async def pay_from_add_task_builder(first_pay=None):
    first_pay_from_add_task = BD()
    first_pay_from_add_task.row(
        *[IB(text=text, callback_data=button[:-7])
          for button, text in payment['buttons']['pay_method'].items()], width=1)
    if first_pay:
        first_pay_from_add_task.row(
            IB(text=payment['buttons']['pay_from_add_task']['first_pay_from_add_task_button'],
               callback_data='back_accept_setting_task'))
    else:
        first_pay_from_add_task.row(
            IB(text=payment['buttons']['pay_from_add_task']['first_pay_from_add_task_button'],
               callback_data='back_accept_all_setting'))

    return first_pay_from_add_task.as_markup()


# Клавиатура, при открытии истории заданий, которая показывает список аккаунтов (за образец взята функция list_account_builder)
# В отличии от клавиатуры работы с заданиями, эта клавиатура
async def history_keyboard_builder(account_list, page=1):
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
async def history_account_keyboard_builder(history_dict, account, page=1):
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
async def list_tasks_keyboards(all_task, page=1):
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
