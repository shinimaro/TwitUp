import asyncio
import copy
import math
import random
import statistics
from time import sleep
from typing import TypedDict, Literal
from databases.database import db
from collections import namedtuple

Variant = namedtuple('Variant', ['one_variant', 'two_variant'])

lock = asyncio.Lock()


class WorkersDict(TypedDict):
    priority: int
    available_accounts: int


class TaskInfo(TypedDict):
    executions: int
    completed_tasks: int
    in_process: int


# main_workers_dict = {
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


# Функция для отбора воркеров на небольшие задания (до 100 штук наверное)
async def selection_of_workers(task_id: int, count_workers: int, min_number_accounts: int) -> dict[int, int]:
    # отбираем новичков, которым отдаём 30% от количества пользвателей, на которых распределим задания
    beginners_dict = await db.get_some_beginners(task_id)
    # Если новички есть, отдаём им задания
    selected_beginners, count_workers, min_number_accounts = _fill_beginner(beginners_dict, count_workers, min_number_accounts)
    # отбор всех воркеров, которые могут выполнить данный таск
    main_workers_dict: dict[int, WorkersDict] = await db.get_all_workers(task_id)
    # Делаем доп словарь для отбора, т.к. из него можно будет ключи убирать и это удобно
    workers_dict = copy.deepcopy(main_workers_dict)

    # Если выполнений больше, чем доступных воркеров, забиваем по максимуму
    if count_workers > len(workers_dict) + len(selected_beginners):
        finally_dict = _max_distribute_accounts(main_workers_dict)
        _max_distribute_account_for_beginners(selected_beginners, beginners_dict)
        return await _fynally_function(finally_dict, selected_beginners)

    # Распределяем воркеров
    selected_workers: list[int] = []
    _fill_out_list_workers(selected_workers, workers_dict, count_workers)
    # Вычисляем, сколько аккаунтов у нас получилось в итоге (не знаю почему, но эта дура иногда не может найти ключи в словаре, в котором они есть, поэтому пока немного переписал)
    # accounts_count = sum(workers_dict[worker]['available_accounts'] for worker in selected_workers)
    accounts_count = sum(main_workers_dict.get(worker, {}).get('available_accounts', 0) for worker in selected_workers)

    # Если слишком мало у нас аккаунтов на воркеров получилось, то добавляем ещё
    if accounts_count <= min_number_accounts:
        result = _addition_of_recommended_values(min_number_accounts, accounts_count, workers_dict, main_workers_dict, selected_workers)
        # Если не получилось загрузить ещё аккаунтов, распределяем их по-максимуму и отправляем
        if not result:
            finally_dict = _max_distribute_accounts(main_workers_dict)
            return await _fynally_function(finally_dict, selected_beginners)
    # Если всё ок и аккаунтов хватает, распределяем их по пользователям
    finally_dict = _distribute_accounts(selected_workers, workers_dict, min_number_accounts)
    return await _fynally_function(finally_dict, selected_beginners)


# Функция для отбора воркеров для конкретного раунда
async def selection_of_workers_for_round(task_id: int, round: Literal['1', '2', '3']) -> dict[int, int]:
    # Отбираем нужное кол-во воркеров для нашего раунда
    count_workers = await strict_selection_of_workers(task_id, int(round))
    # Отбираем воркеров по раундам
    # main_workers_dict: dict[Literal['1', '2', '3'], dict[int, WorkersDict]] = await db.get_all_workers_for_round(task_id)
    main_workers_dict = main_workers_dict = {
    '1': {
        1001: {'priority': 60, 'available_accounts': 15},
        1002: {'priority': 70, 'available_accounts': 15},
        1003: {'priority': 80, 'available_accounts': 15},
        1004: {'priority': 90, 'available_accounts': 15},
        1005: {'priority': 100, 'available_accounts': 15},
        1006: {'priority': 50, 'available_accounts': 15},
        1007: {'priority': 40, 'available_accounts': 15},
        1008: {'priority': 30, 'available_accounts': 15},
        1009: {'priority': 20, 'available_accounts': 15},
        1010: {'priority': 10, 'available_accounts': 15}},
    '2': {},
    '3': {1011: {'priority': 60, 'available_accounts': 15},
        1012: {'priority': 70, 'available_accounts': 15},
        1013: {'priority': 80, 'available_accounts': 15},
        1014: {'priority': 90, 'available_accounts': 15},
        1015: {'priority': 100, 'available_accounts': 15},
        1016: {'priority': 50, 'available_accounts': 15},
        1017: {'priority': 40, 'available_accounts': 15},
        1018: {'priority': 30, 'available_accounts': 15},
        1019: {'priority': 20, 'available_accounts': 15},
        1020: {'priority': 10, 'available_accounts': 15}}}

    workers_dict = copy.deepcopy(main_workers_dict)

    # Проверка на то, что у нас хватит тех, кто должен идти в этом раунде
    if len(main_workers_dict[round]) <= count_workers:
        # Добираем с других кругов
        return _distribution_workers_from_all_rounds(main_workers_dict, workers_dict, count_workers, round)
    selected_workers = []
    _fill_out_list_workers(selected_workers, workers_dict[round], count_workers)
    # Загружаем аккаунты
    return _distribute_accounts(main_workers_dict[round], selected_workers)


