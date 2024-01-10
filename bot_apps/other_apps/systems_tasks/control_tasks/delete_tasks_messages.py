import asyncio

from aiogram import Bot

from bot_apps.other_apps.filters.limits_filters.callback_limit_filter import CallbackFilter
from bot_apps.other_apps.filters.limits_filters.message_limit_filter import MessageFilter
from bot_apps.bot_parts.adding_task.adding_task_keyboards import completed_task_keyboard_builder
from bot_apps.other_apps.systems_tasks.control_users.change_task_button import change_task_buttons
from bot_apps.bot_parts.task_push.task_push_keyboards import ok_button_two_builder
from bot_apps.bot_parts.task_push.task_push_text import chain_letter_builder
from bot_apps.other_apps.wordbank import task_completion, add_task
from config import load_config
from databases.database import Database

config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
db = Database()
callback_filter = CallbackFilter()
message_filter = MessageFilter()


# Функция, которая удаляет/меняет сообщения, в случае, если задание было полностью выполнено другими пользователями, а также отправляет письмо счастья тем, кто на проверке задания, но не успел
async def function_distributor_task_messages(tasks_msg_id):
    # Выслать создателю таска сообщение о том, что он завершён
    await send_message_founder(tasks_msg_id)
    task_id = await db.get_task_id_from_tasks_messages(tasks_msg_id)
    info_dict = await db.info_for_delete_messages(task_id)
    tasks = []
    for key in info_dict:
        # Если мы только предложили пользователю сделать задание, но его уже успели сделать, то удаляем его
        if info_dict[key]['status'] in 'offer':
            tasks.extend([delete_message(info_dict[key], key)])
        else:
            tasks.extend([edit_message(info_dict[key], key)])
    await asyncio.gather(*tasks)


# Функция для удаления
async def delete_message(info_dict, tasks_msg_id):
    await db.change_priority_ignore_task(tasks_msg_id)  # Понижение приоритета юзера
    await db.update_status_on_fully_completed(tasks_msg_id)  # Изменить статус задания
    await db.decrease_counter_execute(tasks_msg_id)  # Понизить счётчик отправленных заданий
    await db.add_del_time_in_task(tasks_msg_id)  # Запись времени удаления
    await change_task_buttons(tasks_msg_id)  # Отключение кнопки, если юзер много игнорит тасков
    await bot.delete_message(
        chat_id=info_dict['telegram_id'],
        message_id=info_dict['message_id'])


# Функция, для изменения текста
async def edit_message(info_dict, tasks_msg_id):
    if await db.check_status_checking(tasks_msg_id):  # Если в этот момент задание проверялось
        text = task_completion['task_ended']
    else:
        text = await chain_letter_builder(tasks_msg_id)  # Если юзер просто его выполнял
    await db.change_priority_not_completed_task(tasks_msg_id)  # Повышение рейтинга юзера
    await db.update_status_on_fully_completed(tasks_msg_id)  # Изменения в сообщении о задании
    await db.add_del_time_in_task(tasks_msg_id)  # Запись времени удаления
    await callback_filter(user_id=info_dict['telegram_id'])
    await bot.edit_message_text(
        chat_id=info_dict['telegram_id'],
        message_id=info_dict['message_id'],
        text=text,
        reply_markup=ok_button_two_builder(tasks_msg_id))


# Функция для отправки сообщения таскодателю
async def send_message_founder(tasks_msg_id):
    # Если задание ещё не отмечено, как завершённое, то кидаем уведомление таскодателю
    if await db.completed_task_status(tasks_msg_id):
        founder_id = await db.get_id_founder_task(tasks_msg_id)
        actions = await db.get_task_actions(tasks_msg_id)
        executions = await db.get_executions(tasks_msg_id)
        actions_dict = {'subscriptions': f'<b>+{executions} подписчиков (профиль)</b>',
                        'likes': f'<b>+{executions} лайков (пост)</b>',
                        'retweets': f'<b>+{executions} ретвитов (пост)</b>',
                        'comments': f'<b>+{executions} комментариев (пост)</b>'}
        actions_text = ''.join([actions_dict[action] + '\n' for action in actions])
        await message_filter(user_id=founder_id)
        await bot.send_message(
            chat_id=founder_id,
            text=add_task['task_completed'].format(actions_text),
            reply_markup=completed_task_keyboard_builder())
