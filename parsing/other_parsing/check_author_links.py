from asyncio import gather
from typing import TypedDict

from pyppeteer.page import Page

from databases.dataclasses_storage import LinkAction
from parsing.manage_webdrivers.master_function import Master
from parsing.parsing_functions.parsing_functions import checking_account_for_life, check_post_for_like


class CheckAuthorLinks(TypedDict):
    profile: bool
    post: bool


async def check_author_links(check_dict: CheckAuthorLinks, link_actions: LinkAction):
    """Проверяет указанные ссылки в задании на жизнь"""
    tasks = []
    master = Master()
    driver = await master.get_driver()
    page_profile = (await driver.pages())[0] if link_actions.account_link else None
    page_post = (await driver.pages())[0] if not link_actions.account_link else await driver.newPage()
    if link_actions.account_link:
        tasks.append(_checking_author_profile(check_dict, page_profile, link_actions.account_link))
    if link_actions.post_link:
        tasks.append(_checkig_author_post(check_dict, page_post, link_actions.post_link))
    await gather(*tasks)
    await master.give_driver(driver)


async def _checking_author_profile(check_dict: CheckAuthorLinks, page: Page, profile_link) -> None:
    """Фанкшин, проверяющий профиль автора на жизнь"""
    ban = await checking_account_for_life(page, profile_link)
    check_dict['profile'] = True if not ban else False


async def _checkig_author_post(check_dict, page: Page, post_link) -> None:
    """Фанкшин, проверяющий пост автора на жизнь"""
    result = await check_post_for_like(page, post_link)
    check_dict['post'] = True if not result else False
