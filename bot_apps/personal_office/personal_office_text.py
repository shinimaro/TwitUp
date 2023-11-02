from databases.database import db
from bot_apps.wordbank.wordlist import accounts
from bot_apps.wordbank.wordlist import personal_account


# Функция, показывающая информацию о пользователе при открытии личного кабинета
# По факту просто берёт готовые данные из функции в базе данных и билдит их в словарь
async def personal_account_text_builder(tg_id: str | int) -> str:
    # uncollected_balance = await db.uncollected_balance_check(tg_id)
    dict_info = await db.get_personal_info(tg_id)
    general_text = personal_account['main_text'].format(int(dict_info['balance']) if dict_info['balance'].is_integer() else round(dict_info['balance'], 2),
                                                        '' if not dict_info['uncollected_balance'] else personal_account['dop_text'].format(
                                                        int(dict_info['uncollected_balance']) if dict_info['uncollected_balance'].is_integer() else
                                                        round(dict_info['uncollected_balance'], 2)),
                                                        dict_info.get('subscriptions', 0),
                                                        dict_info.get('likes', 0),
                                                        dict_info.get('retweets', 0),
                                                        dict_info.get('comments', 0),
                                                        int(dict_info['earned']) if float(dict_info['earned']).is_integer() else round(dict_info['earned'], 2),
                                                        dict_info['count_account'])
    return general_text


# Функция для составления текста с информацией об аккаунтах в один список
# Это нужно для того, чтобы не обращаться раз за разом к базе данных, тормозя бота
async def accounts_text_builder(accounts_dict: dict) -> dict:
    # Если аккаунтов нет
    if not accounts_dict:
        return {'page_1': accounts['not_accounts']}

    main_text = '<b>Информация по аккаунтам:</b>\n\n'
    # Устанавливаем количество аккаунтов на странице
    accounts_in_page = 8
    # Устанавливаем номер страницы
    page = 1
    # Формируем текст страницы
    list_text = {f'page_{page}': [main_text]}
    for account in accounts_dict:
        # Мои "математические расчёты", вычисляющие, стоит ли добавлять новую страницу
        if len(list_text[f'page_{page}'][1:]) % accounts_in_page == 0 and len(list_text[f'page_{page}'][1:]) != 0:
            # Добавляется новая страница
            page += 1
            list_text.setdefault(f'page_{page}', [main_text])
        # Формируется остальной текст с информацией о каждом аккаунте
        text = f'<b><a href="https://twitter.com/{account[1:]}">{account}</a></b>\n'
        # Если на аккаунте есть несобранные монетки, то включаем и их
        if accounts_dict[account]['balance'] > 0:
            text += f"<b>Несобранных монет:</b> {int(accounts_dict[account]['balance']) if accounts_dict[account]['balance'].is_integer() else round(accounts_dict[account]['balance'], 2)} $SBT\n"
        text += f"<b>Доступных заданий:</b> {accounts_dict[account]['count']}\n"
        text += f"<b>Статус:</b><code> {'Включен' if accounts_dict[account]['status'] == 'active' else 'Выключен'}</code>\n\n"
        list_text[f'page_{page}'].append(text)

    return list_text


# Текст для истории конкретного аккаунта
async def history_account_builder(tg_id: int, account: str) -> dict[str, str]:
    history_dict = await db.account_history(tg_id, account)
    page = 1
    main_dict = {account: {}}
    list_text = f'<b>Аккаунт:</b> <a href="https://twitter.com/{account[1:]}"><b>{account}</b></a>\n\n'
    count = 1
    for history in history_dict:
        if count > 8:
            main_dict[account][f'page_{page}'] = list_text
            list_text = f'<b>Аккаунт:</b> <a href="https://twitter.com/{account[1:]}"><b>{account}</b></a>\n\n'
            page += 1
            count = 1

        list_text += f'<b>Дата выполнения: </b>{history_dict[history]["date_of_completion"]}\n'
        list_text += f'<b>Награда: </b>{int(history_dict[history]["price"]) if history_dict[history]["price"].is_integer() else round(history_dict[history]["price"], 2)}\n'
        list_text += f'<b>Действия: </b>\n'
        if 'subscriptions' in history_dict[history]['actions']['type_task']:
            list_text += f'<a href="{history_dict[history]["actions"]["links"]["profile_link"]}">—Подписка на аккаунт</a>\n'
            history_dict[history]['actions']['type_task'].remove('subscriptions')
        if 'likes' in history_dict[history]['actions']['type_task'] or 'retweets' in history_dict[history]['actions']['type_task'] or 'comments' in history_dict[history]['actions']['type_task']:
            action_list = []
            if 'likes' in history_dict[history]['actions']['type_task']:
                action_list.append('лайк')
            if 'retweets' in history_dict[history]['actions']['type_task']:
                action_list.append('ретвит')
            if 'comments' in history_dict[history]['actions']['type_task']:
                action_list.append('комментарий')
            text = '—' + ', '.join(action_list).capitalize() + ' на пост'
            list_text += f'''<a href="{history_dict[history]['actions']['links']['post_link']}">{text}</a>\n'''
        list_text += '\n'
        count += 1
    main_dict[account][f'page_{page}'] = list_text
    return main_dict


# Билдер текста для истории, которую открыли списком
async def tasks_list_text_builder(all_task, page=1):
    main_text = ''
    list_account = [i for i in all_task]
    for task in list_account[page*8-8:page*8-1]:
        main_text += f'<b>Аккаунт: </b><a href="https://twitter.com/{all_task[task]["account_name"][1:]}"><b>{all_task[task]["account_name"]}</b></a>\n'
        main_text += f'<b>Дата выполнения: </b>{all_task[task]["date_of_completion"]}\n'
        main_text += f'<b>Награда:</b> {int(all_task[task]["price"]) if all_task[task]["price"].is_integer() else round(all_task[task]["price"], 2)} $STB\n'
        if 'subscriptions' in all_task[task]['type_task']:
            main_text += f'<a href="{all_task[task]["link_action"]["profile_link"]}">—Подписка на аккаунт</a>\n'
        if 'likes' in all_task[task]['type_task'] or 'retweets' in all_task[task]['type_task'] or 'comments' in all_task[task]['type_task']:
            action_list = []
            if 'likes' in all_task[task]['type_task']:
                action_list.append('лайк')
            if 'retweets' in all_task[task]['type_task']:
                action_list.append('ретвит')
            if 'comments' in all_task[task]['type_task']:
                action_list.append('комментарий')
            text = '—' + ', '.join(action_list).capitalize() + ' на пост'
            main_text += f'''<a href="{all_task[task]['link_action']['post_link']}">{text}</a>\n'''
        main_text += '\n'

    return main_text





