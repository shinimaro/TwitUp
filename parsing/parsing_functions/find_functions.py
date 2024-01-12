from asyncio import sleep

from bs4 import BeautifulSoup
from pyppeteer.page import Page

from parsing.elements_storage.elements_dictionary import subscribers_blocks, post_blocks, comment_blocks, profile_blocks


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


async def find_all_users_list(html_page: str, page: Page) -> list[str]:
    """В отличие от функции выше, находит список юзеров, а не множество"""
    users = []
    for _ in range(2):
        try:
            soup = BeautifulSoup(html_page, 'lxml')
            blocks = soup.find_all('div', class_=subscribers_blocks['username_block'])
            for block in blocks:
                username = block.find('span', class_=subscribers_blocks['username_text']).text
                users.append(username)
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
                        parent_block = block.find_parent('div', class_=post_blocks['post_block'])
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
async def find_all_comments(html_page: str, all_posts: list, user: str, post: str, page: Page) -> tuple[str, str] | tuple[list, None]:
    for _ in range(2):
        try:
            soup = BeautifulSoup(html_page, 'lxml')
            # Дополняем список новыми постами
            blocks = soup.find_all('div', class_=post_blocks['post_block'])
            all_posts.extend([block for block in blocks if block not in all_posts])
            for index, block in enumerate(all_posts):
                post_link = 'https://twitter.com' + block.find('a', class_=post_blocks['time_publish']).get('href')
                # Если мы нашли нужный пост и у нас есть ещё посты для проверки
                if post_link == post and len(all_posts) > index:
                    comment = all_posts[index+1]
                    # Проверка на то, что этот коммент (цитата) написана нашим пользователем
                    author_comment = comment.find('div', class_=post_blocks['username_author']).text
                    if author_comment == user:
                        comment_text: str = comment.find('div', class_=post_blocks['post_text']).text
                        comment_link: str = 'https://twitter.com' + all_posts[index+1].find('a', class_=post_blocks['time_publish']).get('href')
                        return comment_text, comment_link
            return all_posts, None
        except AttributeError:
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
                post_link = soup.find('a', class_=post_blocks['time_publish']).get('href')
                if post_link == post[19:]:
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
        except AttributeError:
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
        except AttributeError:
            await sleep(0.5)
            html_page = await page.content()
    return True


async def find_number_subs(html_page: str, page: Page, find_subscribers_flag: bool = True) -> int | None:
    """Функция по поиску кол-ва подписчиков/подписок в профиле"""
    index = 1 if find_subscribers_flag else 0
    for _ in range(2):
        try:
            soup = BeautifulSoup(html_page, 'lxml')
            nums_text = soup.find_all('span', class_=profile_blocks['sub_info_block'])[index].text
            return _get_correct_sub_numbers(nums_text)
        except AttributeError:
            await sleep(0.5)
            html_page = await page.content()


def _get_correct_sub_numbers(nums_text: str) -> int:
    """Функция для корректного поиска сабов в твиттере"""
    factor_dict = {'тыс': {'first_factor': 1000, 'last_factor': 100},
                   'млн':  {'first_factor': 1000000, 'last_factor': 100000}}
    first_num = int(''.join([num for num in nums_text[:nums_text.find(',')] if num.isdigit()]))
    last_num = int(''.join([num for num in nums_text[nums_text.find(',') + 1:] if num.isdigit()]))
    factor = ''.join([elem for elem in nums_text if elem.isalpha()])
    if factor:
        first_num *= factor_dict[factor]['first_factor']
        last_num *= factor_dict[factor]['last_factor']
        return first_num + last_num
    else:
        return int(nums_text)
