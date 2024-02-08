import datetime
from asyncio import sleep
from typing import NoReturn, NewType

from databases.database import Database
from databases.dataclasses_storage import PriorityChange

db = Database()
TgId = NewType('TgId', int)  # Поставил просто попробовать эту штуку


async def priority_updater() -> None:
    """Сторож, накидывающий приоритета, если юзер долго не получает задания"""
    users: list[TgId] = await db.get_all_users_for_up_priority()
    await _increase_users_priority(users)


async def _increase_users_priority(users: list[TgId]) -> None:
    """Повысить приоритет пользователей(я)"""
    priority_change: PriorityChange = await db.get_priority_change()
    await db.up_priority_users(users, priority_change['downtime_more_20_min'])
    await db.update_date_of_update(users)


async def apply_priority(tg_id: TgId) -> None:
    """Проверка на то, можно ли юзеру немножко повысить приоритет после отключения им кнопки"""
    time_after_update: datetime.timedelta = await db.get_time_after_update_button(tg_id)
    # Если прошло более 80% от 20 минут, т.е. времени, после которого начисляется приоритет, то надо всё же его начислить
    if time_after_update.total_seconds() / 60 > (20 * 0.8):
        await _increase_users_priority([tg_id])
    else:
        await db.update_date_of_update([tg_id])


async def priority_updater_checker() -> NoReturn:
    while True:
        await sleep(5 * 60)
        await priority_updater()
