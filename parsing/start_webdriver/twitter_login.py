from asyncio import sleep

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys


async def login_in_twitter(driver, login: str, password: str) -> None:

    for i in range(3):
        try:
            driver.get('https://www.twitter.com/login')
            await sleep(3 + i)

            username = driver.find_element_by_xpath('//input[@name="text"]')
            username.send_keys(login)
            await sleep(1)
            username.send_keys(Keys.RETURN)
            await sleep(2)

            password_in_twitter = driver.find_element_by_xpath('//input[@name="password"]')
            password_in_twitter.send_keys(password)
            await sleep(1)
            password_in_twitter.send_keys(Keys.RETURN)
            await sleep(3)
            break
        except NoSuchElementException:
            await sleep(1 + i)
            continue
    else:
        print('Ошибка авторизации')
        exit()
