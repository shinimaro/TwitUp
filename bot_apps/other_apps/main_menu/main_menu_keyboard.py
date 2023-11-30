from aiogram.utils.keyboard import InlineKeyboardBuilder as BD
from aiogram.types import InlineKeyboardButton as IB

from databases.database import db
from bot_apps.wordbank import wordlist, BACK_MAIN_MENU
from config import load_config

config = load_config()


# Билдер главного меню бота
async def main_menu_builder(tg_id):
    main_menu = BD()
    # Все обычные кнопки
    buttons = [IB(text=wordlist.main_menu['buttons'][button],
                  callback_data=button[:-7])
               for button in wordlist.main_menu['buttons']]
    # Кнопка рабты с заданиями
    result = await db.check_tasks(tg_id)
    buttons.insert(0, IB(text=wordlist.main_menu['dop_buttons']['add_task_button'] if not result else wordlist.main_menu['dop_buttons']['personal_tasks_button'], callback_data='add_task' if not result else 'personal_tasks'))
    # Кнопка приёма заданий
    result: bool = await db.get_all_notifications(tg_id)
    buttons.insert(2, IB(text=('✅ ' if result else '❌ ') + wordlist.main_menu['dop_buttons']['accepting_task_button'],
                         callback_data=f"all_notifications_{'off' if result else 'on'}"))
    # Кнопка перехода в up-chat
    buttons.insert(4, IB(text=wordlist.main_menu['dop_buttons']['review_button'],
                         url=config.tg_bot.feedback_group))
    main_menu.row(*buttons, width=2)
    # Кнопка TwittUp - litepepper
    main_menu.row(
        IB(text=wordlist.main_menu['dop_buttons']['twittup_litepepper_button'],
           callback_data='other'))

    return main_menu.as_markup()


# Секретный кейборад для одного сообщения
async def welcome_keyboard():
    welcome_kb = BD()
    welcome_kb.row(
        IB(text=BACK_MAIN_MENU,
           callback_data='back_to_main_menu'))
    return welcome_kb.as_markup()
