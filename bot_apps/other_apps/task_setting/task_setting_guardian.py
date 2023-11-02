from databases.database import db
from bot_apps.wordbank import setting


async def text_except_all_notifications(tg_id):
    info_dict = await db.off_all_notifications(tg_id)
    if info_dict['disabled_flag']:
        return setting['exceptions_all_notifications']['disabled_accounts']
    elif info_dict['not_notifications']:
        return setting['exceptions_all_notifications']['not_notifications']
    elif info_dict['deleted_flag']:
        return setting['exceptions_all_notifications']['deleted_accounts']
    else:
        return setting['exceptions_all_notifications']['not_accounts']


