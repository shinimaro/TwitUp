import asyncio
import time
from typing import TypedDict
from aiogram.types import Message, CallbackQuery
from aiogram.filters import BaseFilter
from asyncio import sleep


class PersonalMessages(TypedDict):
    count_messages: int
    time_first_message: float
    personal_event: asyncio.Event
    personal_work_flag: bool


# Главный фильтр для филтра сообщений и колбеков
class CommonFilter(BaseFilter):
    wait: int
    counter: int
    count_messages: int
    count_personal_messages: int
    work_flag: bool
    event: asyncio.Event()
    time_message: float
    personal_messages: dict[int, PersonalMessages]

    async def __call__(self, obj: Message | CallbackQuery = None, user_id: int = None) -> True:
        user_id = obj.from_user.id if obj else user_id
        await self.initialization_dict(user_id)
        # Часть с персональным фильтром
        if self.personal_messages[user_id]['personal_work_flag']:
            await self.personal_await_completion(user_id)
        self.personal_messages[user_id]['count_messages'] += 1
        if self.personal_messages[user_id]['count_messages'] > self.count_personal_messages:
            await self.personal_limit_filter(user_id)

        # Часть с общим фильтром, если бот отправил более 40 сообщений
        if self.work_flag:
            await self.await_completion()
        self.counter += 1
        if self.counter > self.count_messages:
            await self.limit_filter()
        return True

    # Фильтр, который следит за тем, чтобы бот не отправлял много сообщений
    async def limit_filter(self) -> None:
        self.work_flag = True
        time_difference: float = time.time() - self.time_message
        if time_difference < self.wait:
            await sleep(self.wait - time_difference)
            self.event.set()
        self.time_message = time.time()
        self.counter = 0
        self.work_flag = False

    async def personal_limit_filter(self, user_id: int) -> None:
        self.personal_messages[user_id]['personal_work_flag'] = True
        time_difference: float = time.time() - self.personal_messages[user_id]['time_first_message']
        if time_difference < self.wait:
            await sleep(self.wait + 0.1 - time_difference)
            self.personal_messages[user_id]['personal_event'].set()
        self.personal_messages[user_id]['time_first_message'] = time.time()
        self.personal_messages[user_id]['count_messages'] = 0
        self.personal_messages[user_id]['personal_work_flag'] = False

    # Метод для плавного пропуска сообщений, которые могут пройти дальше, остальные будут продолжать ожидать
    async def await_completion(self) -> None:
        await sleep(0.1)  # Минимальная задержка, ибо без неё эта дура не работает
        await self.event.wait()
        if self.work_flag:
            await self.await_completion()

    async def personal_await_completion(self, user_id: int) -> None:
        await sleep(0.1)
        await self.personal_messages[user_id]['personal_event'].wait()
        if self.personal_messages[user_id]['personal_work_flag']:
            await self.personal_await_completion(user_id)

    async def initialization_dict(self, user_id: int) -> None:
        self.personal_messages.setdefault(user_id, {})
        self.personal_messages[user_id].setdefault('count_messages', 0)
        self.personal_messages[user_id].setdefault('time_first_message', time.time())
        self.personal_messages[user_id].setdefault('personal_event', asyncio.Event())
        self.personal_messages[user_id].setdefault('personal_work_flag', False)
