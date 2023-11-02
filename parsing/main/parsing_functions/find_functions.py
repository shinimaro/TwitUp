import asyncio
from asyncio import sleep
from typing import Set, Any

from bs4 import BeautifulSoup
from pyppeteer.page import Page

from parsing.main.elements_dictionary import subscribers_blocks, post_blocks, comment_blocks


# Функция для поиска всех юзеров в списке юзеров через суп
async def find_all_users(html_page: str, page: Page) -> set[str]:
    users = set()
    for _ in range(2):
        try:
            soup = BeautifulSoup(html_page, 'lxml')
            blocks = soup.find_all('div', class_=subscribers_blocks['username_block'])
            for block in blocks:
                username = block.find('span', class_=subscribers_blocks['username_text']).text
                users.add(username)
            return users
        except AttributeError:
            await sleep(0.5)
            html_page = await page.content()
    else:
        return users


# Функция для поиска всех постов юзера, которые он лайкнул
async def find_all_posts(html_page: str, page: Page) -> set[str]:
    posts = set()
    for _ in range(2):
        try:
            soup = BeautifulSoup(html_page, 'lxml')
            blocks = soup.find_all('a', class_=post_blocks['time_publish'])
            for block in blocks:
                part_link = block.get('href')
                base_url = 'https://twitter.com'
                posts.add(base_url + part_link)
            return posts
        except AttributeError:
            await sleep(0.5)
            html_page = await page.content()
    else:
        return posts


# Функция для поиска всех постов юзера, которые он ретвитнул
async def find_all_retweets(html_page: str, page: Page) -> set[str]:
    retweets = set()
    for _ in range(2):
        try:
            soup = BeautifulSoup(html_page, 'lxml')
            blocks = soup.find_all('div', class_=post_blocks['repost_tag'])
            if blocks:
                for block in blocks:
                    try:
                        parent_block = block.find_parent('article', class_=post_blocks['post_block'])
                        part_link = parent_block.find('a', class_=post_blocks['time_publish']).get('href')
                        base_url = 'https://twitter.com'
                        retweets.add(base_url + part_link)
                    except AttributeError:
                        pass
            return retweets
        except AttributeError:
            await sleep(0.5)
            html_page = await page.content()
    else:
        return retweets


# Функция для поиска комментария из постов
async def find_all_comments(html_page: str, all_posts: list, user: str, post: str, page: Page) -> list | str:
    for _ in range(2):
        try:
            soup = BeautifulSoup(html_page, 'lxml')
            # Дополняем список новыми постами
            blocks = soup.find_all('article', class_=post_blocks['post_block'])
            all_posts.extend([block for block in blocks if block not in all_posts])
            for index, block in enumerate(all_posts):
                post_link = 'https://twitter.com' + block.find('a', class_=post_blocks['time_publish']).get('href')
                # Если мы нашли нужный пост и у нас есть ещё посты для проверки
                if post_link == post and len(all_posts) > index:
                    comment = all_posts[index+1]
                    # Проверка на то, что этот коммент (цитата) написана нашим пользователем
                    status_comment = comment.find_parent('article', class_=post_blocks['post_block'])
                    author_comment = comment.find('div', class_=post_blocks['username_author']).text
                    if status_comment and author_comment == user:
                        comment_text = comment.find('div', class_=post_blocks['post_text']).text
                        return comment_text
            return all_posts
        except AttributeError:
            await sleep(0.5)
            html_page = await page.content()
    else:
        return all_posts


# Поиск текста комментария
async def find_comment(html_page: str, post, user, page: Page) -> str | bool | None:
    for _ in range(2):
        try:
            soup = BeautifulSoup(html_page, 'lxml')
            # Проверка на то, что это комментарий/цитата
            check_for_comment = soup.find('article', class_=comment_blocks['comment_block'])
            if check_for_comment:
                # Проверка на то, что пользователь комментирует нужный пост
                post_link = soup.find('a', class_=post_blocks['time_publish']).get('href')
                if post_link == post[19:]:  # Убираем https://twitter.com
                    # Проверка на то, что нужный пользователь оставляет этот комментарий
                    username = check_for_comment.find('div', class_=post_blocks['username_author']).text
                    if username == user:
                        comment_text = check_for_comment.find('div', class_=comment_blocks['text_comment']).text
                        return comment_text
            return False
        except AttributeError:
            await sleep(0.5)
            html_page = await page.content()
    else:
        return None

