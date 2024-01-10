import asyncio
import datetime
import re
from typing import Literal
import asyncpg
import pytz

from config import load_config
from databases.dataclasses_storage import WorkersInfo, ActionsInfo, LinkAction, ActiveTasks, TaskStatus, HistoryTasks, \
    CommentParameter, InfoForDeleteTask, ActiveTask, HistoryTask, PriorityChange, WorkersRoundInfo, TaskInfo, \
    InfoIncreasedExecutions, RemainingTaskBalance, FinesInfo, AllFinesInfo, AdminPanelMainInfo, UsersList, \
    AuthorTaskInfo, FinesPartInfo, SupportPanelInfo, SupportInfo, AdminInfo, AllInfoLimits, AwardsCut, RealPricesTask, \
    UsersPerformTask, TaskAllInfo, AllTasks, UserPayments, UserFines, UserAccount, FineInfo, UserAllInfo, SentTasksInfo, \
    UserTasksInfo, InfoForMainMenu, WaitingStartTask
from parsing.elements_storage.elements_dictionary import base_links

config = load_config()


class Database:
    pool = None

    @classmethod
    async def connect(cls):
        if cls.pool is None:
            cls.pool = await asyncpg.create_pool(
                host=config.database.db_host,
                database=config.database.db_name,
                user=config.database.db_user,
                password=config.database.db_password,
                max_size=15)

    @classmethod
    async def disconnect(cls):
        if cls.pool:
            await cls.pool.close()

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
                    await connection.execute('INSERT INTO date_join(telegram_id) VALUES ($1)', tg_id)
                    # Создаём ему реферальный кабинет и записываем рефовода, если он есть
                    if link:
                        await connection.execute('INSERT INTO referral_office(telegram_id, inviter, date_of_invitation) VALUES ($1, (SELECT telegram_id FROM referral_office WHERE promocode = $2), NOW())', tg_id, link)
                    else:
                        await connection.execute('INSERT INTO referral_office(telegram_id) VALUES ($1)', tg_id)
                else:
                    # Просто обновляем его tg_name
                    await connection.execute('UPDATE users SET telegram_name = $1 WHERE telegram_id = $2', tg_name, tg_id)

    # Добавить главный интерфейс
    async def add_main_interface(self, tg_id, message_id):
        async with self.pool.acquire() as connection:
            await connection.execute('INSERT INTO main_interface(telegram_id, message_id, time_message) VALUES ($1, $2, now())', tg_id, message_id)

    # Получить главный интерфейс
    async def get_main_interface(self, tg_id):
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow('SELECT message_id FROM main_interface WHERE telegram_id = $1', tg_id))['message_id']

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
            account_id = await self.get_account_id_by_name(acc_name)
            info = await connection.fetchrow("SELECT account_name, account_status, account_balance, (SELECT SUM(final_reward) as balancer FROM completed_tasks WHERE account_id = $1 AND telegram_id = $2), accounts_limits.subscriptions, accounts_limits.likes, accounts_limits.comments, accounts_limits.retweets FROM accounts JOIN accounts_limits USING(account_id) WHERE account_id = $1;", account_id, tg_id)
            info_dict = {'status': info['account_status'], 'earned': info['balancer'] if info['balancer'] else 0, 'account_balance': info['account_balance'], 'type': {'subscriptions': info['subscriptions'], 'likes': info['likes'], 'retweets': info['retweets'], 'comments': info['comments']}}
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
                    balance_user = await self.check_balance(tg_id)
                    await self.collect_reward_from_accounts([(await connection.fetchrow('SELECT account_id FROM completed_tasks WHERE acc_name = $1', acc_name))['account_id']])
                    return balance_account['account_balance'], balance_user
                return None, None

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
                await connection.execute("UPDATE accounts SET account_status = 'deleted' WHERE account_name = $1", acc_name)
                # await self.change_status_account(tg_id, acc_name, 'deleted')

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

    # Узнать, есть ли хотя бы 1 задание у пользователя (не удалённое)
    async def check_tasks(self, tg_id):
        async with self.pool.acquire() as connection:
            return bool(await connection.fetchval('SELECT task_id FROM tasks WHERE telegram_id = $1 and deleted_history = False', tg_id))

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
                await connection.execute('UPDATE reminder_steps SET step_1 = TRUE WHERE telegram_id = $1', tg_id)
            elif step == 'step_2':
                await connection.execute('UPDATE reminder_steps SET step_2 = TRUE WHERE telegram_id = $1', tg_id)
            else:
                await connection.execute('UPDATE reminder_steps SET step_3 = TRUE WHERE telegram_id = $1', tg_id)

    # Функция для добавления нового аккаунта
    async def add_account(self, tg_id, acc_name):
        async with self.pool.acquire() as connection:
            # Если аккаунт уже есть в базе данных и был удалён
            account_id = await connection.fetchrow('SELECT account_id FROM accounts WHERE account_name = $1', acc_name)
            if account_id:
                await connection.execute("UPDATE accounts SET telegram_id = $1, account_status = 'active', deleted = False WHERE account_name = $2", tg_id, acc_name)
                return account_id['account_id']
            # Если аккаунт новый
            else:
                account_limit = await self.get_limits_accounts_executions()
                account_id = await connection.fetchval("INSERT INTO accounts(telegram_id, account_name) VALUES ($1, $2) RETURNING account_id", tg_id, acc_name)
                await connection.execute("INSERT INTO accounts_limits(account_id, subscriptions, likes, comments, retweets) VALUES ($1, $2, $3, $4, $5)",
                                         account_id, account_limit['subscriptions'], account_limit['likes'], account_limit['comments'], account_limit['retweets'])
                return account_id



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
                return self._round_number(uncollected_balance['balance'])

    @staticmethod
    def _round_number(number):
        return int(number) if number.is_integer() else round(number, 2)

    # Собираем сразу все награды со всех аккаунтов
    async def collection_of_all_awards(self, tg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute('UPDATE users SET balance = balance + (SELECT SUM(account_balance) FROM accounts WHERE telegram_id = $1  AND deleted = False) WHERE telegram_id = $1', tg_id)
                await connection.execute('UPDATE accounts SET account_balance = 0 WHERE telegram_id = $1', tg_id)
                accs = await connection.fetch('SELECT account_id FROM accounts WHERE telegram_id = $1 AND account_balance > 0', tg_id)
                await self.collect_reward_from_accounts([acc['account_id'] for acc in accs])

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
                collected_from_promocode = await connection.fetchrow('SELECT SUM(withdraw_amount) as total_earned FROM withdraws_account_balance WHERE telegram_id = $1', tg_id)

                # 2 кривых костыля
                if earned_by_friends['earned_by_friends'] is None:
                    earned_by_friends = {'earned_by_friends': 0}
                if sum_earned['sum_earned'] is None:
                    sum_earned = {'sum_earned': 0}

                affiliate_statistics_dict = {
                    'count_people': count_people.get('count_people', 0) if count_people else 0,
                    'active_people': active_people.get('active_people', 0) if active_people else 0,
                    'new_people_in_month': new_people_in_month.get('new_people_in_month', 0) if new_people_in_month else 0,
                    'earned_by_friends': self._round_number(earned_by_friends.get('earned_by_friends', 0)),
                    'sum_earned': self._round_number(sum_earned.get('sum_earned', 0)),
                    'collected_from_promocode': self._round_number(collected_from_promocode.get('total_earned', 0))
                }
                return affiliate_statistics_dict

    # +
    # Проверяем, что пользователь может собрать награды (если только часть. то в каком количестве)
    async def check_referral_reward(self, tg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                current_balance = await connection.fetchrow('SELECT current_balance FROM referral_office WHERE telegram_id = $1', tg_id)
                can_collect = await connection.fetchrow('SELECT (SELECT SUM(final_reward) FROM completed_tasks WHERE telegram_id = $1) - (SELECT SUM(withdraw_amount) FROM withdraws_account_balance WHERE telegram_id = $1) as can_collect FROM referral_office WHERE telegram_id = $1', tg_id)
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
            balance_collection = (await connection.fetchrow('SELECT current_balance FROM referral_office WHERE telegram_id = $1', tg_id))['current_balance']
            await connection.execute('UPDATE users SET balance = balance + (SELECT current_balance FROM referral_office WHERE telegram_id = $1) WHERE telegram_id = $1', tg_id)
            await connection.execute('UPDATE referral_office SET current_balance = 0 WHERE telegram_id = $1', tg_id)
            await self.record_in_withdraws_referral_office(tg_id, balance_collection)
            balance_user = await self.check_balance(tg_id)
            return balance_collection, balance_user

    # Пользователь собирает часть реферальных наград
    async def collect_part_of_referral_rewards(self, tg_id, part):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE users SET balance = balance + $2 WHERE telegram_id = $1', tg_id, part)
            await connection.execute('UPDATE referral_office SET current_balance = current_balance - $2 WHERE telegram_id = $1', tg_id, part)
            await self.record_in_withdraws_referral_office(tg_id, part)
            return await self.check_balance(tg_id)

    # Запись о снятии средств с реферального кабинета
    async def record_in_withdraws_referral_office(self, tg_id: int, amount: float):
        async with self.pool.acquire() as connection:
            await connection.execute('INSERT INTO withdraws_referral_office(telegram_id, withdraw_amount) VALUES ($1, $2)', tg_id, amount)

    # +
    # Вытаскиваем данные для статистики аккаунта
    async def statistic_info(self, tg_id):
        async with self.pool.acquire() as connection:
            tasks = await connection.fetch('SELECT actions.type_task, tasks.date_of_creation FROM completed_tasks INNER JOIN tasks USING(task_id) INNER JOIN actions USING(task_id) WHERE completed_tasks.telegram_id = $1 ORDER BY tasks.date_of_creation DESC', tg_id)
            prices = await connection.fetch('SELECT subscriptions, likes, retweets, comments, date_added FROM prices_actions ORDER BY date_added DESC')
            earned_referrals = await connection.fetchrow('SELECT COALESCE(SUM(withdraw_amount), 0) as total_earned FROM withdraws_account_balance WHERE telegram_id = $1', tg_id)
            # Инициализация словаря
            statistic_dict = {'subscriptions': 0, 'likes': 0, 'retweets': 0, 'comments': 0, 'earned_referrals': self._round_number(earned_referrals['total_earned'])}
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

    # Проверка на то, пополнял ли пользователь хотя бы раз свой аккаунт
    async def check_payment(self, tg_id):
        async with self.pool.acquire() as connection:
            check = await connection.fetchrow('SELECT telegram_id FROM payments WHERE telegram_id = $1', tg_id)
            # Если есть отметка в истории о пополнении аккаунта
            if check:
                return await self.check_balance(tg_id)
            return False

    # Достать баланс пользователя
    async def check_balance(self, tg_id):
        async with self.pool.acquire() as connection:
            balance = (await connection.fetchrow('SELECT balance FROM users WHERE telegram_id = $1', tg_id))['balance']
            return self._round_number(balance)

    # Достать tg_id создателя задания
    async def get_telegram_id_from_tasks(self, task_id):
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow('SELECT telegram_id FROM tasks WHERE task_id = $1', task_id))['telegram_id']

    # Проверка того, хватит ли у нас воркеров для того, чтобы принять задание пользователя
    async def feasibility_check(self, tg_id, data):
        async with self.pool.acquire() as connection:
            all_except = {}
            all_users = {}
            all_accounts = []
            for action in data['setting_actions']:
                link = data['accepted']['profile_link'] if action == 'subscriptions' else data['accepted']['post_link']
                # Запрос, который достаёт все аккаунты и телеграммы людей, которые могут выполнить данное задание, при этом, они должны проявить минимальную активность (выполнить одно задание в течении недели) и их уведомления о всех заданиях тоже должны быть включены, либо выключены, но после этого выключения прошло совсем немного времени (15 минут)
                info = await connection.fetch("SELECT tb_2.telegram_id, account_id, subscriptions, likes, retweets, comments FROM (SELECT tb_1.telegram_id, tb_1.account_id, user_status FROM (SELECT accounts.telegram_id, accounts.account_id, CASE WHEN MAX(CASE WHEN EXISTS (SELECT 1 FROM completed_tasks WHERE accounts.telegram_id = completed_tasks.telegram_id AND NOW() - date_of_completion <= INTERVAL '8 days') THEN 'active' ELSE 'inactive' END) = 'active' THEN 'active' ELSE 'inactive' END AS user_status FROM accounts WHERE account_status = 'active' AND deleted = False AND accounts.telegram_id <> $1 GROUP BY 1, 2) as tb_1 LEFT JOIN completed_tasks USING(account_id) WHERE tb_1.account_id NOT IN (SELECT completed_tasks.account_id FROM actions JOIN tasks USING(task_id) JOIN completed_tasks USING(task_id) WHERE actions.link_action = $2 AND actions.type_task = $3) AND tb_1.account_id NOT IN (SELECT account_id FROM actions JOIN tasks_messages USING(task_id) WHERE tasks_messages.status IN ('process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND actions.link_action = $2 AND actions.type_task = $3) GROUP BY 1, 2, 3) as tb_2 LEFT JOIN user_notifications USING(telegram_id) LEFT JOIN reminder_steps USING(telegram_id) WHERE tb_2.user_status = 'active' AND (all_notifications = True OR (all_notifications = False AND NOW() - countdown <= INTERVAL '15 minutes'));", tg_id, link, action)
                # Добавление всех пользователей в словарь
                for i in info:
                    # Если у пользователя включено получение этого типа заданий
                    if i[action]:
                        all_users.setdefault(i['telegram_id'], {'available': {'subscriptions': i['subscriptions'], 'likes': i['likes'], 'retweets': i['retweets'], 'comments': i['comments']}, 'accounts': []})
                        all_users[i['telegram_id']]['accounts'].append(i['account_id'])
                        all_accounts.append(i['account_id'])
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
            check = await connection.fetch('SELECT (SELECT account_name FROM accounts WHERE account_id = completed_tasks.account_id) FROM completed_tasks WHERE telegram_id = $1 ORDER BY account_id DESC', tg_id)
            if not check:
                return False
            account_list = []
            for c in check:
                if c['account_name'] is not None and c['account_name'] not in account_list:
                    account_list.append(c['account_name'])
            return account_list

    # Достать аккаунт_id аккаунта по его имени
    async def get_account_id_by_name(self, acc_name):
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow("SELECT account_id FROM accounts WHERE account_name = $1", acc_name))['account_id']

    # Запрос, вытаскивающий всю историю заданий какого-то аккаунта
    async def account_history(self, tg_id, acc_name):
        async with self.pool.acquire() as connection:
            account_id = await self.get_account_id_by_name(acc_name)
            account_history = await connection.fetch('SELECT tasks.task_id, completed_tasks.date_of_completion, completed_tasks.final_reward as price, actions.type_task, actions.link_action FROM completed_tasks INNER JOIN tasks USING(task_id) INNER JOIN actions USING(task_id) WHERE completed_tasks.telegram_id = $1 AND completed_tasks.account_id = $2 ORDER BY completed_tasks.date_of_completion DESC', tg_id, account_id)
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

    # Вытаскивает все сделанные задания пользователя в словарь
    async def all_completed_tasks(self, tg_id):
        async with self.pool.acquire() as connection:
            all_tasks = await connection.fetch('SELECT completed_tasks.unique_id, (SELECT account_name FROM accounts WHERE account_id = completed_tasks.account_id), completed_tasks.date_of_completion, completed_tasks.final_reward, actions.type_task, actions.link_action, tasks.price  FROM completed_tasks  INNER JOIN tasks USING(task_id)  INNER JOIN actions USING(task_id)  WHERE completed_tasks.telegram_id = $1 ORDER BY completed_tasks.date_of_completion DESC', tg_id)
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
                task_info = await connection.fetch("SELECT tasks.price, tasks.status, actions.type_task, parameters.parameter_id, words_count, tags_count, words_tags, note, english FROM tasks_messages  INNER JOIN tasks USING(task_id) INNER JOIN actions USING(task_id) LEFT JOIN parameters USING(parameter_id) WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1 AND tasks.status NOT IN ('completed', 'deleted'))", tasks_msg_id)
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
            # Проверка на то, что он может сделать ещё раз, учитывая выданное ему кол-во выполнений на этот таск
            executions_limit = await connection.fetchrow('SELECT available_accounts FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id)
            executions = await connection.fetchrow("SELECT COUNT(*) FROM completed_tasks WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1) AND telegram_id = (SELECT telegram_id FROM tasks_messages WHERE tasks_msg_id = $1)", tasks_msg_id)
            check = max(executions_limit['available_accounts'] - executions['count'], 0)
            # Проверка на то, что лимиты самих аккаунтов не исчерпаны
            tg_id = await self.get_telegram_id_from_tasks_messages(tasks_msg_id)
            accounts = await self.accounts_for_task(tg_id, tasks_msg_id)
            sum_accounts = len([acc for page in accounts for acc in accounts[page]]) if accounts else 0
            return min(check, sum_accounts)

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
                # elif status == 'checking':
                #     await connection.execute('UPDATE tasks_messages SET status = $2 WHERE tasks_msg_id = $1', tasks_msg_id, status)

    # Получить количество выполненных заданий
    async def get_all_completed_and_price(self, task_id):
        async with self.pool.acquire() as connection:
            # completed = await connection.fetchrow('SELECT executions - (SELECT COUNT(*) FROM completed_tasks WHERE task_id = $1) as count_complete FROM tasks WHERE task_id = $1', task_id)
            price = await connection.fetchrow('SELECT price FROM tasks WHERE task_id = $1', task_id)
            executions = await connection.fetchrow('SELECT executions FROM tasks WHERE task_id = $1', task_id)
            # completed = round(completed.get('count_complete', 0) / 5) * 5
            # return {'count_complete': completed, 'price': price['price'] / 100 * (100 - config.task_price.commission_percent)}
            return {'count_complete': round(executions['executions'] / 5) * 5, 'price': self._round_number(price["price"])}

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
            task_id = await self.get_task_id_from_tasks_messages(tasks_msg_id)
            accounts = await connection.fetch("SELECT account_name FROM accounts WHERE account_id NOT IN (SELECT completed_tasks.account_id FROM actions JOIN tasks USING(task_id) JOIN completed_tasks USING(task_id) WHERE (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks JOIN actions USING(task_id) WHERE task_id = $2) AND completed_tasks.telegram_id = $1) AND account_id NOT IN (SELECT account_id FROM actions JOIN tasks_messages USING(task_id) WHERE tasks_messages.status IN ('process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM actions WHERE task_id = $2)) AND accounts.account_id NOT IN (SELECT DISTINCT accounts.account_id FROM accounts JOIN accounts_limits USING(account_id) WHERE telegram_id = $1 AND (('subscriptions' IN (SELECT type_task FROM actions WHERE task_id = $2) AND accounts_limits.subscriptions < 1) OR ('likes' IN (SELECT type_task FROM actions WHERE task_id = $2) AND accounts_limits.likes < 1) OR ('retweets' IN (SELECT type_task FROM actions WHERE task_id = $2) AND accounts_limits.retweets < 1) OR ('comments' IN (SELECT type_task FROM actions WHERE task_id = $2) AND accounts_limits.retweets < 1))) AND telegram_id = $1 AND accounts.deleted <> True AND accounts.account_status <> 'inactive' ORDER BY account_id", tg_id, task_id)
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
            check = await connection.fetch("SELECT account_id FROM accounts WHERE account_id NOT IN (SELECT completed_tasks.account_id FROM actions JOIN tasks USING(task_id) JOIN completed_tasks USING(task_id) WHERE (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN tasks USING(task_id) JOIN actions USING(task_id) WHERE tasks_messages.tasks_msg_id = $2) AND completed_tasks.telegram_id = $1) AND account_id NOT IN (SELECT account_id FROM actions JOIN tasks_messages USING(task_id) WHERE tasks_messages.status IN ('process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN actions USING(task_id) WHERE tasks_msg_id = $2)) AND telegram_id = $1 AND accounts.deleted <> True AND accounts.account_status <> 'inactive'", tg_id, tasks_msg_id)
            if len(check) > 1:
                return True
            return False

    # Обновить аккаунт, с которого воркер выполняет задание
    async def update_task_account(self, tasks_msg_id, account):
        async with self.pool.acquire() as connection:
            account_id = await self.get_account_id_by_name(account)
            await connection.execute('UPDATE tasks_messages SET account_id = $2 WHERE tasks_msg_id = $1', tasks_msg_id, account_id)

    # Получить аккаунт, с которого воркер выполняет задание
    async def get_task_account(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            account = await connection.fetchrow('SELECT account_name FROM tasks_messages JOIN accounts USING(account_id) WHERE tasks_msg_id = $1', tasks_msg_id)
            if account:
                return account['account_name']

    # Завершение таска и добавление всех необходимых изменений в базу данных (время завершения, статус, запись в комплитед таск)
    async def task_completed(self, tasks_msg_id, not_checking_flag=False):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                tg_id = await self.get_telegram_id_from_tasks_messages(tasks_msg_id)
                # Обновления время завершения задания и статуса на "выполненный"
                await connection.execute("UPDATE statistics SET finish_time = (now()) WHERE tasks_msg_id = $1", tasks_msg_id)
                await connection.execute("UPDATE tasks_messages SET status = 'completed' WHERE tasks_msg_id = $1", tasks_msg_id)
                # Изменение баланса задания, чтобы снять то, что заработал пользователь
                await connection.execute('UPDATE tasks SET balance_task = balance_task - (SELECT price FROM tasks_messages JOIN tasks USING(task_id) WHERE tasks_msg_id = $1) WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id)
                # Находим то, сколько перевести пользователю
                reward = (await connection.fetchrow('SELECT price FROM tasks WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id))['price']
                # Выплата всех штрафов юзера
                reward = await self.payment_of_fines(reward, tg_id)
                print('Итоговый ревард ', reward)
                # Добавление таска в сделанные (completed_tasks)
                await connection.execute('INSERT INTO completed_tasks(telegram_id, task_id, account_id, tasks_msg_id, final_reward, date_of_completion) SELECT telegram_id, task_id, account_id, $1, $2, finish_time FROM tasks_messages JOIN statistics USING(tasks_msg_id) WHERE tasks_msg_id = $1;', tasks_msg_id, reward)
                # Перевод заработанного на баланс аккаунта, с которого было выполнено задание
                account_id = await self.get_account_id_from_tasks_messages(tasks_msg_id)
                await connection.execute('UPDATE accounts SET account_balance = account_balance + $2 WHERE account_id = $1', account_id, reward)
                # Запись о пополнении баланса аккаунта
                await connection.execute('INSERT INTO refills_account_balance(telegram_id, account_id, earned_amount) VALUES ($1, $2, $3)', tg_id, account_id, reward)
                # Проверка на то, есть ли у юзера инвайтер
                inviter = await connection.fetchrow('SELECT inviter FROM referral_office WHERE telegram_id = (SELECT telegram_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id)
                if inviter:
                    # Всего рефовод заработал
                    total_earned = reward / 100.0 * 1.5
                    # Перевод заработанного инвайтеру
                    await connection.execute('UPDATE referral_office SET current_balance = current_balance + $1 WHERE telegram_id = ($2)', total_earned, inviter['inviter'])
                    # Запись о пополнении реф. счёта инвайтера
                    await connection.execute('INSERT INTO refills_referral_office(telegram_id, telegram_id_earner, earned_amount) VALUES ($1, $2, $3)', inviter['inviter'], tg_id, total_earned)
                # Добавить запись о постепенной перепроверке выполнения
                await connection.execute('INSERT INTO task_completion_check(tasks_msg_id, do_not_check_flag) VALUES ($1, $2)', tasks_msg_id, not_checking_flag)
                # Узнать таск id
                task_id = (await connection.fetchrow('SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id))['task_id']
                # Повышение приоритета пользователя
                await self.change_priority_completing_task(tg_id, task_id)
                # Понизить лимит заданий на сегодня для твиттер аккаунта
                await self.decrease_accounts_limits(tasks_msg_id)
                # Изменение его круга, если это необходимо
                await self.change_in_circle(tg_id)

    # Уменьшить лимиты на аккаунте, выпонлившим задание
    async def decrease_accounts_limits(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            actions_dict = await self.all_task_actions(tasks_msg_id)
            account_id = await self.get_account_id_from_tasks_messages(tasks_msg_id)
            for action in actions_dict:
                query = f'UPDATE accounts_limits SET {action} = {action} - 1 WHERE account_id = $1'
                await connection.execute(query, account_id)

    # Получить id аккаунта по id сообщении о задании
    async def get_account_id_from_tasks_messages(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow('SELECT account_id FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id))['account_id']



    # Узнать, есть ли активные таски у юзера
    async def get_count_active_tasks(self, tg_id):
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow("SELECT COUNT(task_id) as active_tasks FROM tasks WHERE telegram_id = $1 and status NOT IN('completed', 'deleted')", tg_id))['active_tasks']

    # Получить общее кол-во созданных заданий юзера, не считая удалённые
    async def get_count_all_tasks(self, tg_id):
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow("SELECT COUNT(task_id) as all_tasks FROM tasks WHERE telegram_id = $1 and not deleted_history", tg_id))['all_tasks']

    # Получить кол-во тасков, хранящихся в истории
    async def get_count_task_on_history(self, tg_id):
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow("SELECT COUNT(task_id) as history_tasks FROM tasks WHERE telegram_id = $1 and not deleted_history and status IN ('completed', 'deleted')", tg_id))['history_tasks']

    # Получить информацию о типах действий и параметры комментария
    async def get_actions_info(self, task_id) -> ActionsInfo:
        async with self.pool.acquire() as connection:
            type_actions = await connection.fetch("SELECT type_task FROM actions WHERE task_id = $1", task_id)
            link_action: LinkAction = await self.get_links_on_task(task_id)
            return ActionsInfo(type_action={action['type_task']: (
                link_action.account_link if action['type_task'] == 'subscriptions' else link_action.post_link) for
                                            action in type_actions}, comment_paremeters=await self.get_comment_parameters(task_id))

    # Изменение статуса на удалённое
    async def change_task_status_to_deleted(self, task_id):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE tasks SET status = 'deleted' WHERE task_id = $1", task_id)

    # Функция для удаления задания
    async def delete_task(self, task_id, sum_refund):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await self.change_task_status_to_deleted(task_id)
                await self.return_some_balanc_from_task(task_id, sum_refund)
                await self.record_of_refund(task_id, sum_refund)
                await connection.execute('UPDATE tasks SET date_of_last_update = NOW() WHERE task_id = $1', task_id)

    # Получить активные таски с некоторой информацией
    async def get_active_tasks_inforamtions(self, tg_id) -> dict[int, ActiveTasks]:
        async with self.pool.acquire() as connection:
            active_tasks = await connection.fetch("SELECT task_id, tb_2.task_number, date_of_creation, COUNT(type_task) as number_actions, status, executions, COALESCE(tb_1.completed_task, 0) as completed_task FROM tasks RIGHT JOIN actions USING(task_id) LEFT JOIN (SELECT task_id, COUNT(tasks_msg_id) as completed_task FROM tasks RIGHT JOIN tasks_messages USING(task_id) WHERE tasks_messages.status = 'completed' GROUP BY task_id) as tb_1 USING(task_id) LEFT JOIN (SELECT task_id, ROW_NUMBER() OVER (ORDER BY date_of_creation) as task_number FROM tasks ORDER BY date_of_creation) as tb_2 USING (task_id) WHERE telegram_id = $1 AND tasks.status not IN ('completed', 'deleted') GROUP BY 1, 2, 3, 5, 6, 7 ORDER BY date_of_creation DESC;", tg_id)
            return {task['task_id']: ActiveTasks(
                task_number=task['task_number'],
                date_of_creation=task['date_of_creation'].astimezone(pytz.timezone('Europe/Moscow')),
                number_actions=task['number_actions'],
                status=getattr(TaskStatus, task['status'].upper()),
                completion_percentage=self._round_number(task['completed_task'] / (task['executions'] / 100))) for task in active_tasks}

    # Получить все таски из истории
    async def get_history_tasks_informations(self, tg_id) -> dict[int, HistoryTasks]:
        async with self.pool.acquire() as connection:
            history_tasks = await connection.fetch("SELECT tasks.task_id, tb_2.task_number, date_of_creation, date_of_completed, date_of_completed - date_of_creation as completion_in, COALESCE(ttp.total_pay, 0) + COALESCE(sum_fines, 0) as total_pay, status, executions, COALESCE(tb_1.completed_tasks, 0) as completed_task, COALESCE(sum_fines, 0) as sum_fines, BOOL_OR(CASE WHEN taskus.type_task = 'subscriptions' THEN True ELSE False END) as subscriptions, BOOL_OR(CASE WHEN taskus.type_task = 'likes' THEN True ELSE False END) as likes, BOOL_OR(CASE WHEN taskus.type_task = 'retweets' THEN True ELSE False END) as retweets, BOOL_OR(CASE WHEN taskus.type_task = 'comments' THEN True ELSE False END) as comments, MAX(CASE WHEN taskus.link_action NOT LIKE '%/status/%' THEN taskus.link_action ELSE Null END) as profile_link, MAX(CASE WHEN taskus.link_action LIKE '%/status/%' THEN taskus.link_action ELSE Null END) as post_link FROM tasks LEFT JOIN (SELECT task_id, COUNT(unique_id) as completed_tasks FROM completed_tasks GROUP BY 1) as tb_1 USING(task_id) LEFT JOIN (SELECT task_id, ROW_NUMBER() OVER (ORDER BY date_of_creation) as task_number FROM tasks ORDER BY date_of_creation) as tb_2 USING(task_id) LEFT JOIN (SELECT often_deleted.task_id, SUM(number_awards) as sum_fines FROM fines JOIN often_deleted USING(fines_id) GROUP BY often_deleted.task_id) as fines USING(task_id) LEFT JOIN (SELECT task_id, SUM(final_reward) as total_pay FROM completed_tasks GROUP BY task_id) as ttp USING(task_id) JOIN (SELECT task_id, type_task, link_action FROM actions) as taskus USING(task_id) WHERE telegram_id = $1 AND tasks.status IN ('completed', 'deleted') AND tasks.deleted_history = False GROUP BY tasks.task_id, task_number, date_of_creation, status, executions, completed_task, date_of_completed, completion_in, sum_fines, total_pay, date_of_last_update ORDER BY date_of_last_update DESC;", tg_id)
            history_dict = {}
            for task in history_tasks:
                history_dict[task['task_id']] = HistoryTasks(
                        task_number=task['task_number'],
                        date_of_creation=task['date_of_creation'],
                        date_of_completed=task['date_of_completed'],
                        completion_in=task['completion_in'],
                        status=getattr(TaskStatus, task['status'].upper()),
                        completed_task=task['completed_task'],
                        executions=task['executions'],
                        completion_percentage=self._round_number(task['completed_task'] / (task['executions'] / 100)),
                        total_pay=self._round_number(task['total_pay']),
                        fines=task['sum_fines'],
                        type_action=self._fill_actions_dict(task))
            return history_dict

    # Колхозная обработка для создания словаря с действиями
    @staticmethod
    def _fill_actions_dict(task_info: dict):
        actions_list = ['subscriptions', 'likes', 'retweets', 'comments']
        actions_dict = {}
        for key, value in task_info.items():
            if key in actions_list and value:
                actions_dict[key] = task_info['profile_link'] if key == 'subscriptions' else task_info['post_link']

        return ActionsInfo(type_action=actions_dict,
                           comment_paremeters=None)

    # Получить всю информацию об активном задании
    async def get_active_task_info(self, task_id) -> ActiveTask:
        async with self.pool.acquire() as connection:
            active_task = await connection.fetchrow("SELECT tb_2.task_number, date_of_creation, status, executions, COALESCE((SELECT COUNT(*) FROM completed_tasks WHERE task_id = $1), 0) as completed_tasks, COALESCE(tb_1.doing_now, 0) as doing_now, tb_3.total_pay, tb_3.remaining_balance FROM tasks LEFT JOIN (SELECT task_id, COUNT(*) as doing_now FROM tasks_messages WHERE task_id = $1 AND status IN ('start_task', 'process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments', 'сhecking') GROUP BY 1) as tb_1 USING(task_id) LEFT JOIN (SELECT task_id, ROW_NUMBER() OVER (ORDER BY date_of_creation) as task_number FROM tasks ORDER BY date_of_creation) as tb_2 USING(task_id) JOIN (SELECT task_id, price * COALESCE((SELECT COUNT(*) FROM completed_tasks WHERE task_id = $1), 0) as total_pay, (balance_task - (price * COALESCE((SELECT COUNT(*) FROM completed_tasks WHERE task_id = $1), 0))) as remaining_balance FROM tasks WHERE task_id = $1) as tb_3 USING(task_id) WHERE task_id = $1;", task_id)
            return ActiveTask(
                task_number=active_task['task_number'],
                date_of_creation=active_task['date_of_creation'].astimezone(pytz.timezone('Europe/Moscow')),
                status=getattr(TaskStatus, active_task['status'].upper()),
                actions_info=await self.get_actions_info(task_id),
                executions=active_task['executions'],
                number_completed=active_task['completed_tasks'],
                completion_percent=self._round_number(active_task['completed_tasks'] / (active_task['executions'] / 100)),
                doing_now=active_task['doing_now'],
                total_pay=self._round_number(active_task['total_pay']),
                remaining_balance=self._round_number(active_task['remaining_balance']))

    # Получить всю информацию о таске из истории
    async def get_history_task_info(self, task_id) -> HistoryTask:
        async with self.pool.acquire() as connection:
            history_task = await connection.fetchrow("SELECT tsk_n.task_number, date_of_creation, date_of_completed, date_of_completed - date_of_creation as completion_in, status, COALESCE(ttp.total_pay, 0) + COALESCE(sum_fines, 0) as total_pay, executions, COALESCE(tsk_cmp.completed_task, 0) as completed_task, sum_fines FROM tasks JOIN (SELECT task_id, ROW_NUMBER() OVER (ORDER BY date_of_creation) as task_number FROM tasks ORDER BY date_of_creation) as tsk_n USING(task_id) LEFT JOIN (SELECT task_id, SUM(number_awards) as sum_fines FROM fines JOIN often_deleted USING(fines_id) GROUP BY task_id) as fines USING(task_id) LEFT JOIN (SELECT task_id, SUM(final_reward) as total_pay FROM completed_tasks GROUP BY task_id) as ttp USING(task_id) LEFT JOIN (SELECT task_id, COUNT(unique_id) as completed_task FROM completed_tasks GROUP BY 1) as tsk_cmp USING(task_id) WHERE task_id = $1", task_id)
            return HistoryTask(
                task_number=history_task['task_number'],
                date_of_creation=history_task['date_of_creation'],
                date_of_completed=history_task['date_of_completed'],
                completion_in=history_task['completion_in'],
                status=getattr(TaskStatus, history_task['status'].upper()),
                actions_info=await self.get_actions_info(task_id),
                executions=history_task['executions'],
                completed_task=history_task['completed_task'],
                completion_percent=self._round_number(history_task['completed_task'] / (history_task['executions'] / 100)),
                total_pay=self._round_number(history_task['total_pay']),
                fines=history_task['sum_fines'])

    # Получить ссылки на действия в таске
    async def get_links_on_task(self, task_id) -> LinkAction:
        async with self.pool.acquire() as connection:
            links = await connection.fetch("SELECT link_action FROM actions WHERE task_id = $1", task_id)
            account = next((link['link_action'] for link in links if '/status/' not in link['link_action']), None)
            post = next((link['link_action'] for link in links if '/status/' in link['link_action']), None)
            return LinkAction(account_link=account, post_link=post)

    # Получить информацию о комментарии
    async def get_comment_parameters(self, task_id) -> CommentParameter | None:
        async with self.pool.acquire() as connection:
            actions = await connection.fetchrow("SELECT parameter_id, words_count, tags_count, words_tags, note, english FROM actions LEFT JOIN parameters USING(parameter_id) WHERE task_id = $1 AND parameter_id is not Null", task_id)
            if actions:
                check_parameter = {'words_count': None, 'tags_count': None, 'words_tags': None, 'english': None, 'note': None}
                return {parameter: actions[str(parameter)] for parameter in check_parameter.keys()}
            else:
                return None

    # Выплата штрафов юзера
    async def payment_of_fines(self, reward, tg_id):
        async with self.pool.acquire() as connection:
            fines_to_reward = await connection.fetch("SELECT fines_id, awards_cut, remaining_to_redeem, already_bought, victim_user FROM fines INNER JOIN bought USING(fines_id) WHERE telegram_id = $1 AND remaining_to_redeem > already_bought", tg_id)
            if fines_to_reward:
                all_sum_payment = 0
                for fine in fines_to_reward:
                    fine_stb = fine['remaining_to_redeem'] - fine['already_bought']
                    # Вычисляем процент пореза
                    sum_payment = min(reward / 100 * fine['awards_cut'], fine_stb)  # Если награды хватает, чтобы выплатить сколько нужно, то выплачиваем, если нет, то тратим всю награду на штраф
                    await connection.execute('UPDATE bought SET already_bought = already_bought + $1 WHERE fines_id = $2', sum_payment, fine['fines_id'])
                    await self.record_in_payment_fines(fine['fines_id'], sum_payment)
                    all_sum_payment += sum_payment
                    if sum_payment >= reward:
                        break
                return reward - all_sum_payment
            else:
                return reward

    # Запись в бд о выплате штрафа
    async def record_in_payment_fines(self, fines_id: int, sum_payment: float):
        async with self.pool.acquire() as connection:
            await connection.execute('INSERT INTO payment_fines(telegram_id, fines_id, payment_amount) VALUES ((SELECT telegram_id FROM fines WHERE fines_id = $1), $1, $2)', fines_id, sum_payment)

    # Проверка на то, нужно ли выдать письмо счастья пользователю
    async def check_availability(self, tg_id):
        async with self.pool.acquire() as connection:
            need_reward = 20  # Сколько нужно заработанных stb
            need_complete = 8  # Сколько нужно выполнить заданий
            check = await connection.fetchrow('SELECT reviews.telegram_id FROM reviews RIGHT JOIN completed_tasks USING(telegram_id) WHERE telegram_id = $1 AND ((SELECT SUM(completed_tasks.final_reward) FROM completed_tasks WHERE telegram_id = $1) > $2 OR (SELECT COUNT(*) FROM completed_tasks WHERE telegram_id = $1) > $3) AND offered_reviews = False GROUP BY 1', tg_id, need_reward, need_complete)
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
                account_balance = await connection.fetchrow('SELECT account_balance FROM accounts WHERE account_id IN (SELECT account_id FROM completed_tasks WHERE tasks_msg_id = $1)', tasks_msg_id)
                # Если пользователь не снимал пока STB или баланса хватает, чтобы снять с аккаунта награду и перевести её на баланс
                if account_balance is None or account_balance['account_balance'] >= reward['final_reward']:
                    # Сбор наград с аккаунта, которому были выделены награды
                    await connection.execute('UPDATE users SET balance = balance + (SELECT final_reward FROM completed_tasks WHERE tasks_msg_id = $2) WHERE telegram_id = $1', tg_id, tasks_msg_id)
                    await connection.execute('UPDATE accounts SET account_balance = account_balance - (SELECT final_reward FROM completed_tasks WHERE tasks_msg_id = $1) WHERE account_balance >= (SELECT final_reward FROM completed_tasks WHERE tasks_msg_id = $1) AND account_id = (SELECT account_id FROM completed_tasks WHERE tasks_msg_id = $1)', tasks_msg_id)
                    await self.collect_reward_from_accounts([(await connection.fetchrow('SELECT account_id FROM completed_tasks WHERE tasks_msg_id = $1', tasks_msg_id))['account_id']])

    # Запись о снятии баланса с аккаунтов
    async def collect_reward_from_accounts(self, account_ids: list[int]):
        async with self.pool.acquire() as connection:
            records = [(account_id,) for account_id in account_ids]
            await connection.executemany('INSERT INTO withdraws_account_balance(telegram_id, account_id, withdraw_amount) VALUES ((SELECT telegram_id FROM accounts WHERE account_id = $1), $1, (SELECT account_balance FROM accounts WHERE account_id = $1))', records)

    # Функция для проверки того, есть ли что снять с аккаунта или пользователь уже снимал деньги
    async def check_balance_account(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                account_balance = (await connection.fetchrow('SELECT account_balance FROM accounts WHERE account_id = (SELECT account_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id))['account_balance']
                if account_balance is not None and account_balance <= 0:
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

    # Удалить задание из истории
    async def del_task_from_history(self, task_id):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE tasks SET deleted_history = True WHERE task_id = $1', task_id)

    # Функция, добавляющая время удаления сообщения о таске, а также статус и снижение актива
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
                # Если пользователь незаблогавременно отказался от задания при его первом выполнении или при повторном выполнении через 8 минут
                elif time_difference.total_seconds() < 5 * 60 or (no_first_execution and time_difference.total_seconds() < 8 * 60):
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
            check_tasks = await connection.fetch("SELECT tasks_msg_id, (SELECT account_name FROM accounts WHERE account_id = tasks_messages.account_id) FROM tasks_messages JOIN statistics USING(tasks_msg_id) WHERE telegram_id = $1 AND status IN ('waiting_link', 'process_comments') ORDER BY start_time DESC", tg_id)
            if not check_tasks:
                return False
            for i in check_tasks:
                if i['account_name'].lower() == f'@{account}'.lower():
                    return int(i['tasks_msg_id'])
            return check_tasks[0]  # Если не нашли, возвращаем первый найденный таск

    # Получить всю информацию из задания для функции по проверке комментария
    async def get_all_task_info(self, tasks_msg_id):  # Хз, куда она
        async with self.pool.acquire() as connection:
            task_info = await connection.fetchrow("SELECT tasks_messages.account_id, parameters.* FROM tasks_messages JOIN tasks USING(task_id) JOIN actions USING(task_id) JOIN parameters USING(parameter_id) WHERE tasks_messages.tasks_msg_id = $1 AND actions.type_task = 'comments'", tasks_msg_id)
            return task_info

    # Получить информацию о том, есть ли какие-то ещё задания, которые в процессе выполнения
    async def get_tasks_user(self, tg_id):
        async with self.pool.acquire() as connection:
            # Вытаскивает все задания, у которых статус говорит от том, что таск ещё не завершён/удалён/скрыт
            check_tasks = await connection.fetchrow("SELECT tasks_msg_id FROM tasks_messages WHERE status IN ('offer', 'offer_more', 'start_task', 'process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND telegram_id = $1", tg_id)
            if check_tasks:
                return True
            return False

    # Получить телеграм юзернейм пользователя, который выполняет задание
    async def get_worker_username(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            username = await connection.fetchrow('SELECT account_name FROM tasks_messages JOIN accounts USING(account_id) WHERE tasks_msg_id = $1', tasks_msg_id)
            return username['account_name']

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
    async def task_again(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            # Если задание не было ещё завершено
            if not await connection.fetchrow("SELECT task_id FROM tasks WHERE status IN ('completed', 'deleted') AND task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)", tasks_msg_id):
                if await self.get_task_actual_limit(tasks_msg_id) > 0:
                    return True
            return False

    # Функция для проверки того, что этот таск можно выполнить с 2 их более аккаунтов
    async def task_two_again(self, tg_id, tasks_msg_id):
        async with self.pool.acquire() as connection:
            check_again = await connection.fetch("SELECT account_name FROM accounts WHERE account_id NOT IN (SELECT completed_tasks.account_id FROM actions JOIN tasks USING(task_id) JOIN completed_tasks USING(task_id) WHERE (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN tasks USING(task_id) JOIN actions USING(task_id) WHERE tasks_messages.tasks_msg_id = $2) AND completed_tasks.telegram_id = $1) AND account_id NOT IN (SELECT account_id FROM actions JOIN tasks_messages USING(task_id) WHERE tasks_messages.status IN ('process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks_messages JOIN actions USING(task_id) WHERE tasks_msg_id = $2)) AND telegram_id = $1 AND accounts.deleted <> True AND accounts.account_status <> 'inactive'", tg_id, tasks_msg_id)
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
            account_id = await self.get_account_id_by_name(account)
            await connection.execute('UPDATE tasks_messages SET account_id = $2 WHERE tasks_msg_id = $1', tasks_msg_id, account_id)

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

    # Поменять статус задания на скрытый
    async def add_hidden_status(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE tasks_messages SET status = 'hidden' WHERE tasks_msg_id = $1", tasks_msg_id)

    # Запись в базу даных о скрытии таска
    async def add_note_about_hiding(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            await connection.execute('INSERT INTO tasks_hiding(task_id, tasks_msg_id) VALUES ((SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1), $1)', tasks_msg_id)

    # Функция, которая достаёт все message_id и статусы всех заданий, которые находятся в процессе предложения или выполнения
    async def info_for_delete_messages(self, task_id) -> dict[int, InfoForDeleteTask]:
        async with self.pool.acquire() as connection:
            info = await connection.fetch("SELECT tasks_msg_id, telegram_id, message_id, status FROM tasks_messages WHERE task_id = $1 AND status IN ('offer', 'offer_more', 'start_task', 'process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments')", task_id)
            info_dict = {}
            for i in info:
                info_dict[i['tasks_msg_id']]: InfoForDeleteTask = {'telegram_id': i['telegram_id'], 'message_id': i['message_id'], 'status': i['status']}
            return info_dict

    # Функция, которая достаёт все таски, в которых прошло 8 минут после начала выполнения
    async def info_all_tasks_messages(self):
        async with self.pool.acquire() as connection:
            all_tasks = await connection.fetch("SELECT tm.tasks_msg_id, tm.telegram_id, message_id, start_time, reminder, status, accounts.account_name FROM tasks_messages as tm JOIN statistics USING(tasks_msg_id) JOIN accounts USING(account_id) WHERE now() - start_time >= interval '8 minutes' AND status IN ('start_task', 'process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments')")
            all_tasks_dict = {}
            if all_tasks:
                for i in all_tasks:
                    all_tasks_dict[f"tasks_msg_id_{i['tasks_msg_id']}"] = {'telegram_id': i['telegram_id'], 'message_id': i['message_id'], 'start_time': i['start_time'].astimezone(), 'reminder': i['reminder'], 'status': i['status'], 'account': i['account_name']}
            return all_tasks_dict

    # Раздача части наград от части задания воркерам
    async def distribution_some_awards(self, task_id, number_awards: int):
        async with self.pool.acquire() as connection:
            # Подсчёт наград на 1 воркера
            number_workers = (await connection.fetchrow("SELECT COUNT(*) as number_workers FROM tasks_messages WHERE status IN ('offer', 'offer_more') AND task_id = $1", task_id))['number_workers']
            if number_workers > 0:
                award = number_awards / number_workers
                await connection.execute("UPDATE users SET balance = balance + $2 WHERE telegram_id IN (SELECT telegram_id FROM tasks_messages WHERE status IN ('offer', 'offer_more') AND task_id = $1 GROUP BY 1)", task_id, award)

    # Запись штрафа в бд
    async def penalty_for_frequent_deletion(self, task_id, number_awards):
        async with self.pool.acquire() as connection:
            tg_id = await self.get_telegram_id_from_tasks(task_id)
            fines_id = await connection.fetchval("INSERT INTO fines(telegram_id, fines_type) VALUES($1, 'often_deleted') RETURNING fines_id", tg_id)
            await connection.execute("INSERT INTO often_deleted(fines_id, task_id, number_awards) VALUES ($1, $2, $3)", fines_id, task_id, number_awards)

    # Запись в бд о рефанде средств

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
            if status['status'] in ('start_task', 'process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments', 'сhecking'):
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
            change_priority: PriorityChange = await self.get_priority_change()
            # Если пользователь игнорил таск более часа
            if time_difference >= 60:
                priority = change_priority['ignore_more_60_min']
            # Если пользователь игнорил таск более 40 минут
            elif time_difference >= 40:
                priority = change_priority['ignore_more_40_min']
            # Если пользователь игнорил таск от 20 до 40 минут
            elif 20 <= time_difference <= 40:
                priority = change_priority['ignore_more_20_min']
            tg_id = await self.get_telegram_id_from_tasks_messages(tasks_msg_id)
            finally_priority = await self.min_priority(tg_id, priority)
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
            status = await connection.fetchrow('SELECT status FROM tasks WHERE task_id = (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1)', tasks_msg_id)
            return status['status']

    # Запись в базу нового задания
    async def add_new_task(self, tg_id, balance_task, withdrawal_amount, commission, price, executions, types_tasks, accepted, circular: bool):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                # Создание основы для таска
                task_id = await connection.fetchval("INSERT INTO tasks(telegram_id, balance_task, price, executions, status, round) VALUES ($1, $2, $3, $4, 'waiting_start', $5) RETURNING task_id", tg_id, balance_task, price, executions, 1 if circular else None)
                await connection.execute("INSERT INTO payments_tasks(task_id, prices_id) VALUES ($1, (SELECT prices_id FROM prices_actions ORDER BY date_added DESC LIMIT 1))", task_id)
                # Снятие с пользователя средств и перевод на счёт баланса таска
                await connection.execute('UPDATE users SET balance = balance - $2 WHERE telegram_id = $1', tg_id, withdrawal_amount)
                # Перевод комиссии за задание главному админу
                await connection.execute("UPDATE admins SET admin_balance = admin_balance + $1 WHERE telegram_id = (SELECT telegram_id FROM admins WHERE main_recipient_flag = True)", commission)
                # Запись о поступлении на баланс главного админа
                await connection.execute("INSERT INTO admins_receipts(sum_receipt, type_receipt, id_receipt) VALUES ($1, 'commission', (SELECT telegram_id FROM admins WHERE main_recipient_flag = True))", commission)
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

    # Смена статуса задания на первоначальную рассылку
    async def change_task_status_on_bulk_messaging(self, task_id):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE tasks SET status = 'bulk_messaging' WHERE task_id = $1", task_id)

    # Смена статуса задания на активный
    async def change_status_task_on_active(self, task_id):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE tasks SET status = 'active' WHERE task_id = $1 AND status <> 'deleted'", task_id)

    # Смена статуса задания на "дополнительная рассылка"
    async def change_status_task_on_dop_bulk_messaging(self, task_id):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE tasks SET status = 'dop_bulk_messaging' WHERE task_id = $1", task_id)

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

    # async def get_executions_from_task(self, task_id):
    #     async with self.pool.acquire() as connection:
    #         return (await connection.fetchrow('SELECT executions FROM tasks WHERE task_id = $1', task_id))['executions']

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
            prices_dict = {'subscriptions': self._round_number(prices['subscriptions']),
                           'likes': self._round_number(prices['likes']),
                           'retweets': self._round_number(prices['retweets']),
                           'comments': self._round_number(prices['comments'])}
            return prices_dict

    # Обновить все лимиты пользователей
    async def update_limits_users(self):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE tasks_distribution SET task_sent_today = 0')

    # Обновить все лимиты аккаунтов
    async def update_limits_accounts(self):
        async with self.pool.acquire() as connection:
            account_limit = await self.get_limits_accounts_executions()
            await connection.execute('UPDATE accounts_limits SET subscriptions = $1, likes = $2, comments = $3, retweets = $4',
                                     account_limit['subscriptions'], account_limit['likes'], account_limit['comments'], account_limit['retweets'])

    # Достать лимиты выполнений для аккаунтов
    async def get_limits_accounts_executions(self):
        async with self.pool.acquire() as connection:
            settings = await connection.fetchrow("SELECT subscriptions, likes, comments, retweets FROM limits_accounts_execution ORDER BY date_of_added DESC")
            return {key: value for key, value in settings.items()}

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
    async def get_priority_change(self) -> PriorityChange:
        async with self.pool.acquire() as connection:
            priority_change = await connection.fetchrow('SELECT completing_task, re_execution, max_re_execution, complete_others, downtime_more_20_min, ignore_more_20_min, ignore_more_40_min, ignore_more_60_min, refuse, refuse_late, scored_on_task, ignore_many_times, hidden_many_times, refuse_many_times, scored_many_times FROM priority_change ORDER BY date_of_added DESC')
            return {type_action: change for type_action, change in priority_change.items()}

    # Вытаскивание всех пользователей для задания и проверка некоторых деталей
    async def get_all_workers(self, task_id):
        async with self.pool.acquire() as connection:
            # Сколько максимум можно оставить тасков без реакции
            max_tasks_in_interval = 2
            # Запрос, который отбирает всех воркеров по условиям
            # 1. У воркера включены задания, он не в бане, это не создатель задания
            # 2. Он не выполняет в данный момент похожее задание с такими же ссылками и у него есть свободные аккаунты, которые могут выполнить это задание
            # 3. Это не новичок
            # 4. У него не висит 3 задания, к которым он даже не приторнулся
            all_workers_info: list[WorkersInfo] = await connection.fetch('''SELECT telegram_id, level, priority, COUNT(account_name) as available_accounts, tasks_sent_today, subscriptions, likes, retweets, comments FROM (SELECT user_notifications.telegram_id, level, priority, accounts.account_name, COUNT(CASE WHEN statistics.offer_time AT TIME ZONE 'Europe/Moscow' >= date_trunc('day', current_timestamp AT TIME ZONE 'Europe/Moscow') THEN 1 END) as tasks_sent_today, subscriptions, likes, retweets, comments FROM user_notifications JOIN tasks_distribution USING(telegram_id) LEFT JOIN tasks_messages USING(telegram_id) LEFT JOIN statistics USING(tasks_msg_id) RIGHT JOIN accounts ON user_notifications.telegram_id = accounts.telegram_id WHERE user_notifications.telegram_id IN (SELECT telegram_id FROM users JOIN user_notifications USING(telegram_id) JOIN tasks_distribution USING(telegram_id) WHERE telegram_id NOT IN (SELECT telegram_id FROM is_banned) AND telegram_id NOT IN (SELECT telegram_id FROM they_banned WHERE ban_status = True) AND telegram_id <> (SELECT telegram_id FROM tasks WHERE task_id = $1) AND user_notifications.all_notifications = True) AND accounts.account_name IN (SELECT account_name FROM accounts WHERE account_id NOT IN (SELECT completed_tasks.account_id FROM actions JOIN tasks USING(task_id) JOIN completed_tasks USING(task_id) WHERE (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks JOIN actions USING(task_id) WHERE task_id = $1)) AND account_id NOT IN (SELECT account_id FROM actions JOIN tasks_messages USING(task_id) WHERE tasks_messages.status IN ('process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks JOIN actions USING(task_id) WHERE task_id = $1)) AND accounts.account_id NOT IN (SELECT DISTINCT accounts.account_id FROM accounts JOIN accounts_limits USING(account_id) WHERE (('subscriptions' IN (SELECT type_task FROM actions WHERE task_id = $1) AND accounts_limits.subscriptions < 1) OR ('likes' IN (SELECT type_task FROM actions WHERE task_id = $1) AND accounts_limits.likes < 1) OR ('retweets' IN (SELECT type_task FROM actions WHERE task_id = $1) AND accounts_limits.retweets < 1) OR ('comments' IN (SELECT type_task FROM actions WHERE task_id = $1) AND accounts_limits.retweets < 1))) AND accounts.deleted <> True AND accounts.account_status <> 'inactive') AND user_notifications.telegram_id NOT IN (SELECT telegram_id FROM actions FULL OUTER JOIN tasks_messages USING(task_id) WHERE task_id = $1 AND (telegram_id, link_action, type_task) IN (SELECT telegram_id, link_action, type_task FROM tasks_messages JOIN statistics USING(tasks_msg_id) RIGHT JOIN actions USING(task_id) WHERE tasks_messages.status NOT IN ('completed', 'refuse', 'refuse_late', 'scored', 'fully_completed', 'hidden', 'deleted')) GROUP BY telegram_id) AND EXISTS (SELECT 1 FROM tasks_messages WHERE tasks_messages.telegram_id = user_notifications.telegram_id) GROUP BY accounts.telegram_id, user_notifications.telegram_id, level, priority, accounts.account_name, subscriptions, likes, retweets, comments HAVING COUNT(CASE WHEN tasks_messages.status IN ('offer') THEN 1 END) <= $2) as tg_common GROUP BY telegram_id, level, priority, tasks_sent_today, subscriptions, likes, retweets, comments HAVING COUNT(account_name) > 0;''', task_id, max_tasks_in_interval)
            return await self._get_ready_workers_dict(task_id, all_workers_info)

    # Получить всех воркеров, для какого-то раунда
    async def get_all_workers_for_round(self, task_id):
        async with self.pool.acquire() as connection:
            # В отличии от запроса выше, тут
            # Убрано условие, чтобы не лежало много тасков
            # Добавлено поле с инфо о круге юзера
            # Если юзер уже как-то контактировал конкретно с данным таском, он не отбирается
            all_workers_info: list[WorkersRoundInfo] = await connection.fetch('''SELECT telegram_id, circular_round, level, priority, COUNT(account_name) as available_accounts, tasks_sent_today, subscriptions, likes, retweets, comments FROM (SELECT user_notifications.telegram_id, circular_round, level, priority, accounts.account_name, COUNT(CASE WHEN statistics.offer_time AT TIME ZONE 'Europe/Moscow' >= date_trunc('day', current_timestamp AT TIME ZONE 'Europe/Moscow') THEN 1 END) as tasks_sent_today, subscriptions, likes, retweets, comments FROM user_notifications JOIN tasks_distribution USING(telegram_id) LEFT JOIN tasks_messages USING(telegram_id) LEFT JOIN statistics USING(tasks_msg_id) RIGHT JOIN accounts ON user_notifications.telegram_id = accounts.telegram_id WHERE user_notifications.telegram_id IN (SELECT telegram_id FROM users JOIN user_notifications USING(telegram_id) JOIN tasks_distribution USING(telegram_id) WHERE telegram_id NOT IN (SELECT telegram_id FROM is_banned) AND telegram_id NOT IN (SELECT telegram_id FROM they_banned WHERE ban_status = True) AND telegram_id <> (SELECT telegram_id FROM tasks WHERE task_id = $1) AND user_notifications.all_notifications = True) AND accounts.account_name IN (SELECT account_name FROM accounts WHERE account_id NOT IN (SELECT completed_tasks.account_id FROM actions JOIN tasks USING(task_id) JOIN completed_tasks USING(task_id) WHERE (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks JOIN actions USING(task_id) WHERE task_id = $1)) AND account_id NOT IN (SELECT account_id FROM actions JOIN tasks_messages USING(task_id) WHERE tasks_messages.status IN ('process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments') AND (actions.link_action, actions.type_task) IN (SELECT actions.link_action, actions.type_task FROM tasks JOIN actions USING(task_id) WHERE task_id = $1)) AND accounts.account_id NOT IN (SELECT DISTINCT accounts.account_id FROM accounts JOIN accounts_limits USING(account_id) WHERE (('subscriptions' IN (SELECT type_task FROM actions WHERE task_id = $1) AND accounts_limits.subscriptions < 1) OR ('likes' IN (SELECT type_task FROM actions WHERE task_id = $1) AND accounts_limits.likes < 1) OR ('retweets' IN (SELECT type_task FROM actions WHERE task_id = $1) AND accounts_limits.retweets < 1) OR ('comments' IN (SELECT type_task FROM actions WHERE task_id = $1) AND accounts_limits.retweets < 1))) AND accounts.deleted <> True AND accounts.account_status <> 'inactive') AND user_notifications.telegram_id NOT IN (SELECT telegram_id FROM actions FULL OUTER JOIN tasks_messages USING(task_id) WHERE task_id = $1 AND (telegram_id, link_action, type_task) IN (SELECT telegram_id, link_action, type_task FROM tasks_messages JOIN statistics USING(tasks_msg_id) RIGHT JOIN actions USING(task_id)) GROUP BY telegram_id) AND EXISTS (SELECT 1 FROM tasks_messages WHERE tasks_messages.telegram_id = user_notifications.telegram_id LIMIT 1) GROUP BY accounts.telegram_id, circular_round, user_notifications.telegram_id, level, priority, accounts.account_name, subscriptions, likes, retweets, comments) as tg_common GROUP BY telegram_id, circular_round, level, priority, tasks_sent_today, subscriptions, likes, retweets, comments HAVING COUNT(account_name) > 0;''', task_id)
            return await self._get_ready_workers_dict(task_id, all_workers_info, circular_round=True)

    # Отбор воркеров, у которых нет лимитов на задания, а также отдать им допустимое кол-во аккаунтов для них
    async def _get_ready_workers_dict(self, task_id, all_workers_info: list[WorkersInfo], circular_round=False):
        actions_list = await self.get_actions_list(task_id)
        limits_dict = await self.get_limits_dict()
        limits_executions_dict = await self.get_limits_executions_dict()
        ready_workers_dict: dict[int, dict[str, int]] = {} if not circular_round else {1: {}, 2: {}, 3: {}}
        for info in all_workers_info:
            # Проверка на то, что не превышен лимит на сегодня
            if limits_dict[info['level']] > info['tasks_sent_today']:
                # Проверка на то, что у пользователя включено получение данного вида заданий (лайков, ретвитов)
                for action in actions_list:
                    if action in info and not info[action]:
                        break
                else:
                    # Если у пользователя больше аккаунтов, чем нужно, записываем максимум, доступный ему:
                    if not circular_round:
                        ready_workers_dict[info['telegram_id']] = {'priority': info['priority'], 'available_accounts':  min(info['available_accounts'], limits_executions_dict[info['level']])}
                    else:
                        ready_workers_dict[info['circular_round']][info['telegram_id']] = {'priority': info['priority'], 'available_accounts':  min(info['available_accounts'], limits_executions_dict[info['level']])}
        return ready_workers_dict

    async def get_actions_list(self, task_id):
        async with self.pool.acquire() as connection:
            actions = await connection.fetch('SELECT type_task FROM actions WHERE task_id = $1', task_id)
            actions_dict = [action['type_task'] for action in actions]
            return actions_dict

    # Отбор новичков
    async def get_some_beginners(self, task_id):
        async with self.pool.acquire() as connection:
            # Достаём новичков, применяя минимальную проверку (на бан, на то что им сейчас не отправляется другой таск)
            beginners = await connection.fetch('SELECT users.telegram_id, COUNT(accounts.account_name) FROM users JOIN user_notifications USING(telegram_id) RIGHT JOIN accounts USING(telegram_id) WHERE NOT EXISTS (SELECT 1 FROM tasks_messages t WHERE t.telegram_id = users.telegram_id) AND users.telegram_id NOT IN (SELECT telegram_id FROM tasks WHERE task_id = $1) AND users.telegram_id NOT IN (SELECT telegram_id FROM is_banned) AND users.telegram_id NOT IN (SELECT telegram_id FROM they_banned WHERE ban_status = True) AND user_notifications.all_notifications = True GROUP BY users.telegram_id;', task_id)
            beginner_limit = await self.get_limits_executions_dict()
            beginners_dict = {}
            # Итоговый подсчёт доступных аккаунтов каждого юзера
            for beginner in beginners:
                beginners_dict.setdefault(beginner['telegram_id'], 0)
                beginners_dict[beginner['telegram_id']] += 1 if beginners_dict[beginner['telegram_id']] < beginner_limit['beginner'] else 0
            return beginners_dict

    # Получить количество выполнений для завершения таска
    async def get_amount_executions(self, task_id):
        async with self.pool.acquire() as connection:
            executions = await connection.fetchrow('SELECT executions FROM tasks WHERE task_id = $1', task_id)
            return executions['executions']

    # Достаёт информацию о об отправленных заданиях
    async def get_sent_tasks(self):
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
                    statistics_dict[f'{days_difference}_day_ago'][info['task_id']]['quantity_submitted_tasks'] += 1 if time_difference <= 50 else 0  # Если в последние минуты сообщение о таске пришло, то его не засчитываем
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
            # Хз, зачем почти две одинаковых проверки, но пусть будет
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
            finally_dict = {'time_has_passed': False, 'tasks_sent_recently': False}
            # Если он сам отключал кнопку, проверяем, сколько времени прошло
            if check_time:
                # Вычисляем, сколько прошло между отключением кнопки и настоящим
                late_time = check_time['countdown'].astimezone(pytz.timezone('Europe/Moscow'))
                now_time = datetime.datetime.now(pytz.timezone('Europe/Moscow'))
                late_time_only = late_time.hour * 60 + late_time.minute
                now_time_only = now_time.hour * 60 + now_time.minute
                if late_time_only - now_time_only >= 480:  # Если прошло более 8 часов
                    finally_dict['time_has_passed'] = True
                    return finally_dict  # Ну и всё, то что нужно мы получили
            # Если не прошло более 8 часов, смотрим, получил ли он хотя бы 1 задание за последние 5 часов
            sending_tasks = await connection.fetchval("SELECT COUNT(*) FROM statistics JOIN tasks_messages USING(tasks_msg_id) WHERE tasks_messages.telegram_id = $1 AND offer_time >= NOW() - INTERVAL '5 hours'", tg_id)
            finally_dict['tasks_sent_recently'] = False if sending_tasks else True  # Если не получал задание, то обозначаем флаг как True
            return finally_dict

    # Выдать юзеру новый приоритет
    async def new_user_priority(self, tg_id, new_priority):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE tasks_distribution SET priority = $2 WHERE telegram_id = $1", tg_id, new_priority)

    # Информация о прошлых показателях за последние 3 дня
    async def user_executions_info(self, tg_id):
        async with self.pool.acquire() as connection:
            all_info = await connection.fetch("SELECT * FROM tasks RIGHT JOIN tasks_messages USING(task_id) JOIN statistics USING(tasks_msg_id) WHERE tasks_messages.telegram_id = $1 AND NOW() - offer_time <= INTERVAL '3 days' ORDER BY offer_time", tg_id)
            result_dict = {'number_scored': 0, 'number_failures': 0, 'number_late_failures': 0, 'acceptance_rate': 0}
            tasks_id = []
            tasks_number, start_number = 1, 1  # Ставлю сразу однёрки для упрощения дальнейших вычислений
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
        result_dict['acceptance_rate'] = int(start_number / tasks_number * 100)  # Вичисляем, какой процент из высланых тасков за пол часа он принял
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
    @staticmethod
    def select_completion_rate(all_info):
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
            return TaskInfo(executions=info['executions'], completed_tasks=info['completed_tasks'], in_process=info['in_process'])

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
            last_message = (await connection.fetchrow("SELECT NOW() - last_message as last_message FROM they_banned WHERE telegram_id = $1", tg_id))['last_message']
            await connection.execute('UPDATE they_banned SET ban_status = False, counter = 1, last_message = Null WHERE telegram_id = $1', tg_id)
            return last_message

    # Заполнение в табличку юзера, забанившего нас
    async def they_banned_fill(self, tg_id):
        async with self.pool.acquire() as connection:
            info = await connection.fetchrow('SELECT counter FROM they_banned WHERE telegram_id = $1', tg_id)
            if not info or not info['counter']:
                await connection.execute('INSERT INTO they_banned(telegram_id) VALUES ($1) ON CONFLICT (telegram_id) DO NOTHING', tg_id)
            elif info['counter'] == 1:
                await connection.execute('UPDATE they_banned SET ban_status = True, counter = 2, last_message = NOW() WHERE telegram_id = $1', tg_id)
                return True

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
    async def check_to_ignore_tasks(self, tg_id, tasks_msg_id):
        async with self.pool.acquire() as connection:
            # Отбор последних 5 сообщений о тасках, которые провисели дольше 30 минут
            tasks = await connection.fetch("SELECT offer_time, offer_time_more, start_time, deleted_time, status FROM tasks_messages JOIN statistics USING (tasks_msg_id) WHERE telegram_id = $1 ORDER BY tasks_msg_id DESC LIMIT 5", tg_id)
            priority_change: PriorityChange = await self.get_priority_change()
            if not tasks:
                return False
            counters_dict = {'offer': 0, 'hiding': 0, 'refuse': 0, 'scored': 0}  # Счётчики действий
            punitive_dict = {'offer': 5, 'hiding': 3, 'refuse': 2, 'scored': 2}  # Дикт с тем, до какого числа дожен дойти счётчик, чтобы воркер получил по жопе
            change_priority = {'offer': priority_change['ignore_many_times'], 'hiding': priority_change['hidden_many_times'], 'refuse': priority_change['refuse_many_times'], 'scored': priority_change['scored_many_times']}  # Как сильно изменится приоритет после этого
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
                    counters_dict['offer'] = -10  # Костыли для сброса счётчика
                # Если таск был скрыт
                if task['offer_time_more'] and task['status'] == 'hidden':
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
                            await self.add_new_priority_fines(tg_id, tasks_msg_id)
                        # Понижение в рейтинге + отключение кнопки
                        finally_priority = await self.min_priority(tg_id, change_priority[action])
                        await connection.execute('UPDATE tasks_distribution SET priority = $2 WHERE telegram_id = $1', tg_id, finally_priority)
                        await self.change_in_circle(tg_id)
                        return action
            return False

    # Создать новый штраф, связанный с постоянным понижение рейтинга
    async def add_new_priority_fines(self, tg_id, tasks_msg_id):
        async with self.pool.acquire() as connection:
            sum_fines = await self.get_rating_fines()
            fines_id = await connection.fetchval("INSERT INTO fines(telegram_id, fines_type, tasks_msg_id) VALUES ($1, 'temporary', $2) RETURNING fines_id", tg_id, tasks_msg_id)
            await connection.execute("INSERT INTO temporary(fines_id, valid_until, reduction_in_priority) VALUES ($1, NOW() + INTERVAL '3 days', $2)", fines_id, sum_fines)
            await self.attach_fine_to_accounts(fines_id)

    # Взять понижение максимального рейтинга
    async def get_rating_fines(self):
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow("SELECT sum_fines FROM rating_fines ORDER BY date_of_added DESC"))['sum_fines']

    # Добавление нового штрафа, который нужно отработать
    # хз, куда нужнен был этот фанкшн
    async def add_new_reward_fines(self, tg_id, task_id, awards_cut=0):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                fines_id = await connection.fetchval("INSERT INTO fines(telegram_id, fines_type) VALUES ($1, 'temporary') RETURNING fines_id", tg_id)
                task_info = await connection.fetchrow('SELECT telegram_id, price FROM tasks WHERE task_id = $1', task_id)
                await connection.execute("INSERT INTO bought(fines_id, remaining_to_redeem, awards_cut, victim_user) VALUES ($1, $2, $3, $4)", fines_id, task_info['price'], awards_cut, task_id['telegram_id'])
                await self.attach_fine_to_accounts(fines_id)

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

    # Информация о нужном уровне, действующих аккаунтах и выполненных заданиях для повышения уровня
    async def get_info_for_change_level(self, tg_id):
        async with self.pool.acquire() as connection:
            levels = await connection.fetchrow('SELECT prelim, main, challenger, champion FROM number_of_completed_tasks')
            levels = [level for level in levels.keys()]
            level = await connection.fetchrow('SELECT level FROM tasks_distribution WHERE telegram_id = $1', tg_id)
            need_level = levels[*[i+1 for i in range(len(levels)) if levels[i] == level['level'] and level != 'champion']]
            if need_level:
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
                key = [key for key, level in levels_dict.items() if level == level_worker][0]
                # Понижение на 1 уровень
                if completed_tasks >= need_dict[levels_dict[key - 1]] or need_dict[levels_dict[key - 1]] == 'vacationers':
                    new_level = levels_dict[key - 1]
                # Понижение на 2 уровня
                else:
                    new_level = levels_dict[key - 2]
                await connection.execute('UPDATE tasks_distribution SET level = $2 WHERE telegram_id = $1', worker, new_level)

    # Обновление времени чекоров уровня и чекера тасков
    async def update_time_for_level(self, workers):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE tasks_distribution SET date_of_last_check = NOW(), date_update_level = NOW() WHERE telegram_id = ANY($1)', workers)

    # Достать все таски, которые уже полежали более 10 минут
    async def get_active_tasks(self):
        async with self.pool.acquire() as connection:
            tasks = await connection.fetch("SELECT tb_1.task_id, tb_1.executions, NOW() - tb_1.date_of_creation as passed_after_creation, NOW() - tb_1.date_of_check as passed_after_check, tb_1.in_process, COUNT(completed_tasks.unique_id) as completed_tasks FROM completed_tasks RIGHT JOIN (SELECT tasks.task_id, executions, date_of_creation, date_of_check, COUNT(CASE WHEN tasks_messages.status IN ('start_task', 'process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments', 'checking') THEN 1 END) as in_process FROM tasks_messages RIGHT JOIN tasks USING(task_id) WHERE tasks.status='active' AND NOW() - tasks.date_of_check >= INTERVAL '20 minutes' GROUP BY tasks.task_id, date_of_creation, date_of_check) as tb_1 USING(task_id) GROUP BY 1, 2, 3, 4, 5")
            return {task['task_id']: {'executions': task['executions'], 'passed_after_creation': task['passed_after_creation'], 'passed_after_check': task['passed_after_check'], 'completed_tasks': task['completed_tasks'], 'in_process': task['in_process']} for task in tasks}

    # Обновлить время последнего чека во всех заданиях
    async def update_check_time(self, tasks: list):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE tasks SET date_of_check = NOW() WHERE task_id = ANY($1)', tasks)

    # Получить настоящий раунд какого-то таска
    async def get_next_round_from_task(self, task_id):
        async with self.pool.acquire() as connection:
            task_round = await connection.fetchrow('SELECT round FROM tasks WHERE task_id = $1', task_id)
            if task_round and task_round['round']:
                return task_round['round'] + 1

    # Узнать, есть ли активные задания
    async def check_active_tasks(self):
        async with self.pool.acquire() as connection:
            check_status_tasks = await connection.fetchrow("SELECT task_id FROM tasks WHERE status NOT IN ('completed', 'deleted')")
            if check_status_tasks and check_status_tasks['task_id']:
                return True
            return False

    # Узнать, не завершено ли задание
    async def check_unfinished_task(self, task_id):
        async with self.pool.acquire() as connection:
            return bool(await connection.fetchval("SELECT task_id FROM tasks WHERE task_id = $1 AND status IN ('completed', 'deleted')", task_id))

    # Получить информацию об активном задании
    async def info_for_increased_executions(self, task_id) -> InfoIncreasedExecutions:
        async with self.pool.acquire() as connection:
            info = await connection.fetchrow('SELECT executions, (SELECT COUNT(*) FROM completed_tasks WHERE task_id = $1) as number_completed, price, balance FROM tasks JOIN users USING(telegram_id) WHERE task_id = $1', task_id)
            return InfoIncreasedExecutions(
                executions=info['executions'],
                number_completed=info['number_completed'],
                price=self._round_number(info['price']),
                balance=self._round_number(info['balance']))

    # Обновить выполнения задания
    async def update_task_executions(self, task_id, executions, diff):
        async with self.pool.acquire() as connection:
            tg_id = await self.get_telegram_id_from_tasks(task_id)
            await connection.execute('UPDATE tasks SET executions = executions + $2, date_of_last_update = NOW() WHERE task_id = $1', task_id, executions)
            await connection.execute('UPDATE users SET balance = balance - $2 WHERE telegram_id = $1', tg_id, diff)

    # Взять информацию об оставшемся балансе задания
    async def get_remaining_task_balance(self, task_id):
        async with self.pool.acquire() as connection:
            info = await connection.fetchrow("SELECT status, price, COALESCE(tb_1.doing_now, 0) as doing_now, COALESCE(tg_2.number_sent_users, 0) as number_sent_users, balance_task, COALESCE((SELECT COUNT(*) FROM completed_tasks WHERE task_id = $1), 0) as completed_number FROM tasks LEFT JOIN (SELECT task_id, COUNT(*) as doing_now FROM tasks_messages WHERE task_id = $1 AND status IN ('start_task', 'process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments', 'сhecking') GROUP BY 1) as tb_1 USING(task_id) LEFT JOIN (SELECT task_id, COUNT(*) as number_sent_users FROM tasks_messages WHERE task_id = $1 AND status NOT IN ('completed', 'refuse', 'refuse_late', 'scored', 'fully_completed', 'hidden', 'deleted') GROUP BY 1) as tg_2 USING(task_id) WHERE task_id = $1;", task_id)
            rewards = info['doing_now'] * info['price']
            return RemainingTaskBalance(
                status=info['status'],
                number_rewards=self._round_number(rewards),
                number_workers=info['doing_now'],
                balance_task=self._round_number(info['balance_task']),
                number_sent_users=info['number_sent_users'],
                remaining_task_balance=self._round_number((info['balance_task'] - (info['completed_number'] * info['price'] + rewards))))

    # Проверка на то, что задания не слишком часто удалялись таскодателем в последние дни
    async def check_quantity_delete_task(self, tg_id, task_id, check_number: int = None):
        async with self.pool.acquire() as connection:
            check_executions = await connection.fetchrow("SELECT executions, (SELECT COUNT(*) FROM completed_tasks WHERE task_id = $1) as completed_tasks FROM tasks WHERE task_id = $1", task_id)
            if check_executions['completed_tasks'] < (check_executions['executions'] / 100 * 30):
                deleted_tasks = await connection.fetch("SELECT task_id, executions, COALESCE(tb_1.completed, 0) as completed, date_of_last_update - date_of_creation as passed_after_deleted FROM tasks LEFT JOIN (SELECT task_id, COUNT(*) as completed FROM completed_tasks WHERE task_id IN (SELECT task_id FROM tasks) GROUP BY 1) as tb_1 USING (task_id) WHERE tasks.telegram_id = $1 AND tasks.status = 'deleted' AND NOW() - date_of_last_update < INTERVAL '1 days' GROUP BY 1, 2, 3", tg_id)
                if deleted_tasks:
                    # Отбор всех заданий, в которых было менее 30% выполнений и было хотя бы 1 выполнение или времени после создания прошло ровно столько, чтобы они успели стартануть
                    selected_tasks = [task for task in deleted_tasks if task['completed'] < task['executions'] / 100 * 30 and (True if task['completed'] > 0 or task['passed_after_deleted'].total_seconds() > WaitingStartTask.waiting_time else False)]
                    # Если уже было удалено 2 задания за последние сутки
                    if not check_number and len(selected_tasks) == 2:
                        return True
                    # Если было удалено больше и столько же тасков, как в check_number
                    elif check_number and len(selected_tasks) >= check_number:
                        return True
            return False

    # Вернуть пользователю оставшийся баланс с задания
    async def return_some_balanc_from_task(self, task_id, sum_refund):
        async with self.pool.acquire() as connection:
            tg_id = await self.get_telegram_id_from_tasks(task_id)
            await connection.execute('UPDATE users SET balance = balance + $2 WHERE telegram_id = $1', tg_id, sum_refund)

    # Получить баланс задания
    async def check_balance_task(self, task_id):
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow('SELECT balance_task FROM tasks WHERE task_id = $1', task_id))['balance_task']

    # Получить оставшийся баланс задания
    async def check_remaining_task_balance(self, task_id):
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow("SELECT COALESCE(COALESCE(balance_task - COALESCE(price * tb_1.count_start, 0), 0) - price * (SELECT COALESCE(COUNT(completed_tasks.unique_id), 0) FROM completed_tasks WHERE task_id = $1), 0) as remaining_task_balance FROM tasks LEFT JOIN (SELECT task_id, COUNT(*) as count_start FROM tasks_messages WHERE status IN ('start_task', 'process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments', 'сhecking', 'completed') AND task_id = $1 GROUP BY 1) as tb_1 USING(task_id) WHERE task_id = $1;", task_id))['remaining_task_balance']

    # Добавить запись о возврате баланса
    async def record_of_refund(self, task_id, sum_refund):
        async with self.pool.acquire() as connection:
            await connection.execute("INSERT INTO refund(task_id, refund_amount) VALUES ($1, $2)", task_id, sum_refund)

    # Найти кол-во и процент, сколько уже отказов от тасков
    async def failure_rate_check(self, task_id):
        async with self.pool.acquire() as connection:
            result = await connection.fetchrow("SELECT task_id, COUNT(tasks_msg_id) as count_workers, COUNT(CASE WHEN tasks_messages.status = 'hidden' THEN 1 END) as hidden_task, COUNT(CASE WHEN tasks_messages.status IN ('refuse', 'refuse_late') THEN 1 END) as refuse_task FROM tasks_messages WHERE task_id = $1 GROUP BY task_id", task_id)
            sum_refuse = result['refuse_task'] + result['hidden_task']
            # Если больше 20 отказов от задания и больше 10% от разосланных заданий
            if sum_refuse > 20 and sum_refuse >= (result['count_workers'] / 100 * 1):
                return True
            return False

    # Получить task_id из tasks_msg_id
    async def get_task_id_from_tasks_messages(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow('SELECT task_id FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id))['task_id']

    # Получить все несобранные штрафы
    async def get_number_uncollected_fines(self) -> dict[int, AllFinesInfo]:
        async with self.pool.acquire() as connection:
            fines = await connection.fetch("SELECT victim_user, already_bought, fines_id, tb_1.count_fines, tb_date.last_message FROM fines JOIN bought USING(fines_id) LEFT JOIN (SELECT victim_user, COUNT(*) as count_fines FROM bought GROUP BY 1) as tb_1 USING(victim_user) LEFT JOIN (SELECT victim_user, NOW() - date_of_send as last_message FROM bought WHERE date_of_send IS NOT NULL ORDER BY date_of_send DESC LIMIT 1) as tb_date USING(victim_user) WHERE collection_flag = FALSE AND remaining_to_redeem <= already_bought AND send_id IS Null ORDER BY victim_user;")
            fines_dict = {}
            for fine in fines:
                fines_dict.setdefault(fine['victim_user'], AllFinesInfo(
                    fines_info=FinesInfo(count_fines=fine['count_fines'],
                                         last_message=fine['last_message']),
                    fines_list=[]))
                fines_dict[fine['victim_user']].fines_list.append(FineInfo(
                    fines_id=fine['fines_id'],
                    already_bought=fine['already_bought']))
            return fines_dict

    # Обновить время отправки на штрафах
    async def change_send_time_fines(self, fines_list: list[int]):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE bought SET date_of_send = NOW() WHERE fines_id = ANY($1)', fines_list)

    # Создать новый send_id для пачки штрафов
    async def get_send_id(self, fines_list: list[int]):
        async with self.pool.acquire() as connection:
            next_id = (await connection.fetchrow("SELECT COALESCE(send_id + 1, 1) as next_id FROM bought ORDER BY 1 DESC LIMIT 1"))['next_id']
            await connection.execute("UPDATE bought SET send_id = $1 WHERE fines_id = ANY($2)", next_id, fines_list)
            return next_id

    # Взять все fines_id из пачки
    # Собрать все штрафы
    async def collection_fines(self, send_id: int) -> float:
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                fines_id = await connection.fetch('SELECT fines_id FROM bought WHERE send_id = $1', send_id)
                fines_list = [fine['fines_id'] for fine in fines_id]
                sum_fines = (await connection.fetchrow('SELECT SUM(already_bought) as sum_fines FROM bought WHERE fines_id = ANY($1) AND collection_flag = False', fines_list))['sum_fines']
                tg_id = (await connection.fetchrow('SELECT victim_user FROM bought WHERE fines_id = $1', fines_list[0]))['victim_user']
                await connection.execute('UPDATE users SET balance = balance + $2 WHERE telegram_id = $1', tg_id, sum_fines)
                await connection.execute('UPDATE bought SET collection_flag = True WHERE fines_id = ANY($1)', fines_list)
                return self._round_number(sum_fines)

    # Достать основную информацию для админа
    async def get_main_info_for_admin_panel(self, tg_id) -> AdminPanelMainInfo:
        async with self.pool.acquire() as connection:
            info = await connection.fetchrow("SELECT (SELECT CURRENT_DATE) as now_time, (SELECT admin_balance FROM admins WHERE telegram_id = $1) as admin_balance, COALESCE((SELECT COALESCE(SUM(refund_amount), 0) FROM refund WHERE DATE(date_of_refund) = CURRENT_DATE), 0) as refund_today, COALESCE((SELECT SUM(sum_receipt) FROM admins_receipts WHERE DATE(date_of_receipt) = CURRENT_DATE AND id_receipt = $1), 0) as received_today, COALESCE((SELECT COALESCE(SUM(balance_task + (balance_task * (commission / 100))), 0) FROM tasks JOIN payments_tasks USING(task_id) JOIN prices_actions USING(prices_id) WHERE DATE(date_of_creation) = CURRENT_DATE), 0) as spent_on_task, COALESCE((SELECT COALESCE(SUM(final_reward), 0) FROM completed_tasks WHERE DATE(date_of_completion) = CURRENT_DATE), 0) as earned_by_workers, COALESCE((SELECT COALESCE(COUNT(*), 0) FROM date_join WHERE DATE(date_join) = CURRENT_DATE), 0) as new_users, COALESCE((SELECT COALESCE(COUNT(*), 0) FROM accounts WHERE DATE(adding_time) = CURRENT_DATE), 0) as new_accounts, COALESCE((SELECT COALESCE(COUNT(*), 0) FROM tasks WHERE DATE(date_of_creation) = CURRENT_DATE), 0) as new_tasks, COALESCE((SELECT COALESCE(COUNT(*), 0) FROM statistics WHERE DATE(offer_time) = CURRENT_DATE), 0) as sended_tasks, COALESCE((SELECT COALESCE(COUNT(*), 0) FROM completed_tasks WHERE DATE(date_of_completion) = CURRENT_DATE), 0) as completed_tasks, COALESCE((SELECT COALESCE(COUNT(*), 0) FROM fines WHERE DATE(date_added) = CURRENT_DATE), 0) as sended_fines;", tg_id)
            return AdminPanelMainInfo(
                now_time=info['now_time'],
                admin_balance=self._round_number(info['admin_balance']),
                received_today=self._round_number(info['received_today']),
                spent_on_task=info['spent_on_task'],
                refund_today=info['refund_today'],
                earned_by_workers=info['earned_by_workers'],
                new_users=info['new_users'],
                new_accounts=info['new_accounts'],
                new_tasks=info['new_tasks'],
                sended_tasks=info['sended_tasks'],
                completed_tasks=info['completed_tasks'],
                sended_fines=info['sended_fines'])

    # Достать список юзеров с информацией
    async def get_users_list_with_info(self, condition_list: str = 'white_list', condition_sort: str = None, time_condition: int = None) -> list[UsersList]:
        async with self.pool.acquire() as connection:
            conditions_dict = {
                'white_list': 'WHERE users.telegram_id NOT IN (SELECT telegram_id FROM is_banned) AND users.telegram_id NOT IN (SELECT telegram_id FROM they_banned WHERE ban_status = True)',
                'black_list': 'WHERE users.telegram_id IN (SELECT telegram_id FROM is_banned)',
                'grey_list': 'WHERE users.telegram_id IN (SELECT telegram_id FROM they_banned WHERE ban_status = True)'}
            time_conditions_dict = {
                'registration_date': f"AND NOW() - date_join < INTERVAL '{time_condition} days'",
                'number_accounts': f"AND NOW() - tb_accs.adding_time < INTERVAL '{time_condition} days'",
                'priority': f"NOW() - date_update_level < INTERVAL '{time_condition} days'",
                'level': f"NOW() - date_update_level < INTERVAL '{time_condition} days'",
                'number_completed': f"AND NOW() - tb_cmp_tsks.date_of_completion < INTERVAL '{time_condition} days'",
                'number_add_tasks': f"AND NOW() - date_of_creation < INTERVAL '{time_condition} days'",
                'number_active_tasks': f"AND NOW() - date_of_creation < INTERVAL '{time_condition} days'",
                'number_fines': f"AND NOW() - date_added < INTERVAL '{time_condition} days'"}
            # Запрос через f строки
            # all_users = await connection.fetch(f"SELECT telegram_id, telegram_name, date_join, priority, COALESCE(level, 'beginner') as level, COALESCE(number_accounts, 0) as number_accounts, COALESCE(number_completed, 0) as number_completed, COALESCE(number_add_tasks, 0) as number_add_tasks, COALESCE(number_active_tasks, 0) as number_active_tasks, COALESCE(number_fines, 0) as number_fines FROM users LEFT JOIN date_join USING(telegram_id) LEFT JOIN tasks_distribution USING(telegram_id) LEFT JOIN (SELECT telegram_id, COUNT(*) as number_accounts FROM accounts GROUP BY 1) as tb_accs USING(telegram_id) LEFT JOIN (SELECT telegram_id, COUNT(*) as number_completed FROM completed_tasks GROUP BY 1) tb_cmp_tsks USING(telegram_id) LEFT JOIN (SELECT telegram_id, COUNT(*) as number_add_tasks FROM tasks GROUP BY 1) tb_tasks USING(telegram_id) LEFT JOIN (SELECT telegram_id, COUNT(*) as number_active_tasks FROM tasks WHERE status NOT IN ('completed', 'deleted') GROUP BY 1 ) tb_active_tasks USING(telegram_id) LEFT JOIN (SELECT telegram_id, COUNT(*) as number_fines FROM fines GROUP BY 1) tb_fines USING(telegram_id) {conditions_dict[condition_list]} {time_conditions_dict[condition_sort] if condition_sort else ''} ORDER BY date_join DESC")
            # Запрос без f строк
            query = '''SELECT telegram_id, telegram_name, date_join, priority, COALESCE(level, 'beginner') as level, COALESCE(number_accounts, 0) as number_accounts, COALESCE(number_completed, 0) as number_completed, COALESCE(number_add_tasks, 0) as number_add_tasks, COALESCE(number_active_tasks, 0) as number_active_tasks, COALESCE(number_fines, 0) as number_fines FROM users LEFT JOIN date_join USING(telegram_id) LEFT JOIN tasks_distribution USING(telegram_id) LEFT JOIN (SELECT telegram_id, COUNT(*) as number_accounts FROM accounts GROUP BY 1) as tb_accs USING(telegram_id) LEFT JOIN (SELECT telegram_id, COUNT(*) as number_completed FROM completed_tasks GROUP BY 1) tb_cmp_tsks USING(telegram_id) LEFT JOIN (SELECT telegram_id, COUNT(*) as number_add_tasks FROM tasks GROUP BY 1) tb_tasks USING(telegram_id) LEFT JOIN (SELECT telegram_id, COUNT(*) as number_active_tasks FROM tasks WHERE status NOT IN ('completed', 'deleted') GROUP BY 1 ) tb_active_tasks USING(telegram_id) LEFT JOIN (SELECT telegram_id, COUNT(*) as number_fines FROM fines GROUP BY 1) tb_fines USING(telegram_id) {conditions} {time_conditions} ORDER BY date_join DESC'''
            all_users = await connection.fetch(query.format(conditions=conditions_dict[condition_list], time_conditions=time_conditions_dict[condition_sort] if condition_sort else ''))

            users_list = []
            for user in all_users:
                users_list.append(UsersList(
                    tg_id=user['telegram_id'],
                    username=user['telegram_name'],
                    registration_date=user['date_join'],
                    priority=user['priority'],
                    level=user['level'],
                    number_accounts=user['number_accounts'],
                    number_completed=user['number_completed'],
                    number_add_tasks=user['number_add_tasks'],
                    number_active_tasks=user['number_active_tasks'],
                    number_fines=user['number_fines']))
            return users_list

    # Вся информация о юзере для админ кабинета
    async def get_all_info_for_user(self, tg_id) -> UserAllInfo:
        async with self.pool.acquire() as connection:
            user = await connection.fetchrow("SELECT telegram_id, telegram_name, date_join, (CASE WHEN telegram_id IN (SELECT telegram_id FROM is_banned) THEN 'в чёрном списке' WHEN telegram_id IN (SELECT telegram_id FROM they_banned) THEN 'в сером списке' ELSE 'в белом списке' END) as user_status,   balance,   COALESCE(count_referrals, 0) as count_referrals,   inviting_user,   COALESCE(total_payment, 0) as total_payment,   COALESCE((SELECT SUM(withdraw_amount) FROM withdraws_account_balance WHERE telegram_id = $1), 0) as total_earned, COALESCE(spent_on_tasks, 0) as spent_on_tasks,   COALESCE(total_refund, 0) as total_refund,   COALESCE(number_tasks, 0) as number_tasks,   COALESCE(number_active_tasks, 0) as number_active_tasks, COALESCE(sum_collected_fines, 0) as sum_collected_fines,   COALESCE(sum_uncollected_fines, 0) as sum_uncollected_fines, priority, COALESCE (level, 'beginner') as level, COALESCE(active_accounts, 0) as active_accounts,   COALESCE(total_sent_tasks, 0) as total_sent_tasks,  COALESCE(total_finished_tasks, 0) as total_finished_tasks,  COALESCE(number_unviewed_tasks, 0) as number_unviewed_tasks,   COALESCE(number_refusals_from_tasks, 0) as number_refusals_from_tasks,   COALESCE(number_hiding_tasks, 0) as number_hiding_tasks,   COALESCE(number_scored_tasks, 0) as number_scored_tasks,  number_tasks_active_now,  COALESCE(number_fines, 0) as number_fines,     COALESCE(number_active_fines, 0) as number_active_fines,   COALESCE(fines_on_priority, 0) as fines_on_priority,   COALESCE(sum_of_fines, 0) as sum_of_fines     FROM users   LEFT JOIN date_join USING(telegram_id)   LEFT JOIN tasks_distribution USING(telegram_id)   LEFT JOIN (SELECT inviter, COUNT(unique_id) as count_referrals FROM referral_office GROUP BY 1) as tb_ref ON tb_ref.inviter = users.telegram_id   LEFT JOIN (SELECT telegram_id, inviter as inviting_user FROM referral_office) as tb_inv USING(telegram_id)   LEFT JOIN (SELECT telegram_id, SUM(amount) total_payment FROM payments GROUP BY 1) as tb_pmnt USING(telegram_id)   LEFT JOIN (SELECT telegram_id, SUM(final_reward) as total_earned FROM completed_tasks GROUP BY 1) as tb_cmlp USING(telegram_id)   LEFT JOIN (SELECT telegram_id, SUM(balance_task) as spent_on_tasks FROM tasks GROUP BY 1) as tb_tsk USING(telegram_id)   LEFT JOIN (SELECT telegram_id, SUM(refund_amount) as total_refund FROM refund JOIN tasks USING(task_id) GROUP BY 1) as tb_rfnd USING(telegram_id)  LEFT JOIN (SELECT telegram_id, COUNT(tasks) as number_tasks FROM tasks GROUP BY 1) as tb_cnt_tsks USING(telegram_id)   LEFT JOIN (SELECT telegram_id, COUNT(tasks) as number_active_tasks FROM tasks WHERE status NOT IN ('completed', 'deleted') GROUP BY 1) as tb_ct_actv_tsks USING(telegram_id)   LEFT JOIN (SELECT victim_user, SUM(already_bought) as sum_collected_fines FROM bought WHERE collection_flag = True GROUP BY 1) as tb_fn ON tb_fn.victim_user = users.telegram_id   LEFT JOIN (SELECT victim_user, SUM(already_bought) as sum_uncollected_fines FROM bought WHERE collection_flag = False GROUP BY 1) as tb_unc_fn ON tb_fn.victim_user = users.telegram_id   LEFT JOIN (SELECT telegram_id, COUNT(account_name) as active_accounts FROM accounts WHERE deleted = False AND account_status = 'active' GROUP BY 1) as tb_accs USING(telegram_id)   LEFT JOIN (SELECT telegram_id, COUNT(tasks_msg_id) as total_sent_tasks FROM tasks_messages GROUP BY 1) as tb_tskm USING(telegram_id)     LEFT JOIN (SELECT telegram_id, COUNT(unique_id) as total_finished_tasks FROM completed_tasks GROUP BY 1) as tb_fnshd USING(telegram_id)    LEFT JOIN (SELECT telegram_id, COUNT(tasks_msg_id) as number_refusals_from_tasks FROM tasks_messages WHERE status IN ('refuse', 'refuse_late') GROUP BY 1) as tb_rfse_tsks USING(telegram_id)   LEFT JOIN (SELECT telegram_id, COUNT(tasks_msg_id) as number_hiding_tasks FROM tasks_messages WHERE status IN ('hidden') GROUP BY 1) as tb_hdn USING(telegram_id)   LEFT JOIN (SELECT telegram_id, COUNT(tasks_msg_id) as number_unviewed_tasks FROM tasks_messages WHERE status IN ('deleted') GROUP BY 1) as tb_tks_usrs USING(telegram_id)    LEFT JOIN (SELECT telegram_id, COUNT(tasks_msg_id) as number_scored_tasks FROM tasks_messages WHERE status = 'scored' GROUP BY 1) as tb_scrd USING(telegram_id) 	  LEFT JOIN (SELECT telegram_id, ARRAY_AGG(tasks_msg_id) as number_tasks_active_now FROM tasks_messages WHERE status IN ('start_task', 'process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments', 'сhecking') GROUP BY 1) as tb_tskmgs USING(telegram_id)  LEFT JOIN (SELECT telegram_id, COUNT(fines) as number_fines FROM fines GROUP BY 1) as tb_fins USING(telegram_id)   LEFT JOIN (SELECT telegram_id, COUNT(fines) as number_active_fines FROM fines LEFT JOIN temporary USING(fines_id) LEFT JOIN bought USING(fines_id) WHERE temporary.valid_until > NOW() or bought.remaining_to_redeem > bought.already_bought GROUP BY 1) tb_ctv_fns USING(telegram_id) LEFT JOIN (SELECT telegram_id, SUM(reduction_in_priority) as fines_on_priority FROM fines JOIN temporary USING(fines_id) WHERE temporary.valid_until > NOW() GROUP BY 1) as tb_fns_prt USING(telegram_id)   LEFT JOIN (SELECT telegram_id, SUM(already_bought) as sum_of_fines FROM fines JOIN bought USING(fines_id) WHERE bought.remaining_to_redeem > bought.already_bought GROUP BY 1) as tb_fnl USING(telegram_id) WHERE telegram_id = $1;", tg_id)
            return UserAllInfo(
                    telegram_id=user['telegram_id'],
                    telegram_name=user['telegram_name'],
                    date_join=user['date_join'],
                    user_status=user['user_status'],
                    balance=self._round_number(user['balance']),
                    count_referrals=user['count_referrals'],
                    inviting_user=user['inviting_user'],
                    total_payment=self._round_number(user['total_payment']),
                    total_earned=self._round_number(user['total_earned']),
                    spent_on_tasks=self._round_number(user['spent_on_tasks']),
                    total_refund=self._round_number(user['total_refund']),
                    total_paid=self._round_number(user['spent_on_tasks'] - user['total_refund']),
                    number_tasks=user['number_tasks'],
                    number_active_tasks=user['number_active_tasks'],
                    sum_collected_fines=self._round_number(user['sum_collected_fines']),
                    sum_uncollected_fines=self._round_number(user['sum_uncollected_fines']),
                    priority=user['priority'],
                    level=user['level'],
                    active_accounts=user['active_accounts'],
                    total_sent_tasks=user['total_sent_tasks'],
                    total_finished_tasks=user['total_finished_tasks'],
                    total_unfinished_tasks=user['number_unviewed_tasks'] + user['number_refusals_from_tasks'] + user['number_hiding_tasks'] + user['number_scored_tasks'],
                    number_unviewed_tasks=user['number_unviewed_tasks'],
                    number_scored_tasks=user['number_scored_tasks'],
                    number_tasks_active_now=user['number_tasks_active_now'],
                    number_refusals_from_tasks=user['number_refusals_from_tasks'],
                    number_hiding_tasks=user['number_hiding_tasks'],
                    number_fines=user['number_fines'],
                    number_active_fines=user['number_active_fines'],
                    fines_on_priority=user['fines_on_priority'],
                    sum_of_fines=self._round_number(user['sum_of_fines']))

    # Найти телеграм_id по юзернейму
    async def find_tg_id_on_username(self, username):
        async with self.pool.acquire() as connection:
            tg_id = await connection.fetchrow("SELECT telegram_id FROM users WHERE telegram_name = $1", username)
            if tg_id:
                return tg_id['telegram_id']

    # Смена приоритета пользователя
    async def change_user_priority(self, tg_id, priority: int):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE tasks_distribution SET priority = $2 WHERE telegram_id = $1", tg_id, priority)

    # Смена баланса пользователя
    async def change_user_balance(self, tg_id, balance: int):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE users SET balance = $2 WHERE telegram_id = $1', tg_id, balance)

    # Выдача нового уровня пользователю
    async def change_user_level(self, tg_id, level: str):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE tasks_distribution SET level = $2 WHERE telegram_id = $1', tg_id, level)

    # Выдать штраф от админа на макс приоритет
    async def adding_priority_fines(self, tg_id, fines_priority: int):
        async with self.pool.acquire() as connection:
            fines_id = await connection.fetchval("INSERT INTO fines(telegram_id, fines_type) VALUES ($1, 'temporary') RETURNING fines_id", tg_id)
            await connection.execute("INSERT INTO temporary(fines_id, reduction_in_priority, valid_until ) VALUES ($1, $2, CURRENT_TIMESTAMP + INTERVAL '3 days')", fines_id, fines_priority)
            await self.attach_fine_to_accounts(fines_id)

    # Сделать срез аккаунтов, которым будет прикреплён штраф
    async def attach_fine_to_accounts(self, fines_id):
        async with self.pool.acquire() as connection:
            tg_id = (await connection.fetchrow("SELECT telegram_id FROM fines WHERE fines_id = $1", fines_id))['telegram_id']
            user_accounts = await connection.fetch("SELECT account_id FROM accounts WHERE telegram_id = $1", tg_id)
            await connection.executemany('INSERT INTO accounts_fines_slise(fines_id, account_id) VALUES ($1, $2)', [(fines_id, acc['account_id']) for acc in user_accounts])

    # Выдать штраф от админа на STB сразу с порезом 100%
    async def adding_stb_fines(self, tg_id, fines_stb: int, victim_user: int = None):
        async with self.pool.acquire() as connection:
            fines_id = await connection.fetchval("INSERT INTO fines(telegram_id, fines_type) VALUES ($1, 'bought') RETURNING fines_id", tg_id)
            await self.attach_fine_to_accounts(fines_id)
            if victim_user:
                await connection.execute("INSERT INTO bought(fines_id, remaining_to_redeem, awards_cut, victim_user) VALUES($1, $2, 100, $3)", fines_id, fines_stb, victim_user)
            else:
                await connection.execute("INSERT INTO bought(fines_id, remaining_to_redeem, awards_cut) VALUES($1, $2, 100)", fines_id, fines_stb)

    # Получить информацию о тасках, отправленных пользователю
    async def get_info_about_sent_tasks(self, tg_id) -> list[SentTasksInfo]:
        async with self.pool.acquire() as connection:
            tasks = await connection.fetch("SELECT task_id, tasks_msg_id, (CASE WHEN status = 'completed' AND (SELECT do_not_check_flag FROM task_completion_check WHERE tasks_msg_id = tasks_messages.tasks_msg_id LIMIT 1) = True THEN 'not_confirmed' ELSE status END), offer_time, COALESCE(finish_time, deleted_time) as complete_time FROM tasks_messages INNER JOIN statistics USING(tasks_msg_id) WHERE telegram_id = $1 ORDER BY offer_time DESC;", tg_id)
            return [SentTasksInfo(task_id=task['task_id'],
                                  status=task['status'],
                                  offer_time=task['offer_time'],
                                  complete_time=task['complete_time']) for task in tasks]

    # Получить информацию о тасках, которые создал сам пользователь
    async def get_info_abuot_user_tasks(self, tg_id) -> list[UserTasksInfo]:
        async with self.pool.acquire() as connection:
            tasks_info = await connection.fetch("SELECT task_id, status, date_of_creation, date_of_completed, COALESCE(count_executions, 0) as count_executions FROM tasks LEFT JOIN (SELECT task_id, COUNT(tasks_msg_id) as count_executions FROM tasks_messages GROUP BY 1) as tb_tsks USING(task_id) WHERE telegram_id = $1", tg_id)
            return [UserTasksInfo(
                task_id=task['task_id'],
                status=getattr(TaskStatus, task['status'].upper()),
                date_of_creation=task['date_of_creation'],
                date_of_completed=task['date_of_completed'],
                count_executions=task['count_executions']) for task in tasks_info]

    # Получить информацию обо всех аккаунтах юзера
    async def get_all_user_accounts(self, tg_id) -> list[UserAccount]:
        async with self.pool.acquire() as connection:
            accounts = await connection.fetch("SELECT account_name, account_status, COALESCE(total_executions, 0) as total_executions, adding_time FROM accounts LEFT JOIN (SELECT account_name, COUNT(tasks_msg_id) as total_executions FROM accounts RIGHT JOIN tasks_messages USING(account_id) WHERE status = 'completed' GROUP BY 1) as tb_acs USING(account_name) WHERE telegram_id = $1 ORDER BY adding_time DESC", tg_id)
            return [UserAccount(
                account_name=account['account_name'],
                account_status=account['account_status'],
                total_executions=account['total_executions'],
                adding_time=account['adding_time']) for account in accounts]

    # Получить информацию обо всех штрафах юзера
    async def get_all_fines_user(self, tg_id) -> list[UserFines]:
        async with self.pool.acquire() as connection:
            fines = await connection.fetch("SELECT fines_id, (CASE WHEN bought.fines_id IS NOT NULL THEN 'на $STB' ELSE 'рейтинговый' END) as fines_type, date_added, (CASE WHEN bought.fines_id IS NOT NULL THEN 'Cнятие ' || bought.remaining_to_redeem || ' $STB в пользу ' || bought.victim_user ELSE '-' || ABS(temporary.reduction_in_priority) || ' максимального рейтинга' END) as contents_fine, (CASE WHEN bought.fines_id IS NOT NULL AND bought.already_bought >= bought.remaining_to_redeem THEN 0 ELSE bought.remaining_to_redeem - bought.already_bought END) as stb_left, (CASE WHEN temporary.fines_id IS NOT NULL AND NOW() >= temporary.valid_until THEN INTERVAL '0' SECOND ELSE temporary.valid_until - NOW() END) as time_left FROM fines LEFT JOIN bought USING(fines_id) LEFT JOIN temporary USING(fines_id) WHERE telegram_id = $1 ORDER BY date_added;", tg_id)
            return [UserFines(
                fines_id=fine['fines_id'],
                fines_type=fine['fines_type'],
                date_added=fine['date_added'],
                contents_fine=fine['contents_fine'],
                time_left=fine['time_left'],
                stb_left=fine['stb_left']) for fine in fines]

    # Получить информацию только об активных штрафах юзера
    async def get_only_active_fines_user(self, tg_id) -> list[UserFines]:
        async with self.pool.acquire() as connection:
            fines = await connection.fetch("SELECT fines_id, (CASE WHEN bought.already_bought IS NOT NULL THEN 'на $STB' ELSE 'рейтинговый' END) as fines_type, date_added, (CASE WHEN bought.fines_id IS NOT NULL THEN 'Cнятие ' || bought.remaining_to_redeem || ' $STB в пользу ' || bought.victim_user ELSE '-' || ABS(temporary.reduction_in_priority) || ' максимального рейтинга' END) as contents_fine, (CASE WHEN bought.fines_id IS NOT NULL AND bought.already_bought >= bought.remaining_to_redeem THEN 0 ELSE bought.remaining_to_redeem - bought.already_bought END) as stb_left, (CASE WHEN temporary.fines_id IS NOT NULL AND NOW() >= temporary.valid_until THEN INTERVAL '0' SECOND ELSE temporary.valid_until - NOW() END) as time_left FROM fines LEFT JOIN bought USING(fines_id) LEFT JOIN temporary USING(fines_id) WHERE telegram_id = $1 AND ((bought.fines_id IS NOT NULL AND bought.already_bought < bought.remaining_to_redeem) OR (temporary.fines_id IS NOT NULL AND NOW() <= temporary.valid_until)) ORDER BY date_added;", tg_id)
            return [UserFines(
                fines_id=fine['fines_id'],
                fines_type=fine['fines_type'],
                date_added=fine['date_added'],
                contents_fine=fine['contents_fine'],
                time_left=fine['time_left'],
                stb_left=fine['stb_left']) for fine in fines]

    # Получить информацию обо всех пополнениях юзера
    async def get_all_payments_user(self, tg_id) -> list[UserPayments]:
        async with self.pool.acquire() as connection:
            payments = await connection.fetch("SELECT payment_date, amount, issued_by_stb, payment_method FROM payments WHERE telegram_id = $1", tg_id)
            return [UserPayments(
                payment_date=payment['payment_date'],
                amount_pay=payment['amount'],
                issued_by_stb=payment['issued_by_stb'],
                payment_method=payment['payment_method']) for payment in payments]

    # Удалить штраф с пользователя
    async def delete_user_fines(self, fines_id):
        async with self.pool.acquire() as connection:
            await connection.execute("DELETE FROM fines WHERE fines_id = $1", fines_id)
            await connection.execute('DELETE FROM bought WHERE fines_id = $1', fines_id)
            await connection.execute('DELETE FROM temporary WHERe fines_id = $1', fines_id)

    # Показать все задания для админа
    async def get_all_tasks(self) -> list[AllTasks]:
        async with self.pool.acquire() as connection:
            all_tasks = await connection.fetch("SELECT task_id, date_of_creation, status, executions, COALESCE(tb_1.doing_now, 0) as doing_now, COALESCE(completed_tasks, 0) as completed_tasks, COALESCE(total_pay, 0) as total_pay, COALESCE(tb_3.remaining_balance, 0) as remaining_balance FROM tasks LEFT JOIN (SELECT task_id, COUNT(*) as completed_tasks FROM completed_tasks GROUP BY 1) USING(task_id) LEFT JOIN (SELECT task_id, COUNT(*) as doing_now FROM tasks_messages WHERE status IN ('start_task', 'process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments', 'сhecking') GROUP BY 1) as tb_1 USING(task_id) LEFT JOIN (SELECT task_id, SUM(final_reward) as total_pay FROM completed_tasks GROUP BY 1) as tb_2 USING(task_id) JOIN (SELECT task_id, (balance_task - COALESCE(sum_reward, 0)) as remaining_balance FROM tasks LEFT JOIN (SELECT task_id, SUM(final_reward) as sum_reward FROM completed_tasks GROUP BY 1) as tb_c USING(task_id) GROUP BY 1, sum_reward) as tb_3 USING(task_id) ORDER BY tasks.date_of_creation DESC;")
            return [AllTasks(
                task_id=task['task_id'],
                date_of_creation=task['date_of_creation'],
                status=getattr(TaskStatus, task['status'].upper()),
                executions=task['executions'],
                doing_now=task['doing_now'],
                completed_tasks=task['completed_tasks'],
                completion_percent=self._round_number(task['completed_tasks'] / (task['executions'] / 100)),
                total_pay=self._round_number(task['total_pay']),
                remaining_balance=self._round_number(task['remaining_balance']))for task in all_tasks]

    # Показать всю информацию об аккаунте для админа
    async def get_all_info_about_task(self, task_id) -> TaskAllInfo:
        async with self.pool.acquire() as connection:
            info = await connection.fetchrow("SELECT task_id, telegram_id, status, COALESCE(round::text, '-') AS round, COALESCE(completed_tasks, 0) as completed_tasks, executions, price, price * COALESCE(completed_tasks, 0) as total_pay, date_of_creation, date_of_completed, average_duration, COALESCE((date_of_completed - date_of_creation)::text, '_') as completion_in, MAX(CASE WHEN actions.link_action NOT LIKE '%/status/%' THEN actions.link_action ELSE Null END) as profile_link, MAX(CASE WHEN actions.link_action LIKE '%/status/%' THEN actions.link_action ELSE Null END) as post_link, STRING_AGG(type_task, ', ') as actions, COALESCE(total_sent, 0) as total_sent, COALESCE(number_not_viewed, 0) as number_not_viewed, COALESCE(number_more, 0) as number_more, COALESCE(number_hidden, 0) as number_hidden, COALESCE(number_start_task, 0) as number_start_task, COALESCE(number_refuse, 0) as number_refuse, COALESCE(number_refuse_late, 0) as number_refuse_late, COALESCE(number_scored, 0) as number_scored, COALESCE(number_fully_completed, 0) as number_fully_completed, COALESCE(number_process_subscriptions, 0) as number_process_subscriptions, COALESCE(number_process_likes, 0) as number_process_likes, COALESCE(number_process_retweets, 0) as number_process_retweets, COALESCE(number_process_comments, 0) as number_process_comments, COALESCE(number_waiting_link, 0) as number_waiting_link, COALESCE(doing_now, 0) as doing_now, balance_task, (balance_task - COALESCE(tb_frw.final_reward, 0)) as remaining_balance FROM tasks LEFT JOIN (SELECT task_id, COUNT(*) as completed_tasks FROM completed_tasks GROUP BY 1) as tb_tasks USING(task_id) RIGHT JOIN actions USING(task_id) LEFT JOIN parameters USING(parameter_id) LEFT JOIN (SELECT task_id, COUNT(*) as total_sent, COUNT(CASE WHEN status = 'offer' THEN 1 ELSE Null END) as number_not_viewed, COUNT(CASE WHEN status = 'offer_more' THEN 1 ELSE Null END) as number_more, COUNT(CASE WHEN status = 'hidden' THEN 1 ELSE Null END) as number_hidden, COUNT(CASE WHEN status = 'start_task' THEN 1 ELSE Null END) as number_start_task, COUNT(CASE WHEN status = 'refuse' THEN 1 ELSE Null END) as number_refuse, COUNT(CASE WHEN status = 'refuse_late' THEN 1 ELSE Null END) as number_refuse_late, COUNT(CASE WHEN status = 'scored' THEN 1 ELSE Null END) as number_scored, COUNT(CASE WHEN status = 'fully_completed' THEN 1 ELSE Null END) as number_fully_completed, COUNT(CASE WHEN status = 'process_subscriptions' THEN 1 ELSE Null END) as number_process_subscriptions, COUNT(CASE WHEN status = 'process_likes' THEN 1 ELSE Null END) as number_process_likes, COUNT(CASE WHEN status = 'process_retweets' THEN 1 ELSE Null END) as number_process_retweets, COUNT(CASE WHEN status = 'process_comments' THEN 1 ELSE Null END) as number_process_comments, COUNT(CASE WHEN status = 'waiting_link' THEN 1 ELSE Null END) as number_waiting_link, COUNT(CASE WHEN status IN ('start_task', 'process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments', 'сhecking') THEN 1 ELSE Null END) as doing_now FROM tasks_messages GROUP BY 1) as tb_tsks USING(task_id) LEFT JOIN (SELECT task_id, AVG(start_time - finish_time) as average_duration FROM tasks_messages JOIN statistics USING(tasks_msg_id) WHERE status = 'fully_completed' GROUP BY 1) as tb_vr USING(task_id) LEFT JOIN (SELECT task_id, SUM(final_reward) as final_reward FROM completed_tasks GROUP BY 1) as tb_frw USING(task_id) WHERE task_id = $1 GROUP BY task_id, telegram_id, status, round, completed_tasks, date_of_creation, date_of_completed, completion_in, total_sent, number_not_viewed, number_more, number_hidden, number_refuse, number_refuse_late, number_process_subscriptions, number_process_likes, number_process_retweets, number_process_comments, number_waiting_link, doing_now, average_duration, balance_task, tb_frw.final_reward, executions, number_start_task, number_scored, number_fully_completed, price;", task_id)
            link_action = LinkAction(account_link=info['profile_link'], post_link=info['post_link'])
            return TaskAllInfo(
                task_id=info['task_id'],
                telegram_id=info['telegram_id'],
                status=getattr(TaskStatus, info['status'].upper()),
                round=info['round'],
                completed_tasks=info['completed_tasks'],
                executions=info['executions'],
                completion_percent=self._round_number(info['completed_tasks'] / (info['executions'] / 100)),
                doing_now=info['doing_now'],
                balance=self._round_number(info['balance_task']),
                price=self._round_number(info['price']),
                total_pay=self._round_number(info['total_pay']),
                remaining_balance=self._round_number(info['remaining_balance']),
                actions_link=link_action,
                actions={action: link_action.account_link if action == 'subscriptions' else link_action.post_link for action in info['actions'].split(', ')},
                comment_parameters=await self.get_comment_parameters(task_id),
                total_sent=info['total_sent'],
                number_not_viewed=info['number_not_viewed'],
                number_more=info['number_more'],
                number_hidden=info['number_hidden'],
                number_start_task=info['number_start_task'],
                number_refuse=info['number_refuse'],
                number_refuse_late=info['number_refuse_late'],
                number_scored=info['number_scored'],
                number_fully_completed=info['number_fully_completed'],
                number_process_subscriptions=info['number_process_subscriptions'],
                number_process_likes=info['number_process_likes'],
                number_process_retweets=info['number_process_retweets'],
                number_process_comments=info['number_process_comments'],
                number_waiting_link=info['number_waiting_link'],
                date_of_creation=info['date_of_creation'],
                date_of_completed=info['date_of_completed'],
                completion_in=info['completion_in'] if info['completion_in'] is not None else '-',
                average_duration=info['average_duration'] if info['average_duration'] is not None else '-')

    # Проверка юзера на наличие его в базе данных
    async def check_user_in_db(self, tg_id):
        async with self.pool.acquire() as connection:
            return bool(await connection.fetchval("SELECT telegram_id FROM users WHERE telegram_id = $1", tg_id))

    # Проверка юзера на наличие в датабазе
    async def check_task_in_db(self, task_id):
        async with self.pool.acquire() as connection:
            return bool(await connection.fetchval("SELECT task_id FROM tasks WHERE task_id = $1", task_id))

    # Взять юзеров, выполняющих таск
    async def get_user_performing_task(self, task_id) -> list[UsersPerformTask]:
        async with self.pool.acquire() as connection:
            users = await connection.fetch("SELECT telegram_id, telegram_name, status, offer_time FROM users RIGHT JOIN tasks_messages USING(telegram_id) JOIN statistics USING(tasks_msg_id) WHERE task_id = $1 ORDER BY offer_time DESC", task_id)
            return [UsersPerformTask(
                tg_id=user['telegram_id'],
                telegram_name=user['telegram_name'],
                status=user['status'],
                date_of_sent=user['offer_time']) for user in users]

    # Поменять ссылку в задании
    async def change_link_to_task(self, task_id, type_tasks: list, link):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE actions SET link_action = $1 WHERE task_id = $2 AND type_task = ANY($3)", link, task_id, type_tasks)

    # Снять выполнений с задания
    async def reduse_executions(self, task_id, reduse_executions: int):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE tasks SET executions = executions - $1 WHERE task_id = $2", reduse_executions, task_id)

    # Вернуть кол-во выполнений в виде stb
    async def return_stb_for_reduse(self, task_id, balance_increase: float):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE users SET balance = balance + $2 WHERE telegram_id = (SELECT telegram_id FROM tasks WHERE task_id = $1)", task_id, balance_increase)

    # Увеличить кол-во выполнений и баланс задания
    async def add_executions(self, task_id, executions: int):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE tasks SET executions = executions + $1, balance_task = balance_task + (price * $1) WHERE task_id = $2", executions, task_id)

    # Получить текущие цены за задания
    async def get_prices_for_tasks(self) -> RealPricesTask:
        async with self.pool.acquire() as connection:
            info = await connection.fetchrow("SELECT subscriptions, likes, retweets, comments, commission FROM prices_actions ORDER BY date_added DESC LIMIT 1")
            return RealPricesTask(
                subscriptions=info['subscriptions'],
                likes=info['likes'],
                retweets=info['retweets'],
                comments=info['comments'],
                commission=info['commission'])

    # Сохранить изменения цены за таск
    async def save_task_price_changes(self, task_price: dict):
        async with self.pool.acquire() as connection:
            await connection.execute("INSERT INTO prices_actions(subscriptions, likes, retweets, comments, commission) VALUES ($1, $2, $3, $4, $5)", task_price['subscriptions'], task_price['likes'], task_price['retweets'], task_price['comments'], task_price['commission'])

    # Сохранить изменения приортитеа
    async def save_priority_changes(self, priority_settings: PriorityChange):
        async with self.pool.acquire() as connection:
            await connection.execute("INSERT INTO priority_change(completing_task, re_execution, max_re_execution, complete_others, downtime_more_20_min, ignore_more_20_min, ignore_more_40_min, ignore_more_60_min, refuse, refuse_late, scored_on_task, ignore_many_times, hidden_many_times, refuse_many_times, scored_many_times) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)", priority_settings['completing_task'], priority_settings['re_execution'], priority_settings['max_re_execution'], priority_settings['complete_others'], priority_settings['downtime_more_20_min'], priority_settings['ignore_more_20_min'], priority_settings['ignore_more_40_min'], priority_settings['ignore_more_60_min'], priority_settings['refuse'], priority_settings['refuse_late'], priority_settings['scored_on_task'], priority_settings['ignore_many_times'], priority_settings['hidden_many_times'], priority_settings['refuse_many_times'], priority_settings['scored_many_times'])

    # Получить информацию о порезах
    async def get_info_awards_cut(self) -> AwardsCut:
        async with self.pool.acquire() as connection:
            info = await connection.fetchrow("SELECT first_fine, subsequent_fines FROM awards_cut ORDER BY date_of_added DESC")
            return AwardsCut(
                first_fine=info['first_fine'],
                subsequent_fines=info['subsequent_fines'])

    # Сохранить новые порезы
    async def save_new_awards_cut(self, first_fine: int, subsequent_fines: int):
        async with self.pool.acquire() as connection:
            await connection.execute("INSERT INTO awards_cut(first_fine, subsequent_fines) VALUES ($1, $2)", first_fine, subsequent_fines)

    # Изменить сумму постоянного штрафа
    async def save_sum_temporary_fines(self, new_sum: int):
        async with self.pool.acquire() as connection:
            await connection.execute("INSERT INTO rating_fines(sum_fines) VALUES ($1)", new_sum)

    # Получить процент штрафа за частое удаление заданий
    async def get_fines_task_persent(self):
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow("SELECT percent_fines FROM task_delete_fines ORDER BY date_of_added DESC"))["percent_fines"]

    # Сохранить процент штрафа за частое удаление
    async def change_fines_task_persent(self, percent):
        async with self.pool.acquire() as connection:
            await connection.execute("INSERT INTO task_delete_fines(percent_fines) VALUES ($1)", percent)

    # Достать лимиты на таски в день и их кол-во на аккаунт для всех уровней
    async def get_all_info_levels_limits(self) -> AllInfoLimits:
        async with self.pool.acquire() as connection:
            limits_tasks = await connection.fetchrow("SELECT vacationers, prelim, main, challenger, champion FROM limits_tasks ORDER BY date_of_added DESC")
            limits_execution = await connection.fetchrow("SELECT beginner, vacationers, prelim, main, challenger, champion FROM limits_execution ORDER BY date_of_added DESC")
            number_of_completed_tasks = await connection.fetchrow("SELECT prelim, main, challenger, champion FROM number_of_completed_tasks ORDER BY date_of_added DESC")
            number_of_accounts = await connection.fetchrow("SELECT prelim, main, challenger, champion FROM number_of_accounts ORDER BY date_of_added DESC")
            return {'champion': {'tasks_per_day': limits_tasks['champion'], 'max_accs_on_taks': limits_execution['champion'], 'need_task_for_level': number_of_completed_tasks['champion'], 'need_accs_for_level': number_of_accounts['champion']},
                    'challenger': {'tasks_per_day': limits_tasks['challenger'], 'max_accs_on_taks': limits_execution['challenger'], 'need_task_for_level': number_of_completed_tasks['challenger'], 'need_accs_for_level': number_of_accounts['challenger']},
                    'main': {'tasks_per_day': limits_tasks['main'], 'max_accs_on_taks': limits_execution['main'], 'need_task_for_level': number_of_completed_tasks['main'], 'need_accs_for_level': number_of_accounts['main']},
                    'prelim': {'tasks_per_day': limits_tasks['prelim'], 'max_accs_on_taks': limits_execution['prelim'], 'need_task_for_level': number_of_completed_tasks['prelim'], 'need_accs_for_level': number_of_accounts['prelim']},
                    'vacationers': {'tasks_per_day': limits_tasks['vacationers'], 'max_accs_on_taks': limits_execution['vacationers'], 'need_task_for_level': '-', 'need_accs_for_level': '-'},
                    'beginner': {'tasks_per_day': '-', 'max_accs_on_taks': limits_execution['beginner'], 'need_task_for_level': '-', 'need_accs_for_level': '-'}}

    # Изменить лимит на кол-во тасков в день
    async def add_new_limits_tasks(self, level, new_limit):
        async with self.pool.acquire() as connection:
            limits_tasks = await connection.fetchrow("SELECT vacationers, prelim, main, challenger, champion FROM limits_tasks ORDER BY date_of_added DESC")
            await connection.execute("INSERT INTO limits_tasks(vacationers, prelim, main, challenger, champion) VALUES ($1, $2, $3, $4, $5)", *(limit if key != level else new_limit for key, limit in limits_tasks.items()))

    # Изменить лимит на кол-во аккаунтов на таск
    async def add_new_limits_accounts(self, level, executions):
        async with self.pool.acquire() as connection:
            limits_execution = await connection.fetchrow("SELECT beginner, vacationers, prelim, main, challenger, champion FROM limits_execution ORDER BY date_of_added DESC")
            await connection.execute("INSERT INTO limits_execution(beginner, vacationers, prelim, main, challenger, champion) VALUES ($1, $2, $3, $4, $5, $6)", *(limit if key != level else executions for key, limit in limits_execution.items()))

    # Изменить необходимое кол-во выполненных тасков для получения уровня
    async def change_need_tasks_for_level(self, level, need_tasks):
        async with self.pool.acquire() as connection:
            number_of_completed_tasks = await connection.fetchrow("SELECT prelim, main, challenger, champion FROM number_of_completed_tasks ORDER BY date_of_added DESC")
            await connection.execute("INSERT INTO number_of_completed_tasks(prelim, main, challenger, champion) VALUES ($1, $2, $3, $4)", *(limit if key != level else need_tasks for key, limit in number_of_completed_tasks.items()))

    # Изменить необходимое кол-во выполненных тасков для получения уровня
    async def change_need_active_accs_for_level(self, level, need_active_accs):
        async with self.pool.acquire() as connection:
            number_of_accounts = await connection.fetchrow("SELECT prelim, main, challenger, champion FROM number_of_accounts ORDER BY date_of_added DESC")
            await connection.execute("INSERT INTO number_of_accounts(prelim, main, challenger, champion) VALUES ($1, $2, $3, $4)", *(limit if key != level else need_active_accs for key, limit in number_of_accounts.items()))

    # Получить список админов
    async def get_info_about_admins(self) -> list[AdminInfo]:
        async with self.pool.acquire() as connection:
            admins = await connection.fetch('SELECT telegram_id, telegram_name, admin_balance FROM admins ORDER BY date_of_adding ASC')
            return [AdminInfo(telegram_id=admin['telegram_id'],
                              telegram_name=admin['telegram_name'],
                              admin_balance=self._round_number(admin['admin_balance'])) for admin in admins]

    # Добавить нового админа
    async def adding_admin(self, admin_id):
        async with self.pool.acquire() as connection:
            telegram_name = (await connection.fetchrow('SELECT telegram_name FROM users WHERE telegram_id = $1', admin_id))['telegram_name']
            await connection.execute("INSERT INTO admins(telegram_id, telegram_name) VALUES ($1, $2)", admin_id, telegram_name if telegram_name else 0)

    # Удалить админа
    async def remove_admin(self, admin_id):
        async with self.pool.acquire() as connection:
            await connection.execute("DELETE FROM admins WHERE telegram_id = $1", admin_id)

    # Достать всю инфу о саппортах
    async def get_info_about_supports(self) -> list[SupportInfo]:
        async with self.pool.acquire() as connection:
            supports = await connection.fetch("SELECT telegram_id, telegram_name, active_status, support_balance, main_support_flag FROM supports ORDER BY date_of_adding ASC")
            return [SupportInfo(
                telegram_id=support['telegram_id'],
                telegram_name=support['telegram_name'],
                support_balance=support['support_balance'],
                active_status=support['active_status'],
                main_support=support['main_support_flag']) for support in supports]

    # Достать информацию о саппорте
    async def get_info_about_support(self, support_id) -> SupportInfo:
        async with self.pool.acquire() as connection:
            support = await connection.fetchrow("SELECT telegram_id, telegram_name, active_status, support_balance, main_support_flag FROM supports WHERE telegram_id = $1 ORDER BY date_of_adding ASC", support_id)
            return SupportInfo(
                telegram_id=support['telegram_id'],
                telegram_name=support['telegram_name'],
                support_balance=support['support_balance'],
                active_status=support['active_status'],
                main_support=support['main_support_flag'])

    # Поменять статус саппорта
    async def change_support_status(self, support_id: int, flag: bool):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE supports SET active_status = $2 WHERE telegram_id = $1", support_id, flag)

    # Убрать всех саппортов по умолчанию
    async def reset_support_default(self):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE supports SET main_support_flag = False")

    # Стать саппортом по умолчанию
    async def defaulted_support(self, support_id):
        async with self.pool.acquire() as connection:
            await self.reset_support_default()
            await connection.execute("UPDATE supports SET main_support_flag = True WHERE telegram_id = $1", support_id)

    # Добавить нового саппорта
    async def add_new_supprt(self, support_id):
        async with self.pool.acquire() as connection:
            telegram_name = (await connection.fetchrow('SELECT telegram_name FROM users WHERE telegram_id = $1', support_id))['telegram_name']
            await connection.execute('INSERT INTO supports(telegram_id, telegram_name) VALUES ($1, $2)', support_id, telegram_name if telegram_name else 0)

    # Удалить саппорта
    async def remove_support(self, support_id):
        async with self.pool.acquire() as connection:
            await connection.execute("DELETE FROM supports WHERE telegram_id = $1", support_id)
            await self.new_default_support()

    # Новый саппорт по умолчанию
    async def select_default_support(self, support_id):
        async with self.pool.acquire() as connection:
            await self.reset_support_default()
            await connection.execute("UPDATE supports SET main_support_flag = True WHERE telegram_id = $1", support_id)

    # Поставить нового дефолт саппорта, если старого дефолт саппорта нет
    async def new_default_support(self):
        async with self.pool.acquire() as connection:
            if not await self.get_default_support_name():  # Проверка на то, есть ли активный саппорт
                active_support = await connection.fetchrow("SELECT telegram_id FROM supports WHERE active_status is True")
                if active_support:  # Проверка на то, кто сейчас активен
                    await connection.execute('UPDATE supports SET main_support_flag = True WHERE telegram_id = $1', active_support['telegram_id'])
                else:  # Если ни одного активного нет, берётся самый первый в списке
                    await connection.execute('UPDATE supports SET main_support_flag = True WHERE telegram_id = (SELECT telegram_id FROM supports LIMIT 1)')

    # Старый дефолт саппорт снял с себя полномочия
    async def update_default_support(self, tg_id):
        async with self.pool.acquire() as connection:
            await self.reset_support_default()
            active_sup = await connection.fetchrow('SELECT telegram_id FROM supports WHERE active_status = True AND telegram_id <> $1', tg_id)
            if active_sup:  # Проверка на то, есть ли активный саппорт
                await connection.execute("UPDATE supports SET main_support_flag = True WHERE telegram_id = $1", active_sup['telegram_id'])
            else:
                await connection.execute('UPDATE supports SET main_support_flag = True WHERE telegram_id = (SELECT telegram_id FROM supports WHERE telegram_id <> $1 LIMIT 1)', tg_id)

    # Взять список саппортов
    async def get_support_list(self):
        async with self.pool.acquire() as connection:
            supports = await connection.fetch("SELECT telegram_id FROM supports")
            return [support['telegram_id'] for support in supports]

    # Взять список активных сапортов
    async def get_active_supports_list(self):
        async with self.pool.acquire() as connection:
            supports = await connection.fetch("SELECT telegram_name FROM supports WHERE active_status = True")
            if supports:
                return [support['telegram_name'][1:] for support in supports]
            return [(await self.get_default_support_name())[1:]]

    # Взять id активных саппортов
    async def get_active_support_ids(self):
        async with self.pool.acquire() as connection:
            supports = await connection.fetch("SELECT telegram_id FROM supports WHERE active_status = True")
            if supports:
                return [support['telegram_id'] for support in supports]
            return [(await self.get_default_support_id())]



    # Найти телеграм name сапорта по умолчнанию
    async def get_default_support_name(self):
        async with self.pool.acquire() as connection:
            info = await connection.fetchrow("SELECT telegram_name FROM supports WHERE main_support_flag is True")
            if info:
                return info['telegram_name']

    # Найти телеграм id саппорта по умолчанию
    async def get_default_support_id(self):
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow("SELECT telegram_id FROM supports WHERE main_support_flag = True"))['telegram_id']

    # Получить данные для саппорт панели
    async def get_info_for_support_panel(self, tg_id) -> SupportPanelInfo:
        async with self.pool.acquire() as connection:
            info = await connection.fetchrow("SELECT active_status, (SELECT COUNT(*) as active_tasks FROM tasks WHERE status IN ('waiting_start', 'bulk_messaging', 'dop_bulk_messaging', 'active')) AS active_tasks, (SELECT COUNT(*) as number_offers FROM tasks_messages WHERE status IN ('offer', 'offer_more')) AS number_offers, (SELECT COUNT(*) active_users FROM tasks_messages WHERE status IN ('start_task', 'process', 'сhecking', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments')) AS active_users FROM supports WHERE telegram_id = $1;", tg_id)
            return SupportPanelInfo(
                status=info['active_status'],
                main_support=await self.get_default_support_name(),
                active_tasks=info['active_tasks'],
                number_offers=info['number_offers'],
                active_workers=info['active_users'])

    # Получить id админов
    async def get_admins_ids(self):
        async with self.pool.acquire() as connection:
            ids = await connection.fetch("SELECT telegram_id FROM admins")
            return [admin_id['telegram_id'] for admin_id in ids]

    # Проверка таска на то, что он активный
    async def check_active_task(self, task_id):
        async with self.pool.acquire() as connection:
            return bool(await connection.fetchval("SELECT task_id FROM tasks WHERE task_id = $1 AND tasks.status IN ('waiting_start', 'bulk_messaging', 'dop_bulk_messaging', 'active')", task_id))

    # Вернуть STB создателю задания
    async def return_stb_to_author(self, return_stb: float, tg_id: int):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE users SET balance = balance + $1 WHERE telegram_id = $2", return_stb, tg_id)

    # Получить инфу о сроках проверки заданий
    async def get_info_about_time_check_tasks(self):
        async with self.pool.acquire() as connection:
            info = await connection.fetchrow("SELECT stage_1, stage_2, stage_3, stage_4 FROM task_check_deadlines ORDER BY date_of_adding DESC LIMIT 1")
            return {'stage_1': info['stage_1'], 'stage_2': info['stage_2'], 'stage_3': info['stage_3'], 'stage_4': info['stage_4']}

    # Запрос, отбирающий все задания, выполнение которых пора перепроверить
    async def get_all_task_with_need_checking(self) -> dict[int, int]:
        async with self.pool.acquire() as connection:
            tasks = await connection.fetch("SELECT tasks_msg_id, stage_1, stage_2, stage_3, stage_4, date_of_completion FROM completed_tasks JOIN task_completion_check USING(tasks_msg_id) WHERE do_not_check_flag = False AND stage_1 IS NOT False AND stage_2 IS NOT False AND stage_3 IS NOT False AND stage_4 IS NOT False;")
            time_dict = await self.get_info_about_time_check_tasks()
            keys = ['stage_1', 'stage_2', 'stage_3', 'stage_4']
            result_dict = {}
            for task in tasks:
                for key in keys:
                    if task[key] is None and (datetime.datetime.now(pytz.timezone('Europe/Moscow')) - task['date_of_completion'].astimezone(pytz.timezone('Europe/Moscow'))).total_seconds() / 3600 > time_dict[key]:
                        need_stage = int(key[6:])
                        result_dict[task['tasks_msg_id']] = need_stage
                        break
            return result_dict

    # Меняем очередную стадию проверки задания
    async def change_re_check_stage(self, tasks_msg_id, stage, check_flag=True):
        async with self.pool.acquire() as connection:
            # Это чат gpt мне показал так сделать, чтобы стадию указать в запросе
            query = f"UPDATE task_completion_check SET stage_{stage} = $1 WHERE tasks_msg_id = $2"
            await connection.execute(query, check_flag, tasks_msg_id)

    # Оформить штраф на юзера и взять его с него
    async def collect_stb_from_user(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            tg_id = await self.get_telegram_id_from_tasks_messages(tasks_msg_id)
            task_id = await self.get_task_id_from_tasks_messages(tasks_msg_id)
            sum_fines = (await connection.fetchrow("SELECT price FROM tasks WHERE task_id = $1", task_id))['price']
            balance_user = (await connection.fetchrow("SELECT balance FROM users WHERE telegram_id = $1", tg_id))['balance']
            fines_id = await connection.fetchval("INSERT INTO fines(telegram_id, fines_type, tasks_msg_id) VALUES ($1, $2, $3) RETURNING fines_id", tg_id, 'bought', tasks_msg_id)
            await self.attach_fine_to_accounts(fines_id)
            # Если хватает баланса, как и положено
            if balance_user >= sum_fines:
                await connection.execute("INSERT INTO bought(fines_id, remaining_to_redeem, already_bought, victim_user) VALUES($1, $2, $3, (SELECT telegram_id FROM tasks WHERE task_id = $4))", fines_id, sum_fines, sum_fines, task_id)
                await connection.execute("UPDATE users SET balance = balance - $1 WHERE telegram_id = $2", sum_fines, tg_id)
                await self.record_in_payment_fines(fines_id, balance_user)
            else:
                cut = await self.get_need_cut_for_stb_fine(tg_id)
                await connection.execute("INSERT INTO bought(fines_id, remaining_to_redeem, already_bought, awards_cut, victim_user) VALUES($1, $2, $3, $4, (SELECT telegram_id FROM tasks WHERE task_id = $5))", fines_id, sum_fines, balance_user, cut, task_id)
                await connection.execute("UPDATE users SET balance = 0 WHERE telegram_id = $1", tg_id)
                await self.record_in_payment_fines(fines_id, sum_fines)
            return fines_id

    # Получить информацию по собранному штрафу
    async def get_bought_fines_info(self, tasks_msg_id) -> FinesPartInfo:
        async with self.pool.acquire() as connection:
            fines_info = await connection.fetchrow("SELECT already_bought, awards_cut, (CASE WHEN remaining_to_redeem > already_bought THEN True ELSE False END) as cut_flag, bought.remaining_to_redeem FROM bought JOIN fines USING(fines_id) WHERE tasks_msg_id = $1 ORDER BY fines_id DESC", tasks_msg_id)
            return FinesPartInfo(
                sum_fines=self._round_number(fines_info['already_bought']),
                cut=fines_info['awards_cut'],
                cut_flag=fines_info['cut_flag'],
                remaining_amount=self._round_number(fines_info['remaining_to_redeem'] - fines_info['already_bought']))

    # Получить ссылку на комментарий при перепроверке выполнения
    async def get_link_to_worker_comment(self, tasks_msg_id) -> int | None:
        async with self.pool.acquire() as connection:
            link = await connection.fetchrow("SELECT comment_id FROM task_check_materials WHERE tasks_msg_id = $1", tasks_msg_id)
            if link:
                return link['comment_id']


    # # Получить границу времени, дальше которой уже проверять посты у юзера смысла нет
    # async def get_last_time_for_re_executions(self, tasks_msg_id):
    #     async with self.pool.acquire() as connection:
    #         info = await connection.fetchrow('SELECT finish_time, stage_1, stage_2, stage_3, stage_4 FROM statistics JOIN task_completion_check USING(tasks_msg_id) WHERE tasks_msg_id = $1', tasks_msg_id)
    #         stages = ['stage_1', 'stage_2', 'stage_3', 'stage_4']
    #         last_stage = [stage for stage in stages if info[stage] is None][0]
    #         return info['finish_time'] + datetime.timedelta(hours=info[last_stage] + 1)

    # Получить имя аккаунта, сделавшего задание
    async def get_account_from_completed_tasks(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow("SELECT account_id FROM completed_tasks WHERE tasks_msg_id = $1", tasks_msg_id))['account_id']

    # Получить информацию о срезах подписчиков для парсинга
    async def get_all_cut(self, tasks_msg_id) -> dict[str, dict[str, list[str]]] | None:
        async with self.pool.acquire() as connection:
            cuts = await connection.fetchrow("SELECT author_materials.upper_cut as au_upper_cut, author_materials.lower_cut as au_lower_cut, worker_materials.upper_cut as wr_upper_cut, worker_materials.lower_cut as wr_lower_cut FROM task_check_materials LEFT JOIN author_materials USING(author_materials_id) LEFT JOIN worker_materials USING(worker_materials_id) WHERE tasks_msg_id = $1", tasks_msg_id)
            if cuts:
                return {'worker_cut': {'lower_cut': cuts['wr_lower_cut'] if 'wr_lower_cut' in cuts else None,
                                       'upper_cut': cuts['wr_upper_cut'] if 'wr_upper_cut' in cuts else None},
                        'author_cut': {'lower_cut': cuts['au_lower_cut'] if 'au_lower_cut' in cuts else None,
                                       'upper_cut': cuts['au_upper_cut'] if 'au_upper_cut' in cuts else None}}

    # Проверить, создана ли запись в табличке с материалами для перепроверки
    async def check_task_materials(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            return bool(await connection.fetchval('SELECT materials_id FROM task_check_materials WHERE tasks_msg_id = $1', tasks_msg_id))

    # Функция для сохранения id комментария
    async def save_comment(self, tasks_msg_id, comment_link):
        async with self.pool.acquire() as connection:
            comment_id = int(comment_link.split('/status/')[-1])
            if await self.check_task_materials(tasks_msg_id):
                await connection.execute('UPDATE task_check_materials SET comment_id = $1 WHERE tasks_msg_id = $2', comment_id, tasks_msg_id)
            else:
                await connection.execute("INSERT INTO task_check_materials(tasks_msg_id, comment_id) VALUES ($1, $2)", tasks_msg_id, comment_id)

    # Функция для сохранения среза у воркера
    async def save_worker_cut(self, tasks_msg_id, upper_cut, lower_cut):
        async with self.pool.acquire() as connection:
            worker_materials_id = await connection.fetchval('INSERT INTO worker_materials(upper_cut, lower_cut) VALUES ($1::VARCHAR[], $2::VARCHAR[]) RETURNING worker_materials_id', upper_cut, lower_cut)
            if await self.check_task_materials(tasks_msg_id):
                await connection.execute('INSERT INTO task_check_materials(tasks_msg_id, worker_materials_id) VALUES ($1, $2)', tasks_msg_id, worker_materials_id)
            else:
                await connection.execute('UPDATE task_check_materials SET worker_materials_id = $1 WHERE tasks_msg_id = $2', worker_materials_id, tasks_msg_id)

    # Функция для сохранения среза у автора
    async def save_author_cut(self, tasks_msg_id, upper_cut, lower_cut):
        async with self.pool.acquire() as connection:
            author_materials_id = await connection.fetchval('INSERT INTO author_materials(upper_cut, lower_cut) VALUES ($1::VARCHAR[], $2::VARCHAR[]) RETURNING author_materials_id', upper_cut, lower_cut)
            if await self.check_task_materials(tasks_msg_id):
                await connection.execute('INSERT INTO task_check_materials(tasks_msg_id, author_materials) VALUES ($1, $2)', tasks_msg_id, author_materials_id)
            else:
                await connection.execute('UPDATE task_check_materials SET author_materials = $1 WHERE tasks_msg_id = $2', author_materials_id, tasks_msg_id)

    # Получить все таски авторов, которые пора проверить на жизнь
    async def get_all_authors_tasks(self) -> list[AuthorTaskInfo]:
        async with self.pool.acquire() as connection:
            tasks_messages = list((await self.get_all_task_with_need_checking()).keys())
            tasks_ids = await connection.fetch("SELECT task_id FROM tasks_messages WHERE tasks_msg_id = ANY($1)", tasks_messages)
            tasks_ids = [task_id['task_id'] for task_id in tasks_ids]
            hours_check = 5
            # Запрос отбирает только те ссылки, которые ещё не были проверены в течении последних 5 часов
            all_tasks = await connection.fetch("SELECT task_id, MAX(CASE WHEN actions.link_action NOT LIKE '%/status/%' AND actions.link_action NOT IN (SELECT link_action FROM tasks RIGHT JOIN actions USING(task_id) JOIN task_author_check USING(task_id) WHERE NOW() - last_check < $1 * INTERVAL '1 hours') THEN actions.link_action ELSE NULL END) as profile_link, MAX(CASE WHEN actions.link_action LIKE '%/status/%' AND actions.link_action NOT IN (SELECT link_action FROM tasks RIGHT JOIN actions USING(task_id) JOIN task_author_check USING(task_id) WHERE NOW() - last_check < $1 * INTERVAL '1 hours') THEN actions.link_action ELSE NULL END) as post_link FROM tasks RIGHT JOIN actions USING(task_id) JOIN task_author_check USING(task_id) WHERE do_not_check_flag = False AND (last_check IS NULL OR NOW() - last_check > $1 * INTERVAL '1 hours') AND NOW() - tasks.date_of_creation > INTERVAL '2 hours' AND task_id IN (SELECT task_id FROM tasks_messages WHERE tasks_msg_id = ANY($2)) GROUP BY task_id;", hours_check, tasks_ids)
            finally_list = []
            for task in all_tasks:
                finally_list.append(AuthorTaskInfo(
                    task_id=task['task_id'],
                    links=LinkAction(
                        account_link=task['profile_link'],
                        post_link=task['post_link'])))
            return finally_list

    # Обновить время последней проверки таска
    async def update_check_author_links_time(self, tasks: list):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE task_author_check SET last_check = NOW() WHERE task_id = ANY($1)", tasks)

    # Поставить задание больше не проверяться
    async def not_checking_task_flag(self, task_id):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE task_author_check SET do_not_check_flag = True WHERE task_id = $1", task_id)
            tasks = await connection.fetch("SELECT tasks_msg_id FROM tasks_messages WHERE task_id = $1 AND status = 'completed'", task_id)
            tasks = [task_msg_id['tasks_msg_id'] for task_msg_id in tasks]
            await connection.execute("UPDATE task_completion_check SET do_not_check_flag = True WHERE tasks_msg_id = ANY($1)", tasks)

    # Отключить проверку по ссылке
    async def not_checking_by_link(self, link):
        async with self.pool.acquire() as connection:
            await connection.execute("SELECT tasks_msg_id, task_id FROM tasks_messages RIGHT JOIN (SELECT task_id FROM tasks_messages RIGHT JOIN actions USING(task_id) WHERE link_action = $1) AS t_1 USING(task_id) GROUP BY task_id, tasks_msg_id;", link)

    # Найти все таски, которым пора переходить на новый раунд
    async def get_tasks_for_new_round(self) -> dict[int, Literal[1, 2, 3]]:
        async with self.pool.acquire() as connection:
            tasks = await connection.fetch("SELECT task_id, round, executions, NOW() - date_of_creation as time_passed, COUNT(CASE WHEN tasks_messages.status = 'completed' THEN 1 ELSE NULL END) as count_completed, COUNT(CASE WHEN tasks_messages.status IN ('start_task', 'process', 'process_subscriptions', 'process_likes', 'process_retweets', 'waiting_link', 'process_comments', 'сhecking') THEN 1 ELSE NULL END) as in_process FROM tasks RIGHT JOIN tasks_messages USING(task_id) WHERE round > 0 AND round < 3 AND tasks.status NOT IN ('completed', 'deleted') GROUP BY task_id, round, executions, time_passed, date_of_creation ORDER BY date_of_creation;")
            info_dict = {2: {'time_passed': 20, 'max_completion_percentage': 75},
                         3: {'time_passed': 40, 'max_completion_percentage': 80}}
            tasks_dict = {}
            for task in tasks:
                next_round = task['round'] + 1  # Взять раунд, для которого будут отбираться воркеры
                if info_dict[next_round]['time_passed'] >= task['time_passed'].total_seconds() * 60 and \
                        info_dict[next_round]['max_completion_percentage'] > (task['count_completed'] + (task['in_process'] * 0.8)) / (task['executions'] / 100):
                    tasks_dict[task] = next_round
            return tasks_dict

    # Достать всех юзеров, которые долго ждут задание и которым пора апнуть приоритет
    async def get_all_users_for_up_priority(self):
        async with self.pool.acquire() as connection:
            users = await connection.fetch("SELECT telegram_id FROM user_notifications WHERE all_notifications = TRUE AND NOW() - date_of_update > INTERVAL '20 minutes' AND telegram_id NOT IN (SELECT tasks_messages.telegram_id FROM tasks_messages JOIN statistics USING(tasks_msg_id) WHERE NOW() - offer_time < INTERVAL '20 minutes' OR NOW() - finish_time < INTERVAL '20 minutes' OR tasks_messages.status NOT IN ('completed', 'refuse', 'refuse_late', 'scored', 'fully_completed', 'hidden', 'deleted') GROUP BY tasks_messages.telegram_id)")
            return [user['telegram_id'] for user in users]

    # Повысить приоритет юзеров
    async def up_priority_users(self, users: list[int], dop_priority: int):
        async with self.pool.acquire() as connection:
            await connection.executemany('UPDATE tasks_distribution SET priority = LEAST(priority+$1, 100) WHERE telegram_id = $2', [(dop_priority, user) for user in users])

    # Достать время после активации кнопки по включению получения заданий
    async def get_time_after_update_button(self, tg_id) -> datetime.timedelta:
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow("SELECT (NOW() - date_of_update) as time_after_update FROM user_notifications WHERE telegram_id = $1", tg_id))['time_after_update']

    # Обновление времени активации кнопки по включению заданий у юзеров
    async def update_date_of_update(self, tg_id: list[int]):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE user_notifications SET date_of_update = NOW() WHERE telegram_id = ANY($1)", tg_id)

    # Обновить нейм админа в табличке
    async def update_admin_username(self, tg_id, tg_name):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE admins SET telegram_name = $1 WHERE telegram_id = $2', tg_name, tg_id)

    # Обновить нейм сапорта в табличке
    async def update_support_username(self, tg_id, tg_name):
        async with self.pool.acquire() as connection:
            await connection.execute('UPDATE supports SET telegram_name = $1 WHERE telegram_id = $2', tg_name, tg_id)

    # Получить некоторую статистику по аккаунту для главного меню
    async def get_some_statistics_account(self, tg_id) -> InfoForMainMenu:
        async with self.pool.acquire() as connection:
            info = await connection.fetchrow("SELECT (SELECT COUNT(*) FROM tasks_messages JOIN statistics USING(tasks_msg_id) WHERE offer_time AT TIME ZONE 'Europe/Moscow' >= DATE_TRUNC('days', current_timestamp AT TIME ZONE 'Europe/Moscow') AND telegram_id = $1) as number_sent_tasks, (SELECT COUNT(*) FROM completed_tasks WHERE date_of_completion AT TIME ZONE 'Europe/Moscow' >= DATE_TRUNC('days', current_timestamp AT TIME ZONE 'Europe/Moscow') AND telegram_id = $1) as number_completed_tasks, (SELECT priority FROM tasks_distribution WHERE telegram_id = $1), (SELECT top_priority_flag FROM tasks_distribution WHERE telegram_id = $1), (SELECT GREATEST(SUM(remaining_to_redeem) - SUM(already_bought), 0) as sum_fines_stb FROM bought JOIN fines USING(fines_id) WHERE telegram_id = $1 AND collection_flag = False), (SELECT COALESCE(MAX(awards_cut), 100) as awards_cut FROM bought JOIN fines USING(fines_id) WHERE telegram_id = $1 AND collection_flag = True), (SELECT COALESCE(SUM(reduction_in_priority), 0) FROM temporary JOIN fines USING(fines_id) WHERE valid_until > NOW() AND telegram_id = $1) as sum_fines_priority;", tg_id)
            return InfoForMainMenu(
                number_sent_tasks=info['number_sent_tasks'],
                number_completed_tasks=info['number_completed_tasks'],
                priority=info['priority'],
                top_priority=info['top_priority_flag'],
                sum_fines_stb=self._round_number(info['sum_fines_stb']),
                awards_cut=info['awards_cut'],
                sum_fines_priority=info['sum_fines_priority'])

    # Достать прайс за таск и итоговую награду за выполнение
    async def get_task_price(self, task_id):
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow("SELECT price FROM tasks WHERE task_id = $1", task_id))['price']

    # Достать финальную награду за выполнение задания
    async def get_final_reward(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow("SELECT final_reward FROM completed_tasks WHERE tasks_msg_id = $1", tasks_msg_id))['final_reward']

    # Получить сумму действующих штрафов в stb
    async def get_sum_fines_stb(self, tg_id):
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow('SELECT GREATEST(SUM(remaining_to_redeem) - SUM(already_bought), 0) as sum_fines_stb FROM bought JOIN fines USING(fines_id) WHERE telegram_id = $1 AND collection_flag = False', tg_id))['sum_fines_stb']

    # Поместить юзера вне приоритета
    async def put_user_out_of_priority(self, tg_id):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE tasks_distribution SET top_priority_flag = True WHERE telegram_id = $1", tg_id)

    # Проверить, есть ли у юзера флаг вне приоритета и, если да, то убрать
    async def check_user_priority_queue(self, tg_id):
        async with self.pool.acquire() as connection:
            if (await connection.fetchrow("SELECT top_priority_flag FROM tasks_distribution WHERE telegram_id = $1", tg_id))['top_priority_flag']:
                await connection.execute("UPDATE tasks_distribution SET top_priority_flag = False WHERE telegram_id = $1", tg_id)

    # Проверка на то, что таск завершён
    async def check_task_on_completed_status(self, tasks_msg_id):
        async with self.pool.acquire() as connection:
            return bool(await connection.fetchval("SELECT * FROM completed_tasks WHERE tasks_msg_id = $1", tasks_msg_id))

    # Получить id сообщения о таске по тг id и id самого таска
    async def get_tasks_msg_id_from_task(self, tg_id, task_id):
        async with self.pool.acquire() as connection:
            return (await connection.fetchrow("SELECT tasks_msg_id FROM tasks_messages WHERE telegram_id = $1 AND task_id = $2", tg_id, task_id))['tasks_msg_id']

    # Откатить все изменения за невыполнение задания
    async def roll_back_all_changes_for_not_completed_task(self, tasks_msg_id, tg_id):
        async with self.pool.acquire() as connection:
            await connection.execute("DELETE FROM fines WHERE tasks_msg_id = $1", tasks_msg_id)
            status = (await connection.fetchrow('SELECT status FROM tasks_messages WHERE tasks_msg_id = $1', tasks_msg_id))['status']
            if status in ('refuse', 'refuse_late', 'scored'):
                priority_changes = await self.get_priority_change()
                changes_dict = {'refuse': abs(priority_changes['refuse']), 'refuse_late': abs(priority_changes['refuse_late']), 'scored': abs(priority_changes['scored_on_task'])}
                new_priority = await self.max_priority(tg_id, changes_dict[status])
                await connection.execute("UPDATE tasks_distribution SET priority = $1 WHERE telegram_id = $2", new_priority, tg_id)

    # Добавить действующие штрафы с прошлого тг аккаунта при добавлении нового твиттер аккаунта, если они есть
    async def add_fines_from_account(self, tg_id, account_id):
        async with self.pool.acquire() as connection:
            fines = await connection.fetch("SELECT fines_id, fines_type, tasks_msg_id, valid_until, reduction_in_priority, remaining_to_redeem, awards_cut, victim_user FROM accounts_fines_slise LEFT JOIN fines USING(fines_id) LEFT JOIN bought USING(fines_id) LEFT JOIN temporary USING(fines_id) WHERE ((fines.fines_type = 'bought' AND remaining_to_redeem > already_bought) OR (fines.fines_type = 'temporary' AND valid_until > NOW())) AND account_id = $1 AND fines_id NOT IN (SELECT taken_fines_id FROM fines_taken_from_accounts WHERE telegram_id = $2) AND fines.telegram_id <> $2;", account_id, tg_id)
            if fines:
                # Добавить проверку, что, если штраф денежный, то сам у себя юзер его не будет брать
                for fine in fines:
                    fines_id = await connection.fetchval("INSERT INTO fines(telegram_id, fines_type, tasks_msg_id) VALUES ($1, $2, $3) RETURNING fines_id", tg_id, fine['fines_type'], fine['tasks_msg_id'])
                    if fine['fines_type'] == 'bought':
                        cut = await self.get_need_cut_for_stb_fine(tg_id)
                        await connection.execute("INSERT INTO bought(fines_id, remaining_to_redeem, already_bought, awards_cut, victim_user) VALUES ($1, $2, $3, $4, $5)", fines_id, fine['remaining_to_redeem'], 0, cut, fine['victim_user'])
                    else:
                        await connection.execute("INSERT INTO temporary(fines_id, valid_until, reduction_in_priority) VALUES ($1, $2, $3)", fines_id, fine['valid_until'], fine['reduction_in_priority'])
                    await connection.execute("INSERT INTO fines_taken_from_accounts(telegram_id, taken_fines_id, received_fines_id, account_id) VALUES ($1, $2, $3, $4)", tg_id, fine['fines_id'], fines_id, account_id)
                    await self.attach_fine_to_accounts(fines_id)
                return True
            return False

    # Добавить аккаунт в срез штрафов к какому-то штрафу
    async def add_account_to_slice(self, tg_id, account_id):
        async with self.pool.acquire() as connection:
            fines = await connection.fetch("SELECT fines_id FROM accounts_fines_slise LEFT JOIN fines USING(fines_id) LEFT JOIN bought USING(fines_id) LEFT JOIN temporary USING(fines_id) WHERE ((fines.fines_type = 'bought' AND remaining_to_redeem > already_bought) OR (fines.fines_type = 'temporary' AND valid_until > NOW())) AND telegram_id = $1 GROUP BY fines_id;", tg_id)
            if fines:
                fines_list = [fine['fines_id'] for fine in fines]
                for fines_id in fines_list:
                    await connection.execute('INSERT INTO accounts_fines_slise(fines_id, account_id) VALUES ($1, $2)', fines_id, account_id)

    # Функция, выдающая нужный процент пореза для денежного штрафа
    async def get_need_cut_for_stb_fine(self, tg_id):
        async with self.pool.acquire() as connection:
            cuts = await self.get_info_awards_cut()
            check_first_fine = bool(await connection.fetchval("SELECT fines_id FROM fines JOIN bought USING(fines_id) WHERE remaining_to_redeem > already_bought AND fines.telegram_id = $1", tg_id))
            if check_first_fine:
                return cuts.subsequent_fines
            return cuts.first_fine

    # Функция для переименования аккаунта
    async def rename_account(self, old_account_name, new_account_name):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE accounts SET account_name = $2 WHERE account_name = $1", old_account_name, new_account_name)

    # Проверка на то, что сапорт был оповещён о том, что от какого-то задания слишком часто отказывались
    async def check_support_alert_about_over_refusal(self, task_id):
        async with self.pool.acquire() as connection:
            return bool(await connection.fetchval('SELECT * FROM support_alert_over_refusal WHERE task_id = $1', task_id))

    # Запись о том, что саппорт был оповещён
    async def support_notification_record(self, support_id, task_id):
        async with self.pool.acquire() as connection:
            await connection.execute("INSERT INTO support_alert_over_refusal(telegram_id, task_id) VALUES ($1, $2)", support_id, task_id)

    # Проверка на то, что задание не удалено
    async def check_delete_task(self, task_id):
        async with self.pool.acquire() as connection:
            return bool(await connection.fetchval("SELECT task_id FROM tasks WHERE status <> 'deleted' AND task_id = $1", task_id))