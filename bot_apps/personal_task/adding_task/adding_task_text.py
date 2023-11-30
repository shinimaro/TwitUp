import re

from databases.database import db
from bot_apps.wordbank.wordlist import add_task
from config import load_config

config = load_config()


# Функция, формирующая текст в настройке заданий, которая показывает те настройки, которые указал пользователь
async def task_setting_text_builder(setting_actions, accepted):
    main_text = add_task['main_text']

    # Если были заданы подписки, проверяем, есть ли заданный профиль или ссылка
    if 'subscriptions' in setting_actions:
        main_text += '<b>— Подписка на аккаунт:</b> '
        # Если дана ссылка на профиль
        if accepted['profile_link']:
            main_text += f'{accepted["profile_link"][8:]}\n'
        # Если дана ссылка на пост (в ней содержится ссылка на профиль)
        elif accepted['post_link']:
            main_text += re.search(r"(twitter\.com/\S+?)/status/\d+", accepted["post_link"]).group(1) + '\n'
        # Если ничего не дано, выводим сообщение о том, что этот пункт не заполнен
        else:
            main_text += 'не заполнено\n'

    # Если было задано какое-то действие на пост, то добавляем его в текст
    if 'likes' in setting_actions or 'retweets' in setting_actions or 'comments' in setting_actions:
        action_list = []  # Переменная, чтобы удобно вставить отредаченный текст в основной
        if 'likes' in setting_actions:
            action_list.append('лайк')
        if 'retweets' in setting_actions:
            action_list.append('ретвит')
        if 'comments' in setting_actions:
            action_list.append('комментарий')

        main_text += f"— <b>{', '.join(action_list).capitalize()}</b>" + (f': \n{accepted["post_link"][8:]}\n' if accepted["post_link"] else ': не заполнено\n')

    # Если был задан комментарий
    if 'comments' in setting_actions:
        main_text += '<b>— Параметры комментария:</b> '
        comment_list = []  # Ещё один список со значениями заданных переменных для удобства просмотра на то, добавилось ли в него что-то
        # Если была задана одна из 3 основных проверок комментария
        if 'one_value' in accepted['comment_parameters'] and accepted['comment_parameters']['one_value']:
            # Доп словарь для ответов на одну из 3 проверок комментария
            dop_dict = {'words': '<b>Параметр:</b> по количеству слов (<code>{0}</code>)', 'tags': '<b>Параметр:</b> по количеству тэгов (<code>{0}</code>)', 'tags/words': '<b>Параметр:</b> по ключевым словам и тэгам (<code>{0}</code>)'}
            # Проходимся по каждому значению и если находим то, что указал пользователь, то записываем это в основной текст
            for key in accepted['comment_parameters']['one_value']:
                if accepted['comment_parameters']['one_value'][key]:
                    if key == 'tags/words':
                        words = accepted['comment_parameters']['one_value']['tags/words']['words']
                        tags = accepted['comment_parameters']['one_value']['tags/words']['tags']
                        combined_list = f"<code>{', '.join(words + (tags if tags else []))}</code>"
                        comment_list.append(dop_dict[key].format(combined_list))
                    else:
                        comment_list.append(dop_dict[key].format(accepted['comment_parameters']['one_value'][key]))
                    break
        # Если было задано примечание
        if 'note' in accepted['comment_parameters'] and accepted['comment_parameters']['note']:
            comment_list.append(f"<b>Примечание для исполнителей:</b> {accepted['comment_parameters']['note']}")
        # Если был указан английский язык в качестве обязательного
        if 'only_english' in accepted['comment_parameters'] and accepted['comment_parameters']['only_english']:
            comment_list.append('<b>Язык:</b> только английский')

        # Если не был заполнен ни один параметр
        if not comment_list:
            main_text += 'не заполнено'
        # Если заполнено, формируем готовый текст и отправляет
        else:
            main_text += '\n' + '\n'.join(comment_list)
    return main_text


