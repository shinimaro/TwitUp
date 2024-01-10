import asyncio
import datetime
from asyncio import sleep
from typing import NoReturn

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from bot_apps.bot_parts.task_setting.task_setting_keyboards import keyboard_under_reminder_builder
from bot_apps.other_apps.filters.limits_filters.message_limit_filter import MessageFilter
from bot_apps.other_apps.wordbank import setting
from config import load_config
from databases.database import Database

config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
db = Database()
message_filter = MessageFilter()


# Функция, которая будет напоминать пользователю о том, что он отключил задания
async def setting_reminder():
    users_dict = await db.all_users_task_notifications()

    tasks = []
    for user, value in users_dict.items():
        time_difference = datetime.datetime.now().astimezone() - value['countdown']
        # Если прошло достаточно времени для добавления первого этапа
        if time_difference.total_seconds() - 60 * 60 * 24 >= 0 and value['last_step'] == 'step_0':
            tasks.extend([remind_users_about_notifications(users_dict[user], user)])
        # Для второго этапа
        elif time_difference.total_seconds() - 60 * 60 * 72 >= 0 and value['last_step'] == 'step_1':
            tasks.extend([remind_users_about_notifications(users_dict[user], user)])
        # Для третьего этапа
        elif time_difference.total_seconds() - 60 * 60 * 168 >= 0 and value['last_step'] == 'step_2':
            tasks.extend([remind_users_about_notifications(users_dict[user], user)])

        # По-маленьку сообщения пусть высылает, чтобы не нагружать бота
        if len(tasks) == 3:
            await asyncio.gather(*tasks)
            await sleep(3)
    else:
        await asyncio.gather(*tasks)
        await sleep(3)


# Функция для отправки уведомления о том, что пользователь долго не включал уведомления
async def remind_users_about_notifications(info_dict, tg_id):
    await db.update_step_task_notification(tg_id, f"step_{int(info_dict['last_step'][5:]) + 1}")
    try:
        await message_filter(user_id=tg_id)
        await bot.send_message(
            chat_id=tg_id,
            text=setting['type_notification'][info_dict['last_step']],
            reply_markup=keyboard_under_reminder_builder())
    except TelegramBadRequest:
        pass


async def function_distributor_reminders() -> NoReturn:
    while True:
        await setting_reminder()
        await sleep(20 * 60)
