import asyncio
import pickle

from aiogram import Dispatcher, Bot
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot_apps.adding_task import adding_task_handlers
from bot_apps.databases.database import db
from bot_apps.other_apps.help_center import help_center_handlers
from bot_apps.other_apps.main_menu import main_menu_handlers
from bot_apps.other_apps.task_setting import task_setting_handlers
from bot_apps.other_apps.task_setting.task_setting_reminder import function_distributor_reminders
from bot_apps.personal_office import personal_office_handlers
from bot_apps.personal_office.first_steps import first_steps_handlers
from bot_apps.personal_office.referral_office import referral_office_handlers
from bot_apps.task_push import task_push_handlers
from bot_apps.task_push.system import task_push_new_task
from bot_apps.task_push.system.task_push_task_checker import main_task_checker
from bot_apps.wordbank import commands
from config.config import load_config
from parsing.start_webdriver.webdriver import webdriver

config = load_config()
webdrivers = {}
numbers_webdrivers = 0

async def start_bot():
    storage = MemoryStorage()

    bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
    dp = Dispatcher(storage=storage)

    print('Бот работает')
    dp.include_router(main_menu_handlers.router)  # Должен быть самым первым, т.к. там стоит мой фильтр

    dp.include_router(task_push_new_task.router)
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
    for i in range(numbers_webdrivers):
        webdrivers[f'driver_{i}'] = await webdriver()
        webdrivers[f'driver_{i}'].get('https://twitter.com')
        # Здесь можно задавать им любые аккаунты, в которые они будут входить
        for cookie in pickle.load(open(f'cookies/{config.twitter_login.tw_login}_cookies.pkl', 'rb')):
            webdrivers[f'driver_{i}'].add_cookie(cookie)
        webdrivers[f'driver_{i}'].get('https://twitter.com/home')

    print('Вебдрайверы готовы')


async def main():
    await db.connect()
    await asyncio.gather(function_distributor_reminders(),
                         main_task_checker(),
                         start_bot())



if __name__ == '__main__':
    asyncio.run(main())
