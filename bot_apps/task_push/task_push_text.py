from bot_apps.databases.database import db
from bot_apps.wordbank import task_completion


# Билдер текста к комментарию
async def _comment_note_text_builder(info):
    if not info:
        return False
    note_text = '\n<b>Комментарий должен: </b>\n'
    # Если в комментарии есть ключевые параметры для проверки
    if info['words_count'] or info['tags_count'] or info['words_tags']:
        if info['words_count']:
            note_text += f"- Содержать более {info['words_count']} слов\n"
        elif info['tags_count']:
            note_text += f"- Содержать более {info['tags_count']} тегов\n"
        else:
            note_text += f"- Содержать следующие слова и тэги {info['words_tags']}\n"
    # Если комментарий должен быть на английском языке
    if info['english']:
        note_text += '- Быть написан только на английском языке' + '\n'
    # Если к комментарию было приложено примечание
    if info['note']:
        note_text += '<b>Примечание к комментарию: </b>' + info['note'] + '\n'
    return note_text


# Билдер текста перед началом задания, который подробно говорит, что нужно делать
async def full_text_task_builder(tasks_msg_id):
    task_info = await db.open_task(int(tasks_msg_id))
    text = '✨<b>Новое задание✨</b>\n'
    text += f'<b>Награда: {int(task_info["price"]) if task_info["price"].is_integer() else round(task_info["price"], 2)} $STB</b>\n\n'

    text += '<b>Действия:</b>\n'
    # Своеобразная сортировка и добавление заданий, в соответствии с их нумерацией
    action_order = {'subscriptions': 1, 'likes': 2, 'retweets': 3, 'comments': 4}
    sorted_action = sorted(task_info['type_task'], key=lambda x: action_order.get(x))
    action_dict = {'subscriptions': 'Подписка', 'likes': 'Лайк', 'retweets': 'Ретвит', 'comments': 'Комментарий'}
    text += ''.join(['<b>' + str(i + 1) + '</b>' + '. ' + action_dict[action] + '\n' for i, action in enumerate(sorted_action)])

    # Если были заданы настройки комментария
    text += await _comment_note_text_builder(task_info['comment_parameter']) if 'comment_parameter' in task_info and task_info['comment_parameter'] else ''

    text += '\n<i>После того, как ты нажмёшь кнопку "</i>👨‍🦽<i>Начать задание", у тебя будет 10 минут на его выполнение. Удачи</i>🧚‍♂️'

    # Текст о том, сколько людей завершили таск или уже приступили к выполнению
    result = await db.get_quantity_completed(int(tasks_msg_id))
    if result:
        text += f'\n\n<b>Уже выполнили или выполняют прямо сейчас: <code>{result}</code></b>'

    return text


# Билдер самого текста задания
# Если будешь что-то редачить здесь, в функции ниже надо будет тоже это сделать
async def context_task_builder(tasks_msg_id: int | str, account: str, not_complete: bool = None) -> str:
    task_info = await db.open_task(int(tasks_msg_id))
    link_action = await db.get_link_action(tasks_msg_id)
    text = f"А вот и комплексное задание🧞\n\n<b>Что обязательно нужно сделать?</b> ({len(task_info['type_task'])} действия):\n\n"
    # Сортировка списка
    action_order = {'subscriptions': 1, 'likes': 2, 'retweets': 3, 'comments': 4}
    sorted_action = sorted(task_info['type_task'], key=lambda x: action_order.get(x))
    # Подготовка текста для построения ссылки
    action_dict = {'subscriptions': '🎯Подписка на профиль', 'likes': '🎯Лайк на пост', 'retweets': '🎯Ретвит поста', 'comments': '🎯Комментарий поста'}
    links_dict = {'subscriptions': 'https://twitter.com/intent/follow?screen_name={0}', 'likes': 'https://twitter.com/intent/like?tweet_id={0}',
                  'retweets': 'https://twitter.com/intent/retweet?tweet_id={0}', 'comments': 'https://twitter.com/intent/tweet?in_reply_to={0}'}

    text += ''.join([f'<a href="{links_dict[i].format(link_action["profile_name"] if i == "subscriptions" else link_action["post_id"])}">{action_dict[i]}</a>\n' for i in sorted_action])

    text += await _comment_note_text_builder(task_info['comment_parameter']) if 'comment_parameter' in task_info and task_info['comment_parameter'] else ''
    text += f'\n<b>Аккаунт,</b> с которого нужно выполнить задание: <a href="https://twitter.com/{account[1:]}">{account}</a>\n'

    if not not_complete:
        text += '\nОго, ты всё уже сделал? Тогда жми <b>"ПРОВЕРИТЬ ЗАДАНИЕ"</b>👇'
    else:
        dop_dict = {'subscriptions': 'не подписался на профиль', 'likes': 'не поставил лайк на пост', 'retweets': 'не ретвитнул пост'}
        # Если был задан комментарий, то завершаем работу билдера, т.к. текст для комментария делается в другой функции
        if not_complete in ('comment', 'comments'): # в 1 функции добавляется comments, в остальных comment, поэтому добавил 2 текста в кортеж
            return text
        text += f'\nКажется, ты <b>{dop_dict[not_complete]}</b>🥺\nЗакончи это задание и жми <b>"ПРОВЕРИТЬ ЗАДАНИЕ"</b>👇'
    return text


