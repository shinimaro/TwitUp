import math
from typing import TypedDict

from databases.database import db


class CheckDict(TypedDict):
    time_has_passed: bool
    tasks_sent_recently: int


class LimitsDict(TypedDict):
    max_limits: int
    min_limits: int


class ExecutionInformation(TypedDict):
    number_scored: int
    number_failures: int
    number_late_failures: int
    acceptance_rate: int


# Функция по выдачем начального приоритета пользователю, который только что врубил кнопку
async def determine_initial_priority(tg_id) -> int | None:
    check_dict: CheckDict = await db.check_button_time(tg_id)
    # Если пользователь отключил кнопку 8 часов назад, даём ему новый приоритет
    if check_dict['time_has_passed']:
        return await get_initial_priority(tg_id)
    # Если он не получал заданий последние 5 часов (при условии, что у него итоговый приоритет станет больше)
    if check_dict['tasks_sent_recently'] == 0:
        priority = await db.check_priority(tg_id)
        initial_priority = await get_initial_priority(tg_id)
        if initial_priority > priority:
            return initial_priority


# Получить начальный приоритет
async def get_initial_priority(tg_id) -> int:
    # Взять верхний и нижний лимит приоритета
    limits: LimitsDict = await db.get_user_limits(tg_id)
    fines = await db.get_current_fines(tg_id)
    limits['max_limits'] -= fines
    # Взять информацию о прошлых показателях
    execution_information: ExecutionInformation = await db.user_executions_info(tg_id)
    return math.ceil(calculate_final_priority(limits, execution_information))


def calculate_final_priority(limits: LimitsDict, execution_information: ExecutionInformation) -> float:
    # Распределение 60 на 40, 60 - то, как он вообще хорошо выполняет задания, 40 - как часто принимает
    execution = (limits['max_limits'] - limits['min_limits']) / 100 * 60
    execution_rate = 100
    accepted = (limits['max_limits'] - limits['min_limits']) / 100 * 40
    if execution_information['number_scored'] >= 3:
        execution_rate -= 30
    elif execution_information['number_late_failures'] >= 2:
        execution_rate -= 30
    execution = execution / 100 * execution_rate
    accepted = accepted / 100 * execution_information['acceptance_rate'] if execution_information['acceptance_rate'] > 0 else accepted
    return limits['min_limits'] + execution + accepted
