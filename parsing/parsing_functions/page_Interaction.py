from asyncio import sleep

import pyppeteer.errors
from pyppeteer.page import Page

from parsing.elements_storage.elements_dictionary import subscribers_blocks, converter, scripts, other_blocks, \
    post_blocks, profile_blocks


# Декоратор для повторной загрузки страницы, если она слишком долго загружалась
def handle_timeout_error(func):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except pyppeteer.errors.TimeoutError:
            return await wrapper(*args, **kwargs)
    return wrapper


class PageInteraction:
    def __init__(self, page: Page, link: str):
        self.page = page
        self.link = link

    @handle_timeout_error
    async def open_first_users(self) -> str:
        await self.page.goto(self.link)
        await self.page.waitForSelector(converter(subscribers_blocks['username_block']))
        return await self.page.content()

    @handle_timeout_error
    async def open_first_posts(self) -> str:
        await self.page.goto(self.link, timeout=5000)
        await self.page.waitForSelector(converter(post_blocks['post_block']), timeout=5000)
        return await self.page.content()

    @handle_timeout_error
    async def open_one_post(self) -> str:
        await self.page.goto(self.link)
        await self.page.waitForSelector(converter(other_blocks['publish_button']))
        return await self.page.content()

    @handle_timeout_error
    async def open_profile(self) -> str:
        await self.page.goto(self.link)
        await self.page.waitForSelector(converter(profile_blocks['all_profile_info']))
        return await self.page.content()

    @handle_timeout_error
    async def open_some_page(self) -> str:
        await self.page.goto(self.link)
        await sleep(2)
        return await self.page.content()

    @handle_timeout_error
    async def scroll(self) -> str:
        await self.page.evaluate(scripts['scroll'])
        await sleep(1.5)
        return await self.page.content()