# Билдит текст, для воркеров, которые начали уже выполненное задание с нового аккаунта
async def new_account_from_task_builder(tasks_msg_id, account):
    text = '<b>На повторение задания у тебя всё также 10 минут, кстати, они уже начались🧭</b>\n\n'
    task_info = await db.open_task(int(tasks_msg_id))
    link_action = await db.get_link_action(tasks_msg_id)
    text += f"А вот и комплексное задание🧞\n\n<b>Что обязательно нужно сделать?</b> ({len(task_info['type_task'])} действия):\n\n"
    # Сортировка списка
    action_order = {'subscriptions': 1, 'likes': 2, 'retweets': 3, 'comments': 4}
    sorted_action = sorted(task_info['type_task'], key=lambda x: action_order.get(x))
    # Подготовка текста для построения ссылки
    action_dict = {'subscriptions': '🎯Подписка на профиль', 'likes': '🎯Лайк на пост', 'retweets': '🎯Ретвит поста',
                   'comments': '🎯Комментарий поста'}
    links_dict = {'subscriptions': 'https://twitter.com/intent/follow?screen_name={0}',
                  'likes': 'https://twitter.com/intent/like?tweet_id={0}',
                  'retweets': 'https://twitter.com/intent/retweet?tweet_id={0}',
                  'comments': 'https://twitter.com/intent/tweet?in_reply_to={0}'}
    text += ''.join([f'<a href="{links_dict[i].format(link_action["profile_name"] if i == "subscriptions" else link_action["post_id"])}">{action_dict[i]}</a>\n' for i in sorted_action])
    text += await _comment_note_text_builder(task_info['comment_parameter']) if 'comment_parameter' in task_info and task_info['comment_parameter'] else ''

    # Если у пользователя есть только 1 аккаунт, с которого можно сделать задание, то говорим, чтобы он сделал задание с него
    if account:
        text += f'\n<b>Аккаунт,</b> с которого нужно выполнить задание: <a href="https://twitter.com/{account[1:]}">{account}</a>\n'
    # Если у пользователя много аккаунтов, с которых можно сделать задание
    else:
        text += '\n<b>Выбери аккаунт, чтобы приступить к выполнению задания👇</b>'
    return text


# Текст, который просит пользователя скинуть ссылку на коммент самому
async def please_give_me_link(tasks_msg_id, account):
    text = await context_task_builder(tasks_msg_id, account, 'comment') + f"\n<b>{task_completion['not_check_comment']}</b>"
    text += f'<a href="https://twitter.com/{account[1:]}/with_replies"><b>Ссылка на твои комментарии</b></a>'
    return text


# Обрезанный текст для работы пользователя с комментарием (когда у него какие-то проблемы с ним)
async def content_comment_builder(tasks_msg_id):
    task_info = await db.open_task(tasks_msg_id)
    account = await db.get_task_account(tasks_msg_id)
    text = '\n\nЕсли ты уверен, что оставил его в отведенные 10 минут и всё в нем указано правильно - напиши агенту поддержки, он всё проверит и поможет❤️\n\n'
    text += '<b>✨Напоминание✨</b>'
    text += f'\n<b>Аккаунт,</b> с которого нужно выполнить задание: <a href="https://twitter.com/{account[1:]}">{account}</a>\n'
    text += await _comment_note_text_builder(task_info['comment_parameter']) if 'comment_parameter' in task_info and task_info['comment_parameter'] else ''
    return text


# Текст под окончанием таска, который выдаёт статистику и предлагает пройти ещё раз задание, если оно доступно для него и у него есть, с чего выполнять его
async def control_statistic_builder(tg_id, tasks_msg_id):
    # Предварительный текст
    if await db.get_tasks_user(tg_id):
        text = 'Как я вижу, у тебя еще есть незавершенные задания - можешь начать выполнять их или дождаться новых🌚\n\n'
    else:
        text = 'Отлично! Как только появятся новые задания - я обязательно тебе сообщу🌊\n\n'

    # Текст со статистикой
    text += '<b>А пока немного статистики:</b>\n\n'
    info_dict = await db.get_info_to_user_and_tasks(tg_id)
    text += f"<b>Актуальный баланс: {info_dict['balance'] if info_dict['balance'].is_integer() else round(info_dict['balance'], 2)} STB$</b>\n"
    text += f"<b>Заданий выполнено сегодня: {info_dict['tasks_completed']}</b>\n"
    text += f"<b>Доступно к выполнению на всех аккаунтах: {info_dict['open_tasks']}</b>\n"

    # Если пользователь может выполнить этот таск с ещё одного аккаунта, то предлагаем ему это сделать
    if await db.task_again(tg_id, tasks_msg_id):
        text += '\nКстати, ты можешь выполнить прошлое задание еще раз с другого аккаунта👇'
    return text



