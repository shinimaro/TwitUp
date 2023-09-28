import asyncio
from asyncio import sleep

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from bot_apps.databases.database import db
from bot_apps.adding_task.adding_task_keyboards import completed_task_keyboard_builder
from bot_apps.task_push.task_push_keyboards import ok_button_builder, ok_button_two_builder
from bot_apps.wordbank import task_completion, add_task
from config import load_config

config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")


# Функция, которая удаляет/меняет сообщения, в случае, если задание было полностью выполнено другими пользователями
async def function_distributor_task_messages(tasks_msg_id):
    # Выслать создателю таска сообщение о том, что он завершён
    await send_message_founder(tasks_msg_id)
    info_dict = await db.info_for_delete_messages(tasks_msg_id)
    tasks = []
    for key in info_dict:
        # Если мы только предложили пользователю сделать задание, но его уже успели сделать, то удаляем его
        if info_dict[key]['status'] in 'offer':
            tasks.extend([delete_message(info_dict[key], int(key[13:]))])
        else:
            tasks.extend([edit_message(info_dict[key], int(key[13:]))])
        if len(tasks) == 30:
            await asyncio.gather(*tasks)
            tasks = []
            await sleep(0.5)
    else:
        await asyncio.gather(*tasks)


# Сама функция для удаления
async def delete_message(info_dict, tasks_msg_id):
    await db.update_status_on_fully_completed(tasks_msg_id)
    try:
        await bot.delete_message(
            chat_id=info_dict['telegram_id'],
            message_id=info_dict['message_id'])
    except TelegramBadRequest:
        pass


# Функция, для изменения текста
async def edit_message(info_dict, tasks_msg_id):
    await db.update_status_on_fully_completed(tasks_msg_id)
    try:
        await bot.edit_message_text(
            chat_id=info_dict['telegram_id'],
            message_id=info_dict['message_id'],
            text=task_completion['task_ended'],
            reply_markup=await ok_button_two_builder(tasks_msg_id))
    except TelegramBadRequest:
        pass


# Функция для отправки сообщения таскодателю
async def send_message_founder(tasks_msg_id):
    # Если задание ещё не отмечено, как завершённое, то кидаем уведомление таскодателю
    if await db.completed_task_status(tasks_msg_id):
        # Возможно, эти 3 функции лучше объединить в 1 запрос
        founder_id = await db.get_id_founder_task(tasks_msg_id)
        actions = await db.get_task_actions(tasks_msg_id)
        executions = await db.get_executions(tasks_msg_id)
        actions_dict = {'subscriptions': f'<b>+{executions} подписчиков (профиль)</b>',
                        'likes': f'<b>+{executions} лайков (пост)</b>',
                        'retweets': f'<b>+{executions} ретвитов (пост)</b>',
                        'comments': f'<b>+{executions} комментариев (пост)</b>'}
        actions_text = ''
        for action in actions:
            actions_text += actions_dict[action] + '\n'
        try:
            await bot.send_message(
                chat_id=founder_id,
                text=add_task['task_completed'].format(actions_text),
                reply_markup=await completed_task_keyboard_builder())
        except TelegramBadRequest:
            pass

