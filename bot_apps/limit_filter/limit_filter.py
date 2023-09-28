from datetime import time
import time
from asyncio import sleep
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery


# Ебучий фильтр, который я овер долго понимал, как правильно сделать с этой блять асинхронностью, постоянными апдейтами и разными экземплярами фильтра
class MainFiter(BaseFilter):
    user_messages = {}  # общий словарь сообщений
    users_dict = {}  # личный словарь для каждого пользователя
    wait = 1
    work_flag = False

    async def __call__(self, message: Message = None, callback: CallbackQuery = None):
        # Инициализация переменных
        user_id = message.from_user.id if message else callback.from_user.id
        MainFiter.user_messages.setdefault('first_message', time.time())
        MainFiter.user_messages.setdefault('all_messages', [])
        MainFiter.users_dict.setdefault(user_id, time.time())
        MainFiter.user_messages['all_messages'].append(user_id)
        # print('Общий список: ', MainFiter.user_messages['all_messages'])
        # Если пользователь есть уже 2 раза в общем списке (написал 3 сообщения быстрее 1 раза в секунду)
        if MainFiter.user_messages['all_messages'].count(user_id) >= 3:
            # Игнорируем пользователя, если он отправил сообщение, а бот ему ещё на прошлые не ответил
            if MainFiter.user_messages['all_messages'].count(user_id) > 3:
                # Удаляем старое сообщение
                last_index = len(MainFiter.user_messages['all_messages']) - MainFiter.user_messages['all_messages'][::-1].index(user_id) - 1
                MainFiter.user_messages['all_messages'].pop(last_index)
                return False
            # Проверяем время последнего сообщения
            time_difference_2 = time.time() - MainFiter.users_dict[user_id]
            # Если прошло меньше времени, которое необходимо (1 секунда)
            if time_difference_2 < MainFiter.wait:
                # Пусть спит до конца секунды
                await sleep(MainFiter.wait - time_difference_2 + 0.2)
            # Меняем 3 первых его user_id из общего списка
            count = 0
            for i in range(len(MainFiter.user_messages['all_messages'])):
                if MainFiter.user_messages['all_messages'][i] == user_id:
                    MainFiter.user_messages['all_messages'][i] = None
                    count += 1
                if count == 3:
                    break
            # Обновляем время первого сообщения пользователя
            MainFiter.users_dict[user_id] = time.time()


        # Если функция, которая осуществляет сладкий сон боту, сейчас в действии, то останавливаем остальные колбеки
        while MainFiter.work_flag:
            await sleep(0.1)  # Да, я знаю, что это кривое исполнение. А что вы мне сделаете, я в другом городе
        # Если набралось более 30 сообщений в боте
        if len(MainFiter.user_messages['all_messages']) >= 30:
            # Запускаем функцию, которая поспит необходимое время, до конца секунды
            await self.mainfilter()
        return True

    # Функция для сна
    async def mainfilter(self):
        MainFiter.work_flag = True
        # Находим, сколько прошло после последнего сообщения
        time_difference = time.time() - MainFiter.user_messages['first_message']
        # Если прошло меньше указанного времени (1 секунды)
        if time_difference < MainFiter.wait:
            # Спим, то время, которое необходимо, чтобы прошла 1 секунда
            await sleep(MainFiter.wait - time_difference)
        # Записываем новую точку первого сообщения, и убираем первых 30 пользователей, которым уже ответили, остальные остаются в общем списке
        MainFiter.user_messages = {'first_message': time.time(), 'all_messages': MainFiter.user_messages['all_messages'][30:]}
        MainFiter.work_flag = False























# # Список в виде очереди
# # Чёт пока не хочу его делать, т.к. без списка индивидуальный фильтр для пользователей отлетает
#
# class MainFiters(BaseFilter):
#     first_message = time.time()
#     wait = 3
#     work_flag = False
#     update_queue = Queue()  # Очередь для апдейтов
#
#     async def __call__(self, message: Message = None, callback: CallbackQuery = None):
#         # Инициализация переменных
#         user_id = message.from_user.id if message else callback.from_user.id
#         await self.update_queue.put((message if message else callback))
#
#
#         print('В очередь было добавлено ', self.update_queue.qsize())
#         while self.update_queue.qsize() >= 1:
#             print('Запускаю функцию')
#             await self.sus()
#             for _ in range(1):
#                 await self.update_queue.get()
#                 self.update_queue.task_done()
#                 print('Очередь ', self.update_queue.qsize())
#         return True
#
#
#
#     async def sus(self):
#         print(1)
#         # Находим, сколько прошло после последнего сообщения
#         time_difference = time.time() - MainFiter.user_messages['first_message']
#         # Если прошло меньше указанного времени (1 секунды)
#         if time_difference < MainFiter.wait:
#             # Спим, то время, которое необходимо, чтобы прошла 1 секунда
#             await sleep(MainFiter.wait - time_difference)
#         # Записываем новую точку первого сообщения, и убираем первых 30 пользователей, которым уже ответили, остальные остаются в общем списке
#         MainFiter.user_messages = {'first_message': time.time(),
#                                    'all_messages': MainFiter.user_messages['all_messages'][1:]}
#
#     async def mainfilter(self):
#         MainFiter.work_flag = True
#         # Находим, сколько прошло после последнего сообщения
#         time_difference = time.time() - MainFiter.user_messages['first_message']
#         # Если прошло меньше указанного времени (1 секунды)
#         if time_difference < MainFiter.wait:
#             # Спим, то время, которое необходимо, чтобы прошла 1 секунда
#             await sleep(MainFiter.wait - time_difference)
#         # Записываем новую точку первого сообщения, и убираем первых 30 пользователей, которым уже ответили, остальные остаются в общем списке
#         MainFiter.user_messages = {'first_message': time.time(), 'all_messages': MainFiter.user_messages['all_messages'][1:]}
#         if len(MainFiter.user_messages['all_messages']) >= 1:
#             await self.mainfilter()
#         else:
#             MainFiter.work_flag = False
