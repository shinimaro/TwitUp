import asyncio
import math
import random
import statistics
from typing import TypedDict
from databases.database import db

lock = asyncio.Lock()


class WorkersDict(TypedDict):
    priority: int
    available_accounts: int


# Функция для отбора воркеров на небольшие задания (до 100 штук)
async def selection_of_workers(task_id):
    async with lock:
        # Находим опорное количество воркеров и минимально рекомендованное количество аккаунтов
        count_workers, min_number_accounts = await _easy_selection_of_workers(task_id, 120)

        # отбираем новичков, которым отдаём 30% от количества пользвателей, на которых распределим задания
        beginners_dict = await db.get_some_beginners()
        selected_beginners: dict[int, int] = _fill_beginner(beginners_dict, min_number_accounts, count_workers)

        # отбор всех воркеров, которые могут выполнить данный таск
        workers_dict: dict[int, WorkersDict] = await db.get_all_workers(task_id)
        selected_workers: list[int] = []

        # Если выполнений больше, чем доступных воркеров, забиваем по максимуму
        if count_workers > len(workers_dict):
            finally_dict = _max_distribute_accounts(selected_workers, workers_dict)
            return await _fynally_function(finally_dict, selected_beginners)

        # Распределяем воркеров
        for _ in range(count_workers):
            worker = _select_worker(selected_workers, workers_dict)
            selected_workers.append(worker)

        # Вычисляем, сколько аккаунтов у нас получилось в итоге
        accounts_count = sum(workers_dict[worker]['available_accounts'] for worker in selected_workers)

        # Если слишком мало у нас аккаунтов на воркеров получилось, то добавляем ещё
        if accounts_count <= min_number_accounts:
            result = _addition_of_recommended_values(min_number_accounts, accounts_count, workers_dict, selected_workers)
            # Если не получилось загрузить ещё аккаунтов, распределяем их по-максимуму и отправляем
            if not result:
                finally_dict = _max_distribute_accounts(selected_workers, workers_dict)
                return await _fynally_function(finally_dict, selected_beginners)
        # Если всё ок и теперь аккаунтов хватает, распределяем их по пользователям
        finally_dict = _distribute_accounts(selected_workers, workers_dict, min_number_accounts)
        return await _fynally_function(finally_dict, selected_beginners)


# Лёгкая функция по отбору воркеров, которвя просто выбирает чуть больше, чем нужно
async def _easy_selection_of_workers(task_id, max_increase) -> tuple[int, int]:
    executions = await db.get_amount_executions(task_id)
    increase = max_increase / 100 * executions
    count_workers = int(executions + increase)
    min_number_accounts = 2 * count_workers
    return count_workers, min_number_accounts


# Супер вычисления для поиска нужного количества воркеров и минимального кол-ва аккаунтов
async def _complex_calculations(task_id: int) -> tuple[int, int]:
    executions = await db.get_amount_executions(task_id)

    # Средний коэфициент выполнений одного задания одним юзером
    task_completion_rate = await _calculate_executions_rate()

    # Средний коэфициент принятия за (60) минут в ближайший час
    assignment_acceptance_rate = await _calculate_acceptance_rate(task_id)


    # Вычисляем среднее промежуточное количество воркеров
    intermediate_count_workers = math.ceil(executions / task_completion_rate * assignment_acceptance_rate)
    # Процент прибавки к этому числу
    floating_interest = intermediate_count_workers / 100 * (((executions - 5) / (100 - 5)) * 25)
    # Опорное количество воркеров
    count_workers = math.ceil(intermediate_count_workers + floating_interest)
    # Минимально рекомендованное количество аккаунтов
    min_number_accounts = math.ceil(count_workers * task_completion_rate)
    return count_workers, min_number_accounts


async def _calculate_acceptance_rate(task_id) -> float:
    acceptance_info = await db.get_sent_tasks(task_id)
    results = 0
    counts = 0
    for day in acceptance_info:
        finally_offers, finally_acceptances = 0, 0
        for tasks in acceptance_info[day]:
            finally_offers += acceptance_info[day][tasks]['quantity_submitted_tasks']
            finally_acceptances += acceptance_info[day][tasks]['quantity_accepted_tasks']
        results += finally_acceptances / finally_offers
        counts += 1
    return results / counts


async def _calculate_executions_rate() -> float:
    executions_info = await db.get_accepted_tasks()
    # Собираем средние значения в каждом задании
    values = []
    for task in executions_info:
        executions = 0
        users_counter = 0
        for user in executions_info[task]:
            executions += executions_info[task][user]
            users_counter += 1
        values.append(executions / users_counter)
    # Рассчитываем среднее и стандартное отклонение
    mean = statistics.mean(values)
    std_dev = statistics.stdev(values)
    # Определяем "слишком большое" и "слишком мелкое" значение
    threshold = 1.8 * std_dev
    # Отфильтровываем значения
    filtered_values = list(filter(lambda x: abs(x - mean) <= threshold, values))
    result = sum(filtered_values) / len(filtered_values)
    return result