# Фанкшин, чтобы взять всех остальных юзеров из других раундов, чтобы добрать необходимое кол-во юзеров
def _distribution_workers_from_all_rounds(main_workers_dict: dict[int, dict[int, WorkersDict]], workers_dict: dict[int, dict[int, WorkersDict]],
                                          count_workers: int, round: Literal['1', '2', '3']):
    selected_workers = []
    # Первый максимальный отбор из нужного круга
    _add_all_workers_from_round(selected_workers, main_workers_dict, workers_dict, round)
    print(1)
    need_workers = count_workers - len(selected_workers)
    variants = {
        '1': Variant('2', '3'),
        '2': Variant('1', '2'),
        '3': Variant('2', '1')}
    print(2)
    # Если нам ещё надо больше, чем есть в другом круге, добираем с него
    if need_workers >= len(main_workers_dict[variants[round].one_variant]):
        print(3)
        _add_all_workers_from_round(selected_workers, main_workers_dict, workers_dict, variants[round].one_variant)
        need_workers = count_workers - len(selected_workers)
        print(4)
        if need_workers >= len(main_workers_dict[variants[round].two_variant]):
            _add_all_workers_from_round(selected_workers, main_workers_dict, workers_dict, variants[round].two_variant)
        else:
            print(5)
            _fill_out_list_workers(selected_workers, workers_dict[variants[round].two_variant], count_workers)
    else:
        print(6)
        _fill_out_list_workers(selected_workers, workers_dict[variants[round].one_variant], need_workers)
    print(7)
    # Объединяем дикт из всех раундов в 1 и кидаем в рапределение аккаунтов
    finally_main_workers_dict = {k: v for sub_dict in main_workers_dict.values() for k, v in sub_dict.items()}
    print('Отправляю дистрибютору ', selected_workers, finally_main_workers_dict)
    return _distribute_accounts(selected_workers, finally_main_workers_dict)


# Добавить всех воркеров из какого-то раунда в список и убрать лишние ключи
def _add_all_workers_from_round(selected_workers: list[int], main_workers_dict: dict[int, dict[int, WorkersDict]],
                                workers_dict: dict[int, dict[int, WorkersDict]], round: Literal['1', '2', '3']):
    selected_workers.extend(list(main_workers_dict[round].keys()))
    for selected_worker in selected_workers:
        if selected_worker in workers_dict[round]:
            workers_dict[round].pop(selected_worker)


# Заполнить список с отобранными воркерами
def _fill_out_list_workers(selected_workers: list[int], workers_dict: dict[int, WorkersDict], count_workers: int):
    for _ in range(count_workers):
        worker = _select_worker(selected_workers, workers_dict)
        if not worker:  # Если отборщику воркеров уже нечего возвращать
            break
        selected_workers.append(worker)

# Лёгкая функция по отбору воркеров, которая просто выбирает чуть больше, чем нужно
async def easy_selection_of_workers(task_id: int, max_increase: int) -> tuple[int, int]:
    executions = await db.get_amount_executions(task_id)
    increase = max_increase / 100 * executions
    count_workers = int(executions + increase)
    min_number_accounts = 2 * count_workers
    return count_workers, min_number_accounts


# Функция не по отбору опорного кол-ва воркеров, а конкретного кол-ва, который определён для каждого круга
async def strict_selection_of_workers(task_id: int, round: Literal[1, 2, 3]) -> tuple[int, int]:
    percen_workers = {1: 33, 2: 33, 3: await _selection_workers_for_last_round(task_id)}
    executions = await db.get_amount_executions(task_id)
    count_workers = math.ceil(executions / 100 * percen_workers[int(round)])
    # min_number_accounts = count_workers  # Хз, возможно тут нужно по-максимуму раздавать
    return count_workers


# Отбор кол-ва воркеров, для выполнения последнего круга
async def _selection_workers_for_last_round(task_id):
    # Вычисляем, сколько уже выполнили задания, учитывая средний коэфициент выполнений за 3 последних дня
    task_info: TaskInfo = await db.get_executions_and_in_process_number(task_id)
    completion_rate = await find_completion_rate()
    total_executions = find_total_executions(task_info['completed_tasks'], task_info['in_process'], completion_rate)
    # Вычисляем, сколько осталось выполнений
    completions_left = total_executions - task_info['executions']
    # Вычисляем коэф. выплнения у тех, у кого приоритет ниже 35
    completion_rate_from_low_priority = await db.users_executions_info_with_low_priority()
    # Пока, т.к. данных нет, просто умножаем на 2 и на коэфициент от того кол-ва, которое нужно доделать
    return completions_left * 2 * completion_rate_from_low_priority


# Вычислить итоговые выполнения
def find_total_executions(completed_task: int, in_process: int, completion_rate: float) -> int:
    # Найти все таски за последние 3 дня
    return math.ceil(completed_task + (in_process * completion_rate))


