import re

from aiogram import Router, Bot, F
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message

from bot_apps.bot_parts.task_setting.middlewares import CommentCheck
from bot_apps.other_apps.FSM.FSM_states import FSMAddTask, FSMAdmin, FSMAccounts
from bot_apps.other_apps.filters.ban_filters.is_banned import IsBanned
from bot_apps.other_apps.systems_tasks.control_tasks.check_over_refusal import check_over_refusal
from bot_apps.other_apps.systems_tasks.control_tasks.delete_tasks_messages import function_distributor_task_messages
from bot_apps.other_apps.systems_tasks.control_users.change_task_button import change_task_buttons

from bot_apps.other_apps.systems_tasks.control_users.send_letter_of_happiness import availability_check
from bot_apps.bot_parts.task_push.task_push_filters import comment_check_filter, comment_check_itself
from bot_apps.bot_parts.task_push.task_push_keyboards import revealing_task_builder, accounts_for_task_builder, ok_button_builder, \
    complete_task_builder, finally_task_builder, get_link_comment_builder, comment_check_builder, task_again_builder, \
    new_account_from_task_keyboard_builder, not_again_task_builder, not_parsing_builder
from bot_apps.bot_parts.task_push.task_push_text import full_text_task_builder, context_task_builder, \
    please_give_me_link, \
    control_statistic_builder, new_account_from_task_builder, issuance_of_reward
from bot_apps.other_apps.wordbank import task_completion
from config import load_config
from databases.database import Database
from parsing.main_checkings.checking_executions.main_parsing_functions import ActionsDict, FoundComment
from parsing.main_checkings.checking_executions.start_checking import StartChecking
from parsing.parsing_functions.parsing_functions import parsing_comment_text

router = Router()
config = load_config()
bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
db = Database()
router.callback_query.filter(IsBanned())
router.message.filter(IsBanned())


# Пользователь открывает таск
@router.callback_query(F.data.startswith('open_task_'))
async def open_new_task(callback: CallbackQuery):
    tasks_msg_id = int(callback.data[10:])
    await db.update_status_and_time(tasks_msg_id, 'offer_more')
    await callback.message.edit_text(await full_text_task_builder(tasks_msg_id),
                                     reply_markup=revealing_task_builder(tasks_msg_id))


# Пользователь решил скрыть таск
@router.callback_query(F.data.startswith('hide_task'))
async def process_hide_task(callback: CallbackQuery):
    # Если нужно не просто скрыть таск, а конкретный таск и записать к нему дату удаления и статус
    if callback.data != 'hide_task':
        tasks_msg_id = int(callback.data[10:])
        await db.add_del_time_in_task(tasks_msg_id)
        await db.add_hidden_status(tasks_msg_id)
        await db.add_note_about_hiding(tasks_msg_id)
        await change_task_buttons(tasks_msg_id)
        await check_over_refusal(tasks_msg_id)
    await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)


# Выбор (или смена выбранного) аккаунта под выполнение задания (показываются только те, на которых задание ещё не было выполнено)
@router.callback_query(F.data.startswith('start_task_') | F.data.startswith('back_to_start_task_'))
async def process_select_account(callback: CallbackQuery):
    tasks_msg_id = int(callback.data[11:]) if callback.data.startswith('start_task_') else int(callback.data[19:])
    accounts_dict = await db.accounts_for_task(callback.from_user.id, tasks_msg_id)
    if callback.data.startswith('start_task_'):
        await db.update_status_and_time(tasks_msg_id, 'start_task')
        if not await db.check_active_task(await db.get_task_id_from_tasks_messages(tasks_msg_id)):
            return
    # Колбек на случай, если у пользователя по какой-то причине, не осталось аккаунтов, с которых он может выполнить задание
    if not accounts_dict:
        await callback.message.edit_text(text=task_completion['not_select_account'],
                                         reply_markup=ok_button_builder(tasks_msg_id))
        await db.add_del_time_in_task(tasks_msg_id)
        await db.add_deleted_status(tasks_msg_id)
    elif len(accounts_dict['page_1']) == 1:
        await callback.message.edit_text(await context_task_builder(tasks_msg_id, *accounts_dict['page_1']),
                                         reply_markup=await complete_task_builder(callback.from_user.id, tasks_msg_id),
                                         disable_web_page_preview=True)
        await db.update_task_account(tasks_msg_id, *accounts_dict['page_1'])
        await db.update_status_and_time(tasks_msg_id, 'process')
    else:
        await callback.message.edit_text(text=task_completion['select_account'],
                                         reply_markup=await accounts_for_task_builder(accounts_dict, tasks_msg_id))


