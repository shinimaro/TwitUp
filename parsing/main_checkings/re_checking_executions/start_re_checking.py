import asyncio
from asyncio import gather
from dataclasses import dataclass
from typing import Callable, Optional

from pyppeteer.browser import Browser

from databases.database import Database
from parsing.elements_storage.elements_dictionary import base_links
from parsing.main_checkings.base_start_checking import BaseStartChecking
from parsing.main_checkings.re_checking_executions.main_parsing_functions import ReCheckExecutions
from parsing.manage_webdrivers.master_function import Master

db = Database()


@dataclass(frozen=True, slots=True)
class ReChecingArgs:
    parsing_args: dict[str, tuple[str] | str]
    functions_dict: dict[str, Callable]


class StartReChecking(BaseStartChecking):
    """Класс для перепроверки выполнений"""
    def __init__(self, tasks_msg_id):
        super().__init__(tasks_msg_id)
        self.re_check_execution: Optional[ReCheckExecutions] = None
        self.re_checking_args: Optional[ReChecingArgs] = None

    async def start_re_checking(self) -> bool:
        """Функция, достающая все данные и распределяющая их для функций по перепроверке задания"""
        await self._initialize_attributes()
        await self._set_re_check_execution()
        await self._set_need_args_for_re_checking()

        try:
            async with asyncio.timeout(3 * 60):
                self._full_out_tasks_list()
                await gather(*self.tasks)
                self._return_driver()
                return self._final_check()
        except asyncio.TimeoutError:
            self._return_driver()  # Т.к. машина может проверять очень долго и это не обязательно должен быть сбой драйвера, то возвращаем его таким же, какой и был, а не как сломанный
            if self._check_failure():
                return False
            return True

    async def _set_re_check_execution(self) -> None:
        """Взять все данные, необходимые для проверки выполнения"""
        self.re_check_execution = ReCheckExecutions(actions_dict=self.actions_dict,
                                                    workerk_username=await db.get_worker_username(self.tasks_msg_id),
                                                    post=self._get_links_on_actions().post_link)

    async def _set_need_args_for_re_checking(self) -> None:
        """Получить аргументы и функции для парсинга"""
        links_on_actions = self._get_links_on_actions()
        worker_username = await db.get_worker_username(self.tasks_msg_id)
        base_link_to_worker = f'{base_links["home_page"]}{worker_username}'
        link_to_worker_id: int | None = await db.get_link_to_worker_comment(self.tasks_msg_id)
        cut_dict = await db.get_all_cut(self.tasks_msg_id)

        # Точно поставить актион дикт, пост, воркера и всё

        self.re_checking_args = ReChecingArgs(
            parsing_args={
                'subscriptions': (base_link_to_worker, links_on_actions.account_link, f'{base_link_to_worker}/following', f'{links_on_actions.account_link}/followers', cut_dict),
                'likes': (f'{base_link_to_worker}/likes',),
                'retweets': (f"{links_on_actions.post_link}/retweets",),
                'comments': (f"{base_links['home_page']}{worker_username}/status/{link_to_worker_id}", self.tasks_msg_id)},
            functions_dict={'subscriptions': self.re_check_execution.re_checking_subscriptions,
                            'likes': self.re_check_execution.re_checking_likes,
                            'retweets': self.re_check_execution.re_checking_retweets,
                            'comments': self.re_check_execution.re_checking_comments})

    def _full_out_tasks_list(self) -> None:
        """Заполнить список задач для их параллельного запуска"""
        for action in self.actions_dict:
            page = self.page_list.pop(0)
            self.tasks.extend([self.re_checking_args.functions_dict[action](page, *self.re_checking_args.parsing_args[action])])

    def _final_check(self) -> bool:
        return all(list(self.actions_dict.values()))
