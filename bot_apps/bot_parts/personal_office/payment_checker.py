import asyncio
import datetime
from asyncio import sleep
from decimal import Decimal
from typing import Literal, TypedDict

from aiogram import Bot

from bot_apps.bot_parts.personal_office.payments import CryptoPay
from bot_apps.bot_parts.personal_office.personal_office_keyboards import payment_completed_builder
from bot_apps.other_apps.filters.limits_filters.message_limit_filter import MessageFilter
from bot_apps.other_apps.wordbank import payment
from config import load_config
from databases.database import Database
from databases.dataclasses_storage import PaymentData

db = Database()
config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
message_filter = MessageFilter()


class PaymentReceived(TypedDict):
    id: int
    walletId: str
    token: Literal['USDT', 'BUSD', 'USDC']
    value: int
    usd: Decimal
    txid: str
    chain: int
    timestamp: int
    time: datetime.datetime


async def payment_checker() -> None:
    crypto_pay = CryptoPay()
    while True:
        valid_wallets: bool = await db.check_valid_wallets()
        if valid_wallets:
            last_id: int = await db.get_last_trancaction_id() + 1  # Находим id, с которого стоит начать поиск
            payment_received: list[PaymentReceived] = (crypto_pay.Transactions(str(last_id)))[1]  # Забираем информацию о транзакциях
            cost_stb: float = await db.get_stb_coint_cost()  # Берём актуальный курс нашей монети
            for trancaction_dict in payment_received:  # Отдельно обрабатываем каждую полученную транзакцию
                await _payment_completed(
                    PaymentData(
                        transaction_id=trancaction_dict['id'],
                        wallet_id=int(trancaction_dict['walletId']),
                        amount=trancaction_dict['usd'],
                        issued_by_stb=trancaction_dict['usd'] * Decimal(cost_stb),
                        payment_date=trancaction_dict['time'],
                        token=trancaction_dict['token']))
        await sleep(30)


async def _payment_completed(payment_data: PaymentData) -> None:
    """Обновление баланса и запись в бд о пополнении"""
    tg_id: int = await db.record_of_payment(payment_data)
    await db.update_user_balance_afrter_payment(tg_id, payment_data.issued_by_stb)
    asyncio.get_event_loop().create_task(_send_message_on_payment(tg_id, payment_data.issued_by_stb))


async def _send_message_on_payment(tg_id: int, issued_by_stb) -> None:
    """Отправка сообщения о пополнении"""
    await message_filter(user_id=tg_id)
    await bot.send_message(
        chat_id=tg_id,
        text=payment['account_replenished'].format(issued_by_stb),
        reply_markup=payment_completed_builder())
