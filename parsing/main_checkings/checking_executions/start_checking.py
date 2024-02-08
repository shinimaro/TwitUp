import asyncio
from asyncio import gather
from dataclasses import dataclass
from typing import Callable, Optional

from databases.database import Database
from parsing.elements_storage.elements_dictionary import base_links
from parsing.main_checkings.base_start_checking import BaseStartChecking, ActionsDict
from parsing.main_checkings.checking_exceptions import SubscriptionFailed, LikeFailed, RetweetFailed, CommentFailed
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
                try:
                    await gather(*self.tasks)
                except (SubscriptionFailed, LikeFailed, RetweetFailed, CommentFailed) as ex:
                    self._handle_checking_exceptions(ex)
            self._return_driver()
        except asyncio.TimeoutError:
            self._handle_failure()
            self._return_broke_driver()
        finally:
            return self.actions_dict

    async def _set_check_executions(self) -> None:
        """Взять все данные, необходимые для проверки выполнения"""
        self.check_execution = CheckExecution(action_dict=self.actions_dict,
                                              worker_username=(await db.get_worker_username(self.tasks_msg_id)).lower(),
                                              post=self._get_links_on_actions().post_link)

    async def _set_need_args_for_parsing(self) -> None:
        """Получить аргументы и функции для парсинга"""
        links_on_actions = self._get_links_on_actions()
        worker_username = (await db.get_worker_username(self.tasks_msg_id)).lower()
        base_link_to_worker = f'{base_links["home_page"]}{worker_username}'
        self.parsing_args = ParsingArgs(
            parsing_args={
                'subscriptions': (self.tasks_msg_id, f'{base_link_to_worker}/following', f'{links_on_actions.account_link}/followers'),
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

    def _handle_failure(self) -> bool:
        """Проверить, где застрял бот и пометить это, как ошибку"""
        self.actions_dict = {key: True if value is not None else False for key, value in self.actions_dict.items()}

    def _handle_checking_exceptions(self, exception: Exception):
        """Оставить в словаре только ошибку, все остальные действия засчитать"""
        exceptions_dict = {'SubscriptionFailed': 'subscriptions',
                           'LikeFailed': 'likes',
                           'RetweetFailed': 'retweets',
                           'CommentFailed': 'comments'}
        self.actions_dict = {key: True if key != exceptions_dict[type(exception).__name__] else False for key in self.actions_dict}
