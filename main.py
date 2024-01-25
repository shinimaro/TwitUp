import asyncio
from typing import NoReturn

from aiogram import Dispatcher, Bot
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand
from redis.asyncio import Redis

from bot_apps.bot_parts.adding_task import adding_task_handlers
from bot_apps.bot_parts.help_center import help_center_handlers
from bot_apps.bot_parts.main_menu import main_menu_handlers
from bot_apps.bot_parts.panels.admin_panel import admin_panel_handlers
from bot_apps.bot_parts.panels.support_panel import support_panel_handlers
from bot_apps.bot_parts.personal_office import personal_office_handlers
from bot_apps.bot_parts.personal_office.first_steps import first_steps_handlers
from bot_apps.bot_parts.personal_office.payment_checker import payment_checker
from bot_apps.bot_parts.personal_office.referral_office import referral_office_handlers
from bot_apps.bot_parts.personal_tasks import personal_task_handlers
from bot_apps.bot_parts.task_push import task_push_handlers
from bot_apps.bot_parts.task_setting import task_setting_handlers
from bot_apps.other_apps.errors import errors_handlers
from bot_apps.other_apps.filters.ban_filters.is_banned import IsBanned
from bot_apps.other_apps.filters.ban_filters.they_banned import TheyBanned
from bot_apps.other_apps.other_handlers import other_handlers
from bot_apps.other_apps.systems_tasks.watchmans.checking_tasks import main_task_checker
from bot_apps.other_apps.systems_tasks.watchmans.completing_completion import completing_completion_checker
from bot_apps.other_apps.systems_tasks.watchmans.fines_collector import check_fines_collector
from bot_apps.other_apps.systems_tasks.watchmans.launch_new_rounds import launch_new_rounds_checker
from bot_apps.other_apps.systems_tasks.watchmans.level_watchman import level_watchman_checker
from bot_apps.other_apps.systems_tasks.watchmans.priority_updater import priority_updater_checker
from bot_apps.other_apps.systems_tasks.watchmans.re_check_of_execution import ReCheckExecution
from bot_apps.other_apps.systems_tasks.watchmans.task_setting_reminder import function_distributor_reminders
from bot_apps.other_apps.systems_tasks.watchmans.update_task_limits import update_limits_tasks
from bot_apps.other_apps.wordbank import commands
from config.config import load_config
from databases.start_database import StartDB
from parsing.manage_webdrivers.master_function import Master

start_db = StartDB()
re_checking = ReCheckExecution()
config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")


async def main():
    await start_db.start_database()   # Запуск базы данных
    await _fill_ban_lists()           # Загрузка бан списков
    await _start_webdrivers()       # Запуск всех вебдрайверов
    await asyncio.gather(
        _activate_all_watchman(),   # Запуск сторожей
        _start_bot())               # Запуск бота


async def _start_bot() -> NoReturn:
    redis = Redis(host='redis_db')
    storage = RedisStorage(redis=redis)
    dp = Dispatcher(storage=storage)
    print('Бот работает')
    dp.include_router(main_menu_handlers.router)  # Поставлен фильтр на сообщения
    dp.include_router(task_push_handlers.router)
    dp.include_router(personal_task_handlers.router)
    dp.include_router(admin_panel_handlers.router)
    dp.include_router(support_panel_handlers.router)
    dp.include_router(adding_task_handlers.router)
    dp.include_router(help_center_handlers.router)
    dp.include_router(task_setting_handlers.router)
    dp.include_router(first_steps_handlers.router)
    dp.include_router(referral_office_handlers.router)
    dp.include_router(personal_office_handlers.router)
    dp.include_router(other_handlers.router)
    dp.include_router(errors_handlers.router)
    await bot.delete_webhook(drop_pending_updates=True)
    dp.startup.register(bot_menu_builder)
    await dp.start_polling(bot)


async def bot_menu_builder(bot: Bot):
    """Добавление меню в бота"""
    main_menu_commands = [BotCommand(command='/start',
                                     description=commands['/start'])]
    await bot.set_my_commands(main_menu_commands)


async def _start_webdrivers():
    """Запуск вебдрайверов"""
    master = Master()
    await master.generate_main_driver()
    print('Вебдрайверы готовы')


# Включает всех сторожей
# noinspection PyUnreachableCode
async def _activate_all_watchman():
    tasks = [
        payment_checker(),                 # Проверка пополнений баланса
        function_distributor_reminders(),  # Напоминание о том, что юзер уже давно не включал задание
        main_task_checker(),               # Напоминалка о том, что нужно выполнить таск + сообщение о том, что воркер опоздал
        level_watchman_checker(),          # Проверка выполнения тасков на свой уровень
        update_limits_tasks(),             # Обновление счётчиков лимиток на таски раз в день для юзеров и аккаунтов
        check_fines_collector(),           # Сборщик штрафов
        launch_new_rounds_checker(),       # Сборщик тасков, которым надо начать новый раунд
        priority_updater_checker(),        # Накидывает приоритета за простой юзера
        re_checking.re_check_checker(),    # Перепроверка выполнений
        completing_completion_checker(),   # Проверка отстающийх по выполнению тасков и их добивка
    ]
    running_tasks = [asyncio.create_task(task) for task in tasks]  # Запускаем каждую задачу в фоне
    await asyncio.gather(*running_tasks)


async def _fill_ban_lists():
    """Заполнение бан списков"""
    is_banned = IsBanned()
    they_banned = TheyBanned()
    await is_banned.loading_blocked_users()         # Загрузка юзеров, которые в блоке у нас
    await they_banned.loading_they_blocked_users()  # Загрузка юзеров, у которых мы сами в блоке


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
