from typing import Literal, NoReturn

from bot_apps.other_apps.systems_tasks.sending_tasks.start_task import start_round
from bot_apps.other_apps.systems_tasks.watchmans.completing_completion import WaitingTasks
from databases.database import Database

db = Database()


async def launch_new_rounds() -> None:
    """Отбор всех функций, которым пора начать новый раунд и запуск их по очереди"""
    all_tasks: dict[int, Literal[1, 2, 3]] = await db.get_tasks_for_new_round()
    if all_tasks:
        for task in all_tasks:
            await start_round(task_id=task, number_round=all_tasks[task])


async def launch_new_rounds_checker() -> NoReturn:
    waiting_tasks = WaitingTasks(2 * 60, 20 * 60)
    while True:
        await waiting_tasks()
        await launch_new_rounds()