def _fill_beginner(beginners_dict: dict[int, int], min_number_accounts: int, count_workers: int) -> dict[int, int]:
    selected_beginners: dict[int, int] = {}
    max_beginners = count_workers / 100 * 30
    for beginner in beginners_dict.keys():
        count_accounts = random.randint(1, beginners_dict[beginner])
        selected_beginners[beginner] = count_accounts
        min_number_accounts -= count_accounts
        count_workers -= 1
        max_beginners -= 1
        if max_beginners <= 0:
            return selected_beginners


# Максимальное распределение аккаунтов
def _max_distribute_accounts(selected_workers: list[int], workers_dict: dict[int, WorkersDict]) -> dict[int, int]:
    finally_dict: dict[int, int] = {}
    for worker in selected_workers:
        finally_dict[worker] = workers_dict[worker]['available_accounts']
    return finally_dict


def _select_worker(selected_workers: list[int], workers_dict: dict[int, WorkersDict]) -> int:
    while True:
        workers_list = list(workers_dict.keys())
        priority_list = [entry['priority'] for entry in workers_dict.values()]
        for _ in range(10):
            worker = random.choices(workers_list, weights=priority_list)
            if worker not in selected_workers:
                return worker
        else:
            # Если функция уже 10 раз выбирает одно и то же, то отчищаем список от лишниъ воркеров
            _workers_cleaning(selected_workers, workers_dict)


# Отчистить словарь от лишних воркеров
def _workers_cleaning(selected_workers: list[int], workers_dict: dict[int, WorkersDict]) -> None:
    for selected_worker in selected_workers:
        workers_dict.pop(selected_worker)


# Распределение аккаунтов
def _distribute_accounts(selected_workers: list[int], workers_dict: dict[int, WorkersDict],
                         min_number_accounts: int) -> dict[int, int]:
    finally_dict: dict[int, int] = {}
    for worker in selected_workers:
        finally_dict[worker] = random.randint(1, workers_dict[worker]['available_accounts'])
    accounts_count = sum(accounts for accounts in finally_dict.values())
    # Если в итоге набрали столько, сколько нужно
    if accounts_count >= min_number_accounts:
        return finally_dict
    # Если слишком мало, добиваем до рекомендованного писла аккаунтов
    else:
        return _get_the_required_amount(min_number_accounts, accounts_count, finally_dict, workers_dict, selected_workers)


def _get_the_required_amount(min_number_accounts: int, accounts_count: int, finally_dict: dict[int, int],
                             workers_dict: dict[int, WorkersDict], selected_workers: list[int]) -> dict[int, int]:
    need_accounts = min_number_accounts - accounts_count
    available_accounts_dict = {worker: workers_dict[worker]['available_accounts'] - finally_dict[worker] for worker in selected_workers if workers_dict[worker]['available_accounts'] - finally_dict[worker] >= 1}
    workers = list(available_accounts_dict.keys())
    for _ in range(need_accounts):
        worker = random.choices(workers)
        finally_dict[worker] += 1
        available_accounts_dict[worker] -= 1
        # Если у какого-то пользователя закончились аккаунты, убираем его из словаря
        if available_accounts_dict[worker] == 0:
            available_accounts_dict.pop(worker)
            workers = list(available_accounts_dict.keys())
    return finally_dict


# Функция для добивки нужного значения
def _addition_of_recommended_values(min_number_accounts: int, accounts_count: int,
                                    workers_dict: dict[int, WorkersDict], selected_workers: list[int]) -> bool:
    while True:
        # Если у нас нет новых аккаунтов, то ну мы уже ничего не сможем сделать
        if not workers_dict:
            return False
        worker = _select_worker(selected_workers, workers_dict)
        selected_workers.append(worker)
        accounts_count += workers_dict[worker]['available_accounts']
        if accounts_count >= min_number_accounts:
            return True


# Завершающая функция
async def _fynally_function(finally_dict, selected_beginners):
    # Создаём итоговый словарь
    finally_dict.update(selected_beginners)
    # Бронируем челиксов
    await _book_workers(finally_dict)
    return finally_dict


# Забронировать воркеров, чтоб их никто пока другой не взял
async def _book_workers(workers: dict[int, int]) -> None:
    workers_list = list(workers.keys())
    await db.worker_booking(workers_list)
