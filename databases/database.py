import datetime
import re
from typing import TypedDict

import asyncpg
import pytz as pytz

from config.config import load_config

config = load_config()
account_active_day = 8


class WorkersInfo(TypedDict):
    telegram_id: int
    level: str
    available_accounts: int
    priority: int
    tasks_sent_today: int
    subscriptions: bool
    likes: bool
    retweets: bool
    comments: bool


class Database:
    def __init__(self):
        self.host = config.database.db_host
        self.database = config.database.db_name
        self.user = config.database.db_user
        self.password = config.database.db_password
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            host=self.host,
            database=self.database,
            user=self.user,
            password=self.password)

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

    # Проверка, есть ли пользователь в базе данных
    async def _user_in_database(self, tg_id):
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow("SELECT telegram_id FROM users WHERE telegram_id = $1", tg_id)
            if result is not None:
                return True
            return False

    # Добавление нового пользователя в базу данных
    async def adding_user_in_database(self, tg_id, tg_name, link=None):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                if not await self._user_in_database(tg_id):
                    await connection.execute('INSERT INTO users(telegram_id, telegram_name) VALUES ($1, $2)', tg_id, tg_name)
                    await connection.execute('INSERT INTO user_notifications(telegram_id) VALUES ($1)', tg_id)
                    await connection.execute('INSERT INTO reviews(telegram_id) VALUES ($1)', tg_id)
                    # Создаём ему реферальный кабинет и записываем рефовода, если он есть
                    if link:
                        await connection.execute('INSERT INTO referral_office(telegram_id, inviter, date_of_invitation) VALUES ($1, (SELECT telegram_id FROM referral_office WHERE promocode = $2), NOW())', tg_id, link)
                    else:
                        await connection.execute('INSERT INTO referral_office(telegram_id) VALUES ($1)', tg_id)

    # Добавить главный интерфейс
    async def add_main_interface(self, tg_id, message_id):
        async with self.pool.acquire() as connection:
            await connection.execute('INSERT INTO main_interface(telegram_id, message_id, time_message) VALUES ($1, $2, now())', tg_id, message_id)

    # Получить главный интерфейс
    async def get_main_interface(self, tg_id):
        async with self.pool.acquire() as connection:
            main_interface = await connection.fetchrow('SELECT message_id FROM main_interface WHERE telegram_id = $1', tg_id)
            if main_interface:
                return main_interface['message_id']

    # Обновить главное сообщение
    async def update_main_interface(self, tg_id, message_id):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE main_interface SET message_id = $2, time_message = now() WHERE telegram_id = $1', tg_id, message_id)

    # Получить время последнего сообщение главного интерфейса из бд
    async def get_time_add_main_interface(self, tg_id):
        async with self.pool.acquire() as connection:
            time = await connection.fetchrow('SELECT time_message FROM main_interface WHERE telegram_id = $1', tg_id)
            if time:
                return time['time_message'].astimezone()

    # Проверка на то, нужно ли, при возвращении в главное меню, боту писать новое сообщение, а не изменять существующее
    async def check_answer_message(self, tg_id, message_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                # Проверка того, прошло ли 20 минут с момента последнего обновления сообщения
                check = await connection.fetchrow("SELECT COUNT(*) as countus FROM main_interface WHERE telegram_id = $1 AND now() - time_message >= INTERVAL '20 minutes'", tg_id)
                if check['countus']:
                    return True
                # Вторая проверка, есть ли какие-то задания, которые были отправлены ранее
                check = await connection.fetchrow("SELECT COUNT(*) as countus FROM tasks_messages JOIN statistics USING(tasks_msg_id) LEFT JOIN failure_statistics USING(tasks_msg_id) WHERE telegram_id = $1 AND status IN ('offer', 'offer_more', 'start_task', 'process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND (statistics.offer_time > (SELECT time_message FROM main_interface WHERE telegram_id = $1) OR failure_statistics.perform_time_comment > (SELECT time_message FROM main_interface WHERE telegram_id = $1) OR failure_statistics.waiting_link_time > (SELECT time_message FROM main_interface WHERE telegram_id = $1))", tg_id)
                if check['countus']:
                    return True
                # Последняя проверка на то, что главное меню вызывается не из основного интерфейса
                check = await connection.fetchrow('SELECT message_id FROM main_interface WHERE telegram_id = $1', tg_id)
                if check['message_id'] != message_id:
                    return True
                return False

    # +
    # Получить все данные для личного кабинета
    async def get_personal_info(self, tg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                personal_info = await connection.fetchrow("SELECT users.balance, b1.earned, b2.count_account FROM users, (SELECT SUM(final_reward) as earned FROM completed_tasks WHERE telegram_id = $1) as b1, (SELECT COUNT(account_name) as count_account FROM accounts WHERE telegram_id = $1 and deleted <> True) as b2 WHERE users.telegram_id = $1;", tg_id)
                categories_tasks = await connection.fetch('SELECT actions.type_task as type FROM actions INNER JOIN tasks USING(task_id) INNER JOIN completed_tasks USING(task_id) WHERE completed_tasks.telegram_id = $1', tg_id)
                uncollected_balance = await connection.fetchrow('SELECT SUM(account_balance) as balance FROM accounts WHERE telegram_id = $1 and deleted = False', tg_id)
                dict_info = {'balance': personal_info.get('balance', 0), 'earned': personal_info.get('earned', 0) if personal_info.get('earned', 0) else 0, 'count_account': personal_info.get('count_account', 0), 'uncollected_balance': uncollected_balance.get('balance', 0)}
                for i in range(len(categories_tasks)):
                    dict_info.setdefault(categories_tasks[i][0], 0)
                    dict_info[categories_tasks[i][0]] += 1
                return dict_info

    # +
    # Показывает все аккаунты пользователя
    async def get_accounts(self, tg_id):
        async with self.pool.acquire() as connection:
            # Это старый здоровый запрос, отбирающий все задания, фильры которых проходит аккаунт и все дополнительные уже не нужные данные
            # accounts = await connection.fetch("SELECT accounts.account_name, account_status.level, tb1.counts, accounts.account_status, accounts.account_balance FROM accounts LEFT JOIN (SELECT accounts.account_name, COUNT(b1.type_task) as counts FROM accounts JOIN account_status USING(account_name), (SELECT actions.type_task, tasks.task_id, task_filters.account_level, task_filters.date_of_registration, task_filters.followers, task_filters.subscribers, task_filters.quantity_posts FROM tasks LEFT JOIN task_filters USING(filter_id) LEFT JOIN actions USING(task_id) WHERE tasks.telegram_id <> $1 AND status = 'active') as b1 WHERE accounts.telegram_id = $1 AND (account_status.level >= b1.account_level OR b1.account_level is NULL) AND (AGE(account_status.date_of_registration, b1.date_of_registration) <= INTERVAL '0 days' OR b1.date_of_registration is Null) AND (account_status.followers >= b1.followers OR b1.followers is NULL) AND (account_status.subscribers >= b1.subscribers OR b1.subscribers is NULL) AND ((account_status.posts + account_status.retweets) >= b1.quantity_posts OR b1.quantity_posts is NULL) AND ((b1.task_id, accounts.account_name) NOT IN (SELECT task_id, account_name FROM completed_tasks WHERE telegram_id = $1)) GROUP BY accounts.account_name, account_status.level, accounts.account_status) as tb1 USING(account_name) INNER JOIN account_status USING(account_name) WHERE accounts.deleted = False AND accounts.telegram_id = $1 ORDER BY CASE WHEN accounts.account_status = 'inactive' THEN 1 ELSE 0 END, account_status.level DESC;", tg_id)
            accounts = await connection.fetch("SELECT account_name, account_status, account_balance FROM accounts WHERE accounts.deleted = False AND accounts.telegram_id = $1 ORDER BY CASE WHEN accounts.account_status = 'inactive' THEN 1 ELSE 0 END, account_name", tg_id)
            accounts_dict = {}
            for acc in accounts:
                accounts_dict[acc['account_name']] = {'count': 0, 'balance': acc['account_balance'] if acc['account_balance'] else 0, 'status': acc['account_status']}
            # Выдаёт готовый словарь с текстом
            return accounts_dict

    # Показывает, добавлял ли пользователь когда-то хотя бы 1 аккаунт
    async def check_adding_accounts(self, tg_id):
        async with self.pool.acquire() as connection:
            check = await connection.fetchrow('SELECT account_name FROM accounts WHERE telegram_id = $1', tg_id)
            if check:
                return True
            return False



    # # Получить все задания для каждого аккаунта пользователя
    # async def get_tasks_for_accounts(self, tg_id):
    #     async with self.pool.acquire() as connection:
    #         accounts_info = await connection.fetch("SELECT accounts.account_name, b1.type_task FROM accounts JOIN account_status USING(account_name), (SELECT actions.type_task, task_filters.account_level, task_filters.date_of_registration, task_filters.followers, task_filters.subscribers, task_filters.quantity_posts FROM tasks LEFT JOIN task_filters USING(filter_id) LEFT JOIN actions USING(task_id) WHERE telegram_id <> $1 AND status = 'active') as b1 WHERE accounts.telegram_id = $1 AND accounts.deleted = False AND (account_status.level >= b1.account_level OR b1.account_level is NULL) AND (AGE(account_status.date_of_registration, b1.date_of_registration) <= INTERVAL '0 days' OR b1.date_of_registration is Null) AND (account_status.followers >= b1.followers OR b1.followers is NULL) AND (account_status.subscribers >= b1.subscribers OR b1.subscribers is NULL) AND ((account_status.posts + account_status.retweets) >= b1.quantity_posts OR b1.quantity_posts is NULL) AND (b1.task_id NOT IN (SELECT task_id FROM completed_tasks WHERE telegram_id = $1))", tg_id)
    #         accounts_info_dict = {}
    #         for account in accounts_info:
    #             accounts_info_dict.setdefault(account[0], {'subscriptions': 0, 'likes': 0, 'retweets': 0, 'comments': 0})
    #             accounts_info_dict[account[0]][account[1]] += 1
    #         return accounts_info_dict

    # +
    # Получить информацию по конкретному аккаунту
    async def get_account_info(self, acc_name, tg_id):
        async with self.pool.acquire() as connection:
            # Старый запрос, вытаскивающий все задания, под фильтры которых попадает этот аккаунт и прочую статистику
            # info = await connection.fetch("SELECT accounts.account_name, accounts.account_status, (SELECT SUM(tasks.price) FROM completed_tasks JOIN tasks USING(task_id) WHERE completed_tasks.account_name = $2) as balancer, accounts.account_balance, account_status.level, tb1.type_task FROM accounts LEFT JOIN (SELECT accounts.account_name, b1.type_task FROM accounts JOIN account_status USING(account_name), (SELECT actions.type_task, tasks.task_id, task_filters.account_level, task_filters.date_of_registration, task_filters.followers, task_filters.subscribers, task_filters.quantity_posts FROM tasks LEFT JOIN task_filters USING(filter_id) LEFT JOIN actions USING(task_id) WHERE tasks.telegram_id <> $1 AND status = 'active') as b1 WHERE accounts.telegram_id = $1 AND (account_status.level >= b1.account_level OR b1.account_level is NULL) AND (AGE(account_status.date_of_registration, b1.date_of_registration) <= INTERVAL '0 days' OR b1.date_of_registration is Null) AND (account_status.followers >= b1.followers OR b1.followers is NULL) AND (account_status.subscribers >= b1.subscribers OR b1.subscribers is NULL) AND ((account_status.posts + account_status.retweets) >= b1.quantity_posts OR b1.quantity_posts is NULL) AND ((b1.task_id, accounts.account_name) NOT IN (SELECT task_id, account_name FROM completed_tasks WHERE telegram_id = $1)) GROUP BY accounts.account_name, account_status.level, accounts.account_status, b1.type_task) as tb1 USING(account_name) INNER JOIN account_status USING(account_name) WHERE accounts.deleted = False AND accounts.telegram_id = $1 AND accounts.account_name = $2 ORDER BY CASE WHEN accounts.account_status = 'inactive' THEN 1 ELSE 0 END, account_status.level DESC;", tg_id, acc_name)
            info = await connection.fetchrow("SELECT account_name, account_status, account_balance, (SELECT SUM(final_reward) as balancer FROM completed_tasks WHERE account_name = $1 AND telegram_id = $2) FROM accounts WHERE account_name = $1", acc_name, tg_id)
            info_dict = {'status': info['account_status'], 'earned': info['balancer'] if info['balancer'] else 0, 'account_balance': info['account_balance'], 'type': {'subscriptions': 0, 'likes': 0, 'retweets': 0, 'comments': 0}}
            return info_dict

    # +
    # Собрать все монеты с аккаунта
    async def collect_rewards(self, tg_id, acc_name):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                balance_account = await connection.fetchrow("SELECT account_balance FROM accounts WHERE account_name = $2 AND telegram_id = $1", tg_id, acc_name)
                if balance_account and balance_account['account_balance'] > 0:
                    await connection.execute("UPDATE users SET balance = balance + (SELECT account_balance FROM accounts WHERE account_name = $2) WHERE telegram_id = $1", tg_id, acc_name)
                    await connection.execute("UPDATE accounts SET account_balance = 0 WHERE account_name = $2 AND telegram_id = $1", tg_id, acc_name)
                    balance_user = await connection.fetchrow("SELECT balance FROM users WHERE telegram_id = $1", tg_id)
                    return balance_account['account_balance'], balance_user['balance']
                return None, None

    # +
    # Поменять статус аккаунта на выключен/включён
    async def change_status_account(self, tg_id, acc_name, status):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE accounts SET account_status = $3 WHERE account_name = $2 AND telegram_id = $1", tg_id, acc_name, status)

    # Присваивание аккаунту статуса 'удалён' и перевод всего несобранного баланса на аккаунт пользователя
    async def delete_acc_in_db(self, tg_id, acc_name):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                # Перевод несобранного баланса с аккаунта на баланс пользователя
                await connection.execute("UPDATE users SET balance = balance + (SELECT account_balance FROM accounts WHERE account_name = $2) WHERE telegram_id = $1", tg_id, acc_name)
                await connection.execute("UPDATE accounts SET deleted = True, account_balance = 0 WHERE telegram_id = $1 AND account_name = $2", tg_id, acc_name)

    # +
    # Проверка на то, самый первый ли аккаунт у пользователя, либо уже есть добавленные
    async def check_first_accounts(self, tg_id):
        async with self.pool.acquire() as connection:
            check = await connection.fetchrow('SELECT account_name FROM accounts WHERE telegram_id = $1', tg_id)
            if check:
                return True
            return False

    # Проверка на то, что аккаунт не принадлежит кому-то ещё и не удалён, если принадлежит, отправляет tg_id пользователя
    async def stock_account(self, acc_name):
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow('SELECT telegram_id FROM accounts WHERE account_name = $1 AND deleted = False', acc_name)
            if result:
                return result['telegram_id']
            return False

    # # Отключение всех уведомлений
    # async def enable_all_off(self, tg_id):
    #     async with self.pool.acquire() as connection:
    #         await connection.execute("UPDATE user_notifications SET subscriptions = False, likes = False, retweets = False, comments = False WHERE telegram_id = $1", tg_id)

    # Первое включение всех уведомлений
    async def enable_all_on(self, tg_id):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE user_notifications SET all_notifications = True, notifications_flag = True, subscriptions = True, likes = True, retweets = True, comments = True WHERE telegram_id = $1", tg_id)

    # Получить статус включения всех уведомлений
    async def get_all_notifications(self, tg_id):
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow('SELECT all_notifications FROM user_notifications WHERE telegram_id = $1', tg_id)
            return result['all_notifications']

    # Узнать, включен ли "приём заданий" и есть ли добавленные аккаунты у пользователя
    async def get_all_notifications_and_account(self, tg_id):
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow('SELECT all_notifications FROM user_notifications WHERE telegram_id = $1 AND (SELECT COUNT(*) FROM accounts WHERE telegram_id = $1) > 0', tg_id)
            if result and not result['all_notifications']:
                return True
            return False

    # Функция для отключения всех уведомлений и добавления/удаления из ремайндера
    async def update_all_notifications(self, tg_id, status: bool):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute('UPDATE user_notifications SET all_notifications = $2 WHERE telegram_id = $1;', tg_id, status)
                await connection.execute('UPDATE user_notifications SET notifications_flag = $2 WHERE telegram_id = $1;', tg_id, status)
                # Если пользователь включил все уведомления
                if status:
                    await connection.execute('DELETE FROM reminder_steps WHERE telegram_id = $1', tg_id)
                # Если пользователь выключил уведомления (на всякий случай защита от двойного добавления)
                else:
                    await connection.execute('INSERT INTO reminder_steps (telegram_id) VALUES ($1) ON CONFLICT (telegram_id) DO NOTHING;', tg_id)

    # Самостоятельное отключение/включение приёма задания
    async def change_all_notifications(self, tg_id, change=False):
        async with self.pool.acquire() as connection:
            check = await connection.fetchrow('SELECT all_notifications FROM user_notifications WHERE telegram_id = $1', tg_id)
            check_notifications = check['all_notifications']
            # Если его приём заданий у него включён, то выключаем его
            if not change and check_notifications:
                await connection.execute('UPDATE user_notifications SET all_notifications = False WHERE telegram_id = $1', tg_id)
            # Если его флаг был включён, но мы ему отрубили приём заданий, то включаем их обратно
            if change:
                check_flag = await connection.fetchrow('SELECT notifications_flag FROM user_notifications WHERE telegram_id = $1', tg_id)
                if check_flag['notifications_flag'] and not check_notifications:
                    await connection.execute('UPDATE user_notifications SET all_notifications = True WHERE telegram_id = $1', tg_id)

    # Самостоятельный обруб кнопки
    async def turn_off_receiving_tasks(self, tg_id):
        async with self.pool.acquire() as connection:
            check = await connection.fetchrow('SELECT all_notifications FROM user_notifications WHERE telegram_id = $1', tg_id)
            # Если у пользователя было включено получение заданий
            if check['all_notifications']:
                await self.update_all_notifications(tg_id, False)
                return True
            return False


    # Функция для проверки того, нужно ли отключать приём заданий. Возвращает либо True - всё ок, либо текст того, какая проблема
    async def off_all_notifications(self, tg_id) -> dict | bool:
        async with self.pool.acquire() as connection:
            check = await connection.fetch('SELECT account_name, deleted, account_status, subscriptions, likes, retweets, comments FROM accounts LEFT JOIN user_notifications USING(telegram_id) WHERE telegram_id = $1 ORDER BY deleted, account_status', tg_id)
            if not check:
                check = await connection.fetch('SELECT account_name, deleted, account_status, subscriptions, likes, retweets, comments FROM accounts RIGHT JOIN user_notifications USING(telegram_id) WHERE telegram_id = $1 ORDER BY deleted, account_status', tg_id)
            info_dict = {'not_notifications': False, 'deleted_flag': False, 'disabled_flag': False, 'notifications': {'subscriptions': check[0]['subscriptions'], 'likes': check[0]['likes'], 'retweets': check[0]['retweets'], 'comments': check[0]['comments']}}
            notifications_list = [notification for notification in info_dict['notifications'].values() if notification]
            if not notifications_list:
                await self.change_all_notifications(tg_id)
                info_dict['not_notifications'] = True
                return info_dict
            else:
                for i in check:
                    if not i['account_name']:
                        pass
                    elif i['deleted']:
                        info_dict['deleted_flag'] = True
                    elif i['account_status'] == 'inactive':
                        info_dict['disabled_flag'] = True
                    else:
                        await self.change_all_notifications(tg_id, change=True)
                        return True
                    # Преждевременная остановка цикла, если все ключи получены
                    # if info_dict['deleted_flag'] and info_dict['disabled_flag']:
                    #     break
            await self.change_all_notifications(tg_id)
        return info_dict

    # Функция по поиску всех пользователей, которым нужно напомнить о том, что они отключили задание)
    async def all_users_task_notifications(self):
        async with self.pool.acquire() as connection:
            # Отбираются все записи, в которых, с момента отсчёта времени, прошло более суток
            users = await connection.fetch("SELECT * FROM reminder_steps WHERE NOW() - countdown > INTERVAL '1 day' AND telegram_id NOT IN (SELECT telegram_id FROM is_banned) AND telegram_id NOT IN (SELECT telegram_id FROM they_banned);")
            user_dict = {}
            for user in users:
                if user['step_3']:
                    user_dict[user['telegram_id']] = {'last_step': 'step_3', 'countdown': user['countdown'].astimezone()}
                elif user['step_2']:
                    user_dict[user['telegram_id']] = {'last_step': 'step_2', 'countdown': user['countdown'].astimezone()}
                elif user['step_1']:
                    user_dict[user['telegram_id']] = {'last_step': 'step_1', 'countdown': user['countdown'].astimezone()}
                else:
                    user_dict[user['telegram_id']] = {'last_step': 'step_0', 'countdown': user['countdown'].astimezone()}
            return user_dict

    # Функция, обновляющая этап уведомления пользователей
    async def update_step_task_notification(self, tg_id, step):
        async with self.pool.acquire() as connection:
            if step == 'step_1':
                await connection.execute(f'UPDATE reminder_steps SET step_1 = TRUE WHERE telegram_id = $1', tg_id)
            elif step == 'step_2':
                await connection.execute(f'UPDATE reminder_steps SET step_2 = TRUE WHERE telegram_id = $1', tg_id)
            else:
                await connection.execute(f'UPDATE reminder_steps SET step_3 = TRUE WHERE telegram_id = $1', tg_id)

    # Функция для добавления нового аккаунта
    async def add_account(self, tg_id, acc_name):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                # Если аккаунт уже есть в базе данных и был удалён
                if await connection.fetchrow('SELECT account_name FROM accounts WHERE account_name = $1', acc_name):
                    await connection.execute("UPDATE accounts SET telegram_id = $1, account_status = 'active', deleted = False WHERE account_name = $2", tg_id, acc_name)
                # Если аккаунт новый
                else:
                    await connection.execute("INSERT INTO accounts(telegram_id, account_name) VALUES ($1, $2)", tg_id, acc_name)


    # # Функция для добавления нового аккаунта и его соответствующих характеристик
    # async def add_account(self, tg_id, acc_name, all_info_dict):
    #     async with self.pool.acquire() as connection:
    #         date_of_registration = datetime.datetime.strptime(all_info_dict['date_of_registration'], '%Y-%m-%d').date()
    #         await connection.execute("INSERT INTO accounts(telegram_id, account_name) VALUES($1, $2)", tg_id, acc_name)
    #         await connection.execute("INSERT INTO account_status(account_name, level, date_of_registration, followers, subscribers, posts, retweets) VALUES ($1, $2, $3, $4, $5, $6, $7)", acc_name, all_info_dict['level'], date_of_registration, all_info_dict['followers'], all_info_dict['subscribers'], all_info_dict['posts'], all_info_dict['retweets'])

    # # Проверка аккаунта на то, есть ли он в базе данных и, в зависимости от этого, обновляем/добавляем данные
    # async def check_before_adding(self, tg_id, acc_name, all_info_dict):
    #     async with self.pool.acquire() as connection:
    #         async with connection.transaction():
    #             result = await connection.fetch('SELECT telegram_id FROM accounts WHERE account_name = $1', acc_name)
    #             # Если есть в базе данных в статусе удалённого
    #             if result:
    #                 await connection.execute("UPDATE accounts SET deleted = False, account_status = 'active', telegram_id = $1 WHERE account_name = $2", tg_id, acc_name)
    #             # Если совершенно новый аккаунт
    #             else:
    #                 await self.add_account(tg_id, acc_name, all_info_dict)


    # # Проверка на то, можно ли обновлять аккаунт и, если нет, то показывает время, оставшееся до следующего обновления
    # async def check_to_update(self, acc_name) -> bool | float:
    #     async with self.pool.acquire() as connection:
    #         last_update = await connection.fetchrow('SELECT last_update FROM accounts WHERE account_name = $1', acc_name)
    #         if last_update:
    #             # Преобразовываем объект datetime из результата запроса в "aware" объект с временной зоной UTC
    #             last_update = last_update[0].astimezone(pytz.UTC)
    #             current_time = datetime.datetime.now(pytz.UTC)
    #             time_difference = current_time - last_update
    #             hours_difference = time_difference.total_seconds() / 3600
    #             if hours_difference < 24:
    #                 return 24 - hours_difference
    #             return True
    #         return True

    # Получить все настройки
    async def all_setting(self, tg_id):
        async with self.pool.acquire() as connection:
            settings = await connection.fetch("SELECT subscriptions, likes, retweets, comments FROM user_notifications WHERE telegram_id = $1", tg_id)
            return settings[0]

    # Смена настроек уведомлений
    async def change_setting(self, tg_id, types, action):
        async with self.pool.acquire() as connection:
            if types == 'subscriptions':
                await connection.execute('UPDATE user_notifications SET subscriptions = $1 WHERE telegram_id = $2', action, tg_id)
            elif types == 'likes':
                await connection.execute('UPDATE user_notifications SET likes = $1 WHERE telegram_id = $2', action, tg_id)
            elif types == 'retweets':
                await connection.execute('UPDATE user_notifications SET retweets = $1 WHERE telegram_id = $2', action, tg_id)
            elif types == 'comments':
                await connection.execute('UPDATE user_notifications SET comments = $1 WHERE telegram_id = $2', action, tg_id)



    # Показывает, сколько наград у пользователя
    async def uncollected_balance_check(self, tg_id):
        async with self.pool.acquire() as connection:
            uncollected_balance = await connection.fetchrow('SELECT SUM(account_balance) as balance FROM accounts WHERE telegram_id = $1 and deleted = False', tg_id)
            if uncollected_balance['balance'] and uncollected_balance['balance'] > 0:
                return int(uncollected_balance['balance']) if uncollected_balance['balance'].is_integer() else round(uncollected_balance['balance'], 2)

    # Собираем сразу все награды со всех аккаунтов
    async def collection_of_all_awards(self, tg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute('UPDATE users SET balance = balance + (SELECT SUM(account_balance) FROM accounts WHERE telegram_id = $1  AND deleted = False) WHERE telegram_id = $1', tg_id)
                await connection.execute('UPDATE accounts SET account_balance = 0 WHERE telegram_id = $1', tg_id)

    # Проверка того, что пользователь заработал на заданиях 100 STB и может быть пропущен в реф. аккаунт
    async def check_pass_ref_office(self, tg_id):
        async with self.pool.acquire() as connection:
            check = await connection.fetchrow('SELECT SUM(final_reward) as final_reward FROM completed_tasks WHERE telegram_id = $1', tg_id)
            if check['final_reward'] and check['final_reward'] >= 100:
                return True
            return False

    # Получить промокод
    async def get_promocode(self, tg_id):
        async with self.pool.acquire() as connection:
            promocode = await connection.fetchrow('SELECT promocode FROM referral_office WHERE telegram_id = $1', tg_id)
            if not promocode:
                return False
            return promocode['promocode']

    # Узнать, есть ли у кого-то такой же промокод
    async def check_promocode(self, promocode):
        async with self.pool.acquire() as connection:
            check_promocode = await connection.fetchrow('SELECT promocode FROM referral_office WHERE promocode = $1', promocode)
            if check_promocode:
                return False
            return True

    # Добавление нового промокода
    async def save_new_promocode(self, tg_id, promocode):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE referral_office SET promocode = $2 WHERE telegram_id = $1', tg_id, promocode)

    # +
    # Функция для вытаскивания данных для партнёрской статистики
    async def affiliate_statistics_info(self, tg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                current_month = datetime.datetime.now().month
                # Друзей всего приглашено
                count_people = await connection.fetchrow('SELECT COUNT(telegram_id) as count_people FROM referral_office WHERE inviter = $1', tg_id)
                # Активных из них
                active_people = await connection.fetchrow("SELECT COUNT(DISTINCT telegram_id) as active_people FROM completed_tasks WHERE date_of_completion >= CURRENT_TIMESTAMP - INTERVAL '7 day' AND telegram_id IN (SELECT telegram_id FROM referral_office WHERE inviter = $1)", tg_id)
                # Новых людей приглашено в настоящем месяце
                new_people_in_month = await connection.fetchrow('SELECT COUNT(DISTINCT telegram_id) as new_people_in_month FROM referral_office WHERE EXTRACT(MONTH FROM date_of_invitation) = $2 AND inviter = $1 GROUP BY EXTRACT(MONTH FROM date_of_invitation)', tg_id, current_month)
                # Заработано Рефами за всё время
                earned_by_friends = await connection.fetchrow('SELECT SUM(final_reward) as earned_by_friends FROM completed_tasks WHERE telegram_id IN (SELECT telegram_id FROM referral_office WHERE inviter = $1)', tg_id)
                # Сколько из заработанного было дано рефоводу
                sum_earned = await connection.fetchrow('SELECT SUM(final_reward) / 100.0 * 1.5 AS sum_earned FROM completed_tasks WHERE telegram_id IN (SELECT telegram_id FROM referral_office WHERE inviter = $1)', tg_id)
                # Сколько он собрал в итоге
                collected_from_promocode = await connection.fetchrow('SELECT total_earned as total_earned FROM referral_office WHERE telegram_id = $1', tg_id)

                # 2 кривых костыля
                if earned_by_friends['earned_by_friends'] is None:
                    earned_by_friends = {'earned_by_friends': 0}
                if sum_earned['sum_earned'] is None:
                    sum_earned = {'sum_earned': 0}

                affiliate_statistics_dict = {
                    'count_people': count_people.get('count_people', 0) if count_people else 0,
                    'active_people': active_people.get('active_people', 0) if active_people else 0,
                    'new_people_in_month': new_people_in_month.get('new_people_in_month', 0) if new_people_in_month else 0,
                    'earned_by_friends': int(earned_by_friends.get('earned_by_friends', 0)) if float(earned_by_friends.get('earned_by_friends', 0)).is_integer() else round(earned_by_friends.get('earned_by_friends', 0), 2),
                    'sum_earned': int(sum_earned.get('sum_earned', 0)) if float(sum_earned.get('sum_earned', 0)).is_integer() else round(sum_earned.get('sum_earned', 0), 2),
                    'collected_from_promocode': int(collected_from_promocode.get('total_earned', 0)) if float(collected_from_promocode.get('total_earned', 0)).is_integer() else round(collected_from_promocode.get('total_earned', 0), 2),
                }
                return affiliate_statistics_dict

    # +
    # Проверяем, что пользователь может собрать награды (если только часть. то в каком количестве)
    async def check_referral_reward(self, tg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                current_balance = await connection.fetchrow('SELECT current_balance FROM referral_office WHERE telegram_id = $1', tg_id)
                can_collect = await connection.fetchrow('SELECT (SELECT SUM(final_reward) FROM completed_tasks WHERE telegram_id = $1) - total_earned as can_collect FROM referral_office WHERE telegram_id = $1', tg_id)
                # Если юзер не может собрать ни одной своей награды
                if not can_collect['can_collect'] or can_collect['can_collect'] <= 0:
                    return False
                # Если юзер спокойно может собрать все награды
                elif can_collect['can_collect'] >= current_balance['current_balance']:
                    return True
                # Если юзер может собрать только часть наград
                else:
                    return can_collect['can_collect']

    # +
    # Собираем информацию для реферального кабинета
    async def ref_office_info(self, tg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                ref_office_all_info = await connection.fetchrow("SELECT promocode, current_balance, (SELECT(COUNT(inviter)) FROM referral_office WHERE inviter = $1) as referrals FROM referral_office WHERE telegram_id = $1", tg_id)
                active_referrals = await connection.fetch("SELECT telegram_id FROM completed_tasks WHERE telegram_id IN (SELECT telegram_id FROM referral_office WHERE inviter = $1) AND date_of_completion >= CURRENT_TIMESTAMP - INTERVAL '7 days'", tg_id)
                active_referrals_set = set([i['telegram_id'] for i in active_referrals])
                ref_office_info_dict = {'promocode': None, 'current_balance': 0, 'referrals': 0, 'active_referrals': len(active_referrals_set)}
                for key, value in ref_office_all_info.items():
                    ref_office_info_dict[key] = value if value is not None else 0
                return ref_office_info_dict

    # +
    # Проверка наличия наград
    async def check_referral_rewards(self, tg_id):
        async with self.pool.acquire() as connection:
            check_referral_rewards = await connection.fetchrow('SELECT current_balance FROM referral_office WHERE telegram_id = $1', tg_id)
            if not check_referral_rewards or check_referral_rewards['current_balance'] <= 0:
                return False
            return True

    # +
    # Обновляем балансы реферального кабинета и баланс пользователя, а также выводит, сколько было взято и какой итоговый баланс
    async def collection_of_referral_rewards(self, tg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                balance_collection = await connection.fetchrow('SELECT current_balance FROM referral_office WHERE telegram_id = $1', tg_id)
                await connection.execute('UPDATE referral_office SET total_earned = total_earned + current_balance WHERE telegram_id = $1', tg_id)
                await connection.execute('UPDATE users SET balance = balance + (SELECT current_balance FROM referral_office WHERE telegram_id = $1) WHERE telegram_id = $1', tg_id)
                await connection.execute('UPDATE referral_office SET current_balance = 0 WHERE telegram_id = $1', tg_id)
                balance_user = await connection.fetchrow('SELECT balance FROM users WHERE telegram_id = $1', tg_id)
                return balance_collection['current_balance'], balance_user['balance']

    # Пользователь собирает часть реферальных наград
    async def collect_part_of_referral_rewards(self, tg_id, part):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute('UPDATE referral_office SET total_earned = total_earned + $2 WHERE telegram_id = $1', tg_id, part)
                await connection.execute('UPDATE users SET balance = balance + $2 WHERE telegram_id = $1', tg_id, part)
                await connection.execute('UPDATE referral_office SET current_balance = current_balance - $2 WHERE telegram_id = $1', tg_id, part)
                balance_user = await connection.fetchrow('SELECT balance FROM users WHERE telegram_id = $1', tg_id)
                return balance_user['balance']

    # +
    # Вытаскиваем данные для статистики аккаунта
    async def statistic_info(self, tg_id):
        async with self.pool.acquire() as connection:
            tasks = await connection.fetch('SELECT actions.type_task, tasks.date_of_creation FROM completed_tasks INNER JOIN tasks USING(task_id) INNER JOIN actions USING(task_id) WHERE completed_tasks.telegram_id = $1 ORDER BY tasks.date_of_creation DESC', tg_id)
            prices = await connection.fetch('SELECT subscriptions, likes, retweets, comments, date_added FROM prices_actions ORDER BY date_added DESC')
            earned_referrals = await connection.fetchrow('SELECT total_earned FROM referral_office WHERE telegram_id = $1', tg_id)
            # Инициализация словаря
            statistic_dict = {'subscriptions': 0, 'likes': 0, 'retweets': 0, 'comments': 0, 'earned_referrals': earned_referrals['total_earned']}
            index = 0
            for task in tasks:
                if task['date_of_creation'] >= prices[index]['date_added']:
                    statistic_dict[task['type_task']] += prices[index][task['type_task']]
                else:
                    for price in prices[index+1:]:
                        index += 1
                        if price['date_added'] <= task['date_of_creation']:
                            statistic_dict[task['type_task']] += price[task['type_task']]
                            break
            return statistic_dict





            # # Находим количество всех типов заданий
            # for action in statistic_result:
            #     statistic_dict[action['type_task']] += 1
            # Находим прайс каждого задания
            prices = await connection.fetchrow('SELECT subscriptions, likes, retweets, comments FROM prices_actions ORDER BY prices_id DESC LIMIT 1')
            # Вычисляем итоговый заработок в каждом из типов
            statistic_dict['subscriptions'] = statistic_dict['subscriptions'] * prices['subscriptions']
            statistic_dict['likes'] = statistic_dict['likes'] * prices['likes']
            statistic_dict['retweets'] = statistic_dict['retweets'] * prices['retweets']
            statistic_dict['comments'] = statistic_dict['comments'] * prices['comments']
            # Вычисляем общий заработок
            total_earned = 0
            for i in statistic_dict:
                total_earned += statistic_dict[i]
            statistic_dict['total_earned'] = total_earned

            return statistic_dict

    # # Абсолютно вся информация об аккаунте, включая данные из таблички other_information (нужна для меню повышения уровня аккаунта, либо при первом его добавлении)
    # async def account_all_info(self, tg_id, acc_name):
    #     async with self.pool.acquire() as connection:
    #         async with connection.transaction():
    #             account_all_result = await connection.fetch('SELECT accounts.account_name, account_status.level, account_status.date_of_registration, account_status.followers, account_status.subscribers, account_status.posts, account_status.retweets, other_information.post_per_day, other_information.average_likes, other_information.average_comments  FROM accounts JOIN account_status USING(account_name) LEFT JOIN other_information USING(account_name) WHERE accounts.telegram_id = $1 AND accounts.account_name = $2  AND accounts.deleted = False', tg_id, acc_name)
    #             datetime_obj = datetime.datetime.combine(account_all_result[0]['date_of_registration'], datetime.datetime.min.time())
    #             formatted_date = datetime_obj.strftime('%d.%m.%Y')
    #             account_all_dict = {'account_name': account_all_result[0]['account_name'], 'level': account_all_result[0]['level'], 'date_of_registration': formatted_date, 'followers': account_all_result[0]['followers'], 'subscribers': account_all_result[0]['subscribers'], 'posts': account_all_result[0]['posts'], 'retweets': account_all_result[0]['retweets'], 'post_per_day': account_all_result[0]['post_per_day'], 'average_likes': account_all_result[0]['average_likes'], 'average_comments': account_all_result[0]['average_comments']}
    #             return account_all_dict

    # Проверка на то, пополнял ли пользователь хотя бы раз свой аккаунт
    async def check_payment(self, tg_id):
        async with self.pool.acquire() as connection:
            check = await connection.fetchrow('SELECT telegram_id FROM payments WHERE telegram_id = $1', tg_id)
            # Если есть отметка в истории о пополнении аккаунта
            if check:
                balance = await connection.fetchrow('SELECT balance FROM users WHERE telegram_id = $1', tg_id)
                return balance['balance']
            return False

    # Достать баланс пользователя
    async def check_balance(self, tg_id):
        async with self.pool.acquire() as connection:
            balance = await connection.fetchrow('SELECT balance FROM users WHERE telegram_id = $1', tg_id)
            return balance['balance']

    # Проверка того, хватит ли у нас воркеров для того, чтобы принять задание пользователя
    async def feasibility_check(self, tg_id, data):
        async with self.pool.acquire() as connection:
            all_except = {}
            all_users = {}
            all_accounts = []
            for action in data['setting_actions']:
                link = data['accepted']['profile_link'] if action == 'subscriptions' else data['accepted']['post_link']
                # Запрос, который достаёт все аккаунты и телеграммы людей, которые могут выполнить данное задание, при этом, они должны проявить минимальную активность (выполнить одно задание в течении недели) и их уведомления о всех заданиях тоже должны быть включены, либо выключены, но после этого выключения прошло совсем немного времени (15 минут)
                info = await connection.fetch("SELECT tb_2.telegram_id, account_name, subscriptions, likes, retweets, comments FROM (SELECT tb_1.telegram_id, tb_1.account_name, user_status FROM (SELECT accounts.telegram_id, accounts.account_name, CASE WHEN MAX(CASE WHEN EXISTS (SELECT 1 FROM completed_tasks WHERE accounts.telegram_id = completed_tasks.telegram_id AND NOW() - date_of_completion <= INTERVAL '8 days') THEN 'active' ELSE 'inactive' END) = 'active' THEN 'active' ELSE 'inactive' END AS user_status FROM accounts WHERE account_status = 'active' AND deleted = False AND accounts.telegram_id <> $1 GROUP BY 1, 2) as tb_1 LEFT JOIN completed_tasks USING(account_name) WHERE tb_1.account_name NOT IN (SELECT completed_tasks.account_name FROM actions JOIN tasks USING(task_id) JOIN completed_tasks USING(task_id) WHERE actions.link_action = $2 AND actions.type_task = $3) AND tb_1.account_name NOT IN (SELECT account_name FROM actions JOIN tasks_messages USING(task_id) WHERE tasks_messages.status IN ('process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND actions.link_action = $2 AND actions.type_task = $3) GROUP BY 1, 2, 3) as tb_2 LEFT JOIN user_notifications USING(telegram_id) LEFT JOIN reminder_steps USING(telegram_id) WHERE tb_2.user_status = 'active' AND (all_notifications = True OR (all_notifications = False AND NOW() - countdown <= INTERVAL '15 minutes'));", tg_id, link, action)
                # Добавление всех пользователей в словарь
                for i in info:
                    # Если у пользователя включено получение этого типа заданий
                    if i[action]:
                        all_users.setdefault(i['telegram_id'], {'available': {'subscriptions': i['subscriptions'], 'likes': i['likes'], 'retweets': i['retweets'], 'comments': i['comments']}, 'accounts': []})
                        all_users[i['telegram_id']]['accounts'].append(i['account_name'])
                        all_accounts.append(i['account_name'])
                len_accs = len(all_accounts)
                # Если у нас вообще нет столько аккаунтов, чтобы выполнить этот тип задания
                if len_accs <= data['number_users'] or data['number_users'] / (len_accs / 100) > 90:
                    all_except[action] = 'NotEnoughAccounts'
                # Если количество выполнений, которое он ввёл, больше 70% всех аккаунтов, которые могут выполнить это задание
                elif data['number_users'] / (len_accs / 100) > 70:
                    all_except[action] = 'FewAccounts'
                # Если почти все аккаунты, которые могут выполнить это задание, собраны у небольшой кучки мультиаккеров
                elif (len_accs / len(all_users) / len_accs) * 100 > 60:  # Моя супер формула, вычисляющая % аккаунтов на 1 человека
                    all_except[action] = 'PoorDistribution'
            return all_except

    # Функция для проверки, сколько раз выполняли данное задание
    async def get_number_executions(self, link_action, type_task):
        async with self.pool.acquire() as connection:
            count = await connection.fetchrow("SELECT COUNT(*) as countus FROM completed_tasks INNER JOIN tasks USING(task_id) RIGHT JOIN actions USING(task_id) WHERE link_action = $1 AND type_task = $2", link_action, type_task)
            if count and count['countus'] > 0:
                return count['countus']
            return 0


    # Проверка на то, есть ли у пользователя сделанные задания
    async def check_completed_task(self, tg_id):
        async with self.pool.acquire() as connection:
            check = await connection.fetch('SELECT account_name FROM completed_tasks WHERE telegram_id = $1 ORDER BY unique_id DESC', tg_id)
            if not check:
                return False
            account_list = []
            for c in check:
                if c['account_name'] not in account_list:
                    account_list.append(c['account_name'])
            return account_list

    # +
    # Запрос, вытаскивающий всю историю заданий какого-то аккаунта
    async def account_history(self, tg_id, acc_name):
        async with self.pool.acquire() as connection:
            account_history = await connection.fetch('SELECT tasks.task_id, completed_tasks.date_of_completion, completed_tasks.final_reward as price, actions.type_task, actions.link_action FROM completed_tasks INNER JOIN tasks USING(task_id) INNER JOIN actions USING(task_id) WHERE completed_tasks.telegram_id = $1 AND completed_tasks.account_name = $2 ORDER BY completed_tasks.date_of_completion DESC', tg_id, acc_name)
            account_history_dict = {}
            for info in account_history:
                if not info['task_id'] in account_history_dict:
                    account_history_dict[info['task_id']] = {'date_of_completion': info['date_of_completion'].strftime('%d.%m.%y'), 'price': info['price'], 'actions': {'type_task': [], 'links': {}}}
                account_history_dict[info['task_id']]['actions']['type_task'].append(info['type_task'])
                if info['type_task'] == 'subscriptions':
                    account_history_dict[info['task_id']]['actions']['links']['profile_link'] = info['link_action']
                else:
                    account_history_dict[info['task_id']]['actions']['links']['post_link'] = info['link_action']
            return account_history_dict

    # Вытаскивает все-все сделанные задания пользователя в словарь
    async def all_completed_tasks(self, tg_id):
        async with self.pool.acquire() as connection:
            all_tasks = await connection.fetch('SELECT completed_tasks.unique_id, completed_tasks.account_name, completed_tasks.date_of_completion, completed_tasks.final_reward, actions.type_task, actions.link_action, tasks.price  FROM completed_tasks  INNER JOIN tasks USING(task_id)  INNER JOIN actions USING(task_id)  WHERE completed_tasks.telegram_id = $1 ORDER BY completed_tasks.date_of_completion DESC', tg_id)
            all_tasks_dict = {}
            for task in all_tasks:
                if task['unique_id'] not in all_tasks_dict:
                    all_tasks_dict[task['unique_id']] = {'account_name': task['account_name'], 'date_of_completion': task['date_of_completion'].strftime('%d.%m.%y'), 'price': task['price'] if task['price'] else 0, 'type_task': [], 'link_action': {'profile_link': '', 'post_link': ''}}
                all_tasks_dict[task['unique_id']]['type_task'].append(task['type_task'])
                if task['type_task'] == 'subscriptions':
                    all_tasks_dict[task['unique_id']]['link_action']['profile_link'] = task['link_action']
                else:
                    all_tasks_dict[task['unique_id']]['link_action']['post_link'] = task['link_action']
            return all_tasks_dict

    # Вытаскивает информацию о нужном задании (для его открытия пользователем, после того, как оно ему пришло)
    async def open_task(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                # Вся информация о таске
                task_info = await connection.fetch("SELECT tasks.price, tasks.status, actions.type_task, parameters.parameter_id FROM tasks_messages  INNER JOIN tasks USING(task_id) INNER JOIN actions USING(task_id) LEFT JOIN parameters USING(parameter_id) WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1 AND tasks.deleted <> True)", tasks_msg_id)
                # Если задание было завершено, удалено
                if not task_info:
                    return False
                # Если задание на данный момент неактивно
                if task_info[0]['status'] == 'inactive':
                    return 'inactive'

                task_info_dict = {'price': task_info[0]['price'], 'type_task': []}
                for task in task_info:
                    if task['parameter_id'] and 'comment_parameter' not in task_info_dict:
                        parameter_info = await connection.fetchrow('SELECT * FROM parameters WHERE parameter_id = $1', task['parameter_id'])
                        task_info_dict['comment_parameter'] = {'words_count': parameter_info['words_count'], 'tags_count': parameter_info['tags_count'], 'words_tags': parameter_info['words_tags'], 'note': parameter_info['note'], 'english': parameter_info['english']}
                    if task['type_task'] not in task_info_dict['type_task']:
                        task_info_dict['type_task'].append(task['type_task'])
                return task_info_dict

    # Получить лимит выполнений на задания
    async def get_task_limit(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow('SELECT available_accounts FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id)
            return result['available_accounts']

    # Проверка на то, сколько у пользователя осталось выполнений
    async def get_task_actual_limit(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            executions_limit = await connection.fetchrow('SELECT available_accounts FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id)
            executions = await connection.fetchrow("SELECT COUNT(*) FROM completed_tasks WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1) AND telegram_id = (SELECT telegram_id FROM tasks_messages WHERE tasks_msg_id = $1)", tasks_msg_id)
            return max(executions_limit['available_accounts'] - executions['count'], 0)


    # Функция для вытаскивания id поста и username твиттер профиля
    async def get_link_action(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            links = await connection.fetch('SELECT link_action FROM actions WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id)
            link_action = {'profile_name': '', 'post_id': ''}
            for i in links:
                if re.search(r"/status/\d{19}$", i['link_action']):
                    link_action['post_id'] = re.search(r"/status/(\d{19})$", i['link_action']).group(1)
                else:
                    link_action['profile_name'] = i['link_action'].replace('https://twitter.com/', '')
        return link_action

    # Функция для вытаскивания всех ссылок на задания из таска
    async def get_all_link_on_task(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            all_info = await connection.fetch('SELECT type_task, link_action FROM actions WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id)
            link_dict = {info['type_task']: info['link_action'] for info in all_info}
            return link_dict

    # Функция для формирования начального словаря для старта мейн функции для парсинга
    async def all_task_actions(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            all_actions = await connection.fetch('SELECT type_task FROM actions WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id)
            action_dict = {action['type_task']: None for action in all_actions}
            return action_dict

    # Создание новой записи в базе данных об пуше задания воркеру
    async def create_task_message(self, tg_id, task_id, available_accounts):
        async with self.pool.acquire() as connection:
            tasks_msg_id = await connection.fetchval("INSERT INTO tasks_messages(telegram_id, task_id, status, available_accounts) VALUES ($1, $2, 'offer', $3) RETURNING tasks_msg_id", tg_id, task_id, available_accounts)
            return tasks_msg_id

    # Удаление добавленного сообщения о пуше задания воркеру
    async def delete_task_message(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            await connection.execute('DELETE FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id)

    # Добавление остальных необходимых данных к сообщению
    async def add_info_task_message(self, tasks_msg_id, message_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute('UPDATE tasks_messages SET message_id = $2 WHERE tasks_msg_id = $1', tasks_msg_id, message_id)
                failure_key = await connection.fetchval("INSERT INTO failure_statistics(tasks_msg_id) VALUES ($1) RETURNING failure_key", tasks_msg_id)
                await connection.execute("INSERT INTO statistics(tasks_msg_id, offer_time, failure_key) VALUES ($1, now(), $2)", tasks_msg_id, failure_key)
                # Обновление счётчика отправленных заданий
                tg_id = await self.get_telegram_id_from_tasks_messages(tasks_msg_id)
                await self.update_counter_execute(tg_id)

    # Добавить в счётчик тасков новый таск
    async def update_counter_execute(self, tg_id):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE tasks_distribution SET task_sent_today = task_sent_today + 1 WHERE telegram_id = $1', tg_id)

    # Убрать с счётчика задание, если оно простояло менее 30 минут
    async def decrease_counter_execute(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            check_time = await connection.fetchrow("SELECT * FROM tasks_messages JOIN statistics USING(tasks_msg_id) WHERE deleted_time - offer_time >= INTERVAL '20 minutes' AND tasks_msg_id = $1", tasks_msg_id)
            tg_id = await self.get_telegram_id_from_tasks_messages(tasks_msg_id)
            # Если таск пролежал менее 20 минут
            if not check_time:
                await connection.execute('UPDATE tasks_distribution SET task_sent_today = task_sent_today - 1 WHERE telegram_id = $1', tg_id)


    # Добавить статус и время процесса выполнения задания
    async def update_status_and_time(self, tasks_msg_id, status):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute('UPDATE tasks_messages SET status = $2 WHERE tasks_msg_id = $1', tasks_msg_id, status)
                if status == 'offer_more':
                    await connection.execute('UPDATE statistics SET offer_time_more = now() WHERE tasks_msg_id = $1', tasks_msg_id)
                elif status == 'start_task':
                    await connection.execute('UPDATE statistics SET start_time = now() WHERE tasks_msg_id = $1', tasks_msg_id)
                elif status == 'process':
                    await connection.execute('UPDATE statistics SET perform_time = now() WHERE tasks_msg_id = $1', tasks_msg_id)
                elif status == 'process_subscriptions':
                    await connection.execute('UPDATE failure_statistics SET perform_time_subscriptions = now() WHERE tasks_msg_id = $1', tasks_msg_id)
                elif status == 'process_likes':
                    await connection.execute('UPDATE failure_statistics SET perform_time_like = now() WHERE tasks_msg_id = $1', tasks_msg_id)
                elif status == 'process_retweets':
                    await connection.execute('UPDATE failure_statistics SET perform_time_retweet = now() WHERE tasks_msg_id = $1', tasks_msg_id)
                elif status == 'waiting_link':
                    await connection.execute('UPDATE failure_statistics SET waiting_link_time = now() WHERE tasks_msg_id = $1', tasks_msg_id)
                elif status == 'process_comments':
                    await connection.execute('UPDATE failure_statistics SET perform_time_comment = now() WHERE tasks_msg_id = $1', tasks_msg_id)
                elif status == 'checking':
                    await connection.execute('UPDATE tasks_messages SET status = $2 WHERE tasks_msg_id = $1', tasks_msg_id, status)

    # Получить количество выполненных заданий
    async def get_all_completed_and_price(self, task_id):
        async with self.pool.acquire() as connection:
            # completed = await connection.fetchrow('SELECT executions - (SELECT COUNT(*) FROM completed_tasks WHERE task_id = $1) as count_complete FROM tasks WHERE task_id = $1', task_id)
            price = await connection.fetchrow('SELECT price FROM tasks WHERE task_id = $1', task_id)
            executions = await connection.fetchrow('SELECT executions FROM tasks WHERE task_id = $1', task_id)
            # completed = round(completed.get('count_complete', 0) / 5) * 5
            # return {'count_complete': completed, 'price': price['price'] / 100 * (100 - config.task_price.commission_percent)}
            return {'count_complete': round(executions['executions'] / 5) * 5, 'price': price['price'] if price["price"].is_integer() else round(price["price"], 2)}

    # Получить message_id высланного задания
    async def get_task_message_id(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            message_id = await connection.fetchrow('SELECT message_id FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id)
            if not message_id:
                return False
            return message_id['message_id']

    # Запрос для получения всех аккаунтов пользователя, которые не выполняли заданное задание
    async def accounts_for_task(self, tg_id, tasks_msg_id):
        async with self.pool.acquire() as connection:
            accounts = await connection.fetch("SELECT account_name FROM accounts WHERE account_name NOT IN (SELECT completed_tasks.account_name FROM actions JOIN tasks USING(task_id) JOIN completed_tasks USING(task_id) WHERE (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN tasks USING(task_id) JOIN actions USING(task_id) WHERE tasks_messages.tasks_msg_id = $2) AND completed_tasks.telegram_id = $1) AND account_name NOT IN (SELECT account_name FROM actions JOIN tasks_messages USING(task_id) WHERE tasks_messages.status IN ('process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN actions USING(task_id) WHERE tasks_msg_id = $2)) AND telegram_id = $1 AND accounts.deleted <> True AND accounts.account_status <> 'inactive' ORDER BY account_name", tg_id, tasks_msg_id)
            if not accounts:
                return False
            page = 1
            accounts_dict = {f'page_{page}': []}
            for account in accounts:
                if len(accounts_dict[f'page_{page}']) > 8:
                    page += 1
                    accounts_dict[f'page_{page}'] = []
                accounts_dict[f'page_{page}'].append(account['account_name'])
            return accounts_dict

    # Запрос, который проверяет, есть ли у пользователя другие аккаунты, с которых он может выполнить определённое задание, кроме уже выбранного
    async def accounts_for_task_other_account(self, tg_id, tasks_msg_id):
        async with self.pool.acquire() as connection:
            check = await connection.fetch("SELECT account_name FROM accounts WHERE account_name NOT IN (SELECT completed_tasks.account_name FROM actions JOIN tasks USING(task_id) JOIN completed_tasks USING(task_id) WHERE (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN tasks USING(task_id) JOIN actions USING(task_id) WHERE tasks_messages.tasks_msg_id = $2) AND completed_tasks.telegram_id = $1) AND account_name NOT IN (SELECT account_name FROM actions JOIN tasks_messages USING(task_id) WHERE tasks_messages.status IN ('process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN actions USING(task_id) WHERE tasks_msg_id = $2)) AND telegram_id = $1 AND accounts.deleted <> True AND accounts.account_status <> 'inactive'", tg_id, tasks_msg_id)
            if len(check) > 1:
                return True
            return False

    # Обновить аккаунт, с которого воркер выполняет задание
    async def update_task_account(self, tasks_msg_id, account):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE tasks_messages SET account_name = $2 WHERE tasks_msg_id = $1', tasks_msg_id, account)

    # Получить аккаунт, с которого воркер выполняет задание
    async def get_task_account(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            account = await connection.fetchrow('SELECT account_name FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id)
            return account['account_name']

    # Завершение таска и добавление всех необходимых изменений в базу данных (время завершения, статус, запись в комплитед таск)
    async def task_completed(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                tg_id = await self.get_telegram_id_from_tasks_messages(tasks_msg_id)
                # Обновления время завершения задания и статуса на "выполненный"
                await connection.execute("UPDATE statistics SET finish_time = (now()) WHERE tasks_msg_id = $1", tasks_msg_id)
                await connection.execute("UPDATE tasks_messages SET status = 'completed' WHERE tasks_msg_id = $1", tasks_msg_id)
                # Изменение баланса задания, чтобы снять то, что заработал пользователь
                await connection.execute('UPDATE tasks SET balance_task = balance_task - (SELECT price FROM tasks_messages JOIN tasks USING(task_id) WHERE tasks_msg_id = $1) WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id)
                # Находим то, сколько перевести пользователю
                reward = await connection.fetchrow('SELECT price FROM tasks WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id)
                # Выплата всех штрафов юзера
                reward = await self.payment_of_fines(reward['price'], tg_id)
                # Добавление таска в сделанные (completed_tasks)
                await connection.execute('INSERT INTO completed_tasks(telegram_id, task_id, account_name, tasks_msg_id, final_reward, date_of_completion) SELECT telegram_id, task_id, account_name, $1, $2, (SELECT finish_time FROM statistics WHERE tasks_msg_id = $1) FROM tasks_messages WHERE tasks_msg_id = $1;', tasks_msg_id, reward)
                # Перевод заработанного на баланс аккаунта, с которого было выполнено задание
                await connection.execute('UPDATE accounts SET account_balance = account_balance + $2 WHERE account_name = (SELECT account_name FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id, reward)
                # Перевод заработанного рефоводу
                await connection.execute('UPDATE referral_office SET current_balance = current_balance + $1 WHERE telegram_id = (SELECT inviter FROM referral_office WHERE telegram_id = (SELECT telegram_id FROM tasks_messages WHERE tasks_msg_id = $2))', reward / 100.0 * 1.5, tasks_msg_id)
                # Узнать таск id
                task_id = await connection.fetchrow('SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id)
                # Повышение приоритета пользователя
                await self.change_priority_completing_task(tg_id, task_id['task_id'])
                # Изменение его круга, если это необходимо
                await self.change_in_circle(tg_id)
                # Вернуть итоговое кол-во наград, которое он получил
                return int(reward) if reward.is_integer() else round(reward, 2)

    # Выплата штрафов юзера
    async def payment_of_fines(self, reward, tg_id):
        async with self.pool.acquire() as connection:
            fines_to_reward = await connection.fetch("SELECT fines_id, awards_cut, remaining_to_redeem, already_bought, victim_user FROM fines INNER JOIN bought USING(fines_id) WHERE fines_type = 'bought' AND telegram_id = $1 AND remaining_to_redeem <= already_bought", tg_id)
            if fines_to_reward:
                available_reward = reward / 100 * fines_to_reward[0]['victim_user']
                reward -= available_reward
                for fine in fines_to_reward:
                    need = fine['remaining_to_redeem'] - fine['already_bought']
                    result = need - available_reward
                    available_reward -= need
                    await connection.execute('UPDATE bought SET already_bought = already_bought + $1 WHERE fines_id = $2', result, fine['fines_id'])
                    # Наверное, надо отдельную колоночку создать, с которой он штрафы собирать будет юзер вот этот
                    # await connection.execute('UPDATE users SET balance = balance + $1 WHERE telegram_id = $2', result, fine['victim_user'])
                    if available_reward <= 0:
                        break
                return reward + available_reward
            else:
                return reward

    # Проверка пользователя на то, что ему есть
    async def check_availability(self, tg_id):
        async with self.pool.acquire() as connection:
            # Проверка на то, нужно ли выдать письмо счастья пользователю
            check = await connection.fetchrow('SELECT reviews.telegram_id FROM reviews RIGHT JOIN completed_tasks USING(telegram_id) WHERE telegram_id = $1 AND ((SELECT SUM(completed_tasks.final_reward) FROM completed_tasks WHERE telegram_id = $1) > 20 OR (SELECT COUNT(*) FROM completed_tasks WHERE telegram_id = $1) > 8) AND offered_reviews = False GROUP BY 1', tg_id)
            if check:
                return True
            return False

    # Поменять ключ об уведомлениях
    async def change_offered_reviews(self, tg_id):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE reviews SET offered_reviews = True WHERE telegram_id = $1', tg_id)

    # Пользователь завершил задание и собирает награду - комиссия
    async def collect_reward_from_task(self, tg_id, tasks_msg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                # Проверка на то, что есть что собрать с аккаунта
                reward = await connection.fetchrow('SELECT final_reward FROM completed_tasks WHERE tasks_msg_id = $1', tasks_msg_id)
                account_balance = await connection.fetchrow('SELECT account_balance FROM accounts WHERE account_name IN (SELECT account_name FROM completed_tasks WHERE tasks_msg_id = $1)', tasks_msg_id)
                # Если пользователь не снимал пока STB или баланса хватает, чтобы снять с аккаунта награду и перевести её на баланс
                if account_balance and account_balance['account_balance'] >= reward['final_reward']:
                    # Сбор наград с аккаунта, которому были выделены награды
                    await connection.execute('UPDATE users SET balance = balance + (SELECT final_reward FROM completed_tasks WHERE tasks_msg_id = $2) WHERE telegram_id = $1', tg_id, tasks_msg_id)
                    await connection.execute('UPDATE accounts SET account_balance = account_balance - (SELECT final_reward FROM completed_tasks WHERE tasks_msg_id = $1) WHERE account_balance >= (SELECT final_reward FROM completed_tasks WHERE tasks_msg_id = $1) AND account_name = (SELECT account_name FROM completed_tasks WHERE tasks_msg_id = $1)', tasks_msg_id)

    # Функция для проверки того, есть ли что снять с аккаунта или пользователь уже снимал деньги
    async def check_balance_account(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                balance = await connection.fetchrow('SELECT account_balance FROM accounts WHERE account_name = (SELECT account_name FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id)
                reward = await connection.fetchrow('SELECT price FROM tasks WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id)
                if balance['account_balance'] < reward['price']:
                    return False
                return True

    # Функция для проверки того, завершено уже задание таскодателя или нет
    async def check_completed(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                result = await connection.fetchrow('SELECT executions - (SELECT COUNT(*) as count_completed FROM completed_tasks WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)) AS count_completed FROM tasks WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id)
                if result['count_completed'] <= 0 or not result['count_completed']:
                    return True
                return False

    # Функция, добавляющая время удаления сообщения, а также статус и снижение актива
    async def del_and_change_status_task(self, tasks_msg_id, no_first_execution=False):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                # Если пользователь отказался от задания, то проверяем, поздно он это сделал или нет
                time_difference = await self.get_time_difference_for_refuse_task(tasks_msg_id)
                tg_id = await self.get_telegram_id_from_tasks_messages(tasks_msg_id)
                priority_change = await self.get_priority_change()
                # Если пользователь выполняет таск не в первый раз и заблаговременно его отменил, убираем сообщение о таске
                if no_first_execution and time_difference.total_seconds() < 1 * 60:
                    await connection.execute('DELETE FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id)
                    return
                # Если пользователь незаблогавременно отказался от задания при его первом выполнении или при повторном выполнении через 5 минут
                elif time_difference.total_seconds() < 2 * 60 or (no_first_execution and time_difference.total_seconds() < 5 * 60):
                    finally_priority = await self.min_priority(tg_id, priority_change['refuse'])
                    await connection.execute("UPDATE tasks_messages SET status = 'refuse' WHERE tasks_msg_id = $1", tasks_msg_id)
                # Если пользователь слишком поздно отказался от задания
                else:
                    finally_priority = await self.min_priority(tg_id, priority_change['refuse_late'])
                    await connection.execute("UPDATE tasks_messages SET status = 'refuse_late' WHERE tasks_msg_id = $1", tasks_msg_id)
                await connection.execute("UPDATE tasks_distribution SET priority = $2 WHERE telegram_id = $1", tg_id, finally_priority)
                await connection.execute("UPDATE statistics SET deleted_time = now() WHERE tasks_msg_id = $1", tasks_msg_id)
                await self.change_in_circle(tg_id)

    async def get_time_difference_for_refuse_task(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            time_add_task = await connection.fetchrow('SELECT start_time FROM statistics WHERE tasks_msg_id = $1', tasks_msg_id)
            moscow_timezone = pytz.timezone('Europe/Moscow')
            correct_datetime = time_add_task['start_time'].astimezone(moscow_timezone)
            current_date_moscow = datetime.datetime.now(tz=moscow_timezone)
            return current_date_moscow - correct_datetime



    # Обновить message_id от аккаунта
    async def change_task_message_id(self, tasks_msg_id, message_id):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE tasks_messages SET message_id = $2 WHERE tasks_msg_id = $1", tasks_msg_id, message_id)

    # Получить таск, который ждёт ссылку на комментарий
    async def get_task_for_link(self, tg_id, account):
        async with self.pool.acquire() as connection:
            check_tasks = await connection.fetch("SELECT tasks_msg_id, account_name FROM tasks_messages JOIN statistics USING(tasks_msg_id) WHERE telegram_id = $1 AND status IN ('waiting_link', 'process_comments') ORDER BY start_time DESC", tg_id)
            if not check_tasks:
                return False
            for i in check_tasks:
                if i['account_name'].lower() == f'@{account}'.lower():
                    return int(i['tasks_msg_id'])
            return check_tasks

    # Получить всю информацию из задания для функции по проверке комментария
    async def get_all_task_info(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            task_info = await connection.fetchrow("SELECT tasks_messages.account_name, parameters.* FROM tasks_messages JOIN tasks USING(task_id) JOIN actions USING(task_id) JOIN parameters USING(parameter_id) WHERE tasks_messages.tasks_msg_id = $1 AND actions.type_task = 'comments'", tasks_msg_id)
            return task_info

    # Получить информацию о том, есть ли какие-то ещё задания, которые в процессе выполнения
    async def get_tasks_user(self, tg_id):
        async with self.pool.acquire() as connection:
            # Вытаскивает все задания, у которых статус говорит от том, что таск ещё не завершён/удалён/скрыт
            check_tasks = await connection.fetchrow("SELECT tasks_msg_id  FROM tasks_messages WHERE status IN ('offer', 'offer_more', 'start_task', 'process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND telegram_id = $1", tg_id)
            if check_tasks:
                return True
            return False

    # Получить телеграм юзернейм пользователя, который выполняет задание
    async def get_worker_username(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            username = await connection.fetchrow('SELECT account_name FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id)
            return username

    # Получить ссылку на задание с комментарием
    async def get_link_for_comment(self, tasks_msg_id) -> str:
        async with self.pool.acquire() as connection:
            comment_link = await connection.fetchrow("SELECT link_action FROM actions WHERE type_task = 'comments' AND task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)", tasks_msg_id)
            return comment_link

    # Получить количество тех, кто выполняет задание прямо сейчас и сколько уже выполнений было
    async def get_quantity_completed(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow("SELECT COUNT(*) + (SELECT COUNT(*) FROM completed_tasks WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)) as complete FROM tasks_messages WHERE status IN ('start_task', 'process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1);", tasks_msg_id)
            if result and result['complete'] > 0:
                return result['complete']
            return False

    # +
    # Функция, достающая финальные данные
    async def get_info_to_user_and_tasks(self, tg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                balance = await connection.fetchrow('SELECT users.balance FROM users WHERE telegram_id = $1', tg_id)
                tasks_completed = await connection.fetch("SELECT date_of_completion FROM completed_tasks WHERE telegram_id = $1;", tg_id)
                open_tasks = await connection.fetchrow("SELECT COUNT(*) as count_tasks FROM tasks_messages WHERE status IN ('offer', 'offer_more', 'start_task', 'process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND telegram_id = $1", tg_id)
                # Добываем таймзону, Москвы
                moscow_timezone = pytz.timezone('Europe/Moscow')
                count = 0
                # Сравниваем дату и время с сегодняшним днём
                for task in tasks_completed:
                    # Преобразовываем таймзону в зону МСК
                    correct_datetime = task['date_of_completion'].astimezone(moscow_timezone)
                    # Берём дату Москвы и приставляем ей время 00:00
                    current_date_moscow = datetime.datetime.now(tz=moscow_timezone).date()
                    start_of_day_moscow = datetime.datetime.combine(current_date_moscow, datetime.time.min, tzinfo=moscow_timezone)
                    # Если задача была сделана сегодня по МСК
                    if start_of_day_moscow <= correct_datetime:
                        count += 1
                # Доступно к выполнению, там ещё нужно понять, что значит это доступно
                return {'balance': balance['balance'], 'tasks_completed': count, 'open_tasks': open_tasks['count_tasks']}

    # Функция для проверки того, что этот таск можно выполнить с ещё одного аккаунта и он не завершён
    async def task_again(self, tg_id, tasks_msg_id):
        async with self.pool.acquire() as connection:
            # # Если задание не было ещё завершено
            # if not await connection.fetchrow("SELECT task_id FROM tasks WHERE status = 'completed' AND task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)", tasks_msg_id):
            #     check_again = await connection.fetchrow("SELECT account_name FROM accounts WHERE account_name NOT IN (SELECT completed_tasks.account_name FROM actions JOIN tasks USING(task_id) JOIN completed_tasks USING(task_id) WHERE (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN tasks USING(task_id) JOIN actions USING(task_id) WHERE tasks_messages.tasks_msg_id = $2) AND completed_tasks.telegram_id = $1) AND account_name NOT IN (SELECT account_name FROM actions JOIN tasks_messages USING(task_id) WHERE tasks_messages.status IN ('process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN actions USING(task_id) WHERE tasks_msg_id = $2)) AND telegram_id = $1 AND accounts.deleted <> True AND accounts.account_status <> 'inactive'", tg_id, tasks_msg_id)
            #     if check_again:
            #         return True
            # return False
            # Если задание не было ещё завершено
            if not await connection.fetchrow("SELECT task_id FROM tasks WHERE status = 'completed' AND task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)", tasks_msg_id):
                if await self.get_task_actual_limit(tasks_msg_id) > 0:
                    return True
            return False

    # Функция для проверки того, что этот таск можно выполнить с 2 их более аккаунтов
    async def task_two_again(self, tg_id, tasks_msg_id):
        async with self.pool.acquire() as connection:
            check_again = await connection.fetch("SELECT account_name FROM accounts WHERE account_name NOT IN (SELECT completed_tasks.account_name FROM actions JOIN tasks USING(task_id) JOIN completed_tasks USING(task_id) WHERE (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN tasks USING(task_id) JOIN actions USING(task_id) WHERE tasks_messages.tasks_msg_id = $2) AND completed_tasks.telegram_id = $1) AND account_name NOT IN (SELECT account_name FROM actions JOIN tasks_messages USING(task_id) WHERE tasks_messages.status IN ('process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN actions USING(task_id) WHERE tasks_msg_id = $2)) AND telegram_id = $1 AND accounts.deleted <> True AND accounts.account_status <> 'inactive'", tg_id, tasks_msg_id)
            if len(check_again) > 1:
                return True
            return check_again[0]['account_name']

    # Создание нового сообщения о таске, в случае, когда пользователь решил сделать то же самое задание, но теперь с другого аккаунта
    async def new_tasks_messages(self, tg_id, tasks_msg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                result = await connection.fetchval("INSERT INTO tasks_messages(message_id, task_id, available_accounts, telegram_id, status) VALUES ((SELECT message_id FROM tasks_messages WHERE tasks_msg_id = $2), (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $2), (SELECT available_accounts FROM tasks_messages WHERE tasks_msg_id = $2), $1, 'start_task') RETURNING tasks_msg_id", tg_id, tasks_msg_id)
                failure_key = await connection.fetchval('INSERT INTO failure_statistics(tasks_msg_id) VALUES ($1) RETURNING failure_key', result)
                await connection.execute('INSERT INTO statistics(tasks_msg_id, start_time, failure_key) VALUES ($1, now(), $2)', result, failure_key)
                return result

    # Взять некоторую информацию о задании
    async def info_about_task(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            info = await connection.fetch('SELECT actions.type_task, actions.link_action FROM actions WHERE task_id = (SELECT task_id  FROM tasks_messages WHERE tasks_msg_id = $1) ORDER BY 1', tasks_msg_id)
            info_dict = {'types_actions': [], 'link': info[0]['link_action']}
            for i in info:
                info_dict['types_actions'].append(i['type_task'])
            return info_dict

    # Функция для добавления аккаунта к таску
    async def new_task_account(self, tasks_msg_id, account):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE tasks_messages SET account_name = $2 WHERE tasks_msg_id = $1', tasks_msg_id, account)

    # Функция, добавляющая финальное время удаления
    async def add_del_time_in_task(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE statistics SET deleted_time = (now()) WHERE tasks_msg_id = $1", tasks_msg_id)

    # Функция, добавляющая запись об отказе от задания
    async def add_note_about_refuse(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            await connection.execute('INSERT INTO tasks_refusals(task_id, tasks_msg_id, passed_after_start, execution_stage) VALUES ((SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1), $1, (SELECT NOW() - start_time FROM tasks_messages JOIN statistics USING(tasks_msg_id) WHERE tasks_msg_id = $1), (SELECT COUNT(*) FROM tasks_messages JOIN statistics USING(tasks_msg_id) WHERE telegram_id = (SELECT telegram_id FROM tasks_messages WHERE tasks_msg_id = $1) AND task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)))', tasks_msg_id)

    # Функция, меняющая статус задания на удалённый
    async def add_deleted_status(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE tasks_messages SET status = 'deleted' WHERE tasks_msg_id = $1", tasks_msg_id)

    # Запись в базу даных о скрытии таска
    async def add_note_about_hiding(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            await connection.execute('INSERT INTO tasks_hiding(task_id, tasks_msg_id) VALUES ((SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1), $1)', tasks_msg_id)

    # Функция, которая достаёт все message_id и статусы всех заданий, которые находятся в процессе предложения или выполнения
    async def info_for_delete_messages(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            info = await connection.fetch("SELECT tasks_msg_id, telegram_id, message_id, status FROM tasks_messages WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1) AND status IN ('offer', 'offer_more', 'start_task', 'process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments')", tasks_msg_id)
            info_dict = {}
            for i in info:
                info_dict[f"tasks_msg_id_{i['tasks_msg_id']}"] = {'telegram_id': i['telegram_id'], 'message_id': i['message_id'], 'status': i['status']}
            return info_dict

    # Функция, которая достаёт все таски, в которых прошло 8 минут после начала выполнения
    async def info_all_tasks_messages(self):
        async with self.pool.acquire() as connection:
            all_tasks = await connection.fetch("SELECT tm.tasks_msg_id, telegram_id, message_id, start_time, reminder, status, account_name FROM tasks_messages as tm JOIN statistics USING(tasks_msg_id) WHERE now() - start_time >= interval '8 minutes' AND status IN ('start_task', 'process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments')")
            all_tasks_dict = {}
            for i in all_tasks:
                all_tasks_dict[f"tasks_msg_id_{i['tasks_msg_id']}"] = {'telegram_id': i['telegram_id'], 'message_id': i['message_id'], 'start_time': i['start_time'].astimezone(), 'reminder': i['reminder'], 'status': i['status'], 'account': i['account_name']}
            return all_tasks_dict

    # Обновление статуса задания на "воркер забил, либо забыл"
    async def update_status_on_scored(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute("UPDATE tasks_messages SET status = 'scored' WHERE tasks_msg_id = $1", tasks_msg_id)
                await connection.execute("UPDATE statistics SET deleted_time = now() WHERE tasks_msg_id = $1", tasks_msg_id)
                change_priority = await self.get_priority_change()
                tg_id = await self.get_telegram_id_from_tasks_messages(tasks_msg_id)
                finally_priority = await self.min_priority(tg_id, change_priority['scored_on_task'])
                await connection.execute("UPDATE tasks_distribution SET priority = $2 WHERE telegram_id = $1", tg_id, finally_priority)
                await self.change_in_circle(tg_id)

    # Обновление статуса задания на "другие люди успели завершить задание раньше"
    async def update_status_on_fully_completed(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute("UPDATE tasks_messages SET status = 'fully_completed' WHERE tasks_msg_id = $1", tasks_msg_id)
                await connection.execute("UPDATE statistics SET deleted_time = now() WHERE tasks_msg_id = $1", tasks_msg_id)

    # Повышение рейтинга, в случае, если пользователь делал, но не успел блин доделать
    async def change_priority_not_completed_task(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            status = await connection.execute('SELECT status FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id)
            tg_id = await self.get_telegram_id_from_tasks_messages(tasks_msg_id)
            change_priority = await self.get_priority_change()
            # Если воркер даже не начинал заадние
            if status['status'] == 'offer_more':
                finally_priority = await self.max_priority(tg_id, 3)
            # Если воркер делал задание в этот момент
            else:
                finally_priority = await self.max_priority(tg_id, change_priority['complete_others'])
            await connection.execute('UPDATE tasks_distribution SET priority = $2 WHERE telegram_id = $1', tg_id, finally_priority)
            await self.change_in_circle(tg_id)

    # Понижение рейтинга в зависимости от того, как долго пользователь игнорировал задание
    async def change_priority_ignore_task(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            offer_time = await connection.fetchrow('SELECT offer_time FROM tasks_messages JOIN statistics USING(tasks_msg_id) WHERE tasks_msg_id = $1', tasks_msg_id)
            offer_time = offer_time['offer_time'].astimezone(pytz.timezone('Europe/Moscow'))
            now_time = datetime.datetime.now(pytz.timezone('Europe/Moscow'))
            now_time_only = now_time.hour * 60 + now_time.minute
            offer_time_only = offer_time.hour * 60 + offer_time.minute
            time_difference = offer_time_only - now_time_only
            # change_priority = await self.get_priority_change()
            change_priority = 0
            # Если пользователь игнорил таск более часа 20
            if time_difference >= 80:
                change_priority = -4
            # Если пользователь игнорил таск более 40 минут
            elif time_difference >= 40:
                change_priority = -3
            # Если пользователь игнорил таск от 20 до 40 минут
            elif 20 <= time_difference <= 40:
                change_priority = -1
            tg_id = await self.get_telegram_id_from_tasks_messages(tasks_msg_id)
            finally_priority = await self.min_priority(tg_id, change_priority)
            await connection.execute('UPDATE tasks_distribution SET priority = $2 WHERE telegram_id = $1', tg_id, finally_priority)
            await self.change_in_circle(tg_id)


    # Добавить время удаления (сбора награды) для завершённых заданий
    async def update_deleted_time(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE statistics SET deleted_time = now() WHERE tasks_msg_id = $1', tasks_msg_id)

    # Запись в ремайндер
    async def update_reminder(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE statistics SET reminder = TRUE WHERE tasks_msg_id = $1', tasks_msg_id)

    # Проверка на то, что задание завершено, либо неактивно
    async def get_status_task(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            status = await connection.fetchrow('SELECT status FROM tasks WHERE task_id = (SELECT task_id FROM tasks_messages WHERe tasks_msg_id = $1)', tasks_msg_id)
            return status['status']

    # Запись в базу нового задания
    async def add_new_task(self, tg_id, balance_task, withdrawal_amount, price, executions, types_tasks, accepted):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                # Создание основы для таска
                task_id = await connection.fetchval('INSERT INTO tasks(telegram_id, balance_task, price, executions) VALUES ($1, $2, $3, $4) RETURNING task_id', tg_id, balance_task, price, executions)
                # Снятие с пользователя средств и перевод на счёт баланса таска
                await connection.execute('UPDATE users SET balance = balance - $2 WHERE telegram_id = $1', tg_id, withdrawal_amount)
                # Заполнение всех типов заданий
                for task in types_tasks:
                    if task == 'subscriptions':
                        await connection.execute('INSERT INTO actions(task_id, type_task, link_action) VALUES ($1, $2, $3)', task_id, task, accepted['profile_link'] if accepted['profile_link'] else accepted['post_link'][:accepted['post_link'].find('/status/')])
                    elif task == 'comments':
                        # Объявление переменных
                        words_count = None
                        tags_count = None
                        words_tags = None
                        # Заполнение инглиша и примечания
                        english = accepted['comment_parameters'].get('only_english', None) if accepted['comment_parameters'].get('only_english', None) else None
                        note = accepted['comment_parameters'].get('note', None) if accepted['comment_parameters'].get('note', None) else None
                        # Заполнение параметра проверки
                        if 'one_value' in accepted['comment_parameters']:
                            words_count = int(accepted['comment_parameters']['one_value'].get('words', None)) if accepted['comment_parameters']['one_value'].get('words', None) else None
                            tags_count = int(accepted['comment_parameters']['one_value'].get('tags', None)) if accepted['comment_parameters']['one_value'].get('tags', None) else None
                            if accepted['comment_parameters']['one_value'].get('tags/words', None):
                                words = accepted['comment_parameters']['one_value']['tags/words']['words']
                                tags = accepted['comment_parameters']['one_value']['tags/words']['tags']
                                words_tags = ', '.join(words + (tags if tags else []))
                        parameter_id = await connection.fetchval('INSERT INTO parameters(words_count, tags_count, words_tags, note, english) VALUES ($1, $2, $3, $4, $5) RETURNING parameter_id', words_count, tags_count, words_tags, note, english)
                        await connection.execute('INSERT INTO actions(task_id, type_task, link_action, parameter_id) VALUES ($1, $2, $3, $4)', task_id, task, accepted['post_link'], parameter_id)
                    # Заполнение лайка и ретвита
                    else:
                        await connection.execute('INSERT INTO actions(task_id, type_task, link_action) VALUES ($1, $2, $3)', task_id, task, accepted['post_link'])
                return task_id

    # Получить telegram_id создателя таска
    async def get_id_founder_task(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            telegram_id = await connection.fetchrow('SELECT telegram_id FROM tasks WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id)
            return telegram_id['telegram_id']

    # Получить все действия, которые было необходимо сделать в задании
    async def get_task_actions(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            actions = await connection.fetch('SELECT type_task FROM actions WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id)
            set_actions = set()
            for action in actions:
                set_actions.add(action['type_task'])
            return set_actions

    # Получить количество выполнений, которые нужно сделать в задании
    async def get_executions(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            executions = await connection.fetchrow('SELECT executions FROM tasks WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id)
            return executions['executions']

    # Проверка статуса задания и отметка его, как завершённого
    async def completed_task_status(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            status = await connection.fetchrow('SELECT status FROM tasks WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id)
            # Если статус задания всё ещё стоит как назавершённый
            if status['status'] != 'completed':
                # Смена статуса задания на завершённое
                await connection.execute("UPDATE tasks SET status = 'completed', date_of_completed = now() WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)", tasks_msg_id)
                return True
            return False

    # Проверка статуса задания на то, что оно не проверяется
    async def check_status_checking(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            status = await connection.fetchrow('SELECT status FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id)
            if status['status'] != 'checking':
                return True
            return False

    # Проверка статуса задания на то, что сейчас не выполняется часть с заданием
    async def check_status_comment(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            check = await connection.fetchrow('SELECT status FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id)
            if check['status'] not in ('waiting_link', 'process_comments'):
                return True
            return False

    # Вытаскивание процента из базы данных
    async def get_commission(self):
        async with self.pool.acquire() as connection:
            commission = await connection.fetchrow('SELECT commission FROM prices_actions ORDER BY prices_id DESC LIMIT 1')
            return commission['commission']

    # Вытаскивание всех расценок из базы данных
    async def get_prices(self):
        async with self.pool.acquire() as connection:
            prices = await connection.fetchrow('SELECT subscriptions, likes, retweets, comments FROM prices_actions ORDER BY prices_id DESC LIMIT 1')
            prices_dict = {'subscriptions': int(prices['subscriptions']) if prices['subscriptions'].is_integer() else prices['subscriptions'],
                           'likes': int(prices['likes']) if prices['likes'].is_integer() else prices['likes'],
                           'retweets': int(prices['retweets']) if prices['retweets'].is_integer() else prices['retweets'],
                           'comments': int(prices['comments']) if prices['comments'].is_integer() else prices['comments']}
            return prices_dict

    # Достать словарь с лимитами на задания в день
    async def get_limits_dict(self):
        async with self.pool.acquire() as connection:
            limits = await connection.fetchrow('SELECT vacationers, prelim, main, challenger, champion FROM limits_tasks ORDER BY date_of_added, limits_id DESC LIMIT 1')
            return {action: limit for action, limit in limits.items()}

    # Достать словарь с лимитами на выполнение 1 задания
    async def get_limits_executions_dict(self):
        async with self.pool.acquire() as connection:
            limits = await connection.fetchrow('SELECT beginner, vacationers, prelim, main, challenger, champion FROM limits_execution ORDER BY date_of_added, limits_ex_id DESC LIMIT 1')
            return {level: limit for level, limit in limits.items()}

    # Достать словарь с лимитами на приоритет
    async def get_limits_priority_dict(self):
        async with self.pool.acquire() as connection:
            limits = await connection.fetchrow('SELECT vacationers, prelim, main, challenger, champion FROM limits_priority ORDER BY date_of_added, limits_priority_id DESC LIMIT 1')
            return {level: limit for level, limit in limits.items()}

    # Достать словарь с измененияим приоритета
    async def get_priority_change(self):
        async with self.pool.acquire() as connection:
            priority_change = await connection.fetchrow('SELECT completing_task, re_execution, max_re_execution, complete_others, refuse, refuse_late, hiding_task, number_hiding, scored_on_task FROM priority_change ORDER BY date_of_added, priority_change_id DESC')
            return {type_action: change for type_action, change in priority_change.items()}

    # Вытаскивание всех пользователей для задания и проверка некоторых деталей
    async def get_all_workers(self, task_id):
        async with self.pool.acquire() as connection:
            # Сколько максимум можно оставить тасков без реакции
            max_tasks_in_interval = 2
            # Запрос, который отбирает всех воркеров по условиям
            # 1. У воркера включены задания, он не в бане, это не создатель задания
            # 2. Он не выполняет в данный момент похожее задание и у него есть свободные аккаунты, которые могут выполнить это задание
            # 3. Это не новичок
            # 4. У него уже не висит 3 задания, к которым он даже не приторнуля, ну и вроде всё, может ещё какие-то условия, хз
            all_workers_info: list[WorkersInfo] = await connection.fetch('''SELECT telegram_id, level, priority, COUNT(account_name) as available_accounts, tasks_sent_today, subscriptions, likes, retweets, comments FROM (SELECT user_notifications.telegram_id, level, priority, accounts.account_name, COUNT(CASE WHEN statistics.offer_time >= date_trunc('day', current_timestamp AT TIME ZONE 'Europe/Moscow') THEN 1 END) as tasks_sent_today, subscriptions, likes, retweets, comments FROM user_notifications JOIN tasks_distribution USING(telegram_id) LEFT JOIN tasks_messages USING(telegram_id) LEFT JOIN statistics USING(tasks_msg_id) RIGHT JOIN accounts ON user_notifications.telegram_id = accounts.telegram_id WHERE user_notifications.telegram_id IN (SELECT telegram_id FROM users JOIN user_notifications USING(telegram_id) JOIN tasks_distribution USING(telegram_id) WHERE telegram_id NOT IN (SELECT telegram_id FROM is_banned) AND telegram_id NOT IN (SELECT telegram_id FROM they_banned WHERE ban_status = True) AND telegram_id <> (SELECT telegram_id FROM tasks WHERE task_id = $1) AND user_notifications.all_notifications = True AND tasks_distribution.booking = False) AND accounts.account_name IN (SELECT account_name FROM accounts WHERE account_name NOT IN (SELECT completed_tasks.account_name FROM actions JOIN tasks USING(task_id) JOIN completed_tasks USING(task_id) WHERE (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks JOIN actions USING(task_id) WHERE task_id = $1)) AND account_name NOT IN (SELECT account_name FROM actions JOIN tasks_messages USING(task_id) WHERE tasks_messages.status IN ('process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks JOIN actions USING(task_id) WHERE task_id = $1)) AND accounts.deleted <> True AND accounts.account_status <> 'inactive') AND user_notifications.telegram_id NOT IN (SELECT telegram_id FROM actions FULL OUTER JOIN tasks_messages USING(task_id) WHERE task_id = $1 AND (telegram_id, link_action, type_task) IN (SELECT telegram_id, link_action, type_task FROM tasks_messages JOIN statistics USING(tasks_msg_id) RIGHT JOIN actions USING(task_id) WHERE tasks_messages.status NOT IN ('completed', 'refuse', 'refuse_late', 'scored', 'fully_completed', 'deleted')) GROUP BY telegram_id) AND EXISTS (SELECT 1 FROM tasks_messages WHERE tasks_messages.telegram_id = user_notifications.telegram_id LIMIT 1) GROUP BY accounts.telegram_id, user_notifications.telegram_id, level, priority, accounts.account_name, subscriptions, likes, retweets, comments HAVING COUNT(CASE WHEN tasks_messages.status IN ('offer') THEN 1 END) <= $2) as tg_common GROUP BY telegram_id, level, priority, tasks_sent_today, subscriptions, likes, retweets, comments HAVING COUNT(account_name) > 0;''', task_id, max_tasks_in_interval)
            return await self._get_ready_workers_dict(task_id, all_workers_info)

    # Получить всех воркеров, для какого-то раунда
    async def get_all_workers_for_round(self, task_id):
        async with self.pool.acquire() as connection:
            # all_workers_info: list[WorkersInfo] = await connection.fetch('''SELECT telegram_id, level, priority, COUNT(account_name) as available_accounts, tasks_sent_today, subscriptions, likes, retweets, comments FROM (SELECT user_notifications.telegram_id, level, priority, accounts.account_name, COUNT(CASE WHEN statistics.offer_time >= date_trunc('day', current_timestamp AT TIME ZONE 'Europe/Moscow') THEN 1 END) as tasks_sent_today, subscriptions, likes, retweets, comments FROM user_notifications JOIN tasks_distribution USING(telegram_id) LEFT JOIN tasks_messages USING(telegram_id) LEFT JOIN statistics USING(tasks_msg_id) RIGHT JOIN accounts ON user_notifications.telegram_id = accounts.telegram_id WHERE user_notifications.telegram_id IN (SELECT telegram_id FROM users JOIN user_notifications USING(telegram_id) JOIN tasks_distribution USING(telegram_id) WHERE telegram_id NOT IN (SELECT telegram_id FROM is_banned) AND telegram_id NOT IN (SELECT telegram_id FROM they_banned WHERE ban_status = True) AND telegram_id <> (SELECT telegram_id FROM tasks WHERE task_id = $1) AND user_notifications.all_notifications = True AND tasks_distribution.booking = False) AND accounts.account_name IN (SELECT account_name FROM accounts WHERE account_name NOT IN (SELECT completed_tasks.account_name FROM actions JOIN tasks USING(task_id) JOIN completed_tasks USING(task_id) WHERE (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks JOIN actions USING(task_id) WHERE task_id = $1)) AND account_name NOT IN (SELECT account_name FROM actions JOIN tasks_messages USING(task_id) WHERE tasks_messages.status IN ('process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks JOIN actions USING(task_id) WHERE task_id = $1)) AND accounts.deleted <> True AND accounts.account_status <> 'inactive') AND user_notifications.telegram_id NOT IN (SELECT telegram_id FROM actions FULL OUTER JOIN tasks_messages USING(task_id) WHERE task_id = $1 AND (telegram_id, link_action, type_task) IN (SELECT telegram_id, link_action, type_task FROM tasks_messages JOIN statistics USING(tasks_msg_id) RIGHT JOIN actions USING(task_id) WHERE tasks_messages.status NOT IN ('completed', 'refuse', 'refuse_late', 'scored', 'fully_completed', 'deleted')) GROUP BY telegram_id) AND EXISTS (SELECT 1 FROM tasks_messages WHERE tasks_messages.telegram_id = user_notifications.telegram_id LIMIT 1) GROUP BY accounts.telegram_id, user_notifications.telegram_id, level, priority, accounts.account_name, subscriptions, likes, retweets, comments HAVING COUNT(CASE WHEN tasks_messages.status IN ('offer') THEN 1 END) <= $2) as tg_common GROUP BY telegram_id, level, priority, tasks_sent_today, subscriptions, likes, retweets, comments HAVING COUNT(account_name) > 0;''', task_id, max_tasks_in_interval)

            # В отличии от запроса выше, тут
            # Убрано условие, чтобы не лежало много тасков
            # Добавлено поле с инфо о круге юзера
            # Если юзер уже как-то контактировал с данным таском, он не отбирается
            all_workers_info: list[WorkersInfo] = await connection.fetch('''SELECT telegram_id, circular_round, level, priority, COUNT(account_name) as available_accounts, tasks_sent_today, subscriptions, likes, retweets, comments FROM (SELECT user_notifications.telegram_id, circular_round, level, priority, accounts.account_name, COUNT(CASE WHEN statistics.offer_time >= date_trunc('day', current_timestamp AT TIME ZONE 'Europe/Moscow') THEN 1 END) as tasks_sent_today, subscriptions, likes, retweets, comments FROM user_notifications JOIN tasks_distribution USING(telegram_id) LEFT JOIN tasks_messages USING(telegram_id) LEFT JOIN statistics USING(tasks_msg_id) RIGHT JOIN accounts ON user_notifications.telegram_id = accounts.telegram_id WHERE user_notifications.telegram_id IN (SELECT telegram_id FROM users JOIN user_notifications USING(telegram_id) JOIN tasks_distribution USING(telegram_id) WHERE telegram_id NOT IN (SELECT telegram_id FROM is_banned) AND telegram_id NOT IN (SELECT telegram_id FROM they_banned WHERE ban_status = True) AND telegram_id <> (SELECT telegram_id FROM tasks WHERE task_id = $1) AND user_notifications.all_notifications = True AND tasks_distribution.booking = False) AND accounts.account_name IN (SELECT account_name FROM accounts WHERE account_name NOT IN (SELECT completed_tasks.account_name FROM actions JOIN tasks USING(task_id) JOIN completed_tasks USING(task_id) WHERE (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks JOIN actions USING(task_id) WHERE task_id = $1)) AND account_name NOT IN (SELECT account_name FROM actions JOIN tasks_messages USING(task_id) WHERE tasks_messages.status IN ('process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks JOIN actions USING(task_id) WHERE task_id = $1)) AND accounts.deleted <> True AND accounts.account_status <> 'inactive') AND user_notifications.telegram_id NOT IN (SELECT telegram_id FROM actions FULL OUTER JOIN tasks_messages USING(task_id) WHERE task_id = $1 AND (telegram_id, link_action, type_task) IN (SELECT telegram_id, link_action, type_task FROM tasks_messages JOIN statistics USING(tasks_msg_id) RIGHT JOIN actions USING(task_id)) GROUP BY telegram_id) AND EXISTS (SELECT 1 FROM tasks_messages WHERE tasks_messages.telegram_id = user_notifications.telegram_id LIMIT 1) GROUP BY accounts.telegram_id, circular_round, user_notifications.telegram_id, level, priority, accounts.account_name, subscriptions, likes, retweets, comments) as tg_common GROUP BY telegram_id, circular_round, level, priority, tasks_sent_today, subscriptions, likes, retweets, comments HAVING COUNT(account_name) > 0;''', task_id)
            return self._get_ready_workers_dict(task_id, all_workers_info, circular_round=True)

    # Отбор воркеров, у которых нет лимитов на задания
    async def _get_ready_workers_dict(self, task_id, all_workers_info: list[WorkersInfo], circular_round=False):
        actions_tuple = await self.get_actions_tuple(task_id)
        limits_dict = await self.get_limits_dict()
        limits_executions_dict = await self.get_limits_executions_dict()
        ready_workers_dict: dict[int, dict[str, int]] = {} if not circular_round else {'1': {}, '2': {}, '3': {}}
        for info in all_workers_info:
            # Проверка на то, что не превышен лимит на сегодня
            if limits_dict[info['level']] > info['tasks_sent_today']:
                # Проверка на то, что у пользователя включено получение данного вида заданий (лайков, ретвитов)
                for action in actions_tuple:
                    if action in info and not info[action]:
                        break
                else:
                    # Если у пользователя больше аккаунтов, чем нужно, записываем максимум, доступный ему:
                    if not circular_round:
                        ready_workers_dict[info['telegram_id']] = {'priority': info['priority'], 'available_accounts':  min(info['available_accounts'], limits_executions_dict[info['level']])}
                    else:
                        ready_workers_dict[info['circular_round']][info['telegram_id']] = {'priority': info['priority'], 'available_accounts':  min(info['available_accounts'], limits_executions_dict[info['level']])}
                    return ready_workers_dict

    async def get_actions_tuple(self, task_id):
        async with self.pool.acquire() as connection:
            actions = await connection.fetch('SELECT type_task FROM actions WHERE task_id = $1', task_id)
            return tuple(action['type_task'] for action in actions)


    # Отбоор новичков
    async def get_some_beginners(self, task_id):
        async with self.pool.acquire() as connection:
            # Достаём новичков, применяя минимальную проверку (на бан, на то что им сейчас не отправляется другой таск)
            beginners = await connection.fetch('SELECT users.telegram_id, account_name FROM users JOIN user_notifications USING(telegram_id) RIGHT JOIN accounts ON users.telegram_id = accounts.telegram_id WHERE NOT EXISTS (SELECT 1 FROM tasks_messages t WHERE t.telegram_id = users.telegram_id LIMIT 1) AND users.telegram_id <> (SELECT telegram_id FROM tasks WHERE task_id = $1) AND users.telegram_id NOT IN (SELECT telegram_id FROM is_banned) AND users.telegram_id NOT IN (SELECT telegram_id FROM they_banned WHERE ban_status = True) AND user_notifications.all_notifications = True ORDER BY accounts.adding_time ASC', task_id)
            beginner_limit = await self.get_limits_executions_dict()
            beginners_dict = {}
            for beginner in beginners:
                beginners_dict.setdefault(beginner['telegram_id'], 0)
                beginners_dict[beginner['telegram_id']] += 1 if beginners_dict[beginner['telegram_id']] < beginner_limit['beginner'] else 0
            return beginners_dict

    # Получить количество выполнений для завершения таска
    async def get_amount_executions(self, task_id):
        async with self.pool.acquire() as connection:
            executions = await connection.fetchrow('SELECT executions FROM tasks WHERE task_id = $1', task_id)
            return executions['executions']

    # Бронирование воркеров
    async def worker_booking(self, workers: list[int]):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE tasks_distribution SET booking = True WHERE telegram_id = ANY($1)', workers)

    # Разбронировывание воркеров
    async def worker_unbooking(self, workers: list[int]):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE tasks_distribution SET booking = False WHERE telegram_id = ANY($1)', workers)

    # Достаёт информацию о об отправленных заданиях
    async def get_sent_tasks(self, task_id):
        async with self.pool.acquire() as connection:
            # Я так и не смог взять все записи в нужном мне временном промежутке, как бы не пытался(
            # result = await connection.fetch("SELECT task_id, offer_time, start_time FROM tasks_messages JOIN statistics USING(tasks_msg_id) WHERE offer_time >= now() - interval '4 days' AND telegram_id <> (SELECT telegram_id FROM tasks WHERE task_id = $1) ORDER BY offer_time DESC;", task_id)
            result = await connection.fetch("SELECT task_id, offer_time, start_time FROM tasks_messages JOIN statistics USING(tasks_msg_id) WHERE offer_time >= now() - interval '4 days'  ORDER BY offer_time DESC;")
            statistics_dict = {}
            now_time = datetime.datetime.now(pytz.timezone('Europe/Moscow'))
            for info in result:
                # Проверка на то, что задание было создано в нужном нам промежутке
                offer_time = info['offer_time'].astimezone(pytz.timezone('Europe/Moscow'))
                now_time_only = now_time.hour * 60 + now_time.minute
                offer_time_only = offer_time.hour * 60 + offer_time.minute
                time_difference = offer_time_only - now_time_only
                if 0 <= time_difference <= 60:
                    days_difference = (now_time.date() - offer_time.date()).days
                    statistics_dict.setdefault(f'{days_difference}_day_ago', {})
                    statistics_dict[f'{days_difference}_day_ago'].setdefault(info['task_id'], {'quantity_submitted_tasks': 0, 'quantity_accepted_tasks': 0})
                    statistics_dict[f'{days_difference}_day_ago'][info['task_id']]['quantity_submitted_tasks'] += 1 if time_difference <= 50 else 0  # Если поздно сообщение о таске пришло, то его не засчитываем
                    if info['start_time']:
                        start_time = info['start_time'].astimezone(pytz.timezone('Europe/Moscow'))
                        start_time_only = start_time.hour * 60 + start_time.minute
                        statistics_dict[f'{days_difference}_day_ago'][info['task_id']]['quantity_accepted_tasks'] += 1 if now_time_only - start_time_only <= 65 else 0  # Если принял задание в течении нашего часа
            return statistics_dict

    # Функция для нахождения коэфициента принятия заданий за последние дни
    async def get_accepted_tasks(self):
        async with self.pool.acquire() as connection:
            result = await connection.fetch("SELECT task_id, telegram_id, COUNT(offer_time) as number_executions FROM tasks_messages JOIN statistics USING(tasks_msg_id) WHERE offer_time >= NOW() - INTERVAL '4 days' AND start_time IS NOT NULL GROUP BY task_id, telegram_id")
            finally_executions_dict = {}
            for info in result:
                finally_executions_dict.setdefault(info['task_id'], {info['telegram_id']: info['number_executions']})
            return finally_executions_dict

    # Выдача новичкам среднего приоритета и уровня
    async def definition_of_beginners(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            tg_id = await self.get_telegram_id_from_tasks_messages(tasks_msg_id)
            check_task = await connection.fetchrow('SELECT COUNT(*) FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id)
            check_availability = await connection.fetchrow('SELECT telegram_id FROM tasks_distribution WHERE telegram_id = $1', tg_id)
            # Хз, зачем почти две одинаковых проверки,но пусть будет
            if check_task and not check_availability:
                limits_dict = await self.get_limits_dict()
                await connection.execute("INSERT INTO tasks_distribution(telegram_id, priority, level, circular_round, task_sent_today) VALUES ($1, 50, 'main', 1, $2)", tg_id, limits_dict['main'])

    # Достаёт максимальный и минимальный приоритет, который можно выдать воркеру
    async def get_user_limits(self, tg_id):
        async with self.pool.acquire() as connection:
            level = await connection.fetchrow('SELECT level FROM tasks_distribution WHERE telegram_id = $1', tg_id)
            level = level['level']
            limits = await self.get_limits_priority_dict()
            limits_dict = {'max_limits': limits[level],
                           'min_limits': max([value for value in limits.values() if value < limits[level]], default=0)}
            return limits_dict


    # Функция, достающая штрафы, уменьшающие постоянный приоритет юзера
    async def get_current_fines(self, tg_id):
        async with self.pool.acquire() as connection:
            fines = await connection.fetch("SELECT reduction_in_priority FROM fines JOIN temporary USING(fines_id) WHERE fines_type = 'temporary' AND valid_until > NOW() AND telegram_id = $1", tg_id)
            final_fine = 0
            for fine in fines:
                final_fine += abs(fine['reduction_in_priority'])
            return final_fine

    # Проверяет, сколько времени назад пользователь отключал кнопку и не получал заданий
    async def check_button_time(self, tg_id):
        async with self.pool.acquire() as connection:
            check_time = await connection.fetchrow('SELECT countdown FROM reminder_steps WHERE telegram_id = $1', tg_id)
            finally_dict = {'time_has_passed': False, 'tasks_sent_recently': 0}
            # Если он сам отключал кнопку, проверяем, сколько времени прошло
            if check_time:
                # Вычисляем, сколько прошло между отключением кнопки и настоящим
                late_time = check_time['countdown'].astimezone(pytz.timezone('Europe/Moscow'))
                now_time = datetime.datetime.now(pytz.timezone('Europe/Moscow'))
                late_time_only = late_time.hour * 60 + late_time.minute
                now_time_only = now_time.hour * 60 + now_time.minute
                if late_time_only - now_time_only >= 480:
                    finally_dict['time_has_passed'] = True
            # Смотрим, когда он в последний раз получал задание
            count_sending_tasks = await connection.fetchrow("SELECT COUNT(*) FROM statistics JOIN tasks_messages USING(tasks_msg_id) WHERE tasks_messages.telegram_id = $1 AND offer_time >= NOW() - INTERVAL '5 hours'", tg_id)
            # Записываем, сколько за последних 5 часов ему было дано аккаунтов
            finally_dict['tasks_sent_recently'] = count_sending_tasks['count'] if count_sending_tasks and count_sending_tasks['count'] >= 1 else 0
            return finally_dict

    # Информация о прошлых показателях за последние 3 дня
    async def user_executions_info(self, tg_id):
        async with self.pool.acquire() as connection:
            all_info = await connection.fetch("SELECT * FROM tasks_messages JOIN statistics USING(tasks_msg_id) RIGHT JOIN tasks USING(task_id) WHERE tasks_messages.telegram_id = $1 AND offer_time >= NOW() - INTERVAL '3 days' ORDER BY offer_time", tg_id)
            # all_info = await connection.fetch("SELECT * FROM tasks_messages JOIN statistics USING(tasks_msg_id) RIGHT JOIN tasks USING(task_id) WHERE tasks_messages.telegram_id = $1 ORDER BY offer_time", tg_id)

            result_dict = {'number_scored': 0, 'number_failures': 0, 'number_late_failures': 0, 'acceptance_rate': 0}
            tasks_id = []
            tasks_number, start_number = 0, 0
            for info in all_info:
                # Смотрим только первое выполнение таска, чтобы отсечь повторные
                if info['task_id'] not in tasks_id:
                    # Находим таски, которые он не доделал
                    if info['status'] == 'scored':
                        result_dict['number_scored'] += 1
                    elif info['status'] == 'refuse':
                        result_dict['number_failures'] += 1
                    elif info['status'] == 'refuse_late':
                        result_dict['number_late_failures'] += 1
                    # Если таск был стартанут
                    if info['start_time']:
                        tasks_number += 1
                        start_number += 1
                    # Если нет, проверяем, был ли он у юзера дольше 30 минут в игноре
                    elif info['deleted_time']:
                        offer_time = info['offer_time'].astimezone(pytz.timezone('Europe/Moscow'))
                        current_time = datetime.datetime.now(pytz.timezone('Europe/Moscow'))
                        time_difference = current_time - offer_time
                        if time_difference > datetime.timedelta(minutes=30):
                            tasks_number += 1
                    tasks_id.append(info['task_id'])
        result_dict['acceptance_rate'] = int(start_number / max(tasks_number, 1) * 100)
        return result_dict

    # Найти коэфициент выполнений за последние 3 дня
    async def all_users_executions_info(self):
        async with self.pool.acquire() as connection:
            all_info = await connection.fetch("SELECT tasks_messages.telegram_id, task_id, start_time, tasks_messages.status FROM tasks_messages JOIN statistics USING(tasks_msg_id) RIGHT JOIN tasks USING(task_id) WHERE offer_time >= NOW() - INTERVAL '3 days' ORDER BY offer_time")
            return self.select_completion_rate(all_info)

    # Найти коэфициент выполнений среди пользователей с низким активом за последние 3 дня
    async def users_executions_info_with_low_priority(self):
        async with self.pool.acquire() as connection:
            all_info = await connection.fetch("SELECT tasks_messages.telegram_id, task_id, start_time, tasks_messages.status FROM tasks_messages JOIN statistics USING(tasks_msg_id) RIGHT JOIN tasks_distribution USING(telegram_id) RIGHT JOIN tasks USING(task_id) WHERE offer_time >= NOW() - INTERVAL '3 days' AND priority <= 35 ORDER BY offer_time;")
            return self.select_completion_rate(all_info)

    # Отборрать коэфициент выполнений
    def select_completion_rate(self, all_info):
        all_tasks_executions = {}
        counter_tasks = 0
        counter_executions = 0
        for info in all_info:
            all_tasks_executions.setdefault(info['task_id'], [])
            # Если юзер не выполнял это заданий
            if info['telegram_id'] not in all_tasks_executions[info['task_id']]:
                all_tasks_executions[info['task_id']].append(info['telegram_id'])
                if info['start_time']:
                    counter_tasks += 1
                    if info['status'] == 'completed':
                        counter_executions += 1
        completion_rate = max(counter_executions, 1) / max(counter_tasks, 1)
        return completion_rate if completion_rate > 0 else 1

    # Достать кол-во выполнений и кол-во тех, кто в процессе, в таске
    async def get_executions_and_in_process_number(self, task_id):
        async with self.pool.acquire() as connection:
            info = await connection.fetchrow("SELECT executions, (SELECT COUNT(completed_tasks.unique_id) FROM completed_tasks WHERE task_id = $1) as completed_tasks, COUNT(CASE WHEN tasks_messages.status IN ('start_task', 'process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments', 'checking') THEN 1 END) as in_process FROM tasks_messages RIGHT JOIN tasks USING(task_id) WHERE task_id = $1 GROUP BY 1", task_id)
            return {'executions': info['executions'], 'completed_tasks': info['completed_tasks'], 'in_process': info['in_process']}


    # Достать всех забанненых юзеров
    async def get_is_banned_users(self):
        async with self.pool.acquire() as connection:
            users = await connection.fetch('SELECT telegram_id FROM is_banned')
            return [user['telegram_id'] for user in users]

    # Добавить нового юзера в бан
    async def add_ban_user(self, tg_id, reason: str = None, comment: str = None):
        async with self.pool.acquire() as connection:
            await connection.execute('INSERT INTO is_banned (telegram_id, reason, comment) VALUES($1, $2, $3)', tg_id, reason, comment)

    async def del_ban_user(self, tg_id):
        async with self.pool.acquire() as connection:
            await connection.execute('DELETE FROM is_banned WHERE telegram_id = $1', tg_id)

    async def get_they_banned_users(self):
        async with self.pool.acquire() as connection:
            users = await connection.fetch('SELECT telegram_id FROM they_banned WHERE ban_status = True')
            return [user['telegram_id'] for user in users]

    # Смещаем каунтер на 1, убираем пока юзера из списков
    async def del_they_banned_users(self, tg_id):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE they_banned SET ban_status = False, counter = 1, last_message = Null WHERE telegram_id = $1', tg_id)

    # Заполнение в табличку юзера, забанившего нас
    async def they_banned_fill(self, tg_id):
        async with self.pool.acquire() as connection:
            info = await connection.fetchrow('SELECT counter FROM they_banned WHERE telegram_id = $1', tg_id)
            if not info:
                await connection.execute('INSERT INTO they_banned(telegram_id) VALUES ($1)', tg_id)
            elif info['counter'] == 1:
                await connection.execute('UPDATE they_banned SET ban_status = True, counter = 2 WHERE telegram_id = $1', tg_id)
                return True

    # Проверка на то, что пользователь, у которого мы были в бане, написал нам по прошествии 3 дней
    async def check_wait_time(self, tg_id):
        async with self.pool.acquire() as connection:
            check = await connection.fetchrow("SELECT telegram_id FROM they_banned WHERE last_message <= NOW() - INTERVAL '3 days' AND telegram_id = $1", tg_id)
            if check:
                return True
            return False

    # Узнать приоритет юзера
    async def check_priority(self, tg_id):
        async with self.pool.acquire() as connection:
            check_priority = await connection.fetchrow('SELECT priority FROM tasks_distribution WHERE telegram_id = $1', tg_id)
            return check_priority['priority']

    # Узнать круг юзера
    async def check_circular(self, tg_id):
        async with self.pool.acquire() as connection:
            check_circular = await connection.fetchrow('SELECT circular_round FROM tasks_distribution WHERE telegram_id = $1', tg_id)
            return check_circular['circular_round']

    # Проверка на то, что пользователя можно повысить до 2 круга или наоборот понизить
    async def change_in_circle(self, tg_id):
        async with self.pool.acquire() as connection:
            check_priority = await self.check_priority(tg_id)
            check_circular_round = await self.check_circular(tg_id)
            limits_dict = await self.get_limits_priority_dict()
            # Если пользователя нужно повысить
            if check_circular_round == 3 and \
                    check_priority > limits_dict['prelim']:
                await connection.execute('UPDATE tasks_distribution SET circular_round = 2 WHERE telegram_id = $1')
            # Если пользователя нужно понизить
            elif check_circular_round > 3 and \
                    check_priority <= limits_dict['prelim']:
                await connection.execute('UPDATE tasks_distribution SET circular_round = 3 WHERE telegram_id = $1')

    # Изменение приоритета за выполнение задания
    async def change_priority_completing_task(self, tg_id, task_id):
        async with self.pool.acquire() as connection:
            # Находим иотоговый приоритет, который будет у пользователя
            priority_change = await self.get_priority_change()
            number_executions = await connection.fetchrow("SELECT COUNT(*) as executions FROM completed_tasks WHERE task_id = $2 AND telegram_id = $1", tg_id, task_id)
            # Если это первое выполнение задания и выполнений до этого не было
            if number_executions['executions'] == 0:
                finally_priority = await self.max_priority(tg_id, priority_change['completing_task'])
                await connection.execute('UPDATE tasks_distribution SET priority = $2 WHERE telegram_id = $1', tg_id, finally_priority)
            # Если уже не первое, но не более трёх
            elif number_executions['executions'] <= 3:
                finally_priority = await self.max_priority(tg_id, priority_change['re_execution'])
                await connection.execute('UPDATE tasks_distribution SET priority = $2 WHERE telegram_id = $1', tg_id, finally_priority)

    # Проверка на то, что юзер проигнорил более 5 сообщений о тасках подряд и каждый висел у него более 30 минут
    async def check_to_ignore_tasks(self, tg_id):
        async with self.pool.acquire() as connection:
            # Отбор последних 5 сообщений о тасках, которые провисели дольше 30 минут
            tasks = await connection.fetch("SELECT offer_time, offer_time_more, start_time, deleted_time, status FROM tasks_messages JOIN statistics USING (tasks_msg_id) WHERE telegram_id = $1 ORDER BY tasks_msg_id DESC LIMIT 5", tg_id)
            if not tasks:
                return False
            counters_dict = {'offer': 0, 'hiding': 0, 'refuse': 0, 'scored': 0}  # Счётчики действий
            punitive_dict = {'offer': 5, 'hiding': 3, 'refuse': 3, 'scored': 2}  # Дикт с тем, до какого числа дожен дойти счётчик, чтобы воркер получил по жопе
            change_priority = {'offer': -5, 'hiding': -7, 'refuse': -6, 'scored': -20}  # Как сильно изменится приоритет после этого
            for task in tasks:
                offer_time = task['offer_time'].astimezone(pytz.timezone('Europe/Moscow'))
                deleted_time = task['deleted_time'].astimezone(pytz.timezone('Europe/Moscow')) if task['deleted_time'] else datetime.datetime.now(pytz.timezone('Europe/Moscow'))
                deleted_time_only = deleted_time.hour * 60 + deleted_time.minute
                offer_time_only = offer_time.hour * 60 + offer_time.minute
                time_difference = deleted_time_only - offer_time_only
                # Если таск был проигнорен, но он пролежал более 30 минут
                if not task['offer_time_more'] and time_difference > 30:
                    counters_dict['offer'] += 1
                else:
                    counters_dict['offer'] = -10
                # Если таск был скрыт
                if task['offer_time_more'] and not task['start_time'] and task['status'] == 'deleted':
                    counters_dict['hiding'] += 1
                else:
                    counters_dict['hiding'] = -10
                # Если был отказ от таска
                if task['status'] == 'refuse' or task['status'] == 'refuse_late':
                    counters_dict['refuse'] += 1
                else:
                    counters_dict['refuse'] = -10
                # Если с таском произошло забитие
                if task['status'] == 'scored':
                    counters_dict['scored'] += 1
                else:
                    counters_dict['scored'] = -10

                # Проверяем, было ли что-то найдено
                for action in counters_dict:
                    # Если что-то найдено, даём по жопе
                    if counters_dict[action] == punitive_dict[action]:
                        # Если юзер уже много раз забил на таски, делаем понижение макс рейтинга на 3 дня
                        if action == 'scored':
                            await self.add_new_priority_fines(tg_id)
                        # Понижение в рейтинге + отключение кнопки
                        finally_priority = await self.min_priority(tg_id, change_priority[action])
                        print('Отдаю ключ ', finally_priority)
                        await connection.execute('UPDATE tasks_distribution SET priority = $2 WHERE telegram_id = $1', tg_id, finally_priority)
                        await self.change_in_circle(tg_id)
                        return action
            return False

    # Создать новый штраф, связанный с постоянным понижение рейтинга
    async def add_new_priority_fines(self, tg_id, constant_decline=-10):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                fines_id = await connection.fetchval("INSERT INTO fines(telegram_id, fines_type) VALUES ($1, 'temporary') RETURNING fines_id", tg_id)
                await connection.execute("INSERT INTO temporary(fines_id, valid_until, reduction_in_priority) VALUES ($1, NOW() + INTERVAL '3 days', $2)", fines_id, constant_decline)

    async def add_new_reward_fines(self, tg_id, task_id, awards_cut=30):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                fines_id = await connection.fetchval("INSERT INTO fines(telegram_id, fines_type) VALUES ($1, 'temporary') RETURNING fines_id", tg_id)
                task_info = await connection.fetchrow('SELECT telegram_id, price FROM tasks WHERE task_id = $1', task_id)
                await connection.execute("INSERT INTO bought(fines_id, remaining_to_redeem, awards_cut, victim_user) VALUES ($1, $2, $3, $4)", fines_id, task_info['price'], awards_cut, task_id['telegram_id'])

    # Достать тг id из сообщения о таске
    async def get_telegram_id_from_tasks_messages(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            tg_id = await connection.fetchrow('SELECT telegram_id FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id)
            return tg_id['telegram_id']

    # Взять минимально возможный приоритет юзера
    async def min_priority(self, tg_id, change_priority):
        min_priority = 1
        priority_now = await self.check_priority(tg_id)
        return max(priority_now + change_priority, min_priority)

    # Взять максимально возможный приоритет юзера
    async def max_priority(self, tg_id, change_priority):
        max_priority = 100 - await self.get_current_fines(tg_id)
        priority_now = await self.check_priority(tg_id)
        return min(priority_now + change_priority, max_priority)

    # Взять то, сколько тасков нужно сделать на уровень
    async def get_need_for_level(self):
        async with self.pool.acquire() as connection:
            need_tasks = await connection.fetchrow('SELECT prelim, main, challenger, champion FROM number_of_completed_tasks')
            return {level: value for level, value in need_tasks.items()}

    # Взять то, сколько нужно именть аккаунтов на уровень
    async def get_need_accounts(self):
        async with self.pool.acquire() as connection:
            need_accounts = await connection.fetchrow('SELECT prelim, main, challenger, champion FROM number_of_accounts')
            return {level: value for level, value in need_accounts.items()}

    # Информация о нужно уровне, действующих аккаунтах и выполненных заданиях для повышения уровня
    async def get_info_for_change_level(self, tg_id):
        async with self.pool.acquire() as connection:
            levels = await connection.fetchrow('SELECT prelim, main, challenger, champion FROM number_of_completed_tasks')
            levels = [level for level in levels.keys()]
            need_level = levels[*[i+1 for i in range(len(levels)) if levels[i] == level['level'] and level != 'champion']]
            if need_level:
                level = await connection.fetchrow('SELECT level FROM tasks_distribution WHERE telegram_id = $1', tg_id)
                accounts = await connection.fetchrow("SELECT COUNT(account_name) FROM accounts WHERE telegram_id = $1 AND deleted = False AND account_status = 'active'", tg_id)
                completed_tasks = await connection.fetchrow('SELECT COUNT(*) FROM completed_tasks LEFT JOIN tasks_distribution USING(telegram_id) WHERE date_of_last_check < date_of_completion AND telegram_id = $1', tg_id)
                return {'need_level': need_level, 'accounts': accounts['count'], 'completed_tasks': completed_tasks['count']}
            return False

    # Функция для проверки на повышение уровня и сохранения уровня
    async def up_and_save_level(self, tg_id):
        async with self.pool.acquire() as connection:
            user_info_dict = await self.get_info_for_change_level(tg_id)
            if user_info_dict:  # Если нужный уровень есть в запросе (т.е. юзер не наивысшего уровня и ему есть, куда расти)
                need_tasks_dict = await self.get_need_for_level()
                need_accounts_dict = await self.get_need_for_level()
                # Проверка на то, что хватает выполненных заданий и аккаунтов для нового уровня
                if user_info_dict['completed_tasks'] >= need_tasks_dict[user_info_dict['need_level']] and \
                        user_info_dict['accounts'] >= need_accounts_dict[user_info_dict['need_level']]:
                    # Повышенние уровня
                    await connection.execute("UPDATE tasks_distribution SET level = $2 WHERE telegram_id = $1", tg_id, user_info_dict['need_level'])
                    # Обновление даты взятия уровня
                    await connection.execute('UPDATE tasks_distribution SET date_update_level = now() WHERE telegram_id = $1', tg_id)

    # Сбор всех челиксов, у которых прошла неделя с момента апа уровня
    async def get_users_after_up_level(self):
        async with self.pool.acquire() as connection:
            all_users = await connection.fetch("SELECT telegram_id, level, COUNT(unique_id) as completed_tasks  FROM tasks_distribution RIGHT JOIN completed_tasks USING(telegram_id) WHERE NOW() - date_update_level >= INTERVAL '7 days' AND date_of_completion >= date_of_last_check AND level <> 'vacationers' GROUP BY telegram_id, level")
            return {user['telegram_id']: {'completed_tasks': user['completed_tasks'], 'level': user['level']} for user in all_users}

    # Понижение воркера в уровне
    async def decline_in_level(self, workers_dict):
        # Проверить на работу с левелами прелим и отдыхающий
        async with self.pool.acquire() as connection:
            need_dict = await self.get_need_for_level()
            levels_dict = {1: 'vacationers', 2: 'prelim', 3: 'main', 4: 'challenger', 5: 'champion'}
            # Проверка на то, какой уровень выдать юзеру
            for worker in workers_dict:
                level_worker = workers_dict[worker]['level']
                completed_tasks = workers_dict[worker]['completed_tasks']
                key = [key for key, level in levels_dict.items() if level == level_worker]
                # Понижение на 1 уровень
                if completed_tasks >= need_dict[levels_dict[key[0] - 1]] or need_dict[levels_dict[key[0] - 1]] == 'vacationers':
                    new_level = need_dict[levels_dict[key[0] - 1]]
                # Понижение на 2 уровня
                else:
                    new_level = need_dict[levels_dict[key[0] - 2]]
                await connection.execute('UPDATE tasks_distribution SET level = $2 WHERE telegram_id = $1', worker, new_level)

    # Обновление времени чекоров уровня и чекера тасков
    async def update_time_for_level(self, workers):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE tasks_distribution SET date_of_last_check = NOW(), date_update_level = NOW() WHERE telegram_id = ANY($1)', workers)

    # Достать все таски, которые уже полежали более 10 минут
    async def get_active_tasks(self):
        async with self.pool.acquire() as connection:
            # tasks = await connection.fetch("SELECT tb_1.task_id, tb_1.executions, NOW() - tb_1.date_of_creation as passed_after_creation, NOW() - tb_1.date_of_check as passed_after_check, tb_1.in_process, COUNT(completed_tasks.unique_id) as completed_tasks FROM completed_tasks RIGHT JOIN (SELECT tasks.task_id, executions, date_of_creation, date_of_check, COUNT(CASE WHEN tasks_messages.status IN ('start_task', 'process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments', 'checking') THEN 1 END) as in_process FROM tasks_messages RIGHT JOIN tasks USING(task_id) WHERE tasks.status='active' AND NOW() - tasks.date_of_check >= INTERVAL '20 minutes' GROUP BY tasks.task_id, date_of_creation, date_of_check) as tb_1 USING(task_id) GROUP BY 1, 2, 3, 4, 5")
            tasks = await connection.fetch("SELECT tb_1.task_id, tb_1.executions, NOW() - tb_1.date_of_creation as passed_after_creation, NOW() - tb_1.date_of_check as passed_after_check, tb_1.in_process, COUNT(completed_tasks.unique_id) as completed_tasks FROM completed_tasks RIGHT JOIN (SELECT tasks.task_id, executions, date_of_creation, date_of_check, COUNT(CASE WHEN tasks_messages.status IN ('start_task', 'process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments', 'checking') THEN 1 END) as in_process FROM tasks_messages RIGHT JOIN tasks USING(task_id) WHERE tasks.status='active' AND round IS NULL GROUP BY tasks.task_id, date_of_creation, date_of_check) as tb_1 USING(task_id) GROUP BY 1, 2, 3, 4, 5")
            return {task['task_id']: {'executions': task['executions'], 'passed_after_creation': task['passed_after_creation'], 'passed_after_check': task['passed_after_check'], 'completed_tasks': task['completed_tasks'], 'in_process': task['in_process']} for task in tasks}


    # Обновлить время последнего чека во всех заданиях
    async def update_check_time(self, tasks: list):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE tasks SET date_of_check = NOW() WHERE task_id = ANY($1)', tasks)

    # Получить настоящий раунд какого-то таска
    async def get_round_from_task(self, task_id):
        async with self.pool.acquire() as connection:
            task_round = await connection.fetchrow('SELECT round FROM tasks WHERE task_id = $1', task_id)
            return task_round['round']

    # Узнать, есть ли активные задания
    async def check_active_tasks(self):
        async with self.pool.acquire() as connection:
            check_status_tasks = await connection.fetchrow("SELECT task_id FROM tasks WHERE status = 'active'")
            if check_status_tasks:
                return True
            return False


db = Database()