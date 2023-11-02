import asyncio
import os
import pickle
from typing import IO

import aiofiles
import pyppeteer
from pyppeteer import errors
from pyppeteer import launch
from pyppeteer.browser import Browser
from pyppeteer.page import Page

from config.config import load_config
from parsing.main.elements_dictionary import other_blocks, converter, login_blocks
from parsing.start_webdriver.twitter_login import twitter_login

config = load_config()

twitter_accounts = {}


# Формирование словаря с аккаунтами
def unpacking_twitter_accounts():
    current_file_dir = os.path.dirname(__file__)
    file_path = os.path.join(current_file_dir, '..', '..', 'accounts.txt')
    with open(file_path, 'r', encoding='utf-8') as file:
        all_accounts = file.read()
    for info in all_accounts.split('\n'):
        info_list = info.split(':')
        twitter_accounts[info_list[0]] = {'password': info_list[1],
                                          'proxy': {'proxy_host': info_list[2],
                                                    'proxy_port': info_list[3]}}


# Генератор для выдачи нового аккаунта
def issue_new_account():
    while True:
        for login in twitter_accounts:
            yield login


# Формирование словаря и инициализация общего генератора
unpacking_twitter_accounts()
account_generator = issue_new_account()


# Загрузка cookie
async def load_cookies(login: str) -> IO[bytes]:
    current_file_dir = os.path.dirname(__file__)
    file_path = os.path.join(current_file_dir, '..', f'cookies/{login}_cookies.pkl')
    async with aiofiles.open(file_path, 'rb') as file:
        return pickle.loads(await file.read())


# Загрузка главной страницы твиттера и проверка на то, что аккаунт залогинен
async def load_base_twitter_url(page: Page, login: dict) -> bool:
    timeout = 30000
    for _ in range(2):
        try:
            await page.goto('https://twitter.com/home', timeout=timeout)
            break
        except pyppeteer.errors.TimeoutError:
            timeout += 10000
    else:
        print(f'Не удалось загрузить страницу в {login}')
        return False

    try:
        # Если бот находится на домашней странице и всё ок
        await page.waitForSelector(converter(other_blocks['publish_button']), timeout=3000)
        return True
    except pyppeteer.errors.TimeoutError:
        try:
            # Если бота выкинуло на страницу для входа в аккаунт
            await page.waitForSelector(login_blocks['username_input'], timeout=3000)
            password = twitter_accounts[login]['password']
            print(f'Пробую залогинить аккаунт {login}')
            await twitter_login(page, login, password)
            return False
        except pyppeteer.errors.TimeoutError:
            print(f'Аккаунт {login} попал куда-то непонятно куда, ни на страницу для входа, ни на домашнюю страницу')
            return False


# Создание нового вебдрайвера
async def webdriver() -> Browser:
    login = next(account_generator)
    proxy = f"http://{twitter_accounts[login]['proxy']['proxy_host']}:{twitter_accounts[login]['proxy']['proxy_port']}"
    driver = await launch(headless=False, args=[f'--proxy-server={proxy}'])
    page = (await driver.pages())[0]
    cookies = await load_cookies(login)
    await page.setCookie(*cookies)
    if await load_base_twitter_url(page, login):
        return driver
    else:
        await driver.close()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    driver = loop.run_until_complete(webdriver())
