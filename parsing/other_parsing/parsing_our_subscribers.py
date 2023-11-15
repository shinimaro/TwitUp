import asyncio
import time

from pyppeteer.page import Page
from asyncio import sleep
from parsing.main.elements_dictionary import subscribers_blocks, converter
from parsing.main.master_function import Master
from parsing.main.parsing_functions.find_functions import find_all_users


class AllOurUsers:
    # Временное хранилище, вместо редиса
    all_our_users: set[str] = set()
    all_our_users_lock = asyncio.Lock()
    last_update_time = time.time()
    seconds_waiting = 5
    common_page: Page = None
    master = Master()

    # Генератор, в котором содержатся последние пепещики и, если прошло уже достаточно времени, он обновляет пепещикав
    async def get_all_our_users(self):
        if time.time() - self.last_update_time >= self.seconds_waiting and \
                not self.all_our_users_lock.locked():  # Если прошло много секунд с последнего апдейта и в данный момент не производится новый апдейт
            all_users = await self.parsing_our_subscribers()
            self.last_update_time = time.time()
            return all_users
        else:
            return self.all_our_users

    # Функция для парсинга наших подписчиков
    async def parsing_our_subscribers(self):
        async with self.all_our_users_lock:
            try:
                async with asyncio.timeout(30):
                    self.common_page: Page = self.master.watchman_webdriver['page']
                    while True:
                        result = await self._update_page(converter(subscribers_blocks['username_block']))
                        if not result:  # Если страница не прогрузилась и пришлось обновить вебдрайвер
                            self.common_page: Page = self.master.watchman_webdriver['page']  # Обновляем страницу
                            continue
                        users = set()
                        # while len(users) < 15:
                        while len(users) < 1:
                            await asyncio.sleep(1)
                            html = await self.common_page.content()
                            users.update(await find_all_users(html, self.common_page))
                        self.all_our_users = users
            except TimeoutError:
                pass
            finally:
                return self.all_our_users

    # Обновление страницы с пепещиками
    async def _update_page(self, element: str):
        timeout = 6000
        while timeout < 10000:
            try:
                await self.common_page.reload()
                await self.common_page.waitForSelector(element)
                return True
            except TimeoutError:
                timeout += 4000
        # Если всё же страница не обновилась
        await self.master.update_watchman_webdriver()
        return False
