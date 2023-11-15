import asyncio
from asyncio import sleep

from bot_apps.task_push.system.sending_tasks.completing_completion import completing_completion
from bot_apps.task_push.system.sending_tasks.selection_of_workers import selection_of_workers, \
    easy_selection_of_workers, strict_selection_of_workers, selection_of_workers_for_round
from bot_apps.task_push.system.sending_tasks.sending_tasks import sending_task
from databases.database import db


# Функция, которую я захотел вынести отдельно и которая просто собирает челиксов для выполнения задания и раскидываеn им его
async def start_task(task_id: int) -> None:
    # Обязательно подождать перед отправкой заданий
    await _wait_before_starting()
    async with asyncio.Lock():
        # Находим опорное количество воркеров и минимально рекомендованное количество аккаунтов
        count_workers, min_number_accounts = await easy_selection_of_workers(task_id, max_increase=120)
        # Отбираем воркеров, которые будут выполнять данный таск
        selection_workers = await selection_of_workers(task_id, count_workers, min_number_accounts)
        # Раскидываем по воркерам задание
        await sending_task(task_id, selection_workers)


async def circular_start_task(task_id):
    round = await db.get_round_from_task(task_id)
    next_round = round + 1  # Обозначаем для функций то, к какому раунду они должны готовится
    # Если таск только начат
    if round == 0:
        await _wait_before_starting()
    async with asyncio.Lock():
        # Получаем нужные строгие значения для круга
        count_workers, min_number_accounts = await strict_selection_of_workers(task_id, round=next_round)
        # Отбираем воркерсов
        selection_workers = selection_of_workers_for_round(task_id, str(round))
        # Раскидываем всех воркеров на нужный раунд
        await sending_task(task_id, selection_workers)
        # Обновляем круг у задания
        # Обновляем круги у тех воркеров, которых мы взяли


    # Добавить в сторожа тасков, только таски должны отбираться, после того, как прошло N времени и нужный собстна круг или случилось N выполнений
    # Если круги закончились и время тоже, сторожила должен выбрать самого пиздатого чела на данный момент с самым большим активом и акками, которые могут взять этот таск и позволить ему выполнить на определённое число акков и так по кругу чтобы каждый раз новые челы отбирались надо
    # Засунуть в принятия заданий проверку, что не было добито N заданий и не нужно выпускать новый круг
    # Если нужно сделать новый круг, то обращаемся к фанкшину circular_start_task и он опять делает всё тоже самое

    pass


async def _wait_before_starting():
    await sleep(25)

