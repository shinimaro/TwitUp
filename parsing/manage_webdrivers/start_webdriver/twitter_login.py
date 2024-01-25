import os
import pickle
from asyncio import sleep

import aiofiles
from pyppeteer.page import Page

from config import load_config
from parsing.elements_storage.elements_dictionary import login_blocks, converter, base_links

config = load_config()


# Функция для сохранения куки
async def save_cookies(cookies, login: str) -> None:
    current_file_dir = os.path.dirname(__file__)
    file_path = os.path.join(current_file_dir, '..', f'./cookies/{login}_cookies.pkl')
    async with aiofiles.open(file_path, 'wb') as file:
        await file.write(pickle.dumps(cookies))


async def twitter_login(page: Page, login: str, password: str, ) -> bool:
    timeout = 5000
    for _ in range(3):
        try:
            await page.goto(base_links['login_page'])
            # Ввод логина
            await page.waitForSelector(login_blocks['username_input'], timeout=timeout)
            await page.type(login_blocks['username_input'], login)
            # Нажатие на кнопку "далее"
            await page.waitForSelector(converter(login_blocks['next_button']), timeout=timeout)
            await page.click(converter(login_blocks['next_button']))
            # Ввод пароля
            await page.waitForSelector(login_blocks['password_input'], timeout=timeout)
            await page.type(login_blocks['password_input'], password)
            # Нажатие на кнопку авторизации
            await page.waitForSelector(login_blocks['login_button'], timeout=timeout)
            await page.click(login_blocks['login_button'])
            await sleep(2)  # Небольшая задержка после логирования
            # Ожидаем минимальной прогрузки элементов главной страницы
            await page.goto(base_links['home_page'], timeout=timeout)
            # Сохраняем/обновляем все куки в соответствующем файле
            cookies = await page.cookies()
            await save_cookies(cookies, login)
            return True
        except TimeoutError:
            timeout += 5000
    else:
        print(f'Ошибка авторизации аккаунта {login}')
        return False



