from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot_apps.filters.ban_filters.is_banned import IsBanned
from bot_apps.task_push.system.initial_priority import determine_initial_priority
from databases.database import db
from bot_apps.other_apps.main_menu.main_menu_handlers import process_open_main_menu
from bot_apps.other_apps.task_setting.task_setting_guardian import text_except_all_notifications
from bot_apps.other_apps.task_setting.task_setting_keyboards import setting_tasks_builder
from bot_apps.wordbank.wordlist import setting

router = Router()
router.callback_query.filter(IsBanned())
router.message.filter(IsBanned())


# Пользователь меняет настройки всех уведомлений
@router.callback_query(F.data.startswith('all_notifications_'))
async def process_change_all_notifications(callback: CallbackQuery, state: FSMContext):
    # Проверка на то, что у пользователя есть хотя бы 1 рабочий аккаунт и хотя бы 1 уведомление включено
    if isinstance(await db.off_all_notifications(callback.from_user.id), bool) if callback.data[18:] == 'on' else True:
        status = True if callback.data[18:] == 'on' else False
        await db.update_all_notifications(callback.from_user.id, status)
        await callback.answer(setting[f"all_setting_{callback.data[18:]}"])
        await process_open_main_menu(callback, state)
        if callback.data[18:] == 'on':
            await determine_initial_priority(callback.from_user.id)
    else:
        text = await text_except_all_notifications(callback.from_user.id)
        await callback.answer(text, show_alert=True)



# Пользователь зашёл в настройки уведомлений
@router.callback_query(F.data =='setting_tasks')
async def open_setting_tasks(callback: CallbackQuery):
    await callback.message.edit_text(text=setting['main_text'] + (
        '\n\n' + setting['dop_text'] if await db.get_all_notifications_and_account(callback.from_user.id) else ''),
                                     reply_markup=await setting_tasks_builder(callback.from_user.id))


# Пользователь решил поменять уведомления
@router.callback_query(F.data.startswith('setting_comments_'))
@router.callback_query(F.data.startswith('setting_retweets_'))
@router.callback_query(F.data.startswith('setting_likes_'))
@router.callback_query(F.data.startswith('setting_subscriptions_'))
async def process_change_setting(callback: CallbackQuery, state: FSMContext):
    type_setting = callback.data[8:-5].replace('_', '')
    # Отправляем небольшое уведомление о том, что настройка была изменена
    await callback.answer(setting[f"setting_{'on' if callback.data[-4:] == 'true' else 'off'}"].format(setting['type_setting'][type_setting]))
    await state.update_data(tg_id=callback.from_user.id, type_setting=type_setting, change=True if callback.data[-4:] == 'true' else False)
    # Записываем смену настройки
    await db.change_setting(callback.from_user.id, type_setting, True if callback.data[-4:] == 'true' else False)
    # Редактируем текст с учётом изменения какой-то настройки
    await callback.message.edit_text(text=setting['main_text'],
                                     reply_markup=await setting_tasks_builder(callback.from_user.id))
    await db.off_all_notifications(callback.from_user.id)
