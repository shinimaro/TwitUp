from asyncio import sleep

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Text
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery


from bot_apps.databases.database import db
from bot_apps.limit_filter.limit_filter import MainFiter
from bot_apps.other_apps.main_menu.main_menu_handlers import process_open_main_menu
from bot_apps.other_apps.task_setting.task_setting_keyboards import setting_tasks_builder
from bot_apps.wordbank.wordlist import setting

router = Router()


# Пользователь меняет настройки всех уведомлений
@router.callback_query(lambda x: x.data.startswith('all_notifications_'))
async def process_change_all_notifications(callback: CallbackQuery, state: FSMContext):
    # Проверка на то, что у пользователя есть хотя бы 1 аккаунт и он уже может добавлять задания
    if await db.check_accounts(callback.from_user.id) if callback.data[18:] == 'on' else True:
        status = True if callback.data[18:] == 'on' else False
        await db.update_all_notifications(callback.from_user.id, status)
        await callback.answer(setting[f"all_setting_{callback.data[18:]}"])
        await process_open_main_menu(callback, state)
    else:
        await callback.answer(setting['not_on_all_setting'], show_alert=True)


# Пользователь зашёл в настройки уведомлений
@router.callback_query(Text(text=['setting_tasks']))
async def open_setting_tasks(callback: CallbackQuery):
    await callback.message.edit_text(text=setting['main_text'] + (
        '\n\n' + setting['dop_text'] if not await db.get_all_notifications(callback.from_user.id) else ''),
                                     reply_markup=await setting_tasks_builder(callback.from_user.id))


# Пользователь решил поменять уведомления
@router.callback_query(lambda x: x.data.startswith('setting_comments_') or x.data.startswith('setting_retweets_')
                       or x.data.startswith('setting_likes_') or x.data.startswith('setting_subscriptions_'))
async def process_change_setting(callback: CallbackQuery, state: FSMContext):
    type_setting = callback.data[8:-5].replace('_', '')
    # Отправляем небольшое уведомление о том, что настройка была изменена
    await callback.answer(setting[f"setting_{'on' if callback.data[-4:] == 'true' else 'off'}"].format(setting['type_setting'][type_setting]))
    await state.update_data(tg_id=callback.from_user.id, type_setting=type_setting, change=True if callback.data[-4:] == 'true' else False)
    # Записываем смену настройки
    await db.change_setting(callback.from_user.id, type_setting, True if callback.data[-4:] == 'true' else False)
    # Защита от случаев, если пользователь будет бить по кнопкам, а бот не успевать их правильно обрабатывать и, стараться поменять текст на тот же самый
    try:
        # Редактируем текст с учётом изменения какой-то настройки
        await callback.message.edit_text(text=setting['main_text'],
                                         reply_markup=await setting_tasks_builder(callback.from_user.id))
    except TelegramBadRequest:
        await sleep(1)
