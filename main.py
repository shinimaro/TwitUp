import asyncio
from typing import NoReturn

from aiogram import Dispatcher, Bot
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot_apps.personal_task import personal_task_handlers
from bot_apps.panels.admin_panel import admin_panel_handlers
from bot_apps.personal_task.adding_task import adding_task_handlers
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
from bot_apps.task_push.system.fines_collector import check_fines_collector
from bot_apps.task_push.system.level_watchman import level_watchman_checker
from bot_apps.task_push.system.sending_tasks import sending_tasks
from bot_apps.task_push.system.sending_tasks.start_task import start_new_round_checker
from bot_apps.task_push.system.update_task_limits import update_limits_tasks
from bot_apps.wordbank import commands
from config.config import load_config
from databases.database import db
from parsing.main.master_function import Master


async def start_bot() -> NoReturn:
    storage = MemoryStorage()
    config = load_config()
    bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
    dp = Dispatcher(storage=storage)

    print('Бот работает')
    dp.include_router(main_menu_handlers.router)  # Должен быть самым первым, т.к. там стоит мой фильтр

    dp.include_router(sending_tasks.router)  # Убрать потом
    dp.include_router(task_push_handlers.router)
    dp.include_router(personal_task_handlers.router)
    dp.include_router(admin_panel_handlers.router)
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


# Включает всех сторожей
async def activate_all_watchman():
    tasks = [
        function_distributor_reminders(),  # Напоминание о том, что юзер уже давно не включал задание
        start_new_round_checker(),         # Проверка на то, что нужно рассылать новый рау
        main_task_checker(),               # Напоминалка о том, что нужно выполнить таск + сообщение о том, что воркер опоздал
        level_watchman_checker(),          # Проверка выполнения тасков на свой уровень
        update_limits_tasks(),             # Обновление счётчиков лимиток на таски раз в день для юзеров и аккаунтов
        check_fines_collector(),           # Сборщик штрафов
        # completing_completion_checker(),   # Проверка отстающийх по выполнению тасков и их добивка
    ]
    running_tasks = [asyncio.create_task(task) for task in tasks]  # Запускаем каждую задачу в фоне
    await asyncio.gather(*running_tasks)


# Заполнить списки тех, кто у нас в бане и у кого в бане мы сами
async def fill_ban_lists():
    is_banned = IsBanned()
    they_banned = TheyBanned()
    await is_banned.loading_blocked_users()         # Загрузка юзеров, которые в блоке у нас
    await they_banned.loading_they_blocked_users()  # Загрузка юзеров, у которых мы сами в блоке


async def main():
    await db.connect()               # Коннект к базе данных
    await fill_ban_lists()           # Загрузка бан списков
    # await start_webdrivers()         # Запуск всех вебдрайверов
    await asyncio.gather(
        activate_all_watchman(),   # Запуск сторожей
        start_bot())               # Запуск бота


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
