import asyncio
from asyncio import sleep
from typing import Literal

from bs4 import BeautifulSoup
from pyppeteer.browser import Browser
from pyppeteer.page import Page

from parsing.main.elements_dictionary import post_blocks, profile_blocks
from parsing.main.master_function import Master
from parsing.main.parsing_functions.page_Interaction import PageInteraction


# Проверка поста/аккаунта на то, что он существует на самом деле
async def existence_parser(link: str, what_check: Literal['profile', 'post']) -> bool:
    driver, page = await _get_page()
    try:
        async with asyncio.timeout(25):
            html_page = await _get_html_page(page, link)
            result = await _existence_check_post(html_page, what_check)
            await _return_driver(driver)
    except TimeoutError:
        result = True  # Т.к. это наш косяк, всё равно разрешаем посту пройти
        await _return_broke_driver(driver)
    print(result)
    return result


# Проверка ссылки на то, что там есть теги, которые есть в любом посте
async def _existence_check_post(html_page, what_check: Literal['account', 'post']) -> bool:
    soup = BeautifulSoup(html_page, 'lxml')
    # Если нужно найти пост, либо только аккаунт
    check = soup.find('div', class_=post_blocks['username_author']) if what_check == 'post' else \
        soup.find('div', class_=profile_blocks['all_profile_info'])
    if check:
        return True
    return False


# Фанкшин, достающий новую страницу из хранилища вебдрайверов
async def _get_page() -> tuple[Browser, Page]:
    master = Master()
    driver = await master.get_driver()
    page = (await driver.pages())[0]
    return driver, page


# Фанкшин, возвращающий вебдрайвер обратно
async def _return_driver(driver: Browser) -> None:
    master = Master()
    await master.give_driver(driver)


# фанкшин, возвращающий вебдрайвер в сломанный
async def _return_broke_driver(driver: Browser) -> None:
    master = Master()
    await master.give_broke_driver(driver)

# Выдать html страничку
async def _get_html_page(page: Page, link: str) -> str:
    page_interaction = PageInteraction(page, link)
    await page_interaction.open_first_posts()
    return await page.content()
