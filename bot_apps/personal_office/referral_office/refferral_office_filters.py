import string

from bot_apps.databases.database import db
from bot_apps.wordbank.wordlist import referral_office


# Проверка промокода на корректность и отсутствие у других пользователей
async def correct_promocode(promocode) -> bool | str:
    if not promocode:
        return referral_office['creation_promocode']['not_correct_promocode']
    # Проверка промокода на корректность
    if not 3 <= len(promocode) <= 20:
        return referral_office['creation_promocode']['not_correct_promocode']
    for letter in promocode:
        if letter not in string.ascii_letters + '_' + string.digits:
            return referral_office['creation_promocode']['not_correct_promocode']
    # Проверка промокода на совпадение с существующими
    check_promocode = await db.check_promocode(promocode)
    if not check_promocode:
        return referral_office['creation_promocode']['promocode_already_exists']
    return True
