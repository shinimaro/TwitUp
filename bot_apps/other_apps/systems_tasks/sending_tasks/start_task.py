import asyncio
from asyncio import sleep
from typing import Literal

from bot_apps.other_apps.systems_tasks.sending_tasks.selection_of_workers import SelectionWorkers
from bot_apps.other_apps.systems_tasks.sending_tasks.sending_tasks import sending_task
from databases.database import Database
from databases.dataclasses_storage import WaitingStartTask

db = Database()


async def start_tasks(task_id: int, circular: bool) -> None:
    """Функция для старта таска"""
    number_round: Literal[1, 2, 3] | None = await db.get_next_round_from_task(task_id)
    # Если это не таск, в котором несколько раундов, либо это только первый раунд, обязательно минутку подождать перед началом
    if not circular or number_round == 1:
        await sleep(WaitingStartTask.waiting_time)
    async with asyncio.Lock():
        # Проверка на то, что задание не было удалено
        if await db.check_not_delete_task(task_id):
            await db.change_task_status_on_bulk_messaging(task_id)  # Меняем статус на то, что сейчас идёт процесс отбора воркеров
            if not circular:
                selection_workers = SelectionWorkers(task_id=task_id, max_increase=50)
                selected_workers: dict[int, int] = await selection_workers.selection_of_workers()
            else:
                selection_workers = SelectionWorkers(task_id=task_id, number_round=number_round)
                selected_workers: dict[int, int] = await selection_workers.selection_of_workers_for_round()
            await sending_task(task_id, selected_workers)
            await db.change_status_task_on_active(task_id)


async def start_round(task_id: int, number_round: Literal[1, 2, 3]):
    """Функция для старта нового раунда распределения задания"""
    async with asyncio.Lock():
        if await db.check_not_delete_task(task_id):
            await db.change_status_task_on_dop_bulk_messaging(task_id)
            selection_workers = SelectionWorkers(task_id=task_id, number_round=number_round)
            selected_workers = await selection_workers.selection_of_workers_for_round()
            await sending_task(task_id, selected_workers)
            await db.change_status_task_on_active(task_id)
            await db.update_task_round(task_id)

        # Если нужно сделать новый круг, то обращаемся к фанкшину circular_start_task и он опять делает всё тоже самое


async def admin_additionally_distributed_task(task_id: int, number_workers: int):
    """Функция для дополнительного распределения админом/сапортом задания"""
    await db.change_task_status_on_bulk_messaging(task_id)
    selection_workers = SelectionWorkers(task_id, precise_quantity=number_workers)
    selected_workers: dict[int, int] = await selection_workers.selection_of_workers()
    await sending_task(task_id, selected_workers)
    await db.change_status_task_on_active(task_id)
