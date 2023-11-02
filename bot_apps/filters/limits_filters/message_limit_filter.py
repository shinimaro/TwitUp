import asyncio
import time

from bot_apps.filters.limits_filters.base_filter import CommonFilter, PersonalMessages


# Отдельный фильтр для сообщений
class MessageFilter(CommonFilter):
    wait = 5
    counter = 0
    count_messages = 40
    count_personal_messages = 2
    work_flag = False
    event = asyncio.Event()
    time_message = time.time()
    personal_messages: dict[int, PersonalMessages] = {}




