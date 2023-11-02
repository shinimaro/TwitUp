import asyncio
import time

from bot_apps.filters.limits_filters.base_filter import CommonFilter, PersonalMessages


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





# Старый фильтр
# class CallbackFiter(BaseFilter):
#     user_messages = {}  # общий словарь сообщений
#     users_dict = {}  # личный словарь для каждого пользователя
#     wait = 1
#     work_flag = False
#
#     async def __call__(self, callback: CallbackQuery = None):
#         # Инициализация переменных
#         user_id = callback.from_user.id
#         CallbackFiter.user_messages.setdefault('first_message', time.time())
#         CallbackFiter.user_messages.setdefault('all_messages', [])
#         CallbackFiter.users_dict.setdefault(user_id, time.time())
#         CallbackFiter.user_messages['all_messages'].append(user_id)
#         # print('Общий список: ', CallbackFiter.user_messages['all_messages'])
#         # Если пользователь есть уже 2 раза в общем списке (написал 3 сообщения быстрее 1 раза в секунду)
#         if CallbackFiter.user_messages['all_messages'].count(user_id) >= 3:
#             # Игнорируем пользователя, если он отправил сообщение, а бот ему ещё на прошлые не ответил
#             if CallbackFiter.user_messages['all_messages'].count(user_id) > 3:
#                 # Удаляем старое сообщение
#                 last_index = len(CallbackFiter.user_messages['all_messages']) - CallbackFiter.user_messages[
#                                                                                     'all_messages'][::-1].index(
#                     user_id) - 1
#                 CallbackFiter.user_messages['all_messages'].pop(last_index)
#                 return False
#             # Проверяем время последнего сообщения
#             time_difference_2 = time.time() - CallbackFiter.users_dict[user_id]
#             # Если прошло меньше времени, которое необходимо (1 секунда)
#             if time_difference_2 < CallbackFiter.wait:
#                 # Пусть спит до конца секунды
#                 await sleep(CallbackFiter.wait - time_difference_2 + 0.2)
#             # Меняем 3 первых его user_id из общего списка
#             count = 0
#             for i in range(len(CallbackFiter.user_messages['all_messages'])):
#                 if CallbackFiter.user_messages['all_messages'][i] == user_id:
#                     CallbackFiter.user_messages['all_messages'][i] = None
#                     count += 1
#                 if count == 3:
#                     break
#             # Обновляем время первого сообщения пользователя
#             CallbackFiter.users_dict[user_id] = time.time()
#
#         # Если функция, которая осуществляет сладкий сон боту, сейчас в действии, то останавливаем остальные колбеки
#         while CallbackFiter.work_flag:
#             await sleep(0.1)  # Да, я знаю, что это кривое исполнение. А что вы мне сделаете, я в другом городе
#         # Если набралось более 30 сообщений в боте
#         if len(CallbackFiter.user_messages['all_messages']) >= 30:
#             # Запускаем функцию, которая поспит необходимое время, до конца секунды
#             await self.mainfilter()
#         return True
#
#     # Функция для сна
#     async def mainfilter(self):
#         CallbackFiter.work_flag = True
#         # Находим, сколько прошло после последнего сообщения
#         time_difference = time.time() - CallbackFiter.user_messages['first_message']
#         # Если прошло меньше указанного времени (1 секунды)
#         if time_difference < CallbackFiter.wait:
#             # Спим, то время, которое необходимо, чтобы прошла 1 секунда
#             await sleep(CallbackFiter.wait - time_difference)
#         # Записываем новую точку первого сообщения, и убираем первых 30 пользователей, которым уже ответили, остальные остаются в общем списке
#         CallbackFiter.user_messages = {'first_message': time.time(),
#                                        'all_messages': CallbackFiter.user_messages['all_messages'][30:]}
#         CallbackFiter.work_flag = False
