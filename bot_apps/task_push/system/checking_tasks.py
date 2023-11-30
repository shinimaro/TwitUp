import asyncio
from datetime import datetime
from typing import NoReturn

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from bot_apps.filters.ban_filters.they_banned import TheyBanned
from bot_apps.filters.limits_filters.callback_limit_filter import CallbackFilter
from bot_apps.filters.limits_filters.message_limit_filter import MessageFilter
from bot_apps.task_push.system.change_task_button import change_task_buttons
from bot_apps.task_push.system.sending_tasks.completing_completion import WaitingTasks
from databases.database import db
from bot_apps.task_push.task_push_keyboards import clear_button_builder, accounts_for_task_builder, \
    complete_task_builder, get_link_comment_builder
from bot_apps.task_push.task_push_text import context_task_builder, please_give_me_link
from bot_apps.wordbank import task_completion
from config import load_config

config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
callback_filter = CallbackFilter()
message_filter = MessageFilter()
they_banned = TheyBanned()


# Функция, которая проверяет все запущенные задания на то, что они укладываются во времени
async def check_task_message():
    all_tasks_messages = await db.info_all_tasks_messages()
    tasks = []
    for key in all_tasks_messages:
        time_difference = datetime.now().astimezone() - all_tasks_messages[key]['start_time']
        # Если время вышло, то пишем пользователю, что его время вышло
        if time_difference.total_seconds() >= 10 * 60:
            tasks.extend([edit_task_message(all_tasks_messages[key], int(key[13:]))])
        # Если после начала выполнения таска осталось менее 8 минут, напоминаем пользователю о том, что осталось мало время
        elif 7.5 * 60 <= time_difference.total_seconds() <= 9 * 60 and not all_tasks_messages[key]['reminder']:
            tasks.extend([remind_edit_task_message(all_tasks_messages[key], int(key[13:]))])
    await asyncio.gather(*tasks)


# Функция, сообщающая пользователю о том, что он не успел завершить задание
async def edit_task_message(info_dict, tasks_msg_id):
    if await db.check_status_checking(tasks_msg_id):  # Если статус задания не находится в статусе проверки
        await db.update_status_on_scored(tasks_msg_id)  # Записываем дату удаления задания и статус
        await change_task_buttons(tasks_msg_id)  # Проверим обязательно, какой раз он уже забивает на таск
        try:
            await callback_filter(user_id=info_dict['telegram_id'])
            await bot.edit_message_text(
                chat_id=info_dict['telegram_id'],
                message_id=info_dict['message_id'],
                text=task_completion['scored_on_task'],
                reply_markup=await clear_button_builder(tasks_msg_id))
        except TelegramForbiddenError:
            await they_banned.adding_they_blocked_users(info_dict['telegram_id'])


# Напоминалка, которая определяет по статусу пользователя, на каком он этапе и отправляет пользователю таск + сообщение о том, что осталось всего пару минут
# Важно - все ответы были спизжены с хендлеров, поэтому, если будешь что-то менять в них, меняй и здесь
async def remind_edit_task_message(info_dict, tasks_msg_id):
    # Если статус задания не находится в статусе проверки
    if await db.check_status_checking(tasks_msg_id):
        # Пользователь выбирает задание для таска
        if info_dict['status'] == 'start_task':
            accounts_dict = await db.accounts_for_task(info_dict['telegram_id'], tasks_msg_id)
            text = task_completion['dop_text']['for_start_task'] + task_completion['select_account']
            reply_markup = await accounts_for_task_builder(accounts_dict, tasks_msg_id)
        # Пользователь проходит таск/встрял на каком-то задании при прохождении таска
        elif info_dict['status'].startswith('process'):
            key = info_dict['status'][8:] if info_dict['status'] != 'process' else 'process'
            dop_text = task_completion['dop_text']['for_process'] if info_dict['status'] == 'process' else task_completion['dop_text'][f'for_process_{key}']
            text = await context_task_builder(tasks_msg_id, info_dict['account'], None if key == 'process' else key) + dop_text
            reply_markup = await complete_task_builder(info_dict['telegram_id'], tasks_msg_id)
        # Пользователь вводит ссылку на комментарий
        elif info_dict['status'] == 'waiting_link':
            text = await please_give_me_link(tasks_msg_id, info_dict['account']) + task_completion['dop_text']['for_waiting_link']
            reply_markup = await get_link_comment_builder(info_dict['telegram_id'], tasks_msg_id)

        # Удаление старого сообщения
        await bot.delete_message(
            chat_id=info_dict['telegram_id'],
            message_id=info_dict['message_id'])

        # Добавление этого же сообщения снова
        await message_filter(user_id=info_dict['telegram_id'])
        message_id = await bot.send_message(
            chat_id=info_dict['telegram_id'],
            text=text,
            reply_markup=reply_markup,
            disable_web_page_preview=True)

        # Обновление message_id
        await db.change_task_message_id(tasks_msg_id, message_id.message_id)

        # Запись в ремайндер
        await db.update_reminder(tasks_msg_id)


async def main_task_checker() -> NoReturn:
    waiting_tasks = WaitingTasks(15, 8 * 60)
    while True:
        await waiting_tasks()
        await check_task_message()




