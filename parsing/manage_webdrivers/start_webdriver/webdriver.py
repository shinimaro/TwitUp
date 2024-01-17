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

    def __init__(self):
        self.current_login: str = Webdrivers._set_current_login()
        self.current_page: Optional[Page] = None
        self.current_driver: Optional[Browser] = None

    # Создание нового вебдрайвера
    async def webdriver(self) -> Browser:
        await self._set_current_driver()
        await self._set_current_page()
        await self._load_cookie()
        await self._set_proxy_autentification()
        if await self._load_base_twitter_url():
            return self.current_driver
        else:
            await self.current_driver.close()
            await self.webdriver()

        # Пример настройки мобильного прокси, которое pypetter сам будет менять
        # proxy_endpoint = "http://username:password@p.webshare.io:80"
        # browser = await launch(args=[f'--proxy-server={proxy_endpoint}'])

    @classmethod
    def _set_current_login(cls) -> str:
        """Выдать новый логин аккаунта"""
        if Webdrivers.account_generator:
            return next(Webdrivers.account_generator)
        else:
            # Если генератор не был инициализирован, делаем распаковку и инициализацию
            cls._start_webdriver()
            return next(Webdrivers.account_generator)

    @classmethod
    def _start_webdriver(cls):
        # Формирование словаря и инициализация общего генератора
        cls._unpacking_twitter_accounts()
        Webdrivers.account_generator = cls._issue_new_account()

    @classmethod
    def _unpacking_twitter_accounts(cls):
        """Формирование словаря с аккаунтами"""
        file_path = cls._get_accounts_file_path()
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
        self.current_driver = await launch(headless=Webdrivers.headless_mode, args=[proxy_server])

    def _get_proxy_server(self) -> str:
        return f"--proxy-server={Webdrivers.twitter_accounts[self.current_login].proxy.proxy_host}:{Webdrivers.twitter_accounts[self.current_login].proxy.proxy_port}"

    async def _set_current_page(self):
        self.current_page = (await self.current_driver.pages())[0]

    async def _set_proxy_autentification(self):
        await self.current_page.authenticate(
            {'username': Webdrivers.twitter_accounts[self.current_login].proxy.proxy_login,
             'password': Webdrivers.twitter_accounts[self.current_login].proxy.proxy_password})

    async def _load_cookie(self):
        cookies = await self._load_cookies()
        await self.current_page.setCookie(*cookies)

    async def _load_cookies(self) -> IO[bytes]:
        """Загрузка cookie"""
        file_path = self._get_cookies_file_path()
        async with aiofiles.open(file_path, 'rb') as file:
            return pickle.loads(await file.read())

    async def _load_base_twitter_url(self) -> bool:
        """Загрузка главной страницы твиттера и проверка на то, что аккаунт залогинен"""
        timeout = 5000
        for _ in range(3):
            try:
                await self.current_page.goto(base_links['home_page'], timeout=timeout)
                await self.current_page.waitForSelector(converter(other_blocks['publish_button']), timeout=timeout)
                return True
            except pyppeteer.errors.TimeoutError:
                timeout += 10000
        else:
            print(f'Не удалось загрузить страницу в {self.current_login}')
            return await self._login_account()

    async def _login_account(self):
        """Попытка залогинить аккаунт"""
        try:
            await self.current_page.goto(base_links['login_page'])
            await self.current_page.waitForSelector(login_blocks['username_input'], timeout=8000)
            password = Webdrivers.twitter_accounts[self.current_login].password
            print(f'Пробую залогинить аккаунт {self.current_login}')
            return await twitter_login(self.current_page, self.current_login, password)
        except pyppeteer.errors.TimeoutError:
            print(f'Аккаунт {self.current_login} попал куда-то непонятно куда, ни на страницу для входа, ни на домашнюю страницу')
            return False

    @staticmethod
    def _get_accounts_file_path() -> str:
        """Выдать путь до файла с аккаунтами"""
        current_file_dir = os.path.dirname(__file__)
        return os.path.join(current_file_dir, '../..', '..', 'accounts.txt')

    def _get_cookies_file_path(self) -> str:
        """Выдать путь до куки"""
        current_file_dir = os.path.dirname(__file__)
        return os.path.join(current_file_dir, '..', f'./cookies/{self.current_login}_cookies.pkl')
