from bot_apps.bot_parts.personal_office.referral_office.refferall_office_link_constructor import ref_link_no_text

from bot_apps.other_apps.wordbank import referral_office
from databases.database import Database

db = Database()


# Текст для реферального кабинета
async def ref_office_text_builder(tg_id):
    ref_office_info = await db.ref_office_info(tg_id)
    promocode = await ref_link_no_text(tg_id)
    ref_office_text = referral_office['main_text'].format(ref_office_info.get('promocode', None), promocode,
                                                          int(ref_office_info.get('current_balance', 0)) if float(ref_office_info.get('current_balance', 0)).is_integer() else round(ref_office_info.get('current_balance', 0), 2),
                                                          ref_office_info.get('referrals', 0),
                                                          ref_office_info.get('active_referrals', 0))
    return ref_office_text


# Текст для раздела с партнёрской статистикой
async def affiliate_statistics_text_builder(tg_id):
    affiliate_statistics_dict = await db.affiliate_statistics_info(tg_id)
    affiliate_statistics_text = referral_office['affiliate_statistics'].format(
        affiliate_statistics_dict['count_people'], affiliate_statistics_dict['active_people'],
        affiliate_statistics_dict['new_people_in_month'], affiliate_statistics_dict.get('earned_by_friends'),
        affiliate_statistics_dict.get('sum_earned'), affiliate_statistics_dict.get('collected_from_promocode'))
    return affiliate_statistics_text
