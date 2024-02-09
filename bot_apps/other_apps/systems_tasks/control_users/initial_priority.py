import math
from typing import TypedDict

from databases.database import Database

db = Database()


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


# Функция по выдаче начального приоритета пользователю, который только что врубил кнопку
async def determine_initial_priority(tg_id) -> None:
    if db.newbie_check(tg_id):  # Если юзер не новичок (если новичок, он и так вне очереди обслуживается)
        check_dict: CheckDict = await db.check_button_time(tg_id)
        # Если пользователь отключил кнопку 8 часов назад, даём ему новый приоритет и ставим в приорити очередь
        if check_dict['time_has_passed']:
            initial_priority = await get_initial_priority(tg_id)
            await db.new_user_priority(tg_id, initial_priority)
            await db.put_user_out_of_priority(tg_id)
        # Если он не получал заданий последние 5 часов (при условии, что у него итоговый приоритет станет больше)
        elif check_dict['tasks_sent_recently']:
            priority = await db.check_priority(tg_id)
            initial_priority = await get_initial_priority(tg_id)
            if initial_priority > priority:
                await db.new_user_priority(tg_id, initial_priority)


# Получить начальный приоритет
async def get_initial_priority(tg_id) -> int:
    # Взять верхний и нижний лимит приоритета
    limits: LimitsDict = await db.get_user_limits(tg_id)
    fines = await db.get_current_fines(tg_id)
    limits['max_limits'] -= fines + 10
    # Взять информацию о прошлых показателях
    execution_information: ExecutionInformation = await db.user_executions_info(tg_id)
    return math.ceil(calculate_final_priority(limits, execution_information))


def calculate_final_priority(limits: LimitsDict, execution_information: ExecutionInformation) -> float:
    # Распределение 40 на 60, 40 - то, как он вообще хорошо выполняет задания и 60 - как часто принимает
    execution = (limits['max_limits'] - limits['min_limits']) / 100 * 40
    execution_rate = 100
    accepted = (limits['max_limits'] - limits['min_limits']) / 100 * 60
    # Если 2 и более раз забил на таски, либо 3 и более раз поздно отказался от таска, уменьшаем на 40% кусок приоритета
    if execution_information['number_scored'] >= 2:
        execution_rate -= 40
    if execution_information['number_late_failures'] >= 3:
        execution_rate -= 40
    execution = execution / 100 * execution_rate  # Превращаем обратно в итоговое число приоритета
    accepted = accepted / 100 * execution_information['acceptance_rate'] if execution_information['acceptance_rate'] > 0 else accepted
    return max(limits['min_limits'] + execution + accepted, limits['min_limits'])  # Защита от случаев, когда итоговый рейтинг меньше, чем минимальный
