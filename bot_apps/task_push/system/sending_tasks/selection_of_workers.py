import asyncio
import copy
import math
import random
import statistics
from collections import namedtuple
from dataclasses import dataclass
from typing import TypedDict, Literal

from databases.database import db, TaskInfo

Variant = namedtuple('Variant', ['one_variant', 'two_variant'])

lock = asyncio.Lock()


class WorkersDict(TypedDict):
    priority: int
    available_accounts: int


@dataclass
class SelectionCoefficients:
    count_workers: int
    min_count_accounts: int


class SelectionWorkers:

    def __init__(self, task_id: int = 0, max_increase: int = 0, round: Literal[1, 2, 3] = None):
        self.task_id = task_id
        self.max_increase = max_increase  # Максимальная прибавка к 100 выполнениям
        self.round = round
        # Переменные, которые будут определяться в функции
        self.selection_coefficients: SelectionCoefficients = None
        self.finally_dict: dict[int, int] = {}
        self.accounts_count = 0
        # Новички
        self.beginners_dict: dict[int, int] = {}
        self.selected_beginners: dict[int, int] = {}
        # Остальные воркерсы
        self.main_workers_dict: dict[int, WorkersDict] | dict[Literal[1, 2, 3], dict[int, WorkersDict]] = {}
        self.workers_dict: dict[int, WorkersDict] | dict[Literal[1, 2, 3], dict[int, WorkersDict]] = {}
        self.selected_workers: list[int] = []

    # Функция для отбора воркеров на небольшие задания (до 100 штук наверное)
    async def selection_of_workers(self) -> dict[int, int]:
        # Отбираем рекомендованное кол-во воркеров для задания, а также мин. кол-во аккаунтов, которое должно быть у них
        self.selection_coefficients: SelectionCoefficients = await self._easy_selection_of_workers()
        # отбираем новичков, которым отдаём 30% от количества пользвателей, на которых распределим задания
        self.beginners_dict: dict[int, int] = await db.get_some_beginners(self.task_id)
        # Если новички есть, отдаём им 30% от кол-ва рекомендованных воркеров для задания
        self._fill_beginner()
        # отбор всех воркеров, которые могут выполнить данный таск
        self.main_workers_dict: dict[int, WorkersDict] = await db.get_all_workers(self.task_id)
        # Делаем доп словарь для отбора, т.к. из него можно будет ключи убирать и это удобно
        self.workers_dict = copy.deepcopy(self.main_workers_dict)

        # Если выполнений больше, чем доступных воркеров, забиваем по максимуму
        if self.selection_coefficients.count_workers > len(self.workers_dict) + len(self.selected_beginners):
            # self._max_distribute_account_for_beginners()  # Забиваем по максимум новичков (пока не юзаю, т.к и так по-максу им даём)
            self._max_distribute_accounts()  # Забиваем по максимуму воркеров
            return self._merge_workers()  # Создаём итоговый словарь

        # Распределяем воркеров
        self._fill_out_list_workers()
        # Вычисляем полученное кол-во аккаунтов
        self._get_sum_accounts()

        # Если слишком мало у нас аккаунтов на воркеров получилось, то добавляем ещё
        if self.accounts_count < self.selection_coefficients.min_count_accounts:
            result: bool = self._addition_of_recommended_values()
            # Если не получилось загрузить ещё аккаунтов, распределяем их по-максимуму и отправляем
            if not result:
                self._max_distribute_accounts()  # Распределяем все аккаунты по-максимуму среди воркеров (у новичков и так по максу)
                return self._merge_workers()  # Создаём итоговый словарь
        # Если всё ок и аккаунтов хватает, распределяем их по пользователям
        self._distribute_accounts()
        return self._merge_workers()  # Создаём итоговый словарь

    # Функция для отбора воркеров для конкретного раунда
    async def selection_of_workers_for_round(self) -> dict[int, int]:
        # Отбираем нужное кол-во воркеров для нашего раунда
        self.selection_coefficients: SelectionCoefficients = await self._strict_selection_of_workers()
        # Отбираем воркеров по раундам
        self.main_workers_dict: dict[Literal[1, 2, 3], dict[int, WorkersDict]] = await db.get_all_workers_for_round(self.task_id)
        # self.main_workers_dict = main_workers_dict = {
        #     '1': {
        #         1001: {'priority': 60, 'available_accounts': 15},
        #         1002: {'priority': 70, 'available_accounts': 15},
        #         1003: {'priority': 80, 'available_accounts': 15},
        #         1004: {'priority': 90, 'available_accounts': 15},
        #         1005: {'priority': 100, 'available_accounts': 15},
        #         1006: {'priority': 50, 'available_accounts': 15},
        #         1007: {'priority': 40, 'available_accounts': 15},
        #         1008: {'priority': 30, 'available_accounts': 15},
        #         1009: {'priority': 20, 'available_accounts': 15},
        #         1010: {'priority': 10, 'available_accounts': 15}},
        #     '2': {},
        #     '3': {1011: {'priority': 60, 'available_accounts': 15},
        #           1012: {'priority': 70, 'available_accounts': 15},
        #           1013: {'priority': 80, 'available_accounts': 15},
        #           1014: {'priority': 90, 'available_accounts': 15},
        #           1015: {'priority': 100, 'available_accounts': 15},
        #           1016: {'priority': 50, 'available_accounts': 15},
        #           1017: {'priority': 40, 'available_accounts': 15},
        #           1018: {'priority': 30, 'available_accounts': 15},
        #           1019: {'priority': 20, 'available_accounts': 15},
        #           1020: {'priority': 10, 'available_accounts': 15}}}

        self.workers_dict = copy.deepcopy(self.main_workers_dict)

        # Проверка на то, что у нас хватит тех, кто должен идти в этом раунде
        if len(self.main_workers_dict[self.round]) < self.selection_coefficients.count_workers:
            # Добираем с других кругов
            return self._distribution_workers_from_all_rounds()
        # Если всё ок, рапределяем воркеров
        self._fill_out_list_workers()
        # Загружаем аккаунты
        return self._distribute_accounts()

    # Лёгкая функция по отбору воркеров, которая просто выбирает чуть больше воркеров, чем нужно
    async def _easy_selection_of_workers(self) -> SelectionCoefficients:
        executions = await db.get_amount_executions(self.task_id)
        increase = self.max_increase / 100 * executions
        count_workers = int(executions + increase)
        min_count_accounts = 2 * count_workers
        return SelectionCoefficients(count_workers=count_workers, min_count_accounts=min_count_accounts)

    # Супер вычисления для поиска нужного количества воркеров и минимального кол-ва аккаунтов
    async def _complex_calculations(self) -> None:
        executions = await db.get_amount_executions(self.task_id)
        # Средний коэфициент выполнений одного задания одним юзером
        task_completion_rate: float = await self._calculate_executions_rate()
        # Средний коэфициент принятия за (60) минут в ближайший час
        assignment_acceptance_rate = await self._calculate_acceptance_rate()
        # Вычисляем среднее промежуточное количество воркеров
        intermediate_count_workers = math.ceil(executions / task_completion_rate * assignment_acceptance_rate)
        # Процент прибавки к этому числу
        floating_interest = intermediate_count_workers / 100 * (((executions - 5) / (100 - 5)) * 25)
        # Опорное количество воркеров
        count_workers = math.ceil(intermediate_count_workers + floating_interest)
        # Минимально рекомендованное количество аккаунтов
        min_count_accounts = math.ceil(count_workers * task_completion_rate)
        self.selection_coefficients = SelectionCoefficients(count_workers=count_workers, min_count_accounts=min_count_accounts)

    # Функция не по отбору опорного кол-ва воркеров, а конкретного кол-ва, который определён для каждого круга
    async def _strict_selection_of_workers(self) -> SelectionCoefficients:
        percen_workers = {1: 33, 2: 33, 3: await self._selection_workers_for_last_round()}
        executions = await db.get_amount_executions(self.task_id)
        count_workers = math.ceil(executions / 100 * percen_workers[self.round])
        # min_number_accounts = count_workers  # Хз, возможно тут нужно по-максимуму раздавать
        return SelectionCoefficients(count_workers=count_workers, min_count_accounts=0)

    # Получить коэфициент выполнений за ближайший час
    async def _calculate_executions_rate(self) -> float:
        executions_info = await db.get_accepted_tasks()
        # Собираем средние значения в каждом задании
        values = []
        for task in executions_info:
            executions, users_counter = 0, 0
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

    # Коэфициент принятий за ближайший час
    async def _calculate_acceptance_rate(self) -> float:
        acceptance_info = await db.get_sent_tasks()
        results, counts = 0, 0
        for day in acceptance_info:
            finally_offers, finally_acceptances = 0, 0
            for tasks in acceptance_info[day]:
                finally_offers += acceptance_info[day][tasks]['quantity_submitted_tasks']
                finally_acceptances += acceptance_info[day][tasks]['quantity_accepted_tasks']
            results += finally_acceptances / finally_offers
            counts += 1
        return results / counts

    def _fill_beginner(self) -> None:
        max_beginners = self.selection_coefficients.count_workers / 100 * 30
        # Отбираем новичков по одному
        for beginner in self.beginners_dict.keys():
            # count_accounts = random.randint(1, beginners_dict[beginner])
            # Не будем пидормотами, дадим пока новичкам выполнить по-максимуму
            count_accounts: int = self.beginners_dict[beginner]
            self.selected_beginners[beginner]: int = count_accounts
            self.selection_coefficients.min_count_accounts -= count_accounts
            self.selection_coefficients.count_workers -= 1
            max_beginners -= 1
            if max_beginners <= 0:
                break

    # Максимальное распределение аккаунтов
    def _max_distribute_accounts(self) -> None:
        for worker in self.main_workers_dict:
            self.finally_dict[worker] = self.main_workers_dict[worker]['available_accounts']

    # Дать новичкам по-максимуму аккаунтов
    def _max_distribute_account_for_beginners(self) -> None:
        for beginner in self.selected_beginners:
            self.selected_beginners[beginner] = self.beginners_dict[beginner]

    # Завершающая функция, которая пока только сливает новичков и остальных воркеров
    def _merge_workers(self) -> dict[int, int]:
        return self.finally_dict.update(self.selected_beginners)

    # Заполнить список воркерами
    def _fill_out_list_workers(self) -> None:
        for _ in range(self.selection_coefficients.count_workers):
            worker: int | None = self._select_worker()
            if not worker:  # Если отборщику воркеров уже нечего возвращать
                break
            self.selected_workers.append(worker)

    # Получить итоговое кол-во аккаунтов
    def _get_sum_accounts(self) -> None:
        self.accounts_count = sum(
            self.main_workers_dict.get(worker, {}).get('available_accounts', 0) for worker in self.selected_workers)

    # Функция для добивки нужного значения
    def _addition_of_recommended_values(self) -> bool:
        while self.workers_dict:
            worker: int = self._select_worker()
            self.selected_workers.append(worker)
            self.accounts_count += self.main_workers_dict[worker]['available_accounts']
            # Если набрали скоко нужно аккаунтов
            if self.accounts_count >= self.selection_coefficients.min_count_accounts:
                return True
        # Если новых аккаунтов в итоге нет
        return False

    # Распределение аккаунтов
    def _distribute_accounts(self) -> dict[int, int]:
        for worker in self.selected_workers:
            self.finally_dict[worker]: int = random.randint(1, self.main_workers_dict[worker]['available_accounts'])
        # Определяем новое итоговое кол-во аккаунтов
        self.accounts_count = sum(accounts for accounts in self.finally_dict.values())
        # Если в итоге набрали столько, сколько нужно
        if self.accounts_count >= self.selection_coefficients.min_count_accounts:
            return self.finally_dict
        # Если слишком мало, добиваем до рекомендованного писла аккаунтов
        else:
            return self._get_the_required_amount()

    # Добить кол-во распределённых аккаунтов до рекомендованного числа
    def _get_the_required_amount(self) -> dict[int, int]:
        # Находим, сколько аккаунтов осталось добить
        need_accounts: int = self._get_need_accounts()
        # Берём остальных воркеров с их аккаунтами из общего словаря, которые не были отобраны
        available_accounts_dict: dict[int, int] = {worker: self.main_workers_dict[worker]['available_accounts'] - self.finally_dict[worker] for
                                                   worker in self.selected_workers if self.main_workers_dict[worker]['available_accounts'] -
                                                   self.finally_dict[worker] >= 1}
        workers = list(available_accounts_dict.keys())
        # Добавляем случайному воркеру по 1 аккаунту
        for _ in range(need_accounts):
            worker = random.choices(workers)[0]
            self._add_worker_to_finally_dict(worker)
            self.finally_dict[worker] += 1
            available_accounts_dict[worker] -= 1
            # Если у какого-то пользователя закончились аккаунты, убираем его из словаря
            if available_accounts_dict[worker] == 0:
                available_accounts_dict.pop(worker)
                workers = list(available_accounts_dict.keys())
        return self.finally_dict

    # Добавить какого-то пользователя в итоговый дикт
    def _add_worker_to_finally_dict(self, worker: int) -> None:
        if worker not in self.finally_dict:
            self.finally_dict[worker] = 0

    # Отбор кол-ва воркеров для выполнения первого круга
    # async def


    # Отбор кол-ва воркеров, для выполнения последнего круга
    async def _selection_workers_for_last_round(self) -> int:
        # Вычисляем, сколько уже выполнили задания, учитывая средний коэфициент выполнений за 3 последних дня
        task_info: TaskInfo = await db.get_executions_and_in_process_number(self.task_id)
        # Найти средний процент выполнений до конца за последние 3 дня
        completion_rate: float = await db.all_users_executions_info()
        # Находим итоговые выполнения
        total_executions = math.ceil(task_info.completed_tasks + (task_info.in_process * completion_rate))
        # Вычисляем, сколько осталось выполнений
        completions_left = total_executions - task_info.executions
        # Вычисляем коэф. выплнения у тех, у кого приоритет ниже 35
        completion_rate_from_low_priority = await db.users_executions_info_with_low_priority()
        # Пока, т.к. данных нет, просто умножаем на 2 и на коэфициент от того кол-ва, которое нужно доделать
        return completions_left * 2 * completion_rate_from_low_priority

    # Фанкшин, чтобы взять всех остальных юзеров из других раундов, чтобы добрать необходимое кол-во юзеров
    def _distribution_workers_from_all_rounds(self) -> dict[int, int]:
        # Первый максимальный отбор из нужного круга
        self._add_all_workers_from_round(self.round)
        variants = {
            '1': Variant('2', '3'),
            '2': Variant('1', '2'),
            '3': Variant('2', '1')}
        # Если нам ещё надо больше, чем есть в другом круге, добираем с него
        if self._get_need_workers() >= len(self.main_workers_dict[variants[self.round].one_variant]):
            self._add_all_workers_from_round(variants[self.round].one_variant)
            # Если и в следующем круге не хватает людей, опять добавляем всех, что есть
            if self._get_need_workers() >= len(self.main_workers_dict[variants[self.round].two_variant]):
                self._add_all_workers_from_round(variants[self.round].two_variant)
            else:
                self._fill_out_list_workers()
        else:
            self._fill_out_list_workers()
        # Объединяем воркеров из всех раундов в 1 главный словарь (для того, чтобы проверять, сколько у юзера аккаунтов)
        self._combine_all_rounds()
        return self._distribute_accounts()

    # Добавить всех воркеров из какого-то раунда в список и убрать лишние ключи
    def _add_all_workers_from_round(self, need_round: Literal[1, 2, 3]) -> None:
        self.selected_workers.extend(list(self.main_workers_dict[need_round].keys()))
        for selected_worker in self.selected_workers:
            if selected_worker in self.workers_dict[need_round]:
                self.workers_dict[need_round].pop(selected_worker)

    def _get_need_workers(self) -> int:
        return self.selection_coefficients.count_workers - self.selected_workers

    def _get_need_accounts(self) -> int:
        return self.selection_coefficients.min_count_accounts - self.accounts_count

    def _combine_all_rounds(self) -> None:
        self.main_workers_dict = {k: v for sub_dict in self.main_workers_dict.values() for k, v in sub_dict.items()}

    # Функция отбирает одного воркера для выполнения
    def _select_worker(self) -> int | None:
        workers_list = list(self.workers_dict.keys())
        priority_list = [entry['priority'] for entry in self.workers_dict.values()]
        # Непосредственно отбор самого воркера, учитывая его приоритет
        while workers_list:
            worker = random.choices(workers_list, weights=priority_list)[0]
            if worker not in self.selected_workers:
                self.workers_dict.pop(worker)
                return worker


async def sus():
    bub = SelectionWorkers(1, 120)
    await bub.selection_of_workers()