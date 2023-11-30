import asyncio
import json
from dataclasses import dataclass
from random import choice

import aiohttp
from fake_useragent import UserAgent


@dataclass(frozen=True, slots=True)
class BanResponse:
    ghost_ban: bool      # Сам теневой бан
    more_replies: bool   # Скрыти ли комментарии за кнопокой "показать больше"
    search_ban: str      # Поисковый бан
    search_suggestions: bool  # Тоже поисковый бан, но только в поисковых преждложениях


def _get_headers():
    return {
        'authority': 'shadowban-api.yuzurisa.com:444',
        'accept': '*/*',
        'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'origin': 'https://shadowban.yuzurisa.com',
        'referer': 'https://shadowban.yuzurisa.com/',
        'sec-ch-ua': '"Chromium";v="118", "Opera GX";v="104", "Not=A?Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': choice(['Windows', 'Linux', 'Macintosh', 'Android', 'iOS']),
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': UserAgent().random}


async def _get_response(username: str) -> BanResponse | None:
    """Получение ответа от страницы"""
    async with aiohttp.ClientSession() as session:
        response = await session.get(f'https://shadowban-api.yuzurisa.com:444/{username}', headers=_get_headers())
    if response.status == 200:
        data = (json.loads(await response.text()))['tests']
        return BanResponse(
            ghost_ban=data['ghost'].get('ban'),
            more_replies=data['more_replies'].get('ban'),
            search_ban=data['search'],
            search_suggestions=data['typeahead'])


def _ban_check(data: BanResponse) -> bool:
    """
    Здесь будут храниться условия, по которым будет считаться,
    аккаунт в теневом бане или нет
    """
    return True if not data or (data and not data.ghost_ban) else False


async def parsing_shadowban(username: str) -> bool:
    """Проверить аккаунт на теневой бан"""
    data: BanResponse | None = await _get_response(username)
    return _ban_check(data)


# # Проверка на теневой бан
# async def _check_shadowban(html_page: str) -> bool | None:
#     soup = BeautifulSoup(html_page, 'lxml')
#     check_user_block = soup.find('li', {'data-task-id': 'checkUser'}).get('data-task-status')
#     # Начальная проверка на то, что аккаунт можно проверить
#     if check_user_block == 'warn':
#         return None
#     tag_check_dict = {1: 'checkSuggest', 2: 'checkSearch', 3: 'checkBarrier'}  # Проверяем ещё 3 из 5 блоков, т.к. один не нужен
#     # Проверяем оставшиеся такие же блоки
#     for tag in tag_check_dict.values():
#         check_block = soup.find('li', {'data-task-id': tag}).get('data-task-status')
#         # Если один из блоков показал, что юзер в бане, то выводим False
#         if check_block == 'ban':
#             return False
#     return True
