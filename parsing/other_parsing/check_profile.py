import asyncio

from bot_apps.other_apps.wordbank import accounts
from databases.database import Database
from databases.dataclasses_storage import AccountRequirements, AccountDetails
from parsing.elements_storage.elements_dictionary import base_links
from parsing.manage_webdrivers.master_function import Master
from parsing.parsing_functions.parsing_functions import get_account_info

db = Database()


async def check_profile(profile_name: str) -> bool | str:
    """Проверка на то, что аккаунт соответствует минимальным требованиям"""
    master = Master()
    driver = await master.get_driver()
    page = (await driver.pages())[0]
    account_details: AccountDetails = await get_account_info(page, f"{base_links['home_page']}{profile_name}")
    asyncio.get_event_loop().create_task(master.give_driver(driver))
    return await check_account_info(profile_name, account_details)


async def check_account_info(profile_name: str, account_details: AccountDetails) -> bool | str:
    account_requirements: AccountRequirements = await db.get_account_requirements()
    except_list = []
    exception_dict = accounts['inappropriate_account_types']
    if not account_details.avatar:
        except_list.append(exception_dict['not_avatar'])
    if not account_details.check_posts:
        except_list.append(exception_dict['not_posts'])
    if account_details.followers < account_requirements.min_followers:
        except_list.append(exception_dict['not_min_followers'])
    if account_details.following < account_requirements.min_following:
        except_list.append(exception_dict['not_min_following'])
    if account_details.creation_date > account_requirements.min_creation_date:
        except_list.append(exception_dict['not_min_date'])

    if except_list:
        return accounts['inappropriate_account'].format(profile_name[1:], f"<i>{', '.join(except_list)}</i>")
    else:
        return True