# Пользователь ходит по аккаунтам для задания
@router.callback_query(F.data.startswith('accounts_page_for_task_'))
async def change_page(callback: CallbackQuery):
    # Находим нужные данные без использования состояния
    page = int(callback.data[23: callback.data.find('/')])
    tasks_msg_id = int(callback.data[callback.data.find('/')+1:])
    accounts_dict = await db.accounts_for_task(callback.from_user.id, tasks_msg_id)
    await callback.message.edit_text(text=task_completion['select_account'],
                                     reply_markup=await accounts_for_task_builder(accounts_dict, tasks_msg_id, page))


# Пользователь нажал на кнопку 'ок' и закрыл сообщение (после того, как он решил скрыть задание)
# Также просто закрывает сообщение, после того, как пользователь уже выполнил задание
@router.callback_query(F.data.startswith('delete_task_message_') | F.data.startswith('delete_new_task_'))
async def delete_task_message(callback: CallbackQuery):
    tasks_msg_id = int(callback.data[20:]) if callback.data.startswith('delete_task_message_') else int(callback.data[16:])
    await db.add_del_time_in_task(tasks_msg_id)
    if callback.data.startswith('delete_task_message_'):
        await db.add_deleted_status(tasks_msg_id)
    await bot.delete_message(chat_id=callback.from_user.id, message_id=callback.message.message_id)


# Кнопка в случае, когда прошло 10 минут и пользователь не выполнил таск
@router.callback_query(F.data.startswith('task_message_scored_'))
# Кнопка, в случае, если задание полностью завершили уже другие пользователи
@router.callback_query(F.data.startswith('delete_fully_completed_task_'))
async def task_message_del_button(callback: CallbackQuery):
    await bot.delete_message(chat_id=callback.from_user.id, message_id=callback.message.message_id)


# Пользователь вернулся к выбору аккаунта, но потом решил опять вернуться к заданию
# Хендлер под этим хендлером, в некоторых случаях вызывает его, поэтому я вставил tasks_msg_id в его атрибуты
@router.callback_query(F.data.startswith('back_to_complete_task_'))
async def process_back_to_complete(callback: CallbackQuery, tasks_msg_id=None):
    tasks_msg_id = int(callback.data[22:]) if not tasks_msg_id else tasks_msg_id
    account = await db.get_task_account(tasks_msg_id)
    # Если пользователь делал лайк/ретвит/подписку
    if await db.check_status_comment(tasks_msg_id):
        await callback.message.edit_text(await context_task_builder(tasks_msg_id, account), disable_web_page_preview=True,
                                         reply_markup=await complete_task_builder(callback.from_user.id, tasks_msg_id))
    # Если пользователь делал комментарий
    else:
        await callback.message.edit_text(await please_give_me_link(tasks_msg_id, account),
                                         reply_markup=await get_link_comment_builder(callback.from_user.id, tasks_msg_id),
                                         disable_web_page_preview=True)


# Пользователь выбрал аккаунт и переходит к выполнению задания
@router.callback_query(F.data.startswith('account_for_task_'))
async def process_task_completion(callback: CallbackQuery):
    account = callback.data[17:callback.data.find('/')]
    tasks_msg_id = int(callback.data[callback.data.find('/') + 1:])
    # Если он выбрал новый аккаунт
    if await db.get_task_account(tasks_msg_id) != account:
        # Сохранение аккаунта
        await db.update_task_account(tasks_msg_id, account)
        await db.update_status_and_time(tasks_msg_id, 'process')
        await callback.message.edit_text(await context_task_builder(tasks_msg_id, account), disable_web_page_preview=True,
                                         reply_markup=await complete_task_builder(callback.from_user.id, tasks_msg_id))
    # Если он выбрал тот же самый аккаунт, на котором делает задание, то приравниваем это к возврату назад к заданию
    else:
        await process_back_to_complete(callback, tasks_msg_id)


