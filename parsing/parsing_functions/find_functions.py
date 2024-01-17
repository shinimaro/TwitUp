from asyncio import sleep

import bs4
from bs4 import BeautifulSoup
from pyppeteer.page import Page

from parsing.elements_storage.elements_dictionary import subscribers_blocks, post_blocks, comment_blocks, \
    profile_blocks, base_links


# Функция для поиска всех юзеров в списке юзеров через суп
async def find_all_users(html_page: str, page: Page, storage: list | set):
    """
    :return: set[str] | list[str]
    """
    users = storage
    for _ in range(2):
        try:
            soup = BeautifulSoup(html_page, 'lxml')
            blocks = soup.find_all('div', class_=subscribers_blocks['username_block'])
            for block in blocks:
                username = block.find('span', class_=subscribers_blocks['username_text']).text.lower()
                users.add(username) if isinstance(users, set) else users.append(username)
            return users
        except (AttributeError, TypeError):
            await sleep(0.5)
            html_page = await page.content()
    else:
        return users


# Функция для поиска всех постов у юзера
async def find_all_posts(html_page: str, page: Page) -> set[str]:
    posts = set()
    for _ in range(2):
        try:
            soup = BeautifulSoup(html_page, 'lxml')
            blocks = soup.find_all('a', class_=post_blocks['time_publish'])
            for block in blocks:
                part_link = block.get('href')
                base_url = base_links['home_page'][:-1]
                posts.add(base_url + part_link.lower())
            return posts
        except (AttributeError, TypeError):
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
                        parent_block = block.find_parent('div', class_=post_blocks['post_block'])
                        part_link = _get_post_link(parent_block)
                        base_url = base_links['home_page'][:-1]
                        retweets.add(base_url + part_link)
                    except (AttributeError, TypeError):
                        pass
            return retweets
        except (AttributeError, TypeError):
            await sleep(0.5)
            html_page = await page.content()
    else:
        return retweets


# Функция для поиска комментария из постов
async def find_all_comments(html_page: str, all_posts: list, user: str, post: str, page: Page) -> tuple[str, str] | tuple[list, None]:
    for _ in range(2):
        try:
            soup = BeautifulSoup(html_page, 'lxml')
            # Дополняем список новыми постами
            blocks = soup.find_all('div', class_=post_blocks['post_block'])
            all_posts.extend([block for block in blocks if block not in all_posts])
            for index, block in enumerate(all_posts):
                post_link = base_links['home_page'][:-1] + _get_post_link(block)
                # Если мы нашли нужный пост и у нас есть ещё посты для проверки
                if post_link == post and len(all_posts) > index:
                    comment = all_posts[index+1]
                    # Проверка на то, что этот коммент (цитата) написана нашим пользователем
                    author_comment = comment.find('div', class_=post_blocks['username_author']).text
                    if author_comment == user:
                        comment_text: str = comment.find('div', class_=post_blocks['post_text']).text
                        comment_link: str = base_links['home_page'][:-1] + _get_post_link(all_posts[index+1])
                        return comment_text, comment_link
            return all_posts, None
        except (AttributeError, TypeError):
            await sleep(0.5)
            html_page = await page.content()
    else:
        return all_posts, None


# Поиск текста комментария
async def find_comment(html_page: str, post, user, page: Page) -> str | bool | None:
    for _ in range(2):
        try:
            soup = BeautifulSoup(html_page, 'lxml')
            # Проверка на то, что это комментарий/цитата, а не что-то другое
            check_for_comment = soup.find('article', class_=comment_blocks['comment_block'])
            if check_for_comment:
                # Проверка на то, что пользователь комментирует нужный пост
                post_link = _get_post_link(soup)
                if post_link == post[19:]:
                    # Проверка на то, что нужный пользователь оставляет этот комментарий
                    username = check_for_comment.find('div', class_=post_blocks['username_author']).text.lower()
                    if username == user:
                        comment_text = check_for_comment.find('div', class_=comment_blocks['text_comment']).text
                        return comment_text
            return False
        except (AttributeError, TypeError):
            await sleep(0.5)
            html_page = await page.content()
    else:
        return None


async def find_ban_block(html_page: str, page: Page) -> bool:
    """Функция, ищущая блок с сообщением о бане аккаунта"""
    for _ in range(2):
        try:
            soup = BeautifulSoup(html_page, 'lxml')
            ban_block = soup.find('div', class_=profile_blocks['ban_block'])
            if ban_block:
                return True
            # Он никак не может найти блок с баном аккаунта, поэтому я пока это убрал
            # not_account_block = soup.find('div', class_=profile_blocks['not_account_block'])
            # if not_account_block:
            #     return True
        except (AttributeError, TypeError):
            await sleep(0.5)
            html_page = await page.content()
    return False


async def find_post_block(html_page: str, page: Page) -> bool:
    """Функция, ищущая блок о посте"""
    for _ in range(2):
        try:
            soup = BeautifulSoup(html_page, 'lxml')
            post_block = soup.find('div', class_=post_blocks['post_block'])
            if post_block:
                return False
        except (AttributeError, TypeError):
            await sleep(0.5)
            html_page = await page.content()
    return True


async def find_number_subs(html_page: str, page: Page, find_subscribers_flag: bool = True) -> int | None:
    """Функция по поиску кол-ва подписчиков/подписок в профиле"""
    index = 1 if find_subscribers_flag else 0
    for _ in range(2):
        try:
            # print('Даю html страницу', html_page)
            soup = BeautifulSoup(html_page, 'lxml')
            nums_text = soup.find_all('span', class_=profile_blocks['sub_info_block'])[index].text
            return _get_correct_sub_numbers(nums_text)
        except (AttributeError, TypeError):
            await sleep(0.5)
            html_page = await page.content()


def _get_correct_sub_numbers(nums_text: str) -> int:
    """Функция для корректного поиска сабов в твиттере"""
    factor_dict = {'тыс': {'first_factor': 1000, 'last_factor': 100},
                   'млн':  {'first_factor': 1000000, 'last_factor': 100000},
                   'K': {'first_factor': 1000, 'last_factor': 100},
                   'M':  {'first_factor': 1000000, 'last_factor': 100000}}
    first_num = int(''.join([num for num in str(nums_text.split(',')[0]) if num.isdigit()]))
    last_num = int(''.join([num for num in str(nums_text.split(',')[1:]) if num.isdigit()])) if ',' in nums_text else 0
    factor = ''.join([elem for elem in nums_text if elem.isalpha()])
    if factor:
        first_num *= factor_dict[factor]['first_factor']
        last_num *= factor_dict[factor]['last_factor']
        return first_num + last_num
    return int(nums_text)


def _get_post_link(target_block: bs4.element.Tag):
    """Выделил поиск сссылки на пост в отдельную функцию, чтобы,
    если снова нужно что-то менять, везде не менять каждый раз"""
    return target_block.find('a', class_=post_blocks['time_publish']).get('href').lower()
