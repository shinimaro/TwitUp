import asyncio

from pyppeteer.page import Page

from parsing.main.parsing_functions.parsing_functions import parsing_likes_in_posts, parsing_user_list, \
    parsing_retweets_in_posts, parsing_comments_in_posts


async def parsing_subscriptions(action_dict: dict, page: Page, user: str, link: str):
    result = await parsing_user_list(page, user, link, 50)
    print(result)
    action_dict['subscriptions'] = result


async def parsing_likes(action_dict: dict, page: Page, user: str, post: str, link_to_user_likes: str, link_to_post_likes: str):
    result = await parsing_likes_in_posts(page, post, link_to_user_likes)
    if not result:
        result = await parsing_user_list(page, user, link_to_post_likes)
    action_dict['likes'] = result


async def parsing_retweets(action_dict: dict, page: Page, user: str, post: str, link_to_user_replies: str, link_to_post_retweets: str):
    result = await parsing_retweets_in_posts(page, post, link_to_user_replies)
    if not result:
        result = await parsing_user_list(page, user, link_to_post_retweets)
    action_dict['retweets'] = result


async def parsing_comments(action_dict: dict, page: Page, user, post: str, link_to_user_replies: str):
    result = await parsing_comments_in_posts(page, post, user, link_to_user_replies)
    action_dict['comments'] = result
