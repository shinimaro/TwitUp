import asyncio
import os
import pickle

import aiofiles

from config import load_config
from parsing.main.elements_dictionary import login_blocks, converter, base_links

config = load_config()


# Функция для сохранения куки
async def save_cookies(cookies, login):
    async with aiofiles.open(f'../cookies/{login}_cookies.pkl', 'wb') as file:
        await file.write(pickle.dumps(cookies))


async def twitter_login(page, login, password):
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
            # Ожидаем минимальной прогрузки элементов главной страницы
            await page.waitForNavigation()
            # Сохраняем все куки в соответствующем фалйе, даже если он уже существует
            cookies = await page.cookies()
            await save_cookies(cookies, login)
            break
        except TimeoutError:
            timeout += 5000
    else:
        print(f'Ошибка авторизации аккаунта {login}')