# Пользователь решил отказаться от задания
@router.callback_query((F.data.startswith('refuse_task_')) | (F.data.startswith('refuse_for_new_task_')))
async def process_refuse_task(callback: CallbackQuery):
    # Записываем соответствующий статус задания
    tasks_msg_id = int(callback.data[12:]) if callback.data.startswith("refuse_task_") else int(callback.data[20:])
    no_first_execution = False if callback.data.startswith("refuse_task_") else False
    await db.del_and_change_status_task(tasks_msg_id, no_first_execution=no_first_execution)
    await db.add_note_about_refuse(tasks_msg_id)
    await db.add_del_time_in_task(tasks_msg_id)
    await change_task_buttons(tasks_msg_id)
    await check_over_refusal(tasks_msg_id)
    await callback.answer(task_completion['late_refuse_task'])
    await callback.message.delete()


# Пользователь указал, что завершил задание
@router.callback_query(F.data.startswith('check_complete_task_'))
async def process_refuse_task(callback: CallbackQuery):
    tasks_msg_id = int(callback.data[20:])
    await db.update_status_and_time(tasks_msg_id, 'checking')
    # Сообщаем пользователю о том, что задание проверяется
    await callback.message.edit_text(task_completion['checking_your_performance'])
    account = await db.get_task_account(tasks_msg_id)
    check_execution = StartChecking(tasks_msg_id)
    # result: ActionsDict | None = await check_execution.start_checking()
    result: ActionsDict | None = {'likes': True, 'subscriptions': True}
    # Если так получилось, что проверка так и не удалась
    if result is None:
        await callback.message.edit_text(task_completion['not_check_task'], reply_markup=await not_parsing_builder(tasks_msg_id))
        return
    # Проходимся по все ключам, кроме комментария (т.к. чекер может его просто не найти)
    for key in result:
        # Если чекер нашёл невыполнение какого-то действия и это не комментарий
        if not result[key] and key != 'comments':
            await db.update_status_and_time(tasks_msg_id, f'process_{key}')
            # Добавляем к тому же тексту сообщение о том, что не выполнил пользователь
            await callback.message.edit_text(await context_task_builder(tasks_msg_id, account, key),
                                             reply_markup=await complete_task_builder(callback.from_user.id, tasks_msg_id),
                                             disable_web_page_preview=True)
            break
        # Если комментарий был найден, делаем его проверку
        elif result[key] and key == 'comments':
            check_comment = await comment_check_itself(tasks_msg_id, result[key].comment_text)
            if isinstance(check_comment, str):  # Если пришло сообщение об ошибке
                await db.update_status_and_time(tasks_msg_id, f'process_comments')
                await callback.message.edit_text(await context_task_builder(tasks_msg_id, account, not_complete='not_correct_comm'),
                                                 reply_markup=await complete_task_builder(callback.from_user.id, tasks_msg_id),
                                                 disable_web_page_preview=True)
                break
            else:
                await db.save_comment(tasks_msg_id, result[key].comment_link)

        # Если не был найден комментарий
        elif not result[key] and key == 'comments':
            message_id = await callback.message.answer(await please_give_me_link(tasks_msg_id, account),
                                                       reply_markup=await get_link_comment_builder(callback.from_user.id, tasks_msg_id),
                                                       disable_web_page_preview=True)
            await bot.delete_message(chat_id=callback.from_user.id, message_id=await db.get_task_message_id(tasks_msg_id))
            # Меняем статус задания на тот, который ожидает добавление ссылки
            await db.update_status_and_time(tasks_msg_id, 'waiting_link')
            await db.change_task_message_id(tasks_msg_id, message_id.message_id)
            break
    # Если пользователь завершил все задания
    else:
        await db.task_completed(tasks_msg_id)
        await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=await db.get_task_message_id(tasks_msg_id),
                                    text=await issuance_of_reward(tasks_msg_id),
                                    reply_markup=finally_task_builder(tasks_msg_id))
        await availability_check(callback.from_user.id)
        # Проверка на то, завершено ли задание таскодателя
        if await db.check_completed(tasks_msg_id):
            await function_distributor_task_messages(tasks_msg_id)


# Пользователь ввёл ссылку на комментарий + (убираем, чтобы пользователь случайно не набирал ссылку на пост для нового задания)
@router.message(lambda x: x.text and re.search('https://twitter\.com/([\w\d_]{3,})/status/\d{1,19}', x.text.lower()),
                ~StateFilter(FSMAddTask.add_post_link,
                             FSMAccounts.add_first_account,
                             FSMAdmin.input_link_to_profile,
                             FSMAdmin.input_link_to_post), CommentCheck())
