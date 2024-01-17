import asyncio
import math
import random
from asyncio import sleep, gather
from typing import NoReturn

from aiogram import Bot

from bot_apps.bot_parts.panels.admin_panel.notification import send_notification_to_admin
from bot_apps.bot_parts.task_push.task_push_keyboards import close_kebyoard_builder
from bot_apps.other_apps.filters.limits_filters.message_limit_filter import MessageFilter
from bot_apps.other_apps.wordbank import notifications_to_admin, notifications
from config import load_config
from databases.database import Database
from databases.dataclasses_storage import AuthorTaskInfo
from parsing.main_checkings.re_checking_executions.start_re_checking import StartReChecking
from parsing.manage_webdrivers.master_function import Master
from parsing.other_parsing.check_author_links import check_author_links, CheckAuthorLinks

config = load_config()
db = Database()
message_filter = MessageFilter()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")


class ReCheckExecution:

    def __init__(self):
        self.authors_tasks_list: list[AuthorTaskInfo] = []
        self.tasks_ids_list = []
        self.tasks = []
        self.all_tasks_dict: dict[int, int] = {}
        self.check_queue: dict[int, int] = {}

    async def start_re_check_of_execution(self) -> None:
        """Строж, находящий задания, выполнение которых необходимо перепроверить"""
        await self._checking_all_authors_tasks()
        await self._checking_executions_tasks()
        # Функция для обновления времени последней перепроверки

    async def _checking_all_authors_tasks(self) -> None:
        """Проверка всех тасков авторов на жизнь"""
        await self._initial_author_tasks_list()
        while self.authors_tasks_list:
            self._select_author_tasks()
            await gather(*self.tasks)
            await self._update_last_check_on_author_tasks()

    async def _initial_author_tasks_list(self) -> None:
        """Найти все таски авторов, которые пора перепроверять"""
        self.authors_tasks_list = await db.get_all_authors_tasks()

    def _select_author_tasks(self) -> None:
        """Взять новую пачку заданий по перепроверке ссылок авторов"""
        for task_index in range(min(self._get_max_webdrivers(), len(self.authors_tasks_list))):
            self.tasks_ids_list.append(self.authors_tasks_list[task_index])
            self.tasks.extend([self._check_author_task_on_life(self.authors_tasks_list[task_index])])
        # Удаление элементов после завершения итерации
        self.authors_tasks_list = self.authors_tasks_list[self._get_max_webdrivers():]

    async def _update_last_check_on_author_tasks(self) -> None:
        """Обновить время последней перепроверки на тасках"""
        await db.update_check_author_links_time([task.task_id for task in self.tasks_ids_list])

    @staticmethod
    async def _check_author_task_on_life(task_info: AuthorTaskInfo) -> None:
        """Проверка ссылок, указанные в задании на жизнь"""
        check_dict: CheckAuthorLinks = {'profile': True, 'post': True}
        await check_author_links(check_dict, task_info.links)
        if not check_dict['post']:
            # Флаг на задание, флаг на табличку с проверялкой самого задания
            await db.not_checking_task_flag(task_info.task_id)
        if not check_dict['profile']:
            # Флаг на задание все связанные с этой ссылкой и в табличке на проверялку do_not_check_flag
            await db.not_checking_task_flag(task_info.task_id)
            await db.not_checking_by_link(task_info.links.account_link)

    async def _checking_executions_tasks(self) -> None:
        """Фанкшнин для запуска перепроверок выполнений тасков"""
        self.all_tasks_dict = await db.get_all_task_with_need_checking()
        while self.all_tasks_dict:
            self._select_tasks_messages()
            await gather(*self.tasks)
            self.check_queue.clear()

    def _select_tasks_messages(self):
        self._selected_tasks_msg_ids()
        self.tasks = [self._re_check_of_execution_main(tasks_msg_id, task_stage)
                      for tasks_msg_id, task_stage in self.check_queue.items()]

    def _selected_tasks_msg_ids(self) -> None:
        """Отбирает id в итоговый словарь по стадиям в процентном соотношении"""
        max_values_in_dict = self._get_values_for_rounds()
        for stage in range(1, 5):
            for task_id, task_stage in self.all_tasks_dict.items():
                if len(self.check_queue) > max_values_in_dict[stage]:
                    break
                elif task_stage == stage:
                    self.check_queue[task_id] = task_stage
        # Убрать лишние ключи
        self.all_tasks_dict = {key: value for key, value in self.all_tasks_dict.items() if key not in set(self.check_queue)}

    def _get_values_for_rounds(self) -> dict[int, float]:
        """Получить макс длину итогового словаря для каждого раунда"""
        available_webdrivers = self._get_max_webdrivers()
        return {1: available_webdrivers * 0.5,
                2: available_webdrivers * 0.75,
                3: available_webdrivers * 0.90,
                4: available_webdrivers * 1}

    @staticmethod
    def _get_max_webdrivers() -> int:
        """Дать максимальное число вебдрайверов, доступное для перепроверки задания"""
        return math.ceil(config.webdrivers.num_webdrivers * 0.5)

    async def _re_check_of_execution_main(self, tasks_msg_id: int, task_stage: int) -> None:
        """Основная функция для перепроверки выполнения задания"""
        re_checking = StartReChecking(tasks_msg_id)
        result = await re_checking.start_re_checking()
        if result:
            await db.change_re_check_stage(tasks_msg_id, task_stage)
        else:
            await self._fine_the_user(tasks_msg_id, task_stage)

    async def _fine_the_user(self, tasks_msg_id: int, task_stage) -> None:
        """Выдать штраф юзеру лично в руки"""
        await db.change_re_check_stage(tasks_msg_id, task_stage, check_flag=False)  # Записываем, что последняя проверка была провалена
        await db.collect_stb_from_user(tasks_msg_id)  # Оформляем штраф и забираем STB, сколько можем
        await self._notification_on_fines(tasks_msg_id)  # Отправляем уведомление об этом юзеру

    async def _notification_on_fines(self, tasks_msg_id) -> None:
        """Оповещение юзера о том, что ему пришёл штраф"""
        tg_id = await db.get_telegram_id_from_tasks_messages(tasks_msg_id)
        await message_filter(user_id=tg_id)
        # Оповещающение юзера о штрафе
        await bot.send_message(
            chat_id=tg_id,
            text=await self._notification_text_builder(tasks_msg_id),
            reply_markup=close_kebyoard_builder())

    @staticmethod
    async def _notification_text_builder(tasks_msg_id) -> str:
        """Билдер текста о том, что юзеру пришёл штраф"""
        fines_info = await db.get_bought_fines_info(tasks_msg_id)
        return notifications['collect_fines'].format(
            fines_info.sum_fines,
            notifications['cut_for_collect_fines'].format(
                fines_info.cut,
                fines_info.remaining_amount) if fines_info.cut_flag else '')

    async def re_check_checker(self) -> NoReturn:
        """Функция, вызывающая перепроверку заданий"""
        standart_sleep = 5 * 60
        while True:
            task = asyncio.get_event_loop().create_task(self.start_re_check_of_execution())
            await sleep(standart_sleep)
            while not task.done():
                await send_notification_to_admin(
                    notifications_to_admin['have_not_webdriwers'].format(len(self.all_tasks_dict)))
                await sleep(standart_sleep if not self.check_queue
                            else len(self.check_queue) * 5)
