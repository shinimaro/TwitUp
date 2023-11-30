from asyncio import sleep
from datetime import datetime, timedelta, timezone
from typing import NoReturn

from databases.database import db


async def update_limits_tasks() -> NoReturn:
    """Фанкшн, обноввляющий лимиты на выполнения задания, как для воркеров, так и для всех аккаунтов"""
    while True:
        time_sleep = _get_time_until_midnight_msk()
        await sleep(time_sleep)
        await db.update_limits_users()
        await db.update_limits_accounts()


def _get_time_until_midnight_msk() -> float:
    """Фанкшин, определяющий, сколько осталось спать до следующего дня по МСК"""
    msk_timezone = timezone(timedelta(hours=3))
    midnight_msk = datetime.now(msk_timezone).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return (midnight_msk - datetime.now(msk_timezone)).total_seconds()
