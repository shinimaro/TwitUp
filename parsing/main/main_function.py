import asyncio
from asyncio import gather

from databases.database import db
from parsing.main.elements_dictionary import base_links
from parsing.main.master_function import Master
from parsing.main.parsing_functions.main_parsing_functions import parsing_subscriptions, parsing_likes, parsing_retweets, \
    parsing_comments


# Главная функция, которая берёт вебдрайвер и распределяет задания по функциям для поиска
async def main_parser(tasks_msg_id: int) -> dict[str, bool] | None:
    master = Master()
    driver = await master.get_driver()
    # Достаём все необходимые данные
    action_dict = await db.all_task_actions(tasks_msg_id)
    link_dict = await db.get_all_link_on_task(tasks_msg_id)
    link_user = link_dict['subscriptions'] if 'subscriptions' in link_dict else list(link_dict.keys())[0][:list(link_dict.keys())[0].find('/status/')]
    worker_username = await db.get_worker_username(tasks_msg_id)
    # Делаем необходимое количество страниц
    page_list = await driver.pages()
    page_list.extend([await driver.newPage() for _ in range(len(link_dict) - len(page_list))])
    # Запускаем поиск
    async with asyncio.timeout(35):
        try:
            # Формируем таски
            tasks = []
            for action in action_dict:
                page = page_list.pop(0)
                if action == 'subscriptions':
                    prefix = 'following'
                    link_to_worker_account = f'{base_links["home_page"]}{worker_username}/{prefix}'
                    tasks.extend([parsing_subscriptions(action_dict, page, link_user[20:], link_to_worker_account)])
                elif action == 'likes':
                    prefix = '/likes'
                    tasks.extend([parsing_likes(action_dict, page, worker_username, link_dict['likes'], link_user + prefix, link_dict['likes'] + prefix)])
                elif action == 'retweets':
                    prefix = '/retweets'
                    tasks.extend([parsing_retweets(action_dict, page, worker_username, link_dict['retweets'], link_user + '/with_replies', link_dict['retweets'] + prefix)])
                elif action == 'comments':
                    prefix = '/with_replies'
                    tasks.extend([parsing_comments(action_dict, page, worker_username, link_dict['comments'], link_user + prefix)])
            await gather(*tasks)
            await master.give_driver(driver)
            return action_dict
        except asyncio.TimeoutError:
            # Если есть какая-то функция, которая вернула False, то отправим словарь, т.к. мы уже нашли ошибку
            result = list(filter(lambda x: x is False, action_dict.values()))
            if result:
                # Заочно проставляем выполнение остальным действиям, чтобы хендлер сразу нашёл нужную ошибку и не отвлекался на другие действия
                action_dict = {key: True if value is None else value for key, value in action_dict.items()}
            else:
                action_dict = None
            await master.give_broke_driver(driver)
            return action_dict
