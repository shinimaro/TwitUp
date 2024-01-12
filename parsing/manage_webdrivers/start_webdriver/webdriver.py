import os
import pickle
from dataclasses import dataclass
from typing import IO, Callable, Optional

import aiofiles
import pyppeteer
from pyppeteer import errors
from pyppeteer import launch
from pyppeteer.browser import Browser
from pyppeteer.page import Page

from config.config import load_config
from parsing.elements_storage.elements_dictionary import other_blocks, converter, login_blocks, base_links
from parsing.manage_webdrivers.start_webdriver.twitter_login import twitter_login

config = load_config()


@dataclass(frozen=True, slots=True)
class Proxy:
    proxy_host: str
    proxy_port: str
    proxy_login: str
    proxy_password: str


@dataclass(frozen=True, slots=True)
class TwitterAccount:
    password: str
    proxy: Proxy


async def webdriver():
    pass

class Webdrivers:
    headless_mode: bool = True
    twitter_accounts: dict[str, TwitterAccount] = {}
    account_generator: Optional[Callable] = None
    current_page: Page = None
    current_driver: Browser = None
    current_login: str = None

    # Создание нового вебдрайвера
    async def webdriver(self) -> Browser:
        await self._set_current_login()
        await self._set_current_driver()
        await self._set_current_page()
        await self._load_cookie()
        await self._set_proxy_autentification()
        if await self._load_base_twitter_url():
            return Webdrivers.current_driver
        else:
            await Webdrivers.current_driver.close()

        # Пример настройки мобильного прокси, которое pypetter сам будет менять
        # proxy_endpoint = "http://username:password@p.webshare.io:80"
        # browser = await launch(args=[f'--proxy-server={proxy_endpoint}'])

    async def _set_current_login(self) -> None:
        """Выдать новый логин аккаунта"""
        if Webdrivers.account_generator:
            Webdrivers.current_login = next(Webdrivers.account_generator)
        else:
            # Если генератор не был инициализирован, делаем распаковку и инициализацию
            self._start_webdriver()
            Webdrivers.current_login = next(Webdrivers.account_generator)

    def _start_webdriver(self):
        # Формирование словаря и инициализация общего генератора
        self._unpacking_twitter_accounts()
        Webdrivers.account_generator = self._issue_new_account()

    def _unpacking_twitter_accounts(self):
        """Формирование словаря с аккаунтами"""
        file_path = self._get_accounts_file_path()
        with open(file_path, 'r', encoding='utf-8') as file:
            all_accounts = file.read()
        for info in all_accounts.split('\n'):
            info_list = info.split(':')
            Webdrivers.twitter_accounts[info_list[0]] = TwitterAccount(
                password=info_list[1],
                proxy=Proxy(proxy_host=info_list[2],
                            proxy_port=info_list[3],
                            proxy_login=info_list[4],
                            proxy_password=info_list[5]))

    @classmethod
    def _issue_new_account(cls) -> str:
        """Генератор для выдачи нового аккаунта"""
        while True:
            for login in cls.twitter_accounts:
                yield login

    async def _set_current_driver(self):
        proxy_server = self._get_proxy_server()
        Webdrivers.current_driver = await launch(headless=Webdrivers.headless_mode, args=[proxy_server])

    @classmethod
    def _get_proxy_server(cls) -> str:
        return f"--proxy-server={cls.twitter_accounts[cls.current_login].proxy.proxy_host}:{cls.twitter_accounts[cls.current_login].proxy.proxy_port}"

    @classmethod
    async def _set_current_page(cls):
        cls.current_page = (await cls.current_driver.pages())[0]

    @classmethod
    async def _set_proxy_autentification(cls):
        await cls.current_page.authenticate(
            {'username': Webdrivers.twitter_accounts[Webdrivers.current_login].proxy.proxy_login,
             'password': Webdrivers.twitter_accounts[Webdrivers.current_login].proxy.proxy_password})

    async def _load_cookie(self):
        cookies = await self._load_cookies()
        await Webdrivers.current_page.setCookie(*cookies)

    async def _load_cookies(self) -> IO[bytes]:
        """Загрузка cookie"""
        file_path = self._get_cookies_file_path()
        async with aiofiles.open(file_path, 'rb') as file:
            return pickle.loads(await file.read())

    async def _load_base_twitter_url(self) -> bool:
        """Загрузка главной страницы твиттера и проверка на то, что аккаунт залогинен"""
        timeout = 10000
        for _ in range(2):
            try:
                await Webdrivers.current_page.goto(base_links['home_page'], timeout=timeout)
                break
            except pyppeteer.errors.TimeoutError:
                timeout += 10000
        else:
            print(f'Не удалось загрузить страницу в {Webdrivers.current_login}')
            return False
        return await self._check_home_page()

    async def _check_home_page(self) -> bool:
        try:
            # Если бот находится на домашней странице и всё ок
            await Webdrivers.current_page.waitForSelector(converter(other_blocks['publish_button']), timeout=5000)
            return True
        except pyppeteer.errors.TimeoutError:
            # Если бота выкинуло на страницу для входа в аккаунт
            return await self._login_account()

    @classmethod
    async def _login_account(cls):
        """Попытка залогинить аккаунт"""
        try:
            await cls.current_page.goto(base_links['login_page'])
            await cls.current_page.waitForSelector(login_blocks['username_input'], timeout=8000)
            password = cls.twitter_accounts[cls.current_login].password
            print(f'Пробую залогинить аккаунт {cls.current_login}')
            await twitter_login(cls.current_page, cls.current_login, password)
            return True
        except pyppeteer.errors.TimeoutError:
            print(f'Аккаунт {cls.current_login} попал куда-то непонятно куда, ни на страницу для входа, ни на домашнюю страницу')
            return False

    @staticmethod
    def _get_accounts_file_path() -> str:
        """Выдать путь до файла с аккаунтами"""
        current_file_dir = os.path.dirname(__file__)
        return os.path.join(current_file_dir, '../..', '..', 'accounts.txt')

    @classmethod
    def _get_cookies_file_path(cls) -> str:
        """Выдать путь до куки"""
        current_file_dir = os.path.dirname(__file__)
        return os.path.join(current_file_dir, '..', f'./cookies/{cls.current_login}_cookies.pkl')
