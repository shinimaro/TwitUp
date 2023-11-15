import asyncio

from pyppeteer.page import Page

from databases.database import db
from parsing.main.elements_dictionary import subscribers_blocks, converter
from parsing.main.master_function import Master
from parsing.main.parsing_functions.find_functions import find_all_users, find_all_posts, find_all_retweets, \
    find_all_comments, find_comment
from parsing.main.parsing_functions.page_Interaction import PageInteraction


# Функция для поиска пользователя в лайках/ретвитах постах/подписках
async def parsing_user_list(page: Page, user: str, link: str, count_amount: int = 100) -> bool:
    users = set()
    page_interactions = PageInteraction(page, link)
    # Первоначальный поиск user из первых юзеров
    html = await page_interactions.open_first_users()
    users.update(await find_all_users(html, page))
    # Если не нашли юзера, уходим в цикл
    if user not in users:
        while len(users) <= count_amount:
            intermediate_len = len(users)
            # Берём новых пользователей
            html = await page_interactions.scroll()
            users.update(await find_all_users(html, page))
            # Нашли юзера всё ок
            if user in users:
                return True
            # Дошли до конца страницы
            if intermediate_len == len(users):
                break
    else:
        return True
    return False


# Функция, которая ищет пост среди лайкнувших
async def parsing_likes_in_posts(page: Page, post: str, link: str) -> bool:
    posts = set()
    page_interactions = PageInteraction(page, link)
    # Открытие страницы и сбор первых 2-3 постов
    html = await page_interactions.open_first_posts()
    posts.update(await find_all_posts(html, page))
    # Если среди первых постов не нашлось нужного, спускаемся к другим постам
    if post not in posts:
        while len(posts) <= 15:
            intermediate_len = len(posts)
            html = await page_interactions.scroll()
            posts.update(await find_all_posts(html, page))
            # Нашли нужный пост и всё ок
            if post in posts:
                return True
            # Если постов больше нет, останавливаем
            if intermediate_len == len(posts):
                break
    else:
        return True
    return False


# Функция для поиска ретвита на странице пользователя
async def parsing_retweets_in_posts(page: Page, post: str, link: str) -> bool:
    retweets = set()
    page_interactions = PageInteraction(page, link)
    # Открытие страницы и сбор первых 2-3 постов
    html = await page_interactions.open_first_posts()
    retweets.update(await find_all_retweets(html, page))
    # Если среди первых постов не нашлось нужного ретвита, спускаемся к другим постам
    if post not in retweets:
        while len(retweets) <= 8:
            intermediate_len = len(retweets)
            html = await page_interactions.scroll()
            retweets.update(await find_all_retweets(html, page))
            if post in retweets:
                return True
            # Т.к. непонятно, мы просто ретвитов не видим или постов не осталось, делаем ещё доп прокрутки (пока только одну)
            if intermediate_len == len(retweets):
                for _ in range(1):
                    intermediate_len = len(retweets)
                    html = await page_interactions.scroll()
                    retweets.update(await find_all_retweets(html, page))
                    if intermediate_len < len(retweets):
                        break
                else:
                    return False
    else:
        return True
    return False


# Функция для поиска нужного комментария среди постов пользователя
async def parsing_comments_in_posts(page: Page, post: str, user: str, link: str) -> str | bool:
    page_interactions = PageInteraction(page, link)
    html = await page_interactions.open_first_posts()
    all_posts = await find_all_comments(html, [], user, post, page)
    if not isinstance(all_posts, str):
        while len(all_posts) <= 15:
            intermediate_len = len(all_posts)
            html = await page_interactions.scroll()
            all_posts = await find_all_comments(html, all_posts, user, post, page)
            if isinstance(all_posts, str):
                return all_posts
            if intermediate_len == len(all_posts):
                break
    else:
        return all_posts
    return False


# Достаёт текст комментария, по ссылке, которую отправил пользователь
async def parsing_comment_text(tasks_msg_id, link_to_comment: str) -> str | bool | None:
    master = Master()
    driver = await master.get_driver()
    async with asyncio.timeout(15):
        try:
            page = (await driver.pages())[0]
            post = await db.get_link_for_comment(tasks_msg_id)
            user = await db.get_worker_username(tasks_msg_id)
            page_interactions = PageInteraction(page, link_to_comment)
            html = await page_interactions.open_one_post()
            comment_text = await find_comment(html, post, user, page)
            await master.give_driver(driver)
            return comment_text
        except asyncio.TimeoutError:
            await master.give_broke_driver(driver)
            return None
