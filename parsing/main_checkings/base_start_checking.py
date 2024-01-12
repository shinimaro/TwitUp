import asyncio
from typing import Optional

from pyppeteer.browser import Browser
from pyppeteer.page import Page

from databases.database import Database
from databases.dataclasses_storage import LinkAction
from parsing.main_checkings.checking_executions.main_parsing_functions import ActionsDict
from parsing.main_checkings.re_checking_executions.main_parsing_functions import ReActionsDict
from parsing.manage_webdrivers.master_function import Master

db = Database()


class BaseStartChecking:
    """Базовый класс для проверок и перепроверок заданий"""
    def __init__(self, tasks_msg_id):
        self.tasks_msg_id: int = tasks_msg_id
        self.master = Master()
        self.tasks = []
        self.actions_dict: Optional[ActionsDict | ReActionsDict] = None
        self.links_dict: Optional[dict[str, str]] = None
        self.driver: Optional[Browser] = None
        self.page_list: Optional[list[Page]] = []

    async def _initialize_attributes(self) -> None:
        """Заполнить переменные в __init__"""
        await self._set_links_dict()
        await self._set_actions_dict()
        await self._set_driver()
        await self._get_need_pages_list()

    async def _set_links_dict(self) -> None:
        """Собрать все ссылки на каждое из действий"""
        self.links_dict = await db.get_all_link_on_task(self.tasks_msg_id)

    async def _set_actions_dict(self) -> None:
        """Собрать все действия, которые необходимо проверить"""
        self.actions_dict = await db.all_task_actions(self.tasks_msg_id)

    async def _get_need_pages_list(self) -> None:
        """Получить список страниц в кол-ве, необходимом
        для одновременного парсинга всех действий"""
        pages = await self.driver.pages()
        self.page_list.extend([(await self.driver.pages())[0]])
        self.page_list.extend([await self.driver.newPage() for _ in range(len(self.links_dict) - len(pages))])

    async def _set_driver(self) -> None:
        self.driver = await self.master.get_driver()

    def _get_links_on_actions(self) -> LinkAction:
        """Заполнить датакласс с ссылками на действия"""
        return LinkAction(account_link=self.links_dict.get('subscriptions'),
                          post_link=next((self.links_dict[key] for key in ['likes', 'retweets', 'comments'] if key in self.links_dict), None))

    def _check_failure(self) -> bool:
        """Проверить, была ли найдена хоть одна ошибка"""
        result = list(filter(lambda x: x is False, self.actions_dict.values()))
        return True if result else False

    def _return_driver(self) -> None:
        """Запустить корутину по сдаче драйвера обратно"""
        asyncio.get_event_loop().create_task(self.master.give_driver(self.driver))

    def _return_broke_driver(self) -> None:
        """Запустить корутину по сдаче сломанного драйвера"""
        asyncio.get_event_loop().create_task(self.master.give_broke_driver(self.driver))
