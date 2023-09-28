from asyncio import sleep

from bot_apps.databases.database import db
from bot_apps.databases.database import Database
from bot_apps.wordbank.wordlist import accounts


# Функция для парсинга, которая перед этим проверяет, есть ли аккаунт в базе данных и, если есть, то нужно ли его парсить,
# если нет, то возвращаем сообщение о том, что его не получится пропарсить до N времени и, возвращаем словарь с существующими данными
async def add_new_account(tg_id, acc_name):
    # check_to_update = await db.check_to_update(acc_name)
    # # Если прилетело время, оставшееся до возможности следующего обновления
    # if isinstance(check_to_update, float):
    #     await db.update_deleted_account(tg_id, acc_name)
    #     hours = int(check_to_update)
    #     minutes = int((check_to_update - hours) * 60)
    #     text_for_time = f"Следующее обновление будет доступно через - {hours} часов : {minutes} минуты"
    #     final_text = accounts['not_add_account'].format(acc_name, text_for_time, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    #     return final_text
    # parsing_account = await func()
    # if какая-то ошибка, то можно предложить пропарсить аккаунт снова
    # # Собираем словарь
    # all_info_dict = {'level': 2, 'date_of_registration': '2015-03-05', 'followers': 20, 'subscribers': 8, 'posts': 5, 'retweets': 15}
    # Аккаунт добавляется в базу данных
    # await db.check_before_adding(tg_id, acc_name, all_info_dict)

    # parsing_account = await func()
    # if какая-то ошибка, то можно предложить пропарсить аккаунт снова
    await sleep(2)
    await db.add_account(tg_id, acc_name)
    return True
