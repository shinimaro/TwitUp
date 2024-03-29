import asyncio
import os
import pickle
import re
from asyncio import gather
from asyncio import sleep
from typing import TypedDict

import aiofiles
import pyppeteer.errors
from aiogram import Bot
from pyppeteer.browser import Browser
from pyppeteer.page import Page

from bot_apps.bot_parts.panels.admin_panel.notification import send_notification_to_admin
from bot_apps.other_apps.wordbank import notifications_to_admin
from config import load_config
from parsing.elements_storage.elements_dictionary import other_blocks, converter, base_links
from parsing.manage_webdrivers.start_webdriver.webdriver import Webdrivers

config = load_config()
bot = Bot(token=config.tg_bot.token)


class WatchmanWebdriver(TypedDict):
    page: Page
    driver: Browser


class Master:
    usable_drivers_queue = asyncio.Queue(maxsize=config.webdrivers.num_webdrivers)
    driver_counter = 0
    watchman_webdriver: WatchmanWebdriver = {'page': None, 'driver': None}

    # Генерация всех базовых вебдрайверов
    async def generate_main_driver(self) -> None:
        await self._watchman_webdriver_activate()  # Сразу создадим сторож-вебдрайвер для просмотра пепещиков
        while self.usable_drivers_queue.qsize() < config.webdrivers.num_webdrivers:
            tasks = [self._generate() for _ in range(min(config.webdrivers.webdrivers_at_once,
                                                         config.webdrivers.num_webdrivers - self.usable_drivers_queue.qsize()))]
            await gather(*tasks)

            # await bot.send_message(chat_id=1338827549, text=f'Вебдрайверов готово: {self.usable_drivers_queue.qsize()}. Осталось сгенерировать вебдрайверов: {config.webdrivers.num_webdrivers - self.usable_drivers_queue.qsize()}')
            print(f'Вебдрайверов готово: {self.usable_drivers_queue.qsize()}. Осталось сгенерировать вебдрайверов: {config.webdrivers.num_webdrivers - self.usable_drivers_queue.qsize()}')
        self.change_driver_couter(self.usable_drivers_queue.qsize())

    # Генерация нового вебдрайвера для добавления его в очередь
    async def _generate(self) -> None:
        webdrivers = Webdrivers()
        driver = await webdrivers.webdriver()
        if not self.usable_drivers_queue.full() and driver:  # Если очередь не заполнена и на выходе мы получили готовый вебдрайвер
            await self.usable_drivers_queue.put(driver)
        elif driver:  # Если очередь всё же заполнена, то, во избежание загрузки лишних вебдрайверов, вебдрайвер закрывается
            await self.close_driver(driver)

    # Функция для включения вебдрайвера-сторожа для парсинга пепещиков
    async def _watchman_webdriver_activate(self) -> None:
        webdrivers = Webdrivers()
        while not self.watchman_webdriver['driver']:
            driver = await webdrivers.webdriver()
            if driver:
                self.watchman_webdriver['driver'] = driver
        self.watchman_webdriver['page'] = (await driver.pages())[0]
        page: Page = self.watchman_webdriver['page']
        await page.goto(base_links['followers_page'])

    # Функция для обновления вебдрайвера сторожа
    async def update_watchman_webdriver(self) -> None:
        new_driver = await self.get_driver()
        await self.give_driver(self.watchman_webdriver['driver'])
        self.watchman_webdriver['driver'] = new_driver
        self.watchman_webdriver['page'] = (await new_driver.pages())[0]
        page: Page = self.watchman_webdriver['page']
        await page.goto(base_links['followers_page'])

    # Закрытие вебдрайвера через закрытие всех его страниц
    async def close_driver(self, driver: Browser) -> None:
        await asyncio.gather(*[page.close() for page in await driver.pages()])
        self.change_driver_couter(-1)

    # Закрытие всех лишних страниц в вебдрайвере
    @staticmethod
    async def close_pages(driver) -> None:
        await driver.newPage()
        await asyncio.gather(*[page.close() for page in (await driver.pages())[:-1]])

    # Достать драйвер
    async def get_driver(self) -> Browser:
        # Если в очереди есть вебдрайвер, достаём его
        if not self.usable_drivers_queue.empty():
            return await self.usable_drivers_queue.get()
        # Если нет, создаём новый
        else:
            await self.waiting_before_adding()
            self.change_driver_couter(1)
            webdrivers = Webdrivers()
            driver = None
            while not driver:
                driver = await webdrivers.webdriver()
            return driver

    # Ожидание перед созданием дополнительного вебдрайвера
    @classmethod
    async def waiting_before_adding(cls):
        while cls.driver_counter >= config.webdrivers.max_webdrivers:
            await sleep(2)

    # Вернуть драйвер
    async def give_driver(self, driver: Browser) -> None:
        # Если очередь ещё не заполнена, добавляем в неё новый драйвер, перед этим закрывая лишние окна
        if not self.usable_drivers_queue.full():
            await self.close_pages(driver)
            await self.usable_drivers_queue.put(driver)
        # Если нет, просто удаляем
        else:
            await self.close_driver(driver)

    @classmethod
    def change_driver_couter(cls, num: int) -> None:
        cls.driver_counter += num

    # Функция, в которую будут складывать не рабочие вебдрайверы (должна заменять вебдрайвер, проверять его на работоспособность и, если что-то с аккаунтом, то удалять такой файл и сообщать об этом (наверное изменять название файла на брокен + логин аккаунта)
    async def give_broke_driver(self, driver: Browser) -> None:
        await self.close_pages(driver)
        page = (await driver.pages())[0]
        # Провеяем, заходит ли вебдрайвер на главную страницу или он косячный
        if not await self.check_driver(page):
            # Берём куки и закрываем драйвер
            cookies = (await page.cookies())[0]
            await self.close_driver(driver)
            # Находим папку с куками всех аккаунтов
            current_file_dir = os.path.dirname(__file__)
            file_path = os.path.join(current_file_dir, '.', 'cookies/')
            for file_name in os.listdir(file_path):
                # Находим аккаунт с нашими куки
                full_file_path = os.path.join(file_path, file_name)
                async with aiofiles.open(full_file_path, 'rb') as file:
                    cookies_list = pickle.loads(await file.read())
                values = [cookie for cookie in cookies_list if cookie['value'] == cookies['value']]
                # Если мы нашли этот аккаунт, убираем его из бота
                if values:
                    account = '@' + re.findall(r'@([^_]+)_cookies\.pkl$', full_file_path)[-1]
                    print(f'Вебдрайвер по логину {account} сломался, убираю его из системы')
                    # Удаляем куки сломанного аккаунта
                    os.remove(os.path.join(full_file_path))
                    # Удаляем строку из списка аккаунтов
                    text_file = os.path.join(current_file_dir, '..', '..', 'accounts.txt')
                    async with aiofiles.open(text_file, 'r', encoding='utf-8') as file:
                        accounts = await file.readlines()
                    deleted_line_info = None
                    for index in range(len(accounts)):
                        if accounts[index].startswith(account):
                            deleted_line_info = accounts[index]
                            del accounts[index]
                            async with aiofiles.open(text_file, 'w', encoding='utf-8') as file:
                                await file.writelines(accounts)
                            break
                    # Отправка сообщения админу о том, какой аккаунт убрали из базы
                    await send_notification_to_admin(text=notifications_to_admin['account_crashed'].format(account, deleted_line_info))
                    break
            else:
                print('Какой-то аккаунт оказался сломанным, но я его не нашёл')
        # Если вебдрайвер не оказался сломанным, просто отправляем его в очередь
        else:
            await self.give_driver(driver)

    # Проверка драйвера на то, что он может загрузить главную страницу и всё ок
    @staticmethod
    async def check_driver(page: Page) -> bool:
        try:
            await page.goto(base_links['home_page'], timeout=15000)
            await page.waitForSelector(converter(other_blocks['publish_button']), timeout=15000)
            await page.goto('about:blank')
            return True
        except pyppeteer.errors.TimeoutError:
            return False

