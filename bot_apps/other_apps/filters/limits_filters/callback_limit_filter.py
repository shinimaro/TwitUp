import asyncio
import time

from bot_apps.other_apps.filters.limits_filters.base_filter import CommonFilter, PersonalMessages


# Такой же фильтр, как и в message_limimt, но для колбеков
class CallbackFilter(CommonFilter):
    wait = 1
    counter = 0
    count_messages = 40
    count_personal_messages = 2
    work_flag = False
    event = asyncio.Event()
    time_message = time.time()
    personal_messages: dict[int, PersonalMessages] = {}
