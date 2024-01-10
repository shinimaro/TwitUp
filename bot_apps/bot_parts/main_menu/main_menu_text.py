from datetime import datetime

import pytz

from bot_apps.other_apps.wordbank import main_menu
from databases.database import Database
from databases.dataclasses_storage import InfoForMainMenu

db = Database()


async def main_info_about_user(tg_id: int) -> str:
    """Выдаёт некоторую информацию о юзере в главном меню"""
    account_info: InfoForMainMenu = await db.get_some_statistics_account(tg_id)
    return main_menu['main_text'] + main_menu['account_statistics']['main_text'].format(
        _get_correct_date_now(),
        account_info.number_sent_tasks,
        account_info.number_completed_tasks,
        _get_priority_type_text(account_info)) + _text_abuot_user_fines(account_info)


def _get_correct_date_now() -> str:
    date_dict = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля', 5: 'мая', 6: 'июня',
        7: 'июля', 8: 'августа', 9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
    }
    return datetime.now(pytz.timezone('Europe/Moscow')).strftime(f"%#d {date_dict[datetime.now().month]}")


def _get_priority_type_text(account_info: InfoForMainMenu) -> str:
    """Текст о том, какой у юзера приоритет"""
    priority_dict = {lambda x: x.top_priority: main_menu['account_statistics']['proirity_type']['top_priority'],
                     lambda x: x.priority >= 80: main_menu['account_statistics']['proirity_type']['over_high_priority'],
                     lambda x: x.priority >= 60: main_menu['account_statistics']['proirity_type']['high_priority'],
                     lambda x: x.priority >= 40: main_menu['account_statistics']['proirity_type']['average_priority'],
                     lambda x: x.priority >= 20: main_menu['account_statistics']['proirity_type']['not_high_proority'],
                     lambda x: x.priority >= 0: main_menu['account_statistics']['proirity_type']['low_prioryty']}
    for func in priority_dict:
        if func(account_info):
            return priority_dict[func]


def _text_abuot_user_fines(account_info: InfoForMainMenu) -> str:
    """Текст о действующих штрафах юзера"""
    main_text = main_menu['account_statistics']['fines_type']['main_text']
    if account_info.sum_fines_stb:
        return main_text + main_menu['account_statistics']['fines_type']['bought_fines'].format(
            account_info.awards_cut, account_info.sum_fines_stb)
    elif account_info.sum_fines_priority:
        return main_text + main_menu['account_statistics']['fines_type']['temporary_fines']
    else:
        return ''

# Штрафы на аккаунте отдельный сообщение. если они есть, если их нет, то и писать не надо
# Не забыть добавить новый флаг в бд и придумать, как это сделать с новичками, т.к. у них не помню, какой флаг стоит, либо флаг менять после первого выполнения в проверке на юзера после отправки таска, хз