async def get_link_comment(message: Message, result: int | dict):
    await message.delete()
    # Если вернулся словарь с ошибкой (не на тот аккаунт ссылка)
    if isinstance(result, dict):
        tasks_msg_id = list(result.keys())[0]
        await bot.delete_message(chat_id=message.from_user.id, message_id=await db.get_task_message_id(tasks_msg_id))
        # Возвращаем новое сообщение с ошибкой и удаляем старое задание
        message_id = await message.answer(result[tasks_msg_id], reply_markup=await get_link_comment_builder(message.from_user.id, tasks_msg_id),
                                          disable_web_page_preview=True)
        await db.change_task_message_id(tasks_msg_id, message_id.message_id)
    # Если вернулось id таска, которому была отправлена ссылка
    else:
        tasks_msg_id = result
        await bot.delete_message(chat_id=message.from_user.id, message_id=await db.get_task_message_id(tasks_msg_id))
        await db.update_status_and_time(tasks_msg_id, 'checking')
        message_id = await message.answer(task_completion['checking_your_comment'])
        await db.change_task_message_id(tasks_msg_id, message_id.message_id)
        comment_text = await parsing_comment_text(tasks_msg_id, message.text.lower())
        check_comment = await comment_check_itself(tasks_msg_id, comment_text)
        # Если вернулся текст с ошибкой
        if isinstance(check_comment, str):
            await db.update_status_and_time(tasks_msg_id, 'process_comments')
            message_id = await message.answer(check_comment, reply_markup=await comment_check_builder(message.from_user.id, tasks_msg_id),
                                              disable_web_page_preview=True)
            await bot.delete_message(chat_id=message.from_user.id, message_id=await db.get_task_message_id(tasks_msg_id))
            await db.change_task_message_id(tasks_msg_id, message_id.message_id)
        # Если комментарий успешно прошёл
        else:
            await db.save_comment(tasks_msg_id=tasks_msg_id, comment_link=message.text.lower())
            await db.task_completed(tasks_msg_id)
            await bot.edit_message_text(chat_id=message.chat.id, message_id=await db.get_task_message_id(tasks_msg_id),
                                        text=await issuance_of_reward(tasks_msg_id),
                                        reply_markup=finally_task_builder(tasks_msg_id))
            await availability_check(message.from_user.id)
            # Проверка на то, завершено ли задание таскодателя
            if await db.check_completed(tasks_msg_id):
                await function_distributor_task_messages(tasks_msg_id)


# Пользователь забирает награду
@router.callback_query(F.data.startswith('collect_reward_from_task_'))
async def collect_reward_from_tasks(callback: CallbackQuery):
    tasks_msg_id = int(callback.data[25:])
    check = await db.check_balance_account(tasks_msg_id)
    if not check:
        await callback.answer(task_completion['not_collect_reward'], show_alert=True)
    else:
        await callback.answer(task_completion['collect_reward'])
    await db.collect_reward_from_task(callback.from_user.id, tasks_msg_id)
    await db.update_deleted_time(tasks_msg_id)
    # Если у пользователя ещё есть задания, появляется соответствующее сообщение
    await callback.message.edit_text(text=await control_statistic_builder(callback.from_user.id, tasks_msg_id),
                                     reply_markup=await task_again_builder(tasks_msg_id))


# Пользователь решил выполнить это же задание, но с другого аккаунта
@router.callback_query(F.data.startswith('new_account_task_'))
async def open_task_from_new_account(callback: CallbackQuery):
    status = await db.get_status_task(int(callback.data[17:]))
    if status == 'completed':
        await callback.message.edit_text(text=task_completion['completed_again_task'],
                                         reply_markup=not_again_task_builder())
    else:
        tasks_msg_id = await db.new_tasks_messages(callback.from_user.id, int(callback.data[17:]))
        result = await db.task_two_again(callback.from_user.id, int(callback.data[17:]))
        # Проверка на то, 1 ли аккаунт у пользователя, с которого он может сделать задание
        account = result if isinstance(result, str) else None
        if account:
            await db.new_task_account(tasks_msg_id, account)
        await callback.message.edit_text(await new_account_from_task_builder(tasks_msg_id, account),
                                         reply_markup=new_account_from_task_keyboard_builder(tasks_msg_id, account),
                                         disable_web_page_preview=True)
