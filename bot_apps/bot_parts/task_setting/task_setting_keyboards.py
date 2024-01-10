from aiogram.types import InlineKeyboardButton as IB
from aiogram.types import InlineKeyboardMarkup as IM
from aiogram.utils.keyboard import InlineKeyboardBuilder as BD

from bot_apps.other_apps.wordbank.wordlist import setting, BACK_MAIN_MENU
from databases.database import Database

db = Database()


# Функция для настройки клавиатуры для настройки уведомлений о заданиях
async def setting_tasks_builder(tg_id) -> IM:
    setting_tasks_kb = BD()
    # Собираем все существующие настройки пользователя
    all_setting = await db.all_setting(tg_id)
    # Если пользователь нажимает на любую из настроек, то к её тексту добавляется галочка/крести, а к колбеку добавляется true/false
    setting_tasks_kb.row(
        IB(text=setting['buttons']['subscriptions_button'] + ' ✅' if all_setting['subscriptions'] else setting['buttons']['subscriptions_button'] + ' ❌',
           callback_data='setting_subscriptions_' + 'true' if not all_setting['subscriptions'] else 'setting_subscriptions_' + 'false'),
        IB(text=setting['buttons']['likes_button'] + ' ✅' if all_setting['likes'] else setting['buttons']['likes_button'] + ' ❌',
           callback_data='setting_likes_' + 'true' if not all_setting['likes'] else 'setting_likes_' + 'false'),
        IB(text=setting['buttons']['retweets_button'] + ' ✅' if all_setting['retweets'] else setting['buttons']['retweets_button'] + ' ❌',
           callback_data='setting_retweets_' + 'true' if not all_setting['retweets'] else 'setting_retweets_' + 'false'),
        IB(text=setting['buttons']['comments_button'] + ' ✅' if all_setting['comments'] else setting['buttons']['comments_button'] + ' ❌',
           callback_data='setting_comments_' + 'true' if not all_setting['comments'] else 'setting_comments_' + 'false'),
        IB(text=BACK_MAIN_MENU,
           callback_data='back_to_main_menu'), width=1)
    return setting_tasks_kb.as_markup()


# Клавиатура под уведомлением о том, что пользователь долго не включал получение заданий
def keyboard_under_reminder_builder() -> IM:
    keyboard_under_reminder = BD()
    keyboard_under_reminder.row(
        IB(text=setting['dop_buttons']['on_notifications_button'],
           callback_data='all_notifications_on'),
        IB(text=BACK_MAIN_MENU,
           callback_data='back_to_main_menu'), width=1)
    return keyboard_under_reminder.as_markup()
