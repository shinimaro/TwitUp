import math
from typing import TypedDict

from pyppeteer.page import Page

from bot_apps.bot_parts.task_push.task_push_filters import comment_check_itself
from parsing.elements_storage.elements_dictionary import base_links
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
    def __init__(self, actions_dict: ReActionsDict, workerk_username: str, post: str):
        self.actions_dict = actions_dict
        self.worker_username = workerk_username
        self.post = post

    async def re_checking_subscriptions(self,
                                        page: Page,
                                        profile_worker_link: str,
                                        profile_author_link: str,
                                        subscriptions_worker_link: str,
                                        suscribers_author_link: str,
                                        cut_dict: dict[str, list[str]] | None):
        """Проверка подписки на аккаунт"""
        if await self._check_acc_for_ban(page, profile_worker_link):
            self._change_subscroptions_flag(False)
        else:
            subs_flag: SubscuptionsFlag = await self._set_subs_flags(page, profile_worker_link, profile_author_link)
            author_username = f"@{profile_author_link[len(base_links['home_page']):]}"
            if await self._check_worker_subscriptions(page, subscriptions_worker_link, author_username, cut_dict, subs_flag):
                self._change_subscroptions_flag(True)
            else:
                if await self._check_author_followers(page, suscribers_author_link, cut_dict, subs_flag):
                    self._change_subscroptions_flag(True)
                else:
                    self._change_subscroptions_flag(False)

    async def re_checking_likes(self, page: Page, link_to_user_likes: str) -> None:
        """Проверяем лайки в списке лайкнутых постов юзера"""
        result = await parsing_in_posts(page, self.post, link_to_user_likes, math.inf)
        self._change_likes_flag(result)

    async def re_checking_retweets(self, page: Page, link_to_post_retweets: str) -> None:
        """Проверяем конкретно в посте ретвиты, т.к. их слишком много быть не может"""
        result = await parsing_user_list(page, self.worker_username, link_to_post_retweets, math.inf)
        self._change_retweets_flag(result)

    async def re_checking_comments(self, page: Page, link_to_worker_comment: str, tasks_msg_id: int) -> None:
        """Фанкшин, достающий готовый комментарий по ссылке и перепроверяющий его"""
        comment_text: str | None = await get_comment_text(page, self.post, self.worker_username, link_to_worker_comment)
        result: bool = await comment_check_itself(tasks_msg_id, comment_text)
        self._change_comments_flag(result if isinstance(result, bool) else False)

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

    def _change_subscroptions_flag(self, value: bool) -> None:
        """Поменять флаг проверки подписки"""
        self.actions_dict['subscriptions'] = value

    def _change_likes_flag(self, value: bool) -> None:
        """Поменять флаг проверки лайков"""
        self.actions_dict['likes'] = value

    def _change_retweets_flag(self, value: bool) -> None:
        """Поменять флаг проверки ретвитов"""
        self.actions_dict['retweets'] = value

    def _change_comments_flag(self, value: bool) -> None:
        """Поменять флаг проверки комментариев"""
        self.actions_dict['comments'] = value




