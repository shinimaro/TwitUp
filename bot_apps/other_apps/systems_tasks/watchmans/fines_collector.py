from asyncio import gather, sleep
from typing import NoReturn

from aiogram import Bot

from bot_apps.other_apps.filters.limits_filters.message_limit_filter import MessageFilter
from bot_apps.bot_parts.adding_task.adding_task_text import round_numbers
from bot_apps.bot_parts.personal_tasks.personal_task_keyboards import collect_fines_keyboard
from bot_apps.other_apps.wordbank import personal_task
from config import load_config
from databases.database import Database
from databases.dataclasses_storage import AllFinesInfo, FineInfo

config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
db = Database()
message_filter = MessageFilter()


async def _fines_collector() -> None:
    """Сбор штрафов и их рассылка"""
    fines_dict: dict[int, AllFinesInfo] = await db.get_number_uncollected_fines()
    if fines_dict:
        tasks_list = []
        for tg_id, fines_info in fines_dict.items():
            # Сообщение отправляется, если, набралось более 10 штрафов, либо с момента последнего сообщения прошло более 3 часов и накопилось более 3 штрафов, либо, 1 штраф есть, но с момента последнего уведомления прошло более 8 часов
            if fines_info.fines_info.count_fines > 10 or \
                    (fines_info.fines_info.count_fines > 3 and (not fines_info.fines_info.last_message or fines_info.fines_info.last_message.total_seconds() > 3 * 60 * 60)) or \
                    (not fines_info.fines_info.last_message or fines_info.fines_info.last_message.total_seconds() > 8 * 60 * 60):
                tasks_list.extend([_send_message_for_fine(tg_id, fines_info.fines_list)])
        await gather(*tasks_list)


async def _send_message_for_fine(tg_id: int, fines_list: list[FineInfo]) -> None:
    """Фанкшн, высылающий сообщения о штрафах"""
    await message_filter(user_id=tg_id)
    await bot.send_message(chat_id=tg_id,
                           text=personal_task['collected_fines'].format(_sum_fines(fines_list)),
                           reply_markup=collect_fines_keyboard(await db.get_send_id(_get_fines_id(fines_list))))  # Жесть матрёшка
    await _update_date_send_fines(fines_list)


async def _update_date_send_fines(fines_list: list[FineInfo]) -> None:
    """Фанкшн, обновляющий дату сбора штрафов"""
    fines_id_list = _get_fines_id(fines_list)
    await db.change_send_time_fines(fines_id_list)


def _get_fines_id(fines_list: list[FineInfo]):
    return [fine.fines_id for fine in fines_list]


def _sum_fines(fines_list: list[FineInfo]) -> float:
    return round_numbers(sum([fine.already_bought for fine in fines_list]))


async def check_fines_collector() -> NoReturn:
    """Запускает сборщик штрафов раз в 20 минут"""
    while True:
        await _fines_collector()
        await sleep(20 * 60)
