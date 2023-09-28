import string
import time

from bot_apps.databases.database import db
from bot_apps.wordbank.wordlist import accounts


# Лёгкая проверка аккаунта на минимальную корректность
async def correct_account(tg_id: int = None, name: str = None) -> bool | str:
    if not name:
        return accounts['incorrect_account'].format('')
    # Если пользователь ввёл ссылку, находим из неё корректный юзернейм
    if name.startswith('https://twitter.com/'):
        name = '@' + name[20:]

    if name[0] != '@':
        return accounts['incorrect_start'].format(name[:70])
    # Если аккаунт короче 3 символов, либо в нём есть пробелы
    if len(name[1:]) < 3 or ' ' in name[1:]:
        return accounts['incorrect_account'].format(name[:70])
    # Если аккаунт слишком длинный
    if len(name[1:]) > 15:
        return accounts['very_long_account'].format(name[:70])
    # Если в аккаунте запрещённые символы
    for n in name[1:]:
        if n not in string.ascii_letters + '_' + string.digits:
            return accounts['forbidden_symbols'].format(name[:70])

    # Проверка на то, что его нет у другого пользователя
    if tg_id:
        # Находим аккаунт в базе данных (если аккаунт удалён, то он не будет считаться в бд)
        stock_account = await db.stock_account(name)
        # Если аккаунт уже есть в базе данных и функция вернула тг id владельца
        if stock_account and isinstance(stock_account, int):
            # Если это аккаунт пользователя, и он ему уже принадлежит
            if int(stock_account) == tg_id:
                return accounts['user_have_account'].format(name[:70])
            # Если аккаунт принадлежит другому пользователю
            else:
                return accounts['another_user_account'].format(name[:70])
    return True

