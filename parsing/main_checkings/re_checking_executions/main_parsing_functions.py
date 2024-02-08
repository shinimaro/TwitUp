import math
from typing import TypedDict

from pyppeteer.page import Page

from bot_apps.bot_parts.task_push.task_push_filters import comment_check_itself
from parsing.elements_storage.elements_dictionary import base_links
from parsing.main_checkings.checking_exceptions import SubscriptionFailed, LikeFailed, RetweetFailed, CommentFailed
from parsing.main_checkings.re_checking_executions.elements_control import SubscuptionsFlag, \
    collect_info_about_subs_flags, \
    search_for_user_in_slice
from parsing.parsing_functions.parsing_functions import checking_account_for_life, get_users_list, \
    parsing_user_list, get_comment_text, parsing_in_posts


class ReActionsDict(TypedDict):
    subscriptions: bool
    likes: bool
    retweets: bool
    comments: bool


class ReCheckExecutions:
    """Класс с основными функциями для перепроверки"""
    def __init__(self, workerk_username: str, post: str):
        self.worker_username = workerk_username
        self.post = post

    async def re_checking_subscriptions(self,
                                        page: Page,
                                        profile_worker_link: str,
                                        profile_author_link: str,
                                        subscriptions_worker_link: str,
                                        suscribers_author_link: str,
                                        cut_dict: dict[str, list[str]] | None) -> bool:
        """Проверка подписки на аккаунт"""
        if await self._check_acc_for_ban(page, profile_worker_link):
            self._raise_subscription_except()
        else:
            subs_flag: SubscuptionsFlag = await self._set_subs_flags(page, profile_worker_link, profile_author_link)
            author_username = f"@{profile_author_link[len(base_links['home_page']):]}"
            if await self._check_worker_subscriptions(page, subscriptions_worker_link, author_username, cut_dict, subs_flag):
                self._raise_subscription_except()
            else:
                if await self._check_author_followers(page, suscribers_author_link, cut_dict, subs_flag):
                    self._raise_subscription_except()
                else:
                    return True

    async def re_checking_likes(self, page: Page, link_to_user_likes: str) -> bool:
        """Проверяем лайки в списке лайкнутых постов юзера"""
        result = await parsing_in_posts(page, self.post, link_to_user_likes, math.inf)
        return self._handle_like_checking(result)

    async def re_checking_retweets(self, page: Page, link_to_post_retweets: str) -> bool:
        """Проверяем конкретно в посте ретвиты, т.к. их слишком много быть не может"""
        result = await parsing_user_list(page, self.worker_username, link_to_post_retweets, math.inf)
        return self._handle_retweet_checking(result)

    async def re_checking_comments(self, page: Page, link_to_worker_comment: str, tasks_msg_id: int) -> bool:
        """Фанкшин, достающий готовый комментарий по ссылке и перепроверяющий его"""
        comment_text: str | None = await get_comment_text(page, self.post, self.worker_username, link_to_worker_comment)
        result: bool = await comment_check_itself(tasks_msg_id, comment_text)
        return self._handle_comments_checking(result if isinstance(result, bool) else False)

    @staticmethod
    async def _check_acc_for_ban(page: Page, profile_worker_link: str) -> bool:
        """Проверка аккаунта юзера на бан"""
        return await checking_account_for_life(page, profile_worker_link)

    @staticmethod
    async def _set_subs_flags(page: Page, profile_worker_link: str, profile_author_link: str) -> SubscuptionsFlag:
        """Найти флаги о том, менее ли 50 подписок/подписчиков на аккаунтах автора и воркера"""
        return await collect_info_about_subs_flags(page, profile_worker_link, profile_author_link)

    async def _check_worker_subscriptions(self,
                                          page: Page,
                                          subscriptions_worker_link: str,
                                          author_username: str,
                                          cut_dict: dict,
                                          subs_flags: SubscuptionsFlag) -> bool:
        """Поиск аккаунт автора в подписках юзера"""
        worker_subs: list[str] = await get_users_list(page, subscriptions_worker_link)  # Собираем все подписки воркера
        check_worker: bool = search_for_user_in_slice(worker_subs, author_username, cut_dict)  # Поиск в подписках у юзера
        # Если в читаемых у юзера аккаунта не было и у него менее 50 подписок = бан
        if (self.worker_username not in worker_subs and subs_flags.worker_flag) or not check_worker:
            return False
        return True

    async def _check_author_followers(self,
                                      page: Page,
                                      suscribers_author_link: str,
                                      cut_dict: dict,
                                      subs_flags: SubscuptionsFlag) -> bool:
        """Поиск аккаунта воркера в подписчиках автора"""
        author_subs: list[str] = await get_users_list(page, suscribers_author_link)  # Собираем всех подписчиков автора
        check_author: bool = search_for_user_in_slice(author_subs,
                                                      self.worker_username,
                                                      cut_dict,
                                                      workers_cuts_flag=False)  # Поиск в подписчиках автора
        if (self.worker_username not in author_subs and subs_flags.author_flag) or not check_author:
            return False
        return True

    @staticmethod
    def _raise_subscription_except() -> None:
        """Выкинуть ошибку о подписке"""
        raise SubscriptionFailed

    @staticmethod
    def _handle_like_checking(result: bool) -> bool:
        """Поменять флаг проверки лайков"""
        if result:
            return True
        raise LikeFailed

    @staticmethod
    def _handle_retweet_checking(result: bool) -> bool:
        """Поменять флаг проверки ретвитов"""
        if result:
            return True
        raise RetweetFailed

    @staticmethod
    def _handle_comments_checking(result: bool) -> bool:
        """Поменять флаг проверки комментариев"""
        if result:
            return True
        raise CommentFailed




