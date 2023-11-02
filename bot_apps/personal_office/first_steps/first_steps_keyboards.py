from aiogram.types import InlineKeyboardButton as IB
from aiogram.utils.keyboard import InlineKeyboardBuilder as BD

from bot_apps.wordbank.wordlist import accounts, BACK, BACK_PERSONAL_ACCOUNT, personal_account, main_menu, \
    BACK_MAIN_MENU


# Клавиатура перед указанием первого аккаунта пользователя
async def first_account_builder():
    first_account_kb = BD()
    first_account_kb.row(
        IB(text=accounts['buttons']['buttons_education']['specify_account_button'],
           callback_data='specify_account'),
        IB(text=personal_account['buttons']['rules_button'],
           callback_data='rules_from_training'),
        IB(text=BACK_PERSONAL_ACCOUNT,
           callback_data='back_to_personal_account'),  width=1)
    return first_account_kb.as_markup()


# Клавиатура для добавления первого аккаунта пользователя
async def add_first_account_builder():
    add_first_account = BD()
    add_first_account.row(
        IB(text=accounts['buttons']['buttons_education']['link_twitter_button'],
           url='https://twitter.com/home'),
        IB(text=BACK,
           callback_data='back_to_first_account'),
        IB(text=BACK_PERSONAL_ACCOUNT,
           callback_data='back_to_personal_account_after_education'), width=1)
    return add_first_account.as_markup()


# Клавиатура перед проверкой аккаунта на подписку (чтобы пользователь проверил, что он ввёл и, при желании, поменял аккаунт)
async def before_check_first_account_builder():
    before_check_first_account = BD()
    before_check_first_account.row(
        IB(text=accounts['buttons']['buttons_education']['check_first_task_button'],
           callback_data='check_first_task'),
        IB(text=accounts['buttons']['buttons_education']['change_first_account_button'],
           callback_data='change_first_account'),
        IB(text=BACK_PERSONAL_ACCOUNT,
           callback_data='back_to_personal_account'), width=1)
    return before_check_first_account.as_markup()


# Клавиатура если у пользователя теневой бан
async def shadow_ban_keyboard_builder():
    shadow_ban_keyboad = BD()
    shadow_ban_keyboad.row(
        IB(text=accounts['buttons']['buttons_education']['again_add_account_button'],
           callback_data='add_first_account'),
        IB(text=BACK_PERSONAL_ACCOUNT,
           callback_data='back_to_personal_account'),
        IB(text=BACK_MAIN_MENU,
           callback_data='back_to_main_menu'), width=1)
    return shadow_ban_keyboad.as_markup()


# Клавиатура под первой статистикой аккаунта после его проверки
async def completion_add_first_account_builder():
    completion_add_first_account = BD()
    completion_add_first_account.row(
        IB(text=accounts['buttons']['buttons_education']['enable_execution'],
           callback_data='allow_enabling_tasks'))
    return completion_add_first_account.as_markup()


# Клавиатура в самом конце добавления аккаунта после включения уведомлений
async def completion_of_training_builder():
    completion_of_training = BD()
    completion_of_training.row(
        IB(text=accounts['buttons']['buttons_education']['complete_training'],
           callback_data='back_to_accounts'),
        IB(text=personal_account['buttons']['rules_button'],
           callback_data='rules_from_end_training_notice'), width=1)
    return completion_of_training.as_markup()


# Пользователь завфейлил проверку при добавлении первого аккаунта
async def not_add_first_account_builder(attempt=1):
    not_add_first_account = BD()
    # Если пользователь не зафейлил попытку 3 раза
    # Если пользователь зафейлил 3 раза, бот сообщает о том, что всё, бро, попробуй снова попозже
    if attempt != 3:
        not_add_first_account.row(
            IB(text=accounts['buttons']['try_again_button'],
               callback_data='try_again_education_' + str(attempt)), width=1)
    not_add_first_account.row(
        IB(text=BACK_PERSONAL_ACCOUNT,
           callback_data='back_to_personal_account'), width=1)
    return not_add_first_account.as_markup()



# Клавиатура в самом конце добавления аккаунта без включения уведомлений
async def completion_of_training_with_setting_builder():
    completion_of_training_with_setting = BD()
    completion_of_training_with_setting.row(
        IB(text=accounts['buttons']['buttons_education']['complete_training'],
           callback_data='back_to_accounts'),
        IB(text=main_menu['buttons']['setting_tasks'],
           callback_data='setting_tasks'),
        IB(text=personal_account['buttons']['rules_button'],
           callback_data='rules_from_end_training_without_notice'), width=1)
    return completion_of_training_with_setting.as_markup()


# Кнопка "назад" кнопка под обучением
async def back_button_builder_for_education():
    back_button_for_education = BD()
    back_button_for_education.row(
        IB(text=BACK,
           callback_data='back_at_specify_account'))
    return back_button_for_education.as_markup()


# Кнопка, переводящая обратно в начало обучения
async def button_back_under_ruled_from_training_builder():
    button_back_under_ruled = BD()
    button_back_under_ruled.row(
        IB(text=BACK,
           callback_data='back_at_specify_account')
    )
    return button_back_under_ruled.as_markup()


# Кнопка, переводящая обратно в конец обучения
async def button_back_under_rules_from_end_training_builder(notifications=True):
    button_back_under_ruled = BD()
    button_back_under_ruled.row(
        IB(text=BACK,
           callback_data=f"back_at_end_training_{'true' if notifications else 'false'}")
    )
    return button_back_under_ruled.as_markup()


# Кнопка для блока с конкретным ответом на вопрос об повышении уровня
async def how_up_to_level_builder():
    how_up_to_level_kb = BD()
    how_up_to_level_kb.row(
        IB(text=BACK,
           callback_data='back_check_first_task'))
    return how_up_to_level_kb.as_markup()
