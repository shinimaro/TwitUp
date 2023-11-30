import asyncio
from asyncio import sleep
from typing import Literal

from bot_apps.task_push.system.sending_tasks.completing_completion import WaitingTasks
from bot_apps.task_push.system.sending_tasks.selection_of_workers import SelectionWorkers
from bot_apps.task_push.system.sending_tasks.sending_tasks import sending_task
from databases.database import db


# Основная функция по старту таска, которая работает через lock, чтобы никто другой не подключился до конца работы
async def start_tasks(task_id: int, circular: bool) -> None:
    if circular:
        round: Literal[1, 2, 3] = await db.get_next_round_from_task(task_id)
    if not circular or round != 1:
        await _wait_before_starting()  # Обязательно подождать перед началом
    async with asyncio.Lock():
        await db.change_task_status_on_bulk_messaging(task_id)
        if circular:
            selection_workers = SelectionWorkers(task_id=task_id, max_increase=50)
            selected_workers: dict[int, int] = await selection_workers.selection_of_workers()
        else:
            selection_workers = SelectionWorkers(task_id=task_id, round=round)
            selected_workers: dict[int, int] = await selection_workers.selection_of_workers_for_round()
        await sending_task(task_id, selected_workers)
        await db.change_status_task_on_active(task_id)


# Фанкшин, запускающий новый раунд для воркерсов
async def start_new_round():
    # Отбор тасков, которым нужен новый раунд (прошло достаточно времени и ещё есть доступные выполнения)
    info = await db.get_tasks_for_new_round()
    if info:
        selection_workers = SelectionWorkers(info['task_id'], info['round'])
        selected_workers = selection_workers.selection_of_workers_for_round()
        # await db.change_status_task_on_dop_bulk_messaging(task_id)

        # Придумать как-то, чтобы фанкшин каждый, который отбирает задания, были в локе, т.е. не могли выполняться параллельно

        # Добавить в сторожа тасков, только таски должны отбираться, после того, как прошло N времени и нужный собстна круг или случилось N выполнений
        # Если круги закончились и время тоже, сторожила должен выбрать самого пиздатого чела на данный момент с самым большим активом и акками, которые могут взять этот таск и позволить ему выполнить на определённое число акков и так по кругу чтобы каждый раз новые челы отбирались надо
        # Засунуть в принятия заданий проверку, что не было добито N заданий и не нужно выпускать новый круг
        # Если нужно сделать новый круг, то обращаемся к фанкшину circular_start_task и он опять делает всё тоже самое


async def _wait_before_starting():
    await sleep(25)


async def start_new_round_checker():
    waiting_tasks = WaitingTasks(2 * 60, 15 * 60)
    while True:
        await waiting_tasks()
        await start_new_round()

