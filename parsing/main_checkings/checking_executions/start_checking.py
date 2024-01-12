import asyncio
from asyncio import gather
from dataclasses import dataclass
from typing import Callable, Optional

from databases.database import Database
from parsing.elements_storage.elements_dictionary import base_links
from parsing.main_checkings.base_start_checking import BaseStartChecking, ActionsDict
from parsing.main_checkings.checking_executions.main_parsing_functions import CheckExecution

db = Database()


@dataclass(frozen=True, slots=True)
class ParsingArgs:
    parsing_args: dict[str, tuple[str]]
    functions_dict: dict[str, Callable]


class StartChecking(BaseStartChecking):
    """Класс для проверки выполнения"""
    def __init__(self, tasks_msg_id):
        super().__init__(tasks_msg_id)
        self.check_execution: Optional[CheckExecution] = None
        self.parsing_args: Optional[ParsingArgs] = None

    async def start_checking(self) -> ActionsDict | None:
        """Функция, достающая все данные и распределяющуая их по функциям для парсинга"""
        await self._initialize_attributes()
        await self._set_check_executions()
        await self._set_need_args_for_parsing()
        self._full_out_tasks_list()

        try:
            async with asyncio.timeout(35):
                self._full_out_tasks_list()
                await gather(*self.tasks)
                self._return_driver()
                return self.actions_dict
        except asyncio.TimeoutError:
            if self._check_failure():
                self._apply_default_completion_to_all()
            else:
                self._set_failure_check()
            self._return_broke_driver()
            return self.actions_dict

    async def _set_check_executions(self) -> None:
        """Взять все данные, необходимые для проверки выполнения"""
        self.check_execution = CheckExecution(action_dict=self.actions_dict,
                                              worker_username=await db.get_worker_username(self.tasks_msg_id),
                                              post=self._get_links_on_actions().post_link)

    async def _set_need_args_for_parsing(self) -> None:
        """Получить аргументы и функции для парсинга"""
        links_on_actions = self._get_links_on_actions()
        worker_username = await db.get_worker_username(self.tasks_msg_id)
        base_link_to_worker = f'{base_links["home_page"]}{worker_username}'
        self.parsing_args = ParsingArgs(
            parsing_args={
                'subscriptions': (self.tasks_msg_id, f'{base_link_to_worker}/following', links_on_actions.account_link),
                'likes': (f'{base_link_to_worker}/likes', f"{links_on_actions.post_link}/likes"),
                'retweets': (f'{base_link_to_worker}/with_replies', f"{links_on_actions.post_link}/retweets"),
                'comments': (f'{base_link_to_worker}/with_replies',)},
            functions_dict={'subscriptions': self.check_execution.parsing_subscriptions,
                            'likes': self.check_execution.parsing_likes,
                            'retweets': self.check_execution.parsing_retweets,
                            'comments': self.check_execution.parsing_comments})

    def _full_out_tasks_list(self) -> None:
        """Заполнить список задач для их параллельного запуска"""
        for action in self.actions_dict:
            page = self.page_list.pop(0)
            self.tasks.extend([self.parsing_args.functions_dict[action](page, *self.parsing_args.parsing_args[action])])

    def _set_failure_check(self):
        """Установка того, что проверка не удалась"""
        self.actions_dict = None

    def _apply_default_completion_to_all(self):
        """Заочно проставляем выполнение всем остальным действиям, чтобы дальнейшая проверка на них не отвлекалась"""
        self.actions_dict = {key: True if value is None else value for key, value in self.actions_dict.items()}
