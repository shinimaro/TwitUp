from aiogram import Bot

from bot_apps.task_push.task_push_keyboards import close_button
from config import load_config
from databases.database import db
from bot_apps.wordbank.wordlist import notifications

config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")


# Функция по управлению кнопкой и приоритетом, в случаях, когда пользователь неоднократно совершает нехорошие действия
async def change_task_buttons(tasks_msg_id: int) -> None:
    tg_id = await db.get_telegram_id_from_tasks_messages(tasks_msg_id)
    # Делаем запрос, который проверяет, есть ли что-то, что пользователь сделал, чтобы отключить ему кнопку и снизить приоритет
    action = await db.check_to_ignore_tasks(tg_id)
    # Если да, то выключаем ему кнопку
    if action:
        change = await db.turn_off_receiving_tasks(tg_id)
        # Если мы отключили ему кнопку и она не была включена до этого
        if change:
            # Отправляем уведомление об этом юзеру
            await button_disabling_messages(tg_id, action)


# Сообщение о том, что походу мы отключили тебе получение заданий, походу тебе некогда сейчас дела делать
async def button_disabling_messages(tg_id: int, action: str) -> None:
    await bot.send_message(
        chat_id=tg_id,
        text=notifications['disable_button'][action],
        reply_markup=await close_button())