# Найти средний процент выполнений до конца за последние 3 дня
async def find_completion_rate():
    completion_rate = await db.all_users_executions_info()
    return completion_rate


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


def _fill_beginner(beginners_dict: dict[int, int], count_workers: int, min_number_accounts: int) -> tuple[dict[int, int], int, int]:
    selected_beginners: dict[int, int] = {}
    max_beginners = count_workers / 100 * 30
    for beginner in beginners_dict.keys():
        # count_accounts = random.randint(1, beginners_dict[beginner])
        # Не будем пидормотами, дадим пока новичкам выполнить по-максимуму
        count_accounts = beginners_dict[beginner]
        selected_beginners[beginner] = count_accounts
        min_number_accounts -= count_accounts
        count_workers -= 1
        max_beginners -= 1
        if max_beginners <= 0:
            break
    return selected_beginners, count_workers, min_number_accounts


# Максимальное распределение аккаунтов
def _max_distribute_accounts(main_workers_dict: dict[int, WorkersDict]) -> dict[int, int]:
    finally_dict: dict[int, int] = {}
    for worker in main_workers_dict:
        finally_dict[worker] = main_workers_dict[worker]['available_accounts']
    return finally_dict


# Дать новичкам по-максимуму аккаунтов
def _max_distribute_account_for_beginners(selected_beginners: dict[int, int], beginners_dict: dict[int, int]) -> None:
    for beginner in selected_beginners:
        selected_beginners[beginner] = beginners_dict[beginner]


# Функция отбирает одного воркера для выполнения
def _select_worker(selected_workers: list[int], workers_dict: dict[int, WorkersDict]) -> int:
    workers_list = list(workers_dict.keys())
    priority_list = [entry['priority'] for entry in workers_dict.values()]
    # Непосредственно отбор самого воркера, учитывая его приоритет
    while True and workers_list:
        # try:
        worker = random.choices(workers_list, weights=priority_list)[0]
        if worker not in selected_workers:
            workers_dict.pop(worker)
            return worker
        # except IndexError:
        #     continue


# Распределение аккаунтов
def _distribute_accounts(selected_workers: list[int], main_workers_dict: dict[int, WorkersDict],
                         min_number_accounts: int = 0) -> dict[int, int]:
    # print('Пришло дистрибьютору')
    finally_dict: dict[int, int] = {}
    for worker in selected_workers:
        finally_dict[worker] = random.randint(1, main_workers_dict[worker]['available_accounts'])
    accounts_count = sum(accounts for accounts in finally_dict.values())
    # Если в итоге набрали столько, сколько нужно
    if accounts_count >= min_number_accounts:
        return finally_dict
    # Если слишком мало, добиваем до рекомендованного писла аккаунтов
    else:
        return _get_the_required_amount(min_number_accounts, accounts_count, finally_dict, main_workers_dict, selected_workers)


def _get_the_required_amount(min_number_accounts: int, accounts_count: int, finally_dict: dict[int, int],
                             main_workers_dict: dict[int, WorkersDict], selected_workers: list[int]) -> dict[int, int]:
    need_accounts = min_number_accounts - accounts_count
    available_accounts_dict = {worker: main_workers_dict[worker]['available_accounts'] - finally_dict[worker] for worker in selected_workers if main_workers_dict[worker]['available_accounts'] - finally_dict[worker] >= 1}
    workers = list(available_accounts_dict.keys())
    for _ in range(need_accounts):
        worker = random.choices(workers)[0]
        finally_dict[worker] += 1
        available_accounts_dict[worker] -= 1
        # Если у какого-то пользователя закончились аккаунты, убираем его из словаря
        if available_accounts_dict[worker] == 0:
            available_accounts_dict.pop(worker)
            workers = list(available_accounts_dict.keys())
    return finally_dict


# Функция для добивки нужного значения
def _addition_of_recommended_values(min_number_accounts: int, accounts_count: int,
                                    workers_dict: dict[int, WorkersDict], main_workers_dict: dict[int, WorkersDict],
                                    selected_workers: list[int]) -> bool:
    while True:
        # Если у нас нет новых аккаунтов, то ну мы уже ничего не сможем сделать
        if not workers_dict:
            return False
        worker = _select_worker(selected_workers, workers_dict)
        selected_workers.append(worker)
        accounts_count += main_workers_dict[worker]['available_accounts']
        if accounts_count >= min_number_accounts:
            return True


# Завершающая функция
async def _fynally_function(finally_dict, selected_beginners) -> dict[int, int]:
    # Создаём итоговый словарь
    finally_dict.update(selected_beginners)
    # Бронируем челиксов
    await book_workers(finally_dict)
    return finally_dict


# Забронировать воркеров, чтоб их никто пока другой не взял
async def book_workers(workers: dict[int, int]) -> None:
    workers_list = list(workers.keys())
    # await db.worker_booking(workers_list)

async def sus():
    await db.connect()
    a = await selection_of_workers_for_round(1, '1')
    print('пришло ', a)




asyncio.run(sus())