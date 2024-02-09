from dataclasses import dataclass
from typing import NamedTuple, TypedDict, Optional

from pyppeteer.page import Page

from databases.database import Database
from parsing.elements_storage.elements_dictionary import base_links
from parsing.main_checkings.checking_exceptions import SubscriptionFailed, LikeFailed, RetweetFailed, CommentFailed
from parsing.parsing_functions.parsing_functions import parsing_user_list, \
    parsing_comments_in_posts, parsing_user_subscriptions, parsing_in_posts, get_number_subs

db = Database()


@dataclass(frozen=True, slots=True)
class FoundComment:
    comment_text: str
    comment_link: str


class ActionsDict(TypedDict):
    subscriptions: Optional[bool]
    likes: Optional[bool]
    retweets: Optional[bool]
    comments: Optional[bool | FoundComment]


class SaveCuts(NamedTuple):
    upper_cut: list[str]
    lower_cut: list[str]


class CheckExecution:
    def __init__(self,
                 action_dict: ActionsDict,
                 worker_username: str,
                 post: str | None):
        self.action_dict = action_dict
        self.worker_username = worker_username
        self.post = post

    async def parsing_subscriptions(self, page: Page, tasks_msg_id: int, link_to_worker: str, link_to_author: str) -> None:
        """Проверка подписки"""
        author_username = '@' + link_to_author[20:-10].lower()
        subs_list: list[str] | bool = await parsing_user_subscriptions(page, author_username, link_to_worker)
        if subs_list:
            await db.save_worker_cut(tasks_msg_id, *self._get_cut_users(subs_list, author_username))
            self._handle_subscriptions_checking(True)
        else:
            following_worker = await get_number_subs(page, base_links['home_page'] + self.worker_username, find_subscribers_flag=False)
            if following_worker <= 50:
                self._handle_subscriptions_checking(False)
            else:
                subs_author: list[str] | bool = await parsing_user_subscriptions(page, self.worker_username, link_to_author)
                if subs_author:
                    await db.save_author_cut(tasks_msg_id, *self._get_cut_users(subs_author))
                    self._handle_subscriptions_checking(True)
                else:
                    self._handle_subscriptions_checking(False)

    async def parsing_likes(self, page: Page, link_to_user_likes: str, link_to_post_likes: str) -> None:
        """Проверка лайка"""
        result: bool = await parsing_in_posts(page, self.post, link_to_user_likes)
        if not result:
            result: bool = await parsing_user_list(page, self.worker_username, link_to_post_likes)
        self._handle_likes_checking(result)

    async def parsing_retweets(self, page: Page, link_to_user_replies: str, link_to_post_retweets: str) -> None:
        """Проверка ретвита"""
        result: bool = await parsing_in_posts(page, self.post, link_to_user_replies)
        if not result:
            result: bool = await parsing_user_list(page, self.worker_username, link_to_post_retweets)
        self._handle_retweets_checking(result)

    async def parsing_comments(self, page: Page, link_to_user_replies: str) -> None:
        """Проверка комментария"""
        result: tuple[str, str] | bool = await parsing_comments_in_posts(page, self.post, self.worker_username, link_to_user_replies)
        if result:
            self._set_values_found_comments(result)
        else:
            self._raise_comment_failed()

    def _get_cut_users(self, users: list[str], author_username: str = None) -> SaveCuts:
        """Получить срез юзеров, по которым в дальнейшем будет производиться проверка"""
        user_index = users.index(self.worker_username if not author_username else author_username)
        upper_cut = users[user_index-3 if user_index-3 > 0 else 0:user_index]
        lower_cut = users[user_index+1 if user_index+1 <= len(users) else len(users):
                          user_index+4 if user_index+4 <= len(users) else len(users)]
        return SaveCuts(upper_cut=upper_cut, lower_cut=lower_cut)

    def _handle_subscriptions_checking(self, value: bool) -> None:
        """Установить итог проверки подписки"""
        if value:
            self.action_dict['subscriptions'] = True
        else:
            raise SubscriptionFailed

    def _handle_likes_checking(self, value: bool) -> None:
        """Установить итог проверки лайка"""
        if value:
            self.action_dict['likes'] = True
        else:
            raise LikeFailed

    def _handle_retweets_checking(self, value: bool) -> None:
        """Установить итог проверки ретвита"""
        if value:
            self.action_dict['retweets'] = value
        else:
            raise RetweetFailed

    @staticmethod
    def _raise_comment_failed() -> None:
        """Установить итог проверки подписки"""
        raise CommentFailed

    def _set_values_found_comments(self, values: tuple[str, str]):
        """Установить значения на найденый комментарий"""
        self.action_dict['comments'] = FoundComment(comment_text=values[0],
                                                    comment_link=values[1])
