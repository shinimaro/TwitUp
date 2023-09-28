import asyncio
import string

from aiogram import Router, Bot
from bot_apps.databases.database import db
from bot_apps.task_push.task_push_text import context_task_builder, content_comment_builder
from bot_apps.wordbank import task_completion
from config import load_config
import re
router = Router()
config = load_config()


# Функция для подготовки ссылки комментарии для проверки на корректность
async def comment_check_filter(tg_id: str, link: str) -> dict[str, str] | int:
    result = await db.get_task_for_link(tg_id, re.search('https://twitter\.com/([\w\d_]{3,})/status/\d{1,19}', link).group(1))
    # Если нет задания, которое ждёт ввода ссылки
    if isinstance(result, bool):
        return  # Никак не реагируем
    # Если аккаунт в ссылке оказался не тот, который требуют задания, ожидающие ссылку на комментарий
    if not isinstance(result, int):
        return {result[0]['tasks_msg_id']: await context_task_builder(result[0]['tasks_msg_id'], result[0]['account_name'], 'comment') + task_completion['not_correct_profile_in_link'] + task_completion['dop_not_check_comment'] + f'<a href="https://twitter.com/{result[0]["account_name"][1:]}/with_replies"><b>Ссылка на твои комментарии</b></a>'}
    # Если вернулся id проверяемого таска, то проверяем сам комментарий
    else:
        return int(result)


# Функция для самой проверки комментария
async def comment_check_itself(tasks_msg_id, link):
    # comment_text = await func(link)
    comment_text = 'asd asd qwqe QEQWE adfdfq QWE'
    account_name = await db.get_task_account(tasks_msg_id)
    link_account = task_completion['dop_not_check_comment'] + f'<a href="https://twitter.com/{account_name[1:]}/with_replies"><b>Ссылка на твои комментарии</b></a>'

    # Если комментария нет в ссылке, которую он скинул
    if not comment_text:
        return task_completion['not_correct_link_2'] + link_account + await content_comment_builder(tasks_msg_id)

    task_info = await db.open_task(tasks_msg_id)
    task_info = task_info.get('comment_parameter', None)

    # Если было задано минимальное количество слов
    if task_info.get('words_count'):
        # Разделяю строки, с учётом того, чтобы python не засчитал символ за слово
        text = [i for i in comment_text.split() if i not in '''!'@></.`~,\#$%^&*()_+?:%;№"![]{|*}''']
        # Если длина комментария меньше, чем нужно
        if len(text) < int(task_info['words_count']):
            return task_completion['not_correct_length_comment'] + link_account + await content_comment_builder(tasks_msg_id)
    # Если было задано минимальное количество тэгов
    elif task_info.get('tags_count'):
        text = [i for i in comment_text.split('#') if i[0:] == '#']
        # Если тэгов меньше, чем нужно
        if len(text) < int(task_info['tags_count']):
            return task_completion['not_correct_tags_comment'] + link_account + await content_comment_builder(tasks_msg_id)
    # Если были заданы какие-либо ключевые слова или тэги
    elif task_info.get('words_tags'):
        text_check = [i for i in task_info['words_tags'].split(', ')]
        for element in text_check:
            if element in comment_text:
                break
        # Если так и не оказалось нужного элемента в текста
        else:
            return task_completion['not_correct_elements_comment'] + link_account + await content_comment_builder(tasks_msg_id)

    # Если было написано, что весь текст должен быть на английском
    if task_info.get('english'):
        for i in comment_text:
            # Если символ не является каким-то обычным символом, английской буквой или цифрой
            if i not in string.ascii_letters + string.hexdigits + '''!'>@</.`~,\#$%^&*()_+?:%;№"![]{|*} ''':
                return task_completion['nor_correct_text_comment'] + link_account + await content_comment_builder(tasks_msg_id)

    return True
