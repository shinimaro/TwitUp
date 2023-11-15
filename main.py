import asyncio
from typing import NoReturn

from aiogram import Dispatcher, Bot
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot_apps.adding_task import adding_task_handlers
from bot_apps.filters.ban_filters.is_banned import IsBanned
from bot_apps.filters.ban_filters.they_banned import TheyBanned
from bot_apps.other_apps.help_center import help_center_handlers
from bot_apps.other_apps.main_menu import main_menu_handlers
from bot_apps.other_apps.task_setting import task_setting_handlers
from bot_apps.other_apps.task_setting.task_setting_reminder import function_distributor_reminders
from bot_apps.personal_office import personal_office_handlers
from bot_apps.personal_office.first_steps import first_steps_handlers
from bot_apps.personal_office.referral_office import referral_office_handlers
from bot_apps.task_push import task_push_handlers
from bot_apps.task_push.system.checking_tasks import main_task_checker
from bot_apps.task_push.system.level_watchman import level_watchman_checker
from bot_apps.task_push.system.sending_tasks import sending_tasks
from bot_apps.task_push.system.sending_tasks.completing_completion import completing_completion_checker
from bot_apps.wordbank import commands
from config.config import load_config
from databases.database import db
from parsing.main.master_function import Master

config = load_config()
numbers_webdrivers = 0
is_banned = IsBanned()
they_banned = TheyBanned()


async def start_bot() -> NoReturn:
    storage = MemoryStorage()

    bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
    dp = Dispatcher(storage=storage)

    print('Бот работает')
    dp.include_router(main_menu_handlers.router)  # Должен быть самым первым, т.к. там стоит мой фильтр

    dp.include_router(sending_tasks.router)
    dp.include_router(task_push_handlers.router)

    dp.include_router(adding_task_handlers.router)
    dp.include_router(help_center_handlers.router)
    dp.include_router(task_setting_handlers.router)
    dp.include_router(first_steps_handlers.router)
    dp.include_router(referral_office_handlers.router)
    dp.include_router(personal_office_handlers.router)

    await bot.delete_webhook(drop_pending_updates=True)  # Для пропуска сообщений, когда бот неактивен
    dp.startup.register(bot_menu_builder)
    await dp.start_polling(bot)


# Добавляет команды в бота, которые будут в кнопке "меню" слева от ввода сообщения
async def bot_menu_builder(bot):
    main_menu_commands = [BotCommand(command='/start',
                                     description=commands['/start'])]
    await bot.set_my_commands(main_menu_commands)


# Запускает вебдрайверы
async def start_webdrivers():
    master = Master()
    await master.generate_main_driver()
    print('Вебдрайверы готовы')


async def main():
    await db.connect()                     # Коннект к базе данных
    await is_banned.loading_blocked_users()         # Загрузка юзеров, которые в блоке у нас
    await they_banned.loading_they_blocked_users()  # Загрузка юзеров, у которых мы сами в блоке
    # await start_webdrivers()             # Запуск всех вебдрайверов
    await asyncio.gather(
        function_distributor_reminders(),  # Напоминание о том, что юзер уже давно не включал задание
        main_task_checker(),               # Напоминалка о том, что нужно выполнить таск + сообщение о том, что воркер опоздал
        level_watchman_checker(),          # Проверка выполнения тасков на свой уровень
        # completing_completion_checker(), # Проверка отстающийх по выполнению тасков и их добивка
        start_bot())                       # Запуск бота


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
