import asyncio
from dataclasses import dataclass

from pyppeteer.page import Page

from databases.database import Database
from databases.dataclasses_storage import AccountDetails
from parsing.manage_webdrivers.master_function import Master
from parsing.parsing_functions.find_functions import find_all_users, find_all_posts, find_all_retweets, \
    find_all_comments, find_comment, find_ban_block, find_number_subs, find_post_block, check_profile_avatar, \
    get_date_create_account, check_post_on_profile
from parsing.parsing_functions.page_Interaction import PageInteraction

db = Database()


# Функция для поиска пользователя в лайках/ретвитах постах/подписках
async def parsing_user_list(page: Page, user: str, link: str, count_amount: int | float = 100) -> bool:
    users = []
    page_interactions = PageInteraction(page, link)
    # Первоначальный поиск user из первых юзеров
    html = await page_interactions.open_first_users()
    users.extend(user for user in (await find_all_users(html, page, [])) if user not in users)
    # Если не нашли юзера, уходим в цикл
    if user not in users:
        while len(users) <= count_amount:
            intermediate_len = len(users)
            # Берём новых пользователей
            html = await page_interactions.scroll()
            users.extend(user for user in (await find_all_users(html, page, [])) if user not in users)
            # Нашли юзера всё ок
            if user in users:
                return True
            # Дошли до конца страницы
            if intermediate_len == len(users):
                break
    else:
        return True
    return False


async def parsing_user_subscriptions(page: Page, user: str, link: str) -> list[str] | bool:
    """Функция для сбора всех юзеров в список для функции по поиску в подписчиках"""
    users = []
    page_interactions = PageInteraction(page, link)
    html = await page_interactions.open_first_users()
    users.extend(username for username in await find_all_users(html, page, []) if username not in users)
    if user not in users:
        while True:
            intermediate_len = len(users)
            html = await page_interactions.scroll()
            users.extend(user for user in await find_all_users(html, page, []) if user not in users)
            if user in users:
                html = await page_interactions.scroll()
                users.extend(username for username in await find_all_users(html, page, []) if username not in users)
                return users
            if intermediate_len == len(users):
                break
    else:
        html = await page_interactions.scroll()
        users.extend(username for username in await find_all_users(html, page, []) if username not in users)
        return users
    return False  # Юзер не был найден


# Функция, которая ищет пост среди других постов
async def parsing_in_posts(page: Page, post: str, link: str, number_amount: int | float = 15) -> bool:
    posts = set()
    page_interactions = PageInteraction(page, link)
    # Открытие страницы и сбор первых 2-3 постов
    html = await page_interactions.open_first_posts()
    posts.update(await find_all_posts(html, page))
    # Если среди первых постов не нашлось нужного, спускаемся к другим постам
    if post not in posts:
        while len(posts) <= number_amount:
            intermediate_len = len(posts)
            html = await page_interactions.scroll()
            # print('Получил html страницу после scroll', html)
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


# Функция ищущая ретвиты на странице пользователя (больше не ищет, т.к. просто перестала видеть теги о репосте)
async def parsing_retweets_in_posts(page: Page, post: str, link: str, number_amount: int = 8) -> bool:
    retweets = set()
    page_interactions = PageInteraction(page, link)
    # Открытие страницы и сбор первых 2-3 постов
    html = await page_interactions.open_first_posts()
    retweets.update(await find_all_retweets(html, page))
    # Если среди первых постов не нашлось нужного ретвита, спускаемся к другим постам
    if post not in retweets:
        while len(retweets) <= number_amount:
            intermediate_len = len(retweets)
            html = await page_interactions.scroll()
            retweets.update(await find_all_retweets(html, page))
            if post in retweets:
                return True
            # Т.к. непонятно, мы просто ретвитов не видим или постов не осталось, делаем ещё доп прокрутку
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
async def parsing_comments_in_posts(page: Page, post: str, user: str, link: str, number_amount: int = 15) -> tuple[str, str] | bool:
    page_interactions = PageInteraction(page, link)
    html = await page_interactions.open_first_posts()
    all_posts, com_link = await find_all_comments(html, [], user, post, page)
    if not isinstance(all_posts, str):
        while len(all_posts) <= number_amount:
            intermediate_len = len(all_posts)
            html = await page_interactions.scroll()
            all_posts, com_link = await find_all_comments(html, all_posts, user, post, page)
            if isinstance(com_link, str):
                return all_posts, com_link
            if intermediate_len == len(all_posts):
                break
    else:
        return all_posts, com_link
    return False


# Достаёт текст комментария, по ссылке, которую отправил пользователь
async def parsing_comment_text(tasks_msg_id, link_to_worker_comment: str) -> str | None:
    master = Master()
    driver = await master.get_driver()
    async with asyncio.timeout(20):
        try:
            page = (await driver.pages())[0]
            post = await db.get_link_for_comment(tasks_msg_id)
            username = await db.get_worker_username(tasks_msg_id)
            comment_text = await get_comment_text(page, post, username, link_to_worker_comment)
            await master.give_driver(driver)
            return comment_text
        except asyncio.TimeoutError:
            await master.give_broke_driver(driver)
            return None


async def get_comment_text(page: Page, post: str, username: str, link_to_worker_comment: str) -> str | None:
    """Достать текст комментария"""
    page_interactions = PageInteraction(page, link_to_worker_comment)
    html = await page_interactions.open_one_post()
    comment_text = await find_comment(html, post, username, page)
    return comment_text


async def checking_account_for_life(page: Page, profile_link: str) -> bool:
    """Проверка аккаунта на жизнь"""
    page_interactions = PageInteraction(page, profile_link)
    html = await page_interactions.open_some_page()
    return await find_ban_block(html, page)


async def check_post_for_like(page: Page, post_link: str) -> bool:
    """Проверка поста на жизнь"""
    page_interactions = PageInteraction(page, post_link)
    html = await page_interactions.open_some_page()
    return await find_post_block(html, page)


async def get_users_list(page: Page, link: str) -> list[str]:
    """Получить список всех доступных юзеров в подписках/подписчиках"""
    users_list = []
    page_interactions = PageInteraction(page, link)
    html = await page_interactions.open_first_users()
    users_list.extend(user for user in await find_all_users(html, page, []) if user not in users_list)
    while True:
        intermediate_len = len(users_list)
        # Берём новых пользователей
        html = await page_interactions.scroll()
        users_list.extend(user for user in await find_all_users(html, page, []) if user not in users_list)
        # Дошли до конца страницы
        if intermediate_len == len(users_list):
            await asyncio.sleep(2)
            html = await page_interactions.scroll()
            users_list.extend(user for user in await find_all_users(html, page, []) if user not in users_list)
            if intermediate_len == len(users_list):
                return users_list


async def get_number_subs(page: Page, profile_link: str, find_subscribers_flag: bool = True) -> int | None:
    """Получить число подписчиков/подписок"""
    page_interactions = PageInteraction(page, profile_link)
    html = await page_interactions.open_profile()
    return await find_number_subs(html, page, find_subscribers_flag)


async def get_account_info(page: Page, profile_link: str) -> AccountDetails:
    """Получить всю информацию об аккаунте одним заходом"""
    page_interactions = PageInteraction(page, profile_link)
    html = await page_interactions.open_profile()
    return AccountDetails(
        avatar=check_profile_avatar(html),
        followers=await find_number_subs(html, page),
        following=await find_number_subs(html, page, find_subscribers_flag=False),
        creation_date=get_date_create_account(html),
        check_posts=await check_post_on_profile(page))
