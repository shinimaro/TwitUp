from dataclasses import dataclass

from pyppeteer.page import Page

from parsing.parsing_functions.parsing_functions import get_number_subs


@dataclass(frozen=True, slots=True)
class SubscuptionsFlag:
    worker_flag: bool
    author_flag: bool


async def collect_info_about_subs_flags(page: Page, profile_worker_link: str, profile_author_link: str) -> SubscuptionsFlag:
    """Функция, собирающая флаги о том, менее ли 50 подписок/подписчиков у юзера и автора"""
    num_ceiling = 50
    worker_sub = await get_number_subs(page, profile_worker_link, find_subscribers_flag=False)
    author_sub = await get_number_subs(page, profile_author_link)
    return SubscuptionsFlag(
        worker_flag=False if worker_sub < num_ceiling else True,
        author_flag=False if author_sub < num_ceiling else True)


async def search_for_user_in_slice(users: list[str], user: str, cuts_dict, workers_cuts_flag=True) -> bool:
    """Найти юзера, либо в списке, либо в срезе"""
    if user in users:
        return True
    if cuts_dict:
        cuts: dict[str, list[str]] = cuts_dict['worker_cut'] if workers_cuts_flag else cuts_dict['author_cut']
        if list(cuts.values()):
            result: bool = _search_by_slice(users, cuts['upper_cut'], cuts['lower_cut'])
            return result
    return True


def _search_by_slice(users: list[str], upper_cut: list[str], lower_cut: list[str]) -> bool:
    """Поиск по срезу"""
    upper_counter, lower_counter = 0, 0
    for user in users:
        upper_counter += 1 if user in upper_cut else 0
        lower_counter += 1 if user in lower_cut else 0
        if upper_counter > 0 and lower_counter > 0:  # Если мы нашли верхний и нижний срез
            return False
        elif lower_counter > 1:  # Если нашли только нижний срез
            return False
    return True  # Если срез не найден или недостаточно данных для вынесения решения
