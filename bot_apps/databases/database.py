import asyncio
import datetime
import re
import time
import asyncpg
import pytz as pytz

from config.config import load_config

config = load_config()
# Размер комиссии
commission_percent = 3.0


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
                check = await connection.fetchrow("SELECT COUNT(*) as countus FROM tasks_messages JOIN statistics USING(tasks_msg_id) LEFT JOIN failure_statistics USING(tasks_msg_id) WHERE telegram_id = $1 AND status IN ('offer', 'offer_more', 'start_task', 'process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND (statistics.offer_time > (SELECT time_message FROM main_interface WHERE telegram_id = $1) OR failure_statistics.perform_time_comment > (SELECT time_message FROM main_interface WHERE telegram_id = $1) OR failure_statistics.waiting_link_time > (SELECT time_message FROM main_interface WHERE telegram_id = $1))", tg_id)
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
            await connection.execute("UPDATE user_notifications SET all_notifications = True, subscriptions = True, likes = True, retweets = True, comments = True WHERE telegram_id = $1", tg_id)

    # Проверка на то, что у пользователя есть хотя бы 1 рабочий аккаунт и он может включить все уведомления
    async def check_accounts(self, tg_id):
        async with self.pool.acquire() as connection:
            check = await connection.fetchrow('SELECT account_name FROM accounts WHERE telegram_id = $1 AND deleted = False', tg_id)
            if check:
                return True
            return False

    # Получить статус включения всех уведомлений
    async def get_all_notifications(self, tg_id):
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow('SELECT all_notifications FROM user_notifications WHERE telegram_id = $1', tg_id)
            return result['all_notifications']

    # Функция для отключения всех уведомлений и добавления/удаления из ремайндера
    async def update_all_notifications(self, tg_id, status):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute('UPDATE user_notifications SET all_notifications = $2 WHERE telegram_id = $1', tg_id, status)
                # Если пользователь выключил все уведомления
                if status:
                    await connection.execute('DELETE FROM reminder_steps WHERE telegram_id = $1', tg_id)
                # Если пользователь выключил уведомления (на всякий случай защита от двойного добавления)
                else:
                    await connection.execute('INSERT INTO reminder_steps (telegram_id) VALUES ($1) ON CONFLICT (telegram_id) DO NOTHING;', tg_id)

    # Функция по поиску всех пользователей, которым нужно напомнить о том, что они отключили задание)
    async def all_users_task_notifications(self):
        async with self.pool.acquire() as connection:
            # Отбираются все записи, в которых, с момента отсчёта времени, прошло более суток
            users = await connection.fetch("SELECT * FROM reminder_steps WHERE NOW() - countdown > INTERVAL '1 day';")
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
            statistic_result = await connection.fetch('SELECT actions.type_task, completed_tasks.final_reward as price, (SELECT SUM(final_reward) as total_earned FROM completed_tasks WHERE telegram_id = $1) as total_earned, (SELECT total_earned FROM referral_office WHERE telegram_id = $1) as earned_referrals FROM completed_tasks  INNER JOIN tasks USING(task_id)  INNER JOIN actions USING(task_id) WHERE completed_tasks.telegram_id = $1', tg_id)
            if not statistic_result:
                statistic_dict = {'statistic_dict': 0, 'type': {'subscriptions': 0, 'likes': 0, 'retweets': 0, 'comments': 0}, 'earned_referrals': 0}
            else:
                statistic_dict = {'total_earned': int(statistic_result[0]['total_earned']) if statistic_result[0]['total_earned'].is_integer() else round(statistic_result[0]['total_earned'], 2),
                                  'type': {'subscriptions': 0, 'likes': 0, 'retweets': 0, 'comments': 0}, 'earned_referrals': int(statistic_result[0]['earned_referrals']) if statistic_result[0]['earned_referrals'].is_integer() else round(statistic_result[0]['earned_referrals'], 2)}
            for info in statistic_result:
                statistic_dict['type'][info['type_task']] += info['price']
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
                task_info = await connection.fetch("SELECT tasks.price - (tasks.price / 100.0 * $2) as price, tasks.status, actions.type_task, parameters.parameter_id FROM tasks_messages  INNER JOIN tasks USING(task_id) INNER JOIN actions USING(task_id) LEFT JOIN parameters USING(parameter_id) WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1 AND tasks.deleted <> True)", tasks_msg_id, commission_percent)
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

    # Создание новой записи в базе данных об пуше задания воркеру
    async def create_task_message(self, tg_id, task_id):
        async with self.pool.acquire() as connection:
            tasks_msg_id = await connection.fetchval("INSERT INTO tasks_messages(telegram_id, task_id, status) VALUES ($1, $2, 'offer') RETURNING tasks_msg_id", tg_id, task_id)
            return tasks_msg_id

    # Добавление остальных необходимых данных к сообщению
    async def add_info_task_message(self, tasks_msg_id, message_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute('UPDATE tasks_messages SET message_id = $2 WHERE tasks_msg_id = $1', tasks_msg_id, message_id)
                failure_key = await connection.fetchval("INSERT INTO failure_statistics(tasks_msg_id) VALUES ($1) RETURNING failure_key", tasks_msg_id)
                await connection.execute("INSERT INTO statistics(tasks_msg_id, offer_time, failure_key) VALUES ($1, now(), $2)", tasks_msg_id, failure_key)

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

    # Получить количество выполненных заданий минус общее их количество
    async def get_all_completed_and_price(self, task_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                # completed = await connection.fetchrow('SELECT executions - (SELECT COUNT(*) FROM completed_tasks WHERE task_id = $1) as count_complete FROM tasks WHERE task_id = $1', task_id)
                price = await connection.fetchrow('SELECT price FROM tasks WHERE task_id = $1', task_id)
                executions = await connection.fetchrow('SELECT executions FROM tasks WHERE task_id = $1', task_id)
                # completed = round(completed.get('count_complete', 0) / 5) * 5
                # return {'count_complete': completed, 'price': price['price'] / 100 * (100 - commission_percent)}
                return {'count_complete': round(executions['executions'] / 5) * 5, 'price': price['price']}

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
            print(tg_id, tasks_msg_id)
            # Проверить по этому все остальные запросы (и, по возможности, убрать их)
            # asdfasf,alfskkosmkgkdfmgdkfgkdfkg
            # Нужно запрос переделать, чтобы с ссылками вытаскивался, а то он каждый активный аккаунт убирать будет из запроса
            accounts = await connection.fetch("SELECT account_name FROM accounts WHERE account_name NOT IN (SELECT completed_tasks.account_name FROM actions JOIN tasks USING(task_id) JOIN completed_tasks USING(task_id) WHERE (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN tasks USING(task_id) JOIN actions USING(task_id) WHERE tasks_messages.tasks_msg_id = $2) AND completed_tasks.telegram_id = $1) AND account_name NOT IN (SELECT account_name FROM actions JOIN tasks_messages USING(task_id) WHERE tasks_messages.status IN ('process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN actions USING(task_id) WHERE tasks_msg_id = $2)) AND telegram_id = $1 AND accounts.deleted <> True AND accounts.account_status <> 'inactive'", tg_id, tasks_msg_id)
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
            check = await connection.fetch("SELECT account_name FROM accounts WHERE account_name NOT IN (SELECT completed_tasks.account_name FROM actions JOIN tasks USING(task_id) JOIN completed_tasks USING(task_id) WHERE (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN tasks USING(task_id) JOIN actions USING(task_id) WHERE tasks_messages.tasks_msg_id = $2) AND completed_tasks.telegram_id = $1) AND account_name NOT IN (SELECT account_name FROM actions JOIN tasks_messages USING(task_id) WHERE tasks_messages.status IN ('process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN actions USING(task_id) WHERE tasks_msg_id = $2)) AND telegram_id = $1 AND accounts.deleted <> True AND accounts.account_status <> 'inactive'", tg_id, tasks_msg_id)
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
                # Обновления время завершения задания и статуса на "выполненный"
                await connection.execute("UPDATE statistics SET finish_time = (now()) WHERE tasks_msg_id = $1", tasks_msg_id)
                await connection.execute("UPDATE tasks_messages SET status = 'completed' WHERE tasks_msg_id = $1", tasks_msg_id)
                # Изменение баланса задания, чтобы снять то, что заработал пользователь
                await connection.execute('UPDATE tasks SET balance_task = balance_task - (SELECT price FROM tasks_messages JOIN tasks USING(task_id) WHERE tasks_msg_id = $1) WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id)
                # Находим то, сколько перевести пользователю
                reward = await connection.fetchrow('SELECT price FROM tasks WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id)
                # Отнимаем от награды комиссию
                reward = reward['price'] - (reward['price'] / 100 * commission_percent)
                # Добавление таска в сделанные (completed_tasks)
                await connection.execute('INSERT INTO completed_tasks(telegram_id, task_id, account_name, tasks_msg_id, final_reward, date_of_completion) SELECT telegram_id, task_id, account_name, $1, $2, (SELECT finish_time FROM statistics WHERE tasks_msg_id = $1) FROM tasks_messages WHERE tasks_msg_id = $1;', tasks_msg_id, reward)
                # Перевод заработанного на баланс аккаунта, с которого было выполнено задание
                await connection.execute('UPDATE accounts SET account_balance = account_balance + $2 WHERE account_name = (SELECT account_name FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id, reward)
                # Перевод заработанного рефоводу
                await connection.execute('UPDATE referral_office SET current_balance = current_balance + $1 WHERE telegram_id = (SELECT inviter FROM referral_office WHERE telegram_id = (SELECT telegram_id FROM tasks_messages WHERE tasks_msg_id = $2))', reward / 100.0 * 1.5, tasks_msg_id)
                return reward if reward.is_integer() else round(reward, 2)

    # Пользователь завершил задание и собирает награду - комиссия
    async def collect_reward_from_task(self, tg_id, tasks_msg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                # Проверка на то, что есть что собрать с аккаунта
                reward = await connection.fetchrow('SELECT final_reward FROM completed_tasks WHERE tasks_msg_id = $1', tasks_msg_id)
                account_balance = await connection.fetchrow('SELECT account_balance FROM accounts WHERE account_name IN (SELECT account_name FROM completed_tasks WHERE tasks_msg_id = $1)', tasks_msg_id)
                # Если пользователь не снимал пока STB или баланса хватает, чтобы снять с аккаунта награду и перевести её на баланс
                if account_balance['account_balance'] >= reward['final_reward']:
                    # Сбор наград с аккаунта, которому были выделены награды
                    await connection.execute('UPDATE users SET balance = balance + (SELECT final_reward FROM completed_tasks WHERE tasks_msg_id = $2) WHERE telegram_id = $1', tg_id, tasks_msg_id)
                    await connection.execute('UPDATE accounts SET account_balance = account_balance - (SELECT final_reward FROM completed_tasks WHERE tasks_msg_id = $1) WHERE account_balance >= (SELECT final_reward FROM completed_tasks WHERE tasks_msg_id = $1) AND account_name = (SELECT account_name FROM completed_tasks WHERE tasks_msg_id = $1)', tasks_msg_id)

    # Функция для проверки того, завершено уже задание таскодателя или нет
    async def check_completed(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                result = await connection.fetchrow('SELECT executions - (SELECT COUNT(*) as count_completed FROM completed_tasks WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)) AS count_completed FROM tasks WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id)
                if result['count_completed'] <= 0 or not result['count_completed']:
                    return True
                return False

    # +
    # Функция, добавляющая время удаления сообщения, а также статус
    async def del_and_change_status_task(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                # Если пользователь отказался от задания, то проверяем, поздно он это сделал или нет
                time_add_task = await connection.fetchrow('SELECT start_time FROM statistics WHERE tasks_msg_id = $1', tasks_msg_id)
                moscow_timezone = pytz.timezone('Europe/Moscow')
                correct_datetime = time_add_task['start_time'].astimezone(moscow_timezone)
                current_date_moscow = datetime.datetime.now(tz=moscow_timezone)
                time_difference = current_date_moscow - correct_datetime
                # Если пользователь отказался от задания
                if time_difference.total_seconds() < 3 * 60:
                    await connection.execute("UPDATE tasks_messages SET status = 'refuse' WHERE tasks_msg_id = $1", tasks_msg_id)
                # Если пользователь поздно отказался от задания
                else:
                    await connection.execute("UPDATE tasks_messages SET status = 'refuse_late' WHERE tasks_msg_id = $1", tasks_msg_id)

                # И наложение какого-нибудь штрафа
                await connection.execute("UPDATE statistics SET deleted_time = now() WHERE tasks_msg_id = $1", tasks_msg_id)

    # +
    # Функция, добавляющая время удаления сообщения и статус, но в том случае, когда пользователь уже выполнил задание и хочет сделать его по новой
    async def del_and_change_status_task_2(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                time_add_task = await connection.fetchrow('SELECT start_time FROM statistics WHERE tasks_msg_id = $1', tasks_msg_id)
                moscow_timezone = pytz.timezone('Europe/Moscow')
                correct_datetime = time_add_task['start_time'].astimezone(moscow_timezone)
                current_date_moscow = datetime.datetime.now(tz=moscow_timezone)
                time_difference = current_date_moscow - correct_datetime
                # Если пользователь заблаговременно отказался от задания, то ничего не делаем
                if time_difference.total_seconds() < 2 * 60:
                    await connection.execute('DELETE FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id)
                # Если пользователь в итоге отказался от задания
                elif time_difference.total_seconds() < 5 * 60:
                    await connection.execute("UPDATE tasks_messages SET status = 'refuse' WHERE tasks_msg_id = $1", tasks_msg_id)
                # Если пользователь поздно отказался от задания
                else:
                    await connection.execute("UPDATE tasks_messages SET status = 'refuse_late' WHERE tasks_msg_id = $1", tasks_msg_id)

                await connection.execute("UPDATE statistics SET deleted_time = now() WHERE tasks_msg_id = $1", tasks_msg_id)

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
            check_tasks = await connection.fetchrow("SELECT tasks_msg_id  FROM tasks_messages WHERE status IN ('offer', 'offer_more', 'start_task', 'process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND telegram_id = $1", tg_id)
            if check_tasks:
                return True
            return False

    # Получить количество тех, кто выполняет задание прямо сейчас и сколько уже выполнений было
    async def get_quantity_completed(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow("SELECT COUNT(*) + (SELECT COUNT(*) FROM completed_tasks WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)) as complete FROM tasks_messages WHERE status IN ('start_task', 'process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1);", tasks_msg_id)
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
                open_tasks = await connection.fetchrow("SELECT COUNT(*) as count_tasks FROM tasks_messages WHERE status IN ('offer', 'offer_more', 'start_task', 'process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND telegram_id = $1", tg_id)
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
            # Если задание не было ещё завершено
            if not await connection.fetchrow("SELECT task_id FROM tasks WHERE status = 'completed' AND task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)", tasks_msg_id):
                check_again = await connection.fetchrow("SELECT account_name FROM accounts WHERE account_name NOT IN (SELECT completed_tasks.account_name FROM actions JOIN tasks USING(task_id) JOIN completed_tasks USING(task_id) WHERE (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN tasks USING(task_id) JOIN actions USING(task_id) WHERE tasks_messages.tasks_msg_id = $2) AND completed_tasks.telegram_id = $1) AND account_name NOT IN (SELECT account_name FROM actions JOIN tasks_messages USING(task_id) WHERE tasks_messages.status IN ('process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN actions USING(task_id) WHERE tasks_msg_id = $2)) AND telegram_id = $1 AND accounts.deleted <> True AND accounts.account_status <> 'inactive'", tg_id, tasks_msg_id)
                if check_again:
                    return True
            return False

    # Функция для проверки того, что этот таск можно выполнить с 2 их более аккаунтов
    async def task_two_again(self, tg_id, tasks_msg_id):
        async with self.pool.acquire() as connection:
            check_again = await connection.fetch("SELECT account_name FROM accounts WHERE account_name NOT IN (SELECT completed_tasks.account_name FROM actions JOIN tasks USING(task_id) JOIN completed_tasks USING(task_id) WHERE (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN tasks USING(task_id) JOIN actions USING(task_id) WHERE tasks_messages.tasks_msg_id = $2) AND completed_tasks.telegram_id = $1) AND account_name NOT IN (SELECT account_name FROM actions JOIN tasks_messages USING(task_id) WHERE tasks_messages.status IN ('process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN actions USING(task_id) WHERE tasks_msg_id = $2)) AND telegram_id = $1 AND accounts.deleted <> True AND accounts.account_status <> 'inactive'", tg_id, tasks_msg_id)
            if len(check_again) > 1:
                return True
            return check_again[0]['account_name']

    # Создание нового сообщения о таске, в случае, когда пользователь решил сделать то же самое задание, но теперь с другого аккаунта
    async def new_tasks_messages(self, tg_id, tasks_msg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                result = await connection.fetchval("INSERT INTO tasks_messages(message_id, telegram_id, task_id, status) VALUES ((SELECT message_id FROM tasks_messages WHERE tasks_msg_id = $2), $1, (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $2), 'start_task') RETURNING tasks_msg_id", tg_id, tasks_msg_id)
                failure_key = await connection.fetchval('INSERT INTO failure_statistics(tasks_msg_id) VALUES ($1) RETURNING failure_key', result)
                await connection.execute('INSERT INTO statistics(tasks_msg_id, start_time, failure_key) VALUES ($1, now(), $2)', result, failure_key)
                return result

    # Функция для добавления аккаунта к таску
    async def new_task_account(self, tasks_msg_id, account):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE tasks_messages SET account_name = $2 WHERE tasks_msg_id = $1', tasks_msg_id, account)

    # Функция, добавляющая финальное время удаления
    async def add_del_time_in_task(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE statistics SET deleted_time = (now()) WHERE tasks_msg_id = $1", tasks_msg_id)

    # Функция, меняющая статус задания на удалённый
    async def add_deleted_status(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE tasks_messages SET status = 'deleted' WHERE tasks_msg_id = $1", tasks_msg_id)

    # Функция, которая достаёт все message_id и статусы всех заданий, которые находятся в процессе предложения или выполнения
    async def info_for_delete_messages(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            info = await connection.fetch("SELECT tasks_msg_id, telegram_id, message_id, status FROM tasks_messages WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1) AND status IN ('offer', 'offer_more', 'start_task', 'process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments')", tasks_msg_id)
            info_dict = {}
            for i in info:
                info_dict[f"tasks_msg_id_{i['tasks_msg_id']}"] = {'telegram_id': i['telegram_id'], 'message_id': i['message_id'], 'status': i['status']}
            return info_dict

    # Функция, которая достаёт все таски, в которых прошло 8 минут после начала выполнения
    async def info_all_tasks_messages(self):
        async with self.pool.acquire() as connection:
            all_tasks = await connection.fetch("SELECT tm.tasks_msg_id, telegram_id, message_id, start_time, reminder, status, account_name FROM tasks_messages as tm JOIN statistics USING(tasks_msg_id) WHERE now() - start_time >= interval '8 minutes' AND status IN ('start_task', 'process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments')")
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

    # Обновление статуса задания на "другие люди успели завершить задание раньше"
    async def update_status_on_fully_completed(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute("UPDATE tasks_messages SET status = 'fully_completed' WHERE tasks_msg_id = $1", tasks_msg_id)
                await connection.execute("UPDATE statistics SET deleted_time = now() WHERE tasks_msg_id = $1", tasks_msg_id)

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
    async def add_new_task(self, tg_id, balance_task, price, executions, types_tasks, accepted):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                # Создание основы для таска
                task_id = await connection.fetchval('INSERT INTO tasks(telegram_id, balance_task, price, executions) VALUES ($1, $2, $3, $4) RETURNING task_id', tg_id, balance_task, price, executions)
                # Снятие с пользователя средств и перевод на счёт баланса таска
                await connection.execute('UPDATE users SET balance = balance - $2 WHERE telegram_id = $1', tg_id, balance_task)
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

db = Database()