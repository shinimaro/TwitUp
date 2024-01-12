from dataclasses import dataclass

from aiogram import Bot

from bot_apps.bot_parts.personal_office.payments import CryptoPay
from bot_apps.bot_parts.personal_office.personal_office_keyboards import payment_completed_builder
from bot_apps.other_apps.filters.limits_filters.message_limit_filter import MessageFilter
from bot_apps.other_apps.wordbank import payment
from config import load_config
from databases.database import Database

db = Database()
config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
message_filter = MessageFilter()


# Хранилище вместо редиса
@dataclass()
class PaymentData:
    payment_data = ''


async def payment_checker() -> None:
    crypto_pay = CryptoPay()
    last_id = '0'
    while True:
        last_id, new_trancactions = crypto_pay.Transactions(last_id)


async def _payment_completed(tg_id, amount_payment, issued_by_stb, payment_method) -> None:
    """Обновление баланса и запись в бд о пополнении"""
    await db.record_of_payment(tg_id, amount_payment, issued_by_stb, payment_method)
    await db.update_user_balance_afrter_payment(tg_id, issued_by_stb)


async def _send_message_on_payment(tg_id: int, issued_by_stb) -> None:
    """Отправка сообщения о пополнении"""
    await message_filter(user_id=tg_id)
    await bot.send_message(
        chat_id=tg_id,
        text=payment['account_replenished'].format(issued_by_stb),
        reply_markup=payment_completed_builder())
