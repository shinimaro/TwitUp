from asyncio import sleep

from pyppeteer.errors import TimeoutError, NetworkError
from pyppeteer.page import Page

from parsing.elements_storage.elements_dictionary import subscribers_blocks, converter, scripts, other_blocks, \
    post_blocks, profile_blocks


# Декоратор для повторной загрузки страницы, если она слишком долго загружалась
def handle_timeout_error(func):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except NetworkError:
            await sleep(1)
    return wrapper


class PageInteraction:

    def __init__(self, page: Page, link: str):
        self.page = page
        self.link = link
        self.timeout = 8000
        self.dop_timeout = 3000

    # @handle_timeout_error
    async def open_first_users(self) -> str:
        timeout = self.timeout
        try:
            if not self.page.isClosed():
                await self.page.goto(self.link)
                await self.page.waitForSelector(converter(subscribers_blocks['username_block']), timeout=timeout)
                html = await self.page.content()
                while not html:
                    await sleep(1)
                    html = await self.page.content()
                return html
        except TimeoutError:
            timeout += self.dop_timeout
            await self.open_first_users()

    # @handle_timeout_error
    async def open_first_posts(self) -> str:
        timeout = self.timeout
        try:
            if not self.page.isClosed():
                await self.page.goto(self.link, timeout=self.timeout)
                await self.page.waitForSelector(converter(post_blocks['post_block']), timeout=8000)
                html = await self.page.content()
                while not html:
                    await sleep(1)
                    html = await self.page.content()
                return html
        except TimeoutError:
            timeout += self.dop_timeout
            await self.open_first_posts()

    # @handle_timeout_error
    async def open_one_post(self) -> str:
        timeout = self.timeout
        try:
            if not self.page.isClosed():
                await self.page.goto(self.link, timeout=timeout)
                await self.page.waitForSelector(converter(other_blocks['publish_button']), timeout=timeout)
                html = await self.page.content()
                while not html:
                    await sleep(1)
                    html = await self.page.content()
                return html
        except TimeoutError:
            timeout += self.dop_timeout
            await self.open_one_post()

    # @handle_timeout_error
    async def open_profile(self) -> str:
        timeout = self.timeout
        try:
            if not self.page.isClosed():
                await self.page.goto(self.link, timeout=timeout)
                await self.page.waitForSelector(converter(profile_blocks['all_profile_info']), timeout=timeout)
                html = await self.page.content()
                while not html:
                    await sleep(1)
                    html = await self.page.content()
                return html
        except TimeoutError:
            timeout += self.dop_timeout
            await self.open_profile()

    # @handle_timeout_error
    async def open_some_page(self) -> str:
        timeout = self.timeout
        try:
            if not self.page.isClosed():
                await self.page.goto(self.link, timeout=timeout)
                await sleep(2)
                html = await self.page.content()
                while not html:
                    await sleep(1)
                    html = await self.page.content()
                return html
        except TimeoutError:
            timeout += self.dop_timeout
            await self.open_some_page()

    # @handle_timeout_error
    async def scroll(self) -> str:
        try:
            if not self.page.isClosed():
                await self.page.evaluate(scripts['scroll'])
                await sleep(1.5)
                html = await self.page.content()
                while not html:
                    await sleep(1)
                    html = await self.page.content()
                return html
        except TimeoutError:
            await self.scroll()
        except NetworkError:
            await self.scroll()
