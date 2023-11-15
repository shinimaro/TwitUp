import asyncio
import datetime
import math
import random
import time
from typing import TypedDict, NoReturn
from asyncio import sleep
from bot_apps.task_push.system.sending_tasks.selection_of_workers import book_workers, WorkersDict, \
    find_total_executions, find_completion_rate
from bot_apps.task_push.system.sending_tasks.sending_tasks import sending_task
from databases.database import db
from typing import TypeAlias, Callable

class TasksDict(TypedDict):
    executions: int
    passed_after_creation: datetime.timedelta
    passed_after_check: datetime.timedelta
    completed_tasks: int
    in_process: int


class SelectedDict(TypedDict):
    executions: int
    total_executions: int
    passed_after_creation: datetime.timedelta

Seconds: TypeAlias = int

# Фанкшин, проводящий добивку небольших заданий, если они плохо или долго выполняются
async def completing_completion():
    tasks_dict: dict[int, TasksDict] = await db.get_active_tasks()
    selected_tasks_dict: dict[int, SelectedDict] = await _select_stuck_tasks(tasks_dict)
    # Если были найдены отстающие по выполнениям таски
    if selected_tasks_dict:
        # Делаем словарь для подсчёта выполнения каждого таска
        finally_dict: dict[int, int] = _calculate_execution(selected_tasks_dict)
        # Отбор воркеров для каждого таска
        finally_selected_workers = await _select_workers(finally_dict)
        # Отправляем это всё воркерам
        await _finish_sending_tasks(finally_selected_workers)


# Отбор тасков, которые за бок совали
async def _select_stuck_tasks(tasks_dict: dict[int, TasksDict]) -> dict[int, SelectedDict]:
    # Ориентир на выполнения - час = 90% выполнений готовы
    selected_tasks_dict = {}
    completion_rate = await find_completion_rate()
    for task in tasks_dict:
        # Ищем процент выполнений
        total_executions = find_total_executions(tasks_dict[task]['completed_tasks'], tasks_dict[task]['in_process'], completion_rate)
        completion_percentage = total_executions * (tasks_dict[task]['executions'] / 100)
        # Если таск не добивает по показателям, или, как в самом конце, таск уже делается овер долго
        if completion_percentage <= 5 \
                or (tasks_dict[task]['passed_after_creation'].total_seconds() >= 20 * 60 and completion_percentage <= 20) \
                or (tasks_dict[task]['passed_after_creation'].total_seconds() >= 40 * 60 and completion_percentage <= 30) \
                or (tasks_dict[task]['passed_after_creation'].total_seconds() >= 60 * 60 and completion_percentage <= 50) \
                or tasks_dict[task]['passed_after_check'].total_seconds() >= 20 * 60 and tasks_dict[task]['passed_after_creation'].total_seconds() >= 80 * 60:
            selected_tasks_dict[task] = {'executions': tasks_dict[task]['executions'], 'total_executions': total_executions, 'passed_after_creation': tasks_dict[task]['passed_after_creation']}
    await db.update_check_time([selected_tasks_dict.keys()])  # Обновление времени последнего чека у отобранных тасков
    return selected_tasks_dict


# Простая функция для вычесления кол-ва тех, кто пойдёт добивать таск
def _calculate_execution(selected_tasks_dict: dict[int, SelectedDict]) -> dict[int, int]:
    finally_dict = {}
    for task in selected_tasks_dict:
        # Находим конкретно в воркерах, сколько их надо, в зависимости от выполнений
        need_executions = selected_tasks_dict[task]['executions'] - selected_tasks_dict[task]['total_executions']
        # Находим коэффициент понижение, в зависимости от того, как мало времени прошло (до 30 минут)
        reduction_coefficient = selected_tasks_dict[task]['passed_after_creation'].total_seconds() / 60 * (1 / 30) if \
            selected_tasks_dict[task]['passed_after_creation'].total_seconds() / 60 <= 30 else 1
        count_workers = math.ceil(need_executions * reduction_coefficient)
        finally_dict[task] = count_workers
    return finally_dict


async def _select_workers(finally_dict: dict[int, int]):
    finally_selected_workers = {}
    for task_id in finally_dict:
        finally_selected_workers.setdefault(task_id, {})
        # Собираем воркерсов для таска
        workers_dict: dict[int, WorkersDict] = await db.get_all_workers(task_id)
        # workers_dict = {
        #     1001: {'priority': 60, 'available_accounts': 15},
        #     1002: {'priority': 70, 'available_accounts': 15},
        #     1003: {'priority': 80, 'available_accounts': 15},
        #     1004: {'priority': 90, 'available_accounts': 15},
        #     1005: {'priority': 100, 'available_accounts': 15},
        #     1006: {'priority': 50, 'available_accounts': 15},
        #     1007: {'priority': 40, 'available_accounts': 15},
        #     1008: {'priority': 30, 'available_accounts': 15},
        #     1009: {'priority': 20, 'available_accounts': 15},
        #     1010: {'priority': 10, 'available_accounts': 15}}

        selected_workers: list[int] = []
        for _ in range(finally_dict[task_id]):
            workers_list = list(workers_dict.keys())
            priority_list = [entry['priority'] for entry in workers_dict.values()]
            for _ in range(10):
                try:
                    worker = random.choices(workers_list, weights=priority_list)[0]
                except IndexError:
                    break
                if worker not in selected_workers:
                    selected_workers.append(worker)
                    finally_selected_workers[task_id][worker] = random.randint(1, workers_dict[worker]['available_accounts'])
            else:
                # Почистить словарь
                for selected_worker in selected_workers:
                    if selected_worker in workers_dict:
                        workers_dict.pop(selected_worker)
            if not workers_dict:
                break
        return finally_selected_workers


# Функция для финальной отправки тасков
async def _finish_sending_tasks(finally_selected_workers):
    for task in finally_selected_workers:
        await book_workers(finally_selected_workers[task])
        await sending_task(task, finally_selected_workers[task])

# Класс для сна сторожа
class WaitingTasks:

    def __init__(self, normal_sleep_time: Seconds, more_sleep_time: Seconds):
        self.normal_sleep_time = normal_sleep_time
        self.more_sleep_time = more_sleep_time
        # self.lock = asyncio.Lock
        self.lock_flag = False
        self.start_time = time.time()

    async def __call__(self):
        is_active: bool = await db.check_active_tasks() if not self.lock_flag else True
        # Если not флаг и нет активных заданий, то спим много
        if not self.lock_flag and not is_active:
            await sleep(self.more_sleep_time)
        else:
            # Если же нет, то спим по обычному
            await sleep(self.normal_sleep_time)
            # Если флаг true, то проверяем, прошло ли 5 минут и, если да, запустим новую проверку
            if self.lock_flag and time.time() - self.start_time >= 5 * 60:
                self.lock_flag = False
            # Если флаг не равен true, то проверяем, есть ли актив и, если да, запускаем таймер по-новой
            elif not self.lock_flag and is_active:
                self.lock_flag = True
                self.start_time = time.time()




async def completing_completion_checker() -> NoReturn:
    waiting_tasks = WaitingTasks(3 * 60, 20 * 60)
    while True:
        await waiting_tasks()
        await completing_completion()


asyncio.run(completing_completion_checker())