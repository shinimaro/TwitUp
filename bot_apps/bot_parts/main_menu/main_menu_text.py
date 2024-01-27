from datetime import datetime

import pytz

from bot_apps.other_apps.wordbank import main_menu
from databases.database import Database
from databases.dataclasses_storage import InfoForMainMenu

db = Database()


async def main_info_about_user(tg_id: int) -> str:
    """Выдаёт некоторую информацию о юзере в главном меню"""
    text = main_menu['main_text']
    account_info: InfoForMainMenu = await db.get_some_statistics_account(tg_id)
    if account_info.number_accounts < 1:
        text += main_menu['dop_main_text']
        if account_info.sum_fines_stb:
            text += _text_about_user_fines(account_info)
    else:
        text += main_menu['account_statistics']['main_text'].format(_get_correct_date_now())
        text += _sent_tasks_text(account_info)
        text += _priority_text(account_info)
        text += _text_about_user_fines(account_info)
    return text


def _get_correct_date_now() -> str:
    date_dict = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля', 5: 'мая', 6: 'июня',
        7: 'июля', 8: 'августа', 9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
    }
    return datetime.now(pytz.timezone('Europe/Moscow')).strftime(f"%#d {date_dict[datetime.now().month]}")


def _priority_text(account_info: InfoForMainMenu) -> str:
    """Текст о том, какой у юзера приоритет"""
    priority_dict = {lambda x: x.top_priority: main_menu['account_statistics']['proirity_type']['top_priority'],
                     lambda x: x.priority >= 80: main_menu['account_statistics']['proirity_type']['over_high_priority'],
                     lambda x: x.priority >= 60: main_menu['account_statistics']['proirity_type']['high_priority'],
                     lambda x: x.priority >= 40: main_menu['account_statistics']['proirity_type']['average_priority'],
                     lambda x: x.priority >= 20: main_menu['account_statistics']['proirity_type']['not_high_proority'],
                     lambda x: x.priority >= 0: main_menu['account_statistics']['proirity_type']['low_prioryty']}
    for func in priority_dict:
        if func(account_info):
            return main_menu['account_statistics']['proirity_type']['main_text'].format(priority_dict[func])


def _sent_tasks_text(account_info: InfoForMainMenu) -> str:
    """Текст об отправленных тасках юзеру"""
    return main_menu['account_statistics']['sent_tasks'].format(
        account_info.number_sent_tasks,
        account_info.number_completed_tasks)


def _text_about_user_fines(account_info: InfoForMainMenu) -> str:
    """Текст о действующих штрафах юзера"""
    main_text = main_menu['account_statistics']['fines_type']['main_text']
    if account_info.sum_fines_stb:
        return main_text + main_menu['account_statistics']['fines_type']['bought_fines'].format(
            account_info.awards_cut, account_info.sum_fines_stb)
    # Пока убрал, чтобы эта хрень, т.к. не вижу смысла в уведомлять постоянно юзера об этом мелком штрафе
    # elif account_info.sum_fines_priority:
    #     return main_text + main_menu['account_statistics']['fines_type']['temporary_fines']
    else:
        return ''
