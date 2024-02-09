import asyncio
import inspect
from asyncio import gather
from typing import Callable

import asyncpg

from config import load_config
from databases.database import Database

config = load_config()


class StartDB:
    pool = None

    @classmethod
    async def connect(cls):
        cls.pool = await Database.common_connect(cls.pool)

    @classmethod
    async def disconnect(cls):
        if cls.pool:
            await cls.pool.close()

    async def start_database(self):
        await self.connect()
        await self._create_all_tabels()
        await self._set_initial_values()
        await self.disconnect()
        await self._initial_main_connect()

    async def _create_all_tabels(self):
        """Создание всех таблиц"""
        create_methods_list: list[Callable] = self._get_create_table_methods()
        main_tables_list = ['users', 'tasks', 'fines', 'accounts', 'tasks_messages']
        await gather(*[coroutine(self) for coroutine in create_methods_list if coroutine.__name__[7:-6] in main_tables_list])
        await gather(*[coroutine(self) for coroutine in create_methods_list if not coroutine.__name__[7:-6] in main_tables_list])


    async def _set_initial_values(self):
        """Установка начальных значения, которые сейчас есть"""
        initial_value_methods_list: list[Callable] = self._get_initial_value_methods()
        await gather(*[coroutine(self) for coroutine in initial_value_methods_list])

    @classmethod
    def _get_create_table_methods(cls) -> list[Callable]:
        return [method for name, method in inspect.getmembers(cls) if name.startswith('create')]

    @classmethod
    def _get_initial_value_methods(cls) -> list[Callable]:
        return [method for name, method in inspect.getmembers(cls) if name.startswith('initial')]

    @staticmethod
    async def _initial_main_connect():
        db = Database()
        await db.connect()

    async def create_users_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('users')"):
                await connection.execute('CREATE TABLE users('
                                         'unique_id SERIAL PRIMARY KEY,'
                                         'telegram_id BIGINT UNIQUE,'
                                         'telegram_name VARCHAR(45),'
                                         'balance REAL DEFAULT 0.0)')

    async def create_main_interface_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('main_interface')"):
                await connection.execute('CREATE TABLE main_interface('
                                         'telegram_id BIGINT,'
                                         'message_id BIGINT,'
                                         'time_message TIMESTAMP WITH TIME ZONE)')

    async def create_payments_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('payments')"):
                await connection.execute('CREATE TABLE payments('
                                         'transaction_id INT,'
                                         'telegram_id BIGINT,'
                                         'amount REAL,'
                                         'issued_by_STB REAL,'
                                         'payment_date TIMESTAMP WITH TIME ZONE DEFAULT (now()),'
                                         'token VARCHAR(12),'
                                         'payments_wallets_id INT)')

    async def create_payments_wallets_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('payments_wallets')"):
                await connection.execute('CREATE TABLE payments_wallets('
                                         'payments_wallets_id SERIAL PRIMARY KEY,'
                                         'telegram_id BIGINT,'
                                         'wallet_id INT,'
                                         'valid_until TIMESTAMP WITH TIME ZONE)')

    async def create_payments_tasks_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('payments_tasks')"):
                await connection.execute('CREATE TABLE payments_tasks('
                                         'unique_id SERIAL PRIMARY KEY,'
                                         'task_id INT,'
                                         'prices_id INT,'
                                         'date_of_pay TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_refund_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('refund')"):
                await connection.execute('CREATE TABLE refund('
                                         'refund_id INT,'
                                         'task_id INT,'
                                         'refund_amount REAL,'
                                         'date_of_refund TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_accounts_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('accounts')"):
                await connection.execute('CREATE TABLE accounts('
                                         'account_id SERIAL PRIMARY KEY,'
                                         'telegram_id BIGINT,'
                                         'account_name VARCHAR(35) UNIQUE,'
                                         'account_status VARCHAR(8) DEFAULT \'active\','
                                         'account_balance REAL DEFAULT 0.0,'
                                         'account_limits INT DEFAULT 0,'
                                         'deleted BOOLEAN DEFAULT False,'
                                         'adding_time TIMESTAMP WITH TIME ZONE DEFAULT (now()))')

    async def create_accounts_limits_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('accounts_limits')"):
                await connection.execute('CREATE TABLE accounts_limits('
                                         'account_id INT,'
                                         'subscriptions INT,'
                                         'likes INT,'
                                         'comments INT,'
                                         'retweets INT,'
                                         'FOREIGN KEY (account_id) REFERENCES accounts(account_id))')

    async def create_date_join_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('date_join')"):
                await connection.execute('CREATE TABLE date_join('
                                         'telegram_id BIGINT,'
                                         'date_join TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_referral_office_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('referral_office')"):
                await connection.execute('CREATE TABLE referral_office('
                                         'unique_id SERIAL PRIMARY KEY,'
                                         'telegram_id BIGINT,'
                                         'promocode VARCHAR(21),'
                                         'inviter INT,'
                                         'date_of_invitation DATE DEFAULT (now()),'
                                         'current_balance REAL DEFAULT 0.0)')

    async def create_user_notifications_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('user_notifications')"):
                await connection.execute('CREATE TABLE user_notifications('
                                         'unique_id SERIAL PRIMARY KEY,'
                                         'telegram_id BIGINT,'
                                         'all_notifications BOOLEAN DEFAULT False,'
                                         'notifications_flag BOOL DEFAULT False,'
                                         'subscriptions BOOLEAN DEFAULT False,'
                                         'likes BOOLEAN DEFAULT False,'
                                         'retweets BOOLEAN DEFAULT False,'
                                         'comments BOOLEAN DEFAULT False,'
                                         'date_of_update TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_reminder_steps_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('reminder_steps')"):
                await connection.execute('CREATE TABLE reminder_steps('
                                         'telegram_id BIGINT,'
                                         'countdown TIMESTAMP WITH TIME ZONE DEFAULT (now()),'
                                         'step_1 BOOL DEFAULT false,'
                                         'step_2 BOOL DEFAULT false,'
                                         'step_3 BOOL DEFAULT false,'
                                         'FOREIGN KEY (telegram_id) REFERENCES users(telegram_id),'
                                         'CONSTRAINT unique_telegram_id UNIQUE (telegram_id))')

    async def create_tasks_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('tasks')"):
                await connection.execute('CREATE TABLE tasks('
                                         'task_id SERIAL PRIMARY KEY,'
                                         'telegram_id BIGINT,'
                                         'balance_task REAL,'
                                         'price REAL,'
                                         'executions INT,'
                                         'status VARCHAR(25) DEFAULT \'waiting_start\','
                                         'round INT DEFAULT NULL,'
                                         'deleted_history BOOLEAN DEFAULT False,'
                                         'date_of_creation TIMESTAMP WITH TIME ZONE DEFAULT (now()),'
                                         'date_of_check TIMESTAMP WITH TIME ZONE DEFAULT (now()),'
                                         'date_of_last_update TIMESTAMP WITH TIME ZONE DEFAULT (now()),'
                                         'date_of_completed TIMESTAMP WITH TIME ZONE)')

    async def create_actions_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('actions')"):
                await connection.execute('CREATE TABLE actions('
                                         'unique_id SERIAL PRIMARY KEY,'
                                         'task_id INT,'
                                         'type_task VARCHAR(15),'
                                         'link_action VARCHAR(250),'
                                         'parameter_id INT,'
                                         'FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE)')

    async def create_parameters_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('parameters')"):
                await connection.execute('CREATE TABLE parameters('
                                         'parameter_id SERIAL PRIMARY KEY,'
                                         'words_count INT,'
                                         'tags_count INT,'
                                         'words_tags VARCHAR(250),'
                                         'note VARCHAR(260),'
                                         'english bool DEFAULT False)')

    async def create_tasks_messages_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('tasks_messages')"):
                await connection.execute('CREATE TABLE tasks_messages('
                                         'tasks_msg_id SERIAL PRIMARY KEY,'
                                         'telegram_id BIGINT,'
                                         'message_id INT,'
                                         'task_id INT,'
                                         'account_id INT,'
                                         'available_accounts INT,'
                                         'status VARCHAR(35))')

    async def create_statistics_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('statistics')"):
                await connection.execute('CREATE TABLE statistics('
                                         'tasks_msg_id INT,'
                                         'offer_time TIMESTAMP WITH TIME ZONE,'
                                         'offer_time_more TIMESTAMP WITH TIME ZONE,'
                                         'start_time TIMESTAMP WITH TIME ZONE,'
                                         'perform_time TIMESTAMP WITH TIME ZONE,'
                                         'failure_key INT,'
                                         'finish_time TIMESTAMP WITH TIME ZONE,'
                                         'deleted_time TIMESTAMP WITH TIME ZONE,'
                                         'reminder BOOL DEFAULT FALSE,'
                                         'FOREIGN KEY (tasks_msg_id) REFERENCES tasks_messages(tasks_msg_id) ON DELETE CASCADE)')

    async def create_failure_statistics_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('failure_statistics')"):
                await connection.execute('CREATE TABLE failure_statistics('
                                         'failure_key SERIAL PRIMARY KEY,'
                                         'tasks_msg_id INT,'
                                         'perform_time_subscriptions TIMESTAMP WITH TIME ZONE,'
                                         'perform_time_like TIMESTAMP WITH TIME ZONE,'
                                         'perform_time_retweet TIMESTAMP WITH TIME ZONE,'
                                         'waiting_link_time TIMESTAMP WITH TIME ZONE,'
                                         'perform_time_comment TIMESTAMP WITH TIME ZONE,'
                                         'FOREIGN KEY (tasks_msg_id) REFERENCES tasks_messages(tasks_msg_id) ON DELETE CASCADE)')

    async def create_completed_tasks_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('completed_tasks')"):
                await connection.execute('CREATE TABLE completed_tasks('
                                         'unique_id SERIAL PRIMARY KEY,'
                                         'telegram_id BIGINT,'
                                         'task_id INT,'
                                         'account_id INT,'
                                         'tasks_msg_id INT,'
                                         'final_reward REAL,'
                                         'date_of_completion TIMESTAMP WITH TIME ZONE DEFAULT (now()))')

    async def create_reviews_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('reviews')"):
                await connection.execute('CREATE TABLE reviews('
                                         'telegram_id BIGINT,'
                                         'offered_reviews BOOL DEFAULT False)')

    async def create_prices_actions_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('prices_actions')"):
                await connection.execute('CREATE TABLE prices_actions('
                                         'prices_id SERIAL PRIMARY KEY,'
                                         'subscriptions REAL,'
                                         'likes REAL,'
                                         'retweets REAL,'
                                         'comments REAL,'
                                         'commission REAL,'
                                         'date_added TIMESTAMP WITH TIME ZONE DEFAULT (now()))')

    async def create_is_banned_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('is_banned')"):
                await connection.execute('CREATE TABLE is_banned('
                                         'telegram_id BIGINT UNIQUE,'
                                         'reason VARCHAR(120),'
                                         'date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),'
                                         'comment VARCHAR(250))')

    async def create_they_banned_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('they_banned')"):
                await connection.execute('CREATE TABLE they_banned('
                                         'telegram_id BIGINT UNIQUE,'
                                         'ban_status BOOL DEFAULT False,'
                                         'counter INT DEFAULT 1,'
                                         'last_message TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_tasks_distribution_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('tasks_distribution')"):
                await connection.execute('CREATE TABLE tasks_distribution('
                                         'telegram_id BIGINT,'
                                         'priority INT CHECK (priority >= 1 AND priority <= 100),'
                                         'level VARCHAR(35),'
                                         'top_priority_flag BOOL DEFAULT False,'
                                         'date_of_last_check TIMESTAMP WITH TIME ZONE DEFAULT NOW(),'
                                         'date_update_level TIMESTAMP WITH TIME ZONE DEFAULT NOW(),'
                                         'circular_round INT DEFAULT 1,'
                                         'task_sent_today INT)')

    async def create_fines_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('fines')"):
                await connection.execute('CREATE TABLE fines('
                                         'fines_id SERIAL PRIMARY KEY,'
                                         'telegram_id BIGINT,'
                                         'fines_type VARCHAR(30),'
                                         'tasks_msg_id INT,'
                                         'date_added TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_temporary_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('temporary')"):
                await connection.execute('CREATE TABLE temporary('
                                         'fines_id INT,'
                                         'valid_until TIMESTAMP WITH TIME ZONE,'
                                         'reduction_in_priority INT,'
                                         'FOREIGN KEY (fines_id) REFERENCES fines(fines_id) ON DELETE CASCADE)')

    async def create_often_deleted_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('often_deleted')"):
                await connection.execute('CREATE TABLE often_deleted('
                                         'fines_id INT,'
                                         'task_id INT,'
                                         'number_awards REAL,'
                                         'FOREIGN KEY (fines_id) REFERENCES fines(fines_id) ON DELETE CASCADE)')

    async def create_bought_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('bought')"):
                await connection.execute('CREATE TABLE bought('
                                         'fines_id INT,'
                                         'remaining_to_redeem REAL,'
                                         'already_bought REAL DEFAULT 0.0,'
                                         'awards_cut INT,'
                                         'victim_user INT,'
                                         'collection_flag BOOL DEFAULT False,'
                                         'date_of_send TIMESTAMP WITH TIME ZONE,'
                                         'send_id INT,'
                                         'FOREIGN KEY (fines_id) REFERENCES fines(fines_id) ON DELETE CASCADE)')

    async def create_accounts_fines_slise_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('accounts_fines_slise')"):
                await connection.execute('CREATE TABLE accounts_fines_slise('
                                         'unique_id SERIAL PRIMARY KEY,'
                                         'fines_id INT,'
                                         'account_id INT)')

    async def create_fines_taken_from_accounts_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('fines_taken_from_accounts')"):
                await connection.execute('CREATE TABLE fines_taken_from_accounts('
                                         'unique_id SERIAL PRIMARY KEY,'
                                         'telegram_id BIGINT,'
                                         'taken_fines_id INT,'
                                         'received_fines_id INT,'
                                         'account_id INT)')

    async def create_limits_tasks_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('limits_tasks')"):
                await connection.execute('CREATE TABLE limits_tasks('
                                         'limits_id SERIAL PRIMARY KEY,'
                                         'vacationers INT,'
                                         'prelim INT,'
                                         'main INT,'
                                         'challenger INT,'
                                         'champion INT,'
                                         'date_of_added TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_limits_execution_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('limits_execution')"):
                await connection.execute('CREATE TABLE limits_execution('
                                         'limits_ex_id SERIAL PRIMARY KEY,'
                                         'beginner INT,'
                                         'vacationers INT,'
                                         'prelim INT,'
                                         'main INT,'
                                         'challenger INT,'
                                         'champion INT,'
                                         'date_of_added TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_limits_priority_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('limits_priority')"):
                await connection.execute('CREATE TABLE limits_priority('
                                         'limits_priority_id SERIAL PRIMARY KEY,'
                                         'vacationers INT,'
                                         'prelim INT,'
                                         'main INT,'
                                         'challenger INT,'
                                         'champion INT,'
                                         'date_of_added TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_limits_accounts_execution_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('limits_accounts_execution')"):
                await connection.execute('CREATE TABLE limits_accounts_execution('
                                         'limits_accounts_execution_id SERIAL PRIMARY KEY,'
                                         'subscriptions INT,'
                                         'likes INT,'
                                         'comments INT,'
                                         'retweets INT,'
                                         'date_of_added TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_tasks_refusals_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('tasks_refusals')"):
                await connection.execute('CREATE TABLE tasks_refusals('
                                         'refusals_id SERIAL PRIMARY KEY,'
                                         'task_id INT,'
                                         'tasks_msg_id INT,'
                                         'passed_after_start TIME,'
                                         'execution_stage INT,'
                                         'date_of_refusal TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_tasks_hiding_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('tasks_hiding')"):
                await connection.execute('CREATE TABLE tasks_hiding('
                                         'hiding_id SERIAL PRIMARY KEY,'
                                         'task_id INT,'
                                         'tasks_msg_id INT,'
                                         'date_of_hiding TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_priority_change_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('priority_change')"):
                await connection.execute('CREATE TABLE priority_change('
                                         'priority_change_id SERIAL PRIMARY KEY,'
                                         'completing_task INT,'
                                         're_execution INT,'
                                         'max_re_execution INT,'
                                         'complete_others INT,'
                                         'downtime_more_20_min INT,'
                                         'ignore_more_20_min INT,'
                                         'ignore_more_40_min INT,'
                                         'ignore_more_60_min INT,'
                                         'refuse INT,'
                                         'refuse_late INT,'
                                         'scored_on_task INT,'
                                         'ignore_many_times INT,'
                                         'hidden_many_times INT,'
                                         'refuse_many_times INT,'
                                         'scored_many_times INT,'
                                         'date_of_added TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_number_of_completed_tasks_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('number_of_completed_tasks')"):
                await connection.execute('CREATE TABLE number_of_completed_tasks('
                                         'unique_id SERIAL PRIMARY KEY,'
                                         'prelim INT,'
                                         'main INT,'
                                         'challenger INT,'
                                         'champion INT,'
                                         'date_of_added TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_number_of_accounts_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('number_of_accounts')"):
                await connection.execute('CREATE TABLE number_of_accounts('
                                         'unique_id SERIAL PRIMARY KEY,'
                                         'prelim INT,'
                                         'main INT,'
                                         'challenger INT,'
                                         'champion INT,'
                                         'date_of_added TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_level_loss_conditions_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('level_loss_conditions')"):
                await connection.execute('CREATE TABLE level_loss_conditions('
                                         'unique_id SERIAL PRIMARY KEY,'
                                         'prelim INT,'
                                         'main INT,'
                                         'challenger INT,'
                                         'champion INT,'
                                         'date_of_added TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_awards_cut_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('awards_cut')"):
                await connection.execute('CREATE TABLE awards_cut('
                                         'awards_cut_id SERIAL PRIMARY KEY,'
                                         'first_fine INT,'
                                         'subsequent_fines INT,'
                                         'date_of_added TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_rating_fines_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('rating_fines')"):
                await connection.execute('CREATE TABLE rating_fines('
                                         'rating_fines_id SERIAL PRIMARY KEY,'
                                         'sum_fines INT,'
                                         'date_of_added TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_task_delete_fines_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('task_delete_fines')"):
                await connection.execute('CREATE TABLE task_delete_fines('
                                         'task_delete_fines_id SERIAL PRIMARY KEY,'
                                         'percent_fines INT,'
                                         'date_of_added TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_cost_stb_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('cost_stb')"):
                await connection.execute('CREATE TABLE cost_stb('
                                         'cost_id SERIAL PRIMARY KEY,'
                                         'cost_to_dollar REAL,'
                                         'date_of_added TIMESTAMP WITH TIME ZONE DEFAULT NOW());')

    async def create_account_requirements_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('account_requirements')"):
                await connection.execute('CREATE TABLE account_requirements('
                                         'requirement_id SERIAL PRIMARY KEY,'
                                         'min_followers INT,'
                                         'min_following INT,'
                                         'min_creation_date DATE,'
                                         'date_of_added TIMESTAMP WITH TIME ZONE DEFAULT NOW());')

    async def create_admins_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('admins')"):
                await connection.execute('CREATE TABLE admins('
                                         'telegram_id BIGINT,'
                                         'telegram_name VARCHAR(40),'
                                         'admin_balance REAL DEFAULT 0.0,'
                                         'main_recipient_flag BOOL DEFAULT False,'
                                         'date_of_adding TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_supports_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('supports')"):
                await connection.execute('CREATE TABLE supports('
                                         'telegram_id BIGINT,'
                                         'telegram_name VARCHAR(40),'
                                         'active_status BOOL DEFAULT False,'
                                         'support_balance REAL DEFAULT 0.0,'
                                         'main_support_flag BOOL DEFAULT False,'
                                         'date_of_adding TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_support_alert_over_refusal_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('support_alert_over_refusal')"):
                await connection.execute('CREATE TABLE support_alert_over_refusal('
                                         'telegram_id BIGINT,'
                                         'task_id INT,'
                                         'date_of_alert TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_task_completion_check_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('task_completion_check')"):
                await connection.execute('CREATE TABLE task_completion_check('
                                         'check_id SERIAL PRIMARY KEY,'
                                         'tasks_msg_id INT,'
                                         'stage_1 BOOL DEFAULT NULL,'
                                         'stage_2 BOOL DEFAULT NULL,'
                                         'stage_3 BOOL DEFAULT NULL,'
                                         'stage_4 BOOL DEFAULT NULL,'
                                         'last_checking TIMESTAMP WITH TIME ZONE DEFAULT NOW(),'
                                         'do_not_check_flag BOOL DEFAULT False)')

    async def create_task_check_deadlines_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('task_check_deadlines')"):
                await connection.execute('CREATE TABLE task_check_deadlines('
                                         'deadline_id SERIAL PRIMARY KEY,'
                                         'stage_1 INT,'
                                         'stage_2 INT,'
                                         'stage_3 INT,'
                                         'stage_4 INT,'
                                         'date_of_adding TIMESTAMP WITH TIME ZONE DEFAULT NULL)')

    async def create_admins_receipts_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('admins_receipts')"):
                await connection.execute('CREATE TABLE admins_receipts('
                                         'receipt_id SERIAL PRIMARY KEY,'
                                         'sum_receipt REAL,'
                                         'type_receipt VARCHAR(35),'
                                         'id_receipt INT,'
                                         'date_of_receipt TIMESTAMP WITH TIME ZONE DEFAULT NOW())')

    async def create_task_check_materials_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('task_check_materials')"):
                await connection.execute('CREATE TABLE task_check_materials('
                                         'materials_id SERIAL PRIMARY KEY,'
                                         'tasks_msg_id INT,'
                                         'comment_id BIGINT,'
                                         'author_materials_id INT,'
                                         'worker_materials_id INT)')

    async def create_author_materials_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('author_materials')"):
                await connection.execute('CREATE TABLE author_materials('
                                         'author_materials_id SERIAL PRIMARY KEY,'
                                         'upper_cut VARCHAR(45)[],'
                                         'lower_cut VARCHAR(45)[])')

    async def create_worker_materials_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('worker_materials')"):
                await connection.execute('CREATE TABLE worker_materials('
                                         'worker_materials_id SERIAL PRIMARY KEY,'
                                         'upper_cut VARCHAR(45)[],'
                                         'lower_cut VARCHAR(45)[])')

    async def create_task_author_check_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('task_author_check')"):
                await connection.execute('CREATE TABLE task_author_check('
                                         'task_id INT,'
                                         'last_check TIMESTAMP WITH TIME ZONE DEFAULT NOW(),'
                                         'do_not_check_flag BOOL DEFAULT False)')

    async def create_refills_referral_office_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('refills_referral_office')"):
                await connection.execute('CREATE TABLE refills_referral_office('
                                         'unique_id SERIAL PRIMARY KEY,'
                                         'telegram_id BIGINT,'
                                         'telegram_id_earner INT,'
                                         'earned_amount REAL,'
                                         'date_of_refill TIMESTAMP WITH TIME ZONE DEFAULT NOW());')

    async def create_withdraws_referral_office_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('withdraws_referral_office')"):
                await connection.execute('CREATE TABLE withdraws_referral_office('
                                         'unique_id SERIAL PRIMARY KEY,'
                                         'telegram_id BIGINT,'
                                         'withdraw_amount REAL,'
                                         'date_of_withdraw TIMESTAMP WITH TIME ZONE DEFAULT NOW());')

    async def create_refills_account_balance_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('refills_account_balance')"):
                await connection.execute('CREATE TABLE refills_account_balance('
                                         'unique_id SERIAL PRIMARY KEY,'
                                         'telegram_id BIGINT,'
                                         'account_id INT,'
                                         'earned_amount REAL,'
                                         'date_of_refills TIMESTAMP WITH TIME ZONE DEFAULT NOW());')

    async def create_withdraws_account_balance_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('withdraws_account_balance')"):
                await connection.execute('CREATE TABLE withdraws_account_balance('
                                         'unique_id SERIAL PRIMARY KEY,'
                                         'telegram_id BIGINT,'
                                         'account_id INT,'
                                         'withdraw_amount REAL,'
                                         'date_of_withdraw TIMESTAMP WITH TIME ZONE DEFAULT NOW());')

    async def create_payment_fines_table(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval("SELECT to_regclass('payment_fines')"):
                await connection.execute('CREATE TABLE payment_fines('
                                         'unique_id SERIAL PRIMARY KEY,'
                                         'telegram_id BIGINT,'
                                         'fines_id INT,'
                                         'payment_amount REAL,'
                                         'date_of_payment TIMESTAMP WITH TIME ZONE DEFAULT NOW());')

    async def initial_prices_actions_values(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval('SELECT EXISTS (SELECT 1 FROM prices_actions)'):
                await connection.execute('INSERT INTO prices_actions('
                                         'subscriptions,'
                                         'likes,'
                                         'retweets,'
                                         'comments,'
                                         'commission)'
                                         'VALUES (3, 1, 1, 3, 3)')

    async def initial_limits_tasks_values(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval('SELECT EXISTS (SELECT 1 FROM limits_tasks)'):
                await connection.execute('INSERT INTO limits_tasks('
                                         'vacationers,'
                                         'prelim,'
                                         'main,'
                                         'challenger,'
                                         'champion)'
                                         'VALUES (3, 5, 10, 13, 15)')

    async def initial_limits_execution_values(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval('SELECT EXISTS (SELECT 1 FROM limits_execution)'):
                await connection.execute('INSERT INTO limits_execution('
                                         'beginner,'
                                         'vacationers,'
                                         'prelim, main,'
                                         'challenger,'
                                         'champion)'
                                         'VALUES (3, 3, 5, 8, 10, 15)')

    async def initial_limits_priority_values(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval('SELECT EXISTS (SELECT 1 FROM limits_priority)'):
                await connection.execute('INSERT INTO limits_priority('
                                         'vacationers,'
                                         'prelim,'
                                         'main,'
                                         'challenger,'
                                         'champion)'
                                         'VALUES (10, 35, 70, 90, 100)')

    async def initial_limits_accounts_execution_values(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval('SELECT EXISTS (SELECT 1 FROM limits_accounts_execution)'):
                await connection.execute("INSERT INTO limits_accounts_execution"
                                         "(subscriptions, "
                                         "likes, "
                                         "comments, "
                                         "retweets) "
                                         "VALUES (40, 40, 40, 40)")

    async def initial_priority_change_values(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval('SELECT EXISTS (SELECT 1 FROM priority_change)'):
                await connection.execute('INSERT INTO priority_change('
                                         'completing_task,'
                                         're_execution,'
                                         'max_re_execution,'
                                         'complete_others,'
                                         'downtime_more_20_min,'
                                         'ignore_more_20_min,'
                                         'ignore_more_40_min,'
                                         'ignore_more_60_min,'
                                         'refuse,'
                                         'refuse_late,'
                                         'scored_on_task,'
                                         'ignore_many_times,'
                                         'hidden_many_times,'
                                         'refuse_many_times,'
                                         'scored_many_times) '
                                         'VALUES (5, 1, 3, 6, 2, -1, -3, -4, -1, -6, -10, -5, -7, -6, -20)')

    async def initial_number_of_completed_tasks_values(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval('SELECT EXISTS (SELECT 1 FROM number_of_completed_tasks)'):
                await connection.execute('INSERT INTO number_of_completed_tasks('
                                         'prelim,'
                                         'main,'
                                         'challenger,'
                                         'champion) '
                                         'VALUES (3, 10, 20, 30)')

    async def initial_number_of_accounts_values(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval('SELECT EXISTS (SELECT 1 FROM number_of_accounts)'):
                await connection.execute('INSERT INTO number_of_accounts('
                                         'prelim,'
                                         'main,'
                                         'challenger,'
                                         'champion) '
                                         'VALUES (1, 1, 3, 5)')

    async def initial_cost_stb_values(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval('SELECT EXISTS (SELECT 1 FROM cost_stb)'):
                await connection.execute('INSERT INTO cost_stb('
                                         'cost_to_dollar)'
                                         'VALUES (1);')

    async def initial_account_requirements_values(self):
        async with (self.pool.acquire() as connection):
            if not await connection.fetchval('SELECT EXISTS (SELECT 1 FROM account_requirements)'):
                await connection.execute('INSERT INTO account_requirements('
                                         'min_followers,'
                                         'min_following,'
                                         'min_creation_date) '
                                         'VALUES (1, 1, NOW());')

    async def initial_level_loss_conditions_values(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval('SELECT EXISTS (SELECT 1 FROM level_loss_conditions)'):
                await connection.execute('INSERT INTO level_loss_conditions('
                                         'prelim,'
                                         'main,'
                                         'challenger,'
                                         'champion) '
                                         'VALUES (6, 5, 4, 3)')

    async def initial_awards_cut_values(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval('SELECT EXISTS (SELECT 1 FROM awards_cut)'):
                await connection.execute('INSERT INTO awards_cut('
                                         'first_fine,'
                                         'subsequent_fines) '
                                         'VALUES (30, 100)')

    async def initial_rating_fines_values(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval('SELECT EXISTS (SELECT 1 FROM rating_fines)'):
                await connection.execute('INSERT INTO rating_fines('
                                         'sum_fines) '
                                         'VALUES (-10)')

    async def initial_task_delete_fines_values(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval('SELECT EXISTS (SELECT 1 FROM task_delete_fines)'):
                await connection.execute('INSERT INTO task_delete_fines('
                                         'percent_fines) '
                                         'VALUES (30)')

    async def initial_task_check_deadlines_values(self):
        async with self.pool.acquire() as connection:
            if not await connection.fetchval('SELECT EXISTS (SELECT 1 FROM task_check_deadlines)'):
                await connection.execute('INSERT INTO task_check_deadlines('
                                         'stage_1,'
                                         'stage_2,'
                                         'stage_3,'
                                         'stage_4) '
                                         'VALUES (1, 8, 48, 168)')