# Функция, показывающая пользователю под добавлением параметров комментария текст о всём то, что он уже выбрал
async def text_under_comment_parameters_builder(info):
    # info =  data['accepted']['comment_parameters']
    main_text = add_task['user_setting_comment']

    # Если нет заданных параметров или только словарь с предварительно заданными значениями
    if not info or \
            info == {'one_value': {}} or \
            info == {'only_english': False, 'one_value': {}} or \
            info == {'only_english': False}:
        return main_text + '\n\nИ так, давай начнём настройку👇'
    # Если есть заданные параметры
    else:
        main_text += '\n\n<b>Заданные настройки:</b>'

    # Если были заданы одни из настроек для проверки текста
    if 'one_value' in info and 'words' in info['one_value']:
        main_text += '\n<b>— Параметр:</b> '
        # Если было задано количество слов
        if info['one_value']['words']:
            main_text += f"по количеству слов (<code>{info['one_value']['words']}</code>)"
        # Если было задано количество тэгов
        elif info['one_value']['tags']:
            main_text += f"по количеству тэгов (<code>{info['one_value']['tags']}</code>)"
        # Если были заданы ключевые слова/тэги
        else:
            words = info['one_value']['tags/words']['words']
            tags = info['one_value']['tags/words']['tags']
            main_text += f"по ключевым словам/тэгам (<code>{', '.join(words + (tags if tags else []))}</code>)"
    if 'note' in info:
        main_text += f"\n<b>— Примечание для исполнителей:</b> {info['note']}"

    # Если был задан английский язык
    if 'only_english' in info and info['only_english']:
        main_text += '\n<b>— Язык:</b> только английский'
    return main_text


# Функция под добавление одного из трёх параметров проверки (по словам/тэгам/словам и тегам)
async def text_under_adding_one_parameter_builder(info):
    # info = data['accepted']['comment_parameters']
    main_text = add_task['user_add_one_comment_parameter']
    # Если не было задано ни одного параметра
    if not info or info == {'one_value': {}}:
        return main_text + '\n\nКакую проверку ты хочешь активировать и настроить?👇'

    # Если был задан хоть один параметр
    main_text += '\n\n<b>— Заданный параметр:</b> '
    # Если было задано количество слов
    if info['words']:
        main_text += f"по количеству слов (<code>{info['words']}</code>)"
    # Если было задано количество тэгов
    elif info['tags']:
        main_text += f"по количеству тэгов (<code>{info['tags']}</code>"
    # Если были заданы ключевые слова/тэги
    else:
        words = info['tags/words']['words']
        tags = info['tags/words']['tags']
        main_text += f"по ключевым словам/тэгам (<code>{', '.join(words + (tags if tags else []))}</code>)"
    return main_text


# Находит итоговую комиссию
async def count_commission(list_actions: list[str], count=1):
    total_price = await define_price(list_actions, count)
    original_price = total_price / (1 + await db.get_commission() / 100)
    commission = total_price - original_price
    return round_numbers(commission)


# Добавляет тот прайс, который будет за определённое количество заданий
async def define_price(list_actions: list, count=1) -> int | float:
    sum = 0
    prices_dict = await db.get_prices()
    if 'subscriptions' in list_actions:
        sum += prices_dict['subscriptions']
    if 'likes' in list_actions:
        sum += prices_dict['likes']
    if 'retweets' in list_actions:
        sum += prices_dict['retweets']
    if 'comments' in list_actions:
        sum += prices_dict['comments']

    # Считает комиссию
    sum += (sum / 100 * await db.get_commission())
    sum *= count
    return round_numbers(sum)


def round_numbers(num: int | float) -> int | float:
    return int(num) if float(num).is_integer() else round(num, 2)


# Текст, который показывает пользователю, почему такая стоимость задания
async def final_text_builder(list_actions: list) -> str:
    prices_dict = await db.get_prices()
    answer_dict = {'subscriptions': f"<b>+{prices_dict['subscriptions']} $STB за подписку</b>",
                   'likes': f"<b>+{prices_dict['likes']} $STB за поставленный лайк</b>",
                   'retweets': f"<b>+{prices_dict['retweets']} $STB за ретвит</b>",
                   'comments': f"<b>+{prices_dict['comments']} $STB за комментарий</b>",
                   'commission': f"<b>+{await count_commission(list_actions)} $STB в качестве комиссии за добавление задания</b>"}
    prices = ''
    for type_task in list_actions:
        prices += answer_dict[type_task] + '\n'
    prices += answer_dict['commission'] + '\n'

    return prices


# Небольшая функция для того, чтобы собрать нужный текст в блоке, который говорит о том, что у пользователя не хватает денег на добавление задания
async def no_money_text_builder(data, balance: float, balance_flag: bool = False):
    need = await define_price(data['setting_actions'], data["number_users"] if "number_users" in data else 5)
    result = int(need - balance) if (need - balance).is_integer() else round(need - balance, 2)
    balance = int(balance) if type(balance) == float and balance.is_integer() else round(balance, 2)
    # Если у пользователя хватает баланса для добавления минимального количества заданий и он просто указал больше, чем нужно
    if balance_flag:
        text = 'Упс, как я вижу, <b>твоего баланса не хватит на добавление такого количества выполнений🥲</b>\n\n' + \
                f'<b>Выполнений указано:</b> {data["number_users"]}\n' + \
                add_task['not_have_need_balance'].format(need, balance, result, await final_text_builder(data['setting_actions']))
    # Если у пользователя нет баланса или не хватает на добавление минимального количества
    else:
        text = 'Упс, как я вижу, <b>твоего баланса не хватит на добавление минимального количества выполнений, равного <code>5</code> 🥲</b>\n\n' + \
                add_task['not_have_need_balance'].format(need, balance, result, await final_text_builder(data['setting_actions']))
    return text


# Уёбищнейшая функция, собирающая текст-предупреждение о том, что мы не сможем выполнить задание, либо его выполнение может сильно затянуться
async def text_before_posting(tg_id, data):
    exceptions = await db.feasibility_check(tg_id, data)
    # Если ошибок нет, ничего не отправляем
    if not exceptions:
        return ''

    text = '\nПредупреждение: '
    executions = {}
    for action in exceptions:
        execution = await db.get_number_executions(data['accepted']['profile_link'] if action == 'subscriptions' else data['accepted']['post_link'], action)
        if execution > 20:
            executions[action] = execution
    # Собираем основные предупреждения, если они есть (это о том, что мы такой объём просто не вывезем, у нас аккаунтов столько нет)
    basic_warnings = []
    for action, exception in exceptions.items():
        if exception == 'NotEnoughAccounts':
            basic_warnings.append(action)

    if basic_warnings:
        exceptions_basic_warning = {key: value for key, value in executions.items() if key in basic_warnings}
        dop_text = ''
        dop_dict = {'subscriptions': 'подписку', 'likes': 'лайк', 'retweets': 'ретвит', 'comments': 'комментарий'}
        for action in exceptions_basic_warning:
            if action == 'subscriptions':
                dop_text += 'подписку на указанный тобой аккаунт' + (', а также ' if 'likes' in exceptions_basic_warning or 'retweets' in exceptions_basic_warning or 'comments' in exceptions_basic_warning else '')
            else:
                dop_text += f"{', '.join([dop_dict[action] for action in exceptions_basic_warning if action != 'subscriptions'])} на указанный тобой пост"
                break
        if dop_text:
            text += dop_text + ' уже много раз выполняли\n'
        else:
            text += 'кажется, ты ввёл слишком большое количество заданий'

        dop = f", либо же убрать {list(dop_dict)[0] + ' из действий в задании' if len(dop_dict) == 1 else 'одно из действий в задании'}" if dop_text else ''
        text += f"Поскольку у нас нет такого количества аккаунтов, которые смогут выполнить твоё задание, его выполнение может затянуться. Во избежание этого, ты можешь уменьшить число выполнений" + dop

    else:
        dop_text = ''
        dop_dict = {'subscriptions': 'подписку', 'likes': 'лайк', 'retweets': 'ретвит', 'comments': 'комментарий'}
        for action in executions:
            if action == 'subscriptions':
                dop_text += 'подписку на указанный тобой аккаунт' + (
                    ', а также ' if 'likes' in executions or 'retweets' in executions or 'comments' in executions else '')
            else:
                dop_text += f"{', '.join([dop_dict[action] for action in executions if action != 'subscriptions'])} на указанный тобой пост"
                break
        if dop_text:
            text += dop_text + ' уже много раз выполняли\n'
        dop = f", либо же убрать {list(dop_dict)[0] + ' из действий в задании' if len(dop_dict) == 1 else 'одно из действий в задании'}" if dop_text else ''
        text = 'Выполнение данного задания может затянуться. Во избежание этого, ты можешь уменьшить число выполнений' + dop

    return f'<i>{text}</i>'

