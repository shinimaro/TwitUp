import asyncio
from asyncio import sleep
from typing import TypedDict, NoReturn

from databases.database import Database

db = Database()


class WorkersDict(TypedDict):
    completed_tasks: int
    sent_tasks: int
    level: str


# Сторож, собирающий всех воркеров, у которых есть уровень какой-то и проверяет, выполнили ли они тасков на свой уровень
async def level_watchman() -> None:
    # Собираем всех юзеров, у которых уже прошла неделя после обновления уровня
    workers_dict: dict[int, WorkersDict] = await db.get_users_after_up_level()
    # Отбираем всех воркеров, которые не выполнили заданий на свой уровень
    selected_workers_dict: dict[int, WorkersDict] = await select_workers(workers_dict)
    # Понижаем в уровне всех, кто не выполнил условия
    await db.decline_in_level(selected_workers_dict)
    # Обновляем дату проверки и обновления уровня у всех юзеров
    await db.update_time_for_level(list(workers_dict.keys()))


# Отобрать всех воркеров, не выполнивших всех условий на свой уровень
async def select_workers(workers_dict: dict[int, WorkersDict]) -> dict[int, WorkersDict]:
    need_dict = await db.get_need_for_level()
    selected_workers_dict = {}
    for worker in workers_dict:
        # Если юзеру было отправлено достаточно тасков на свой уровень, а также, он выполнил из них меньше, чем нужно
        if (workers_dict[worker]['sent_tasks'] >= need_dict[workers_dict[worker]['level']] and
                workers_dict[worker]['sent_tasks'] > workers_dict[worker]['completed_tasks']):
            selected_workers_dict[worker] = {'completed_tasks': workers_dict[worker]['completed_tasks'], 'level': workers_dict[worker]['level']}
    return selected_workers_dict


# Раз в 10 минут запускает сторожа для просмотра того, что юзер выполнил работы на свой уровень
async def level_watchman_checker() -> NoReturn:
    while True:
        await sleep(20 * 60)
        await level_watchman()
