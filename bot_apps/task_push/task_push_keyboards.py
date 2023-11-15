from aiogram.types import InlineKeyboardButton as IB
from aiogram.utils.keyboard import InlineKeyboardBuilder as BD

from databases.database import db
from bot_apps.wordbank.wordlist import BACK_MAIN_MENU, BACK, FORWARD, notifications
from bot_apps.wordbank.wordlist import task_completion
from config import load_config

config = load_config()


# Клавиатура под отправкой пользователю уведомления о задании
async def new_task_keyboard_builder(tasks_msg_id):
    new_task_keyboard = BD()
    new_task_keyboard.row(
        IB(text=task_completion['buttons']['more_button'],
           callback_data=f'open_task_{tasks_msg_id}'))
    return new_task_keyboard.as_markup()


# Клавиатура после того, как пользователь открыл задание
async def revealing_task_builder(tasks_msg_id):
    revealing_task = BD()
    revealing_task.row(
        IB(text=task_completion['buttons']['start_task_button'],
           callback_data=f'start_task_{tasks_msg_id}'),
        IB(text=task_completion['buttons']['hide_task_button'],
           callback_data=f'hide_task_{tasks_msg_id}'), width=1)
    return revealing_task.as_markup()


# Кнопка для закрытия таска
async def ok_button_builder(tasks_msg_id):
    ok_button_kb = BD()
    ok_button_kb.row(
        IB(text='Ок',
           callback_data=f'delete_task_message_{tasks_msg_id}'))
    return ok_button_kb.as_markup()


# Кнопка для закрытия
async def close_button():
    close_kb = BD()
    close_kb.row(
        IB(text='Ok',
           callback_data='close'))
    return close_kb.as_markup()


# Кнопка для закрытия таска, но его завершили другие пользователи
async def ok_button_two_builder(tasks_msg_id):
    ok_button_kb = BD()
    ok_button_kb.row(
        IB(text='Понятно',
           callback_data=f'delete_fully_completed_task_{tasks_msg_id}'))
    return ok_button_kb.as_markup()


# Клавиатура, выводящая все аккаунты, с которых можно выполнить данное задание
async def accounts_for_task_builder(accounts_dict, tasks_msg_id, page=1):
    accounts_for_task_kb = BD()
    # Если у пользователя меньше 8 аккаунтов, не добавляем пагинацию
    if len(accounts_dict) == 1:
        for account in accounts_dict['page_1']:
            accounts_for_task_kb.row(
                IB(text=account,
                   callback_data=f'account_for_task_{account}/{tasks_msg_id}'))

    # Если у пользователя много аккаунтов, то создаём пагинацию на странице
    else:
        for account in accounts_dict[f'page_{page}']:
            accounts_for_task_kb.row(
                IB(text=account,
                   callback_data=f'account_for_task_{account}/{tasks_msg_id}'))

        # Докидываем оставшиеся кнопки для пагинации и выхода из аккаунтов
        accounts_for_task_kb.row(
            IB(text=BACK,
               callback_data=f'accounts_page_for_task_{page - 1}/{tasks_msg_id}' if page > 1 else 'other_apps'),
            IB(text=f'{page}/{len(accounts_dict)}',
               callback_data='other_apps'),
            IB(text=FORWARD,
               callback_data=f'accounts_page_for_task_{page + 1}/{tasks_msg_id}' if page < len(accounts_dict) else 'other_apps', width=3))

    # Если у пользователя есть выбранный аккаунт, добавляем кнопку для перехода назад
    if await db.get_task_account(tasks_msg_id):
        accounts_for_task_kb.row(
            IB(text=task_completion['buttons']['back_to_task_button'],
               callback_data=f'back_to_complete_task_{tasks_msg_id}'))

    return accounts_for_task_kb.as_markup()


# Клавиатура под выполнением задания
async def complete_task_builder(tg_id, tasks_msg_id):
    complete_task = BD()
    complete_task.row(
        IB(text=task_completion['buttons']['check_task_button'],
           callback_data=f'check_complete_task_{tasks_msg_id}'),
        IB(text=task_completion['buttons']['refuse_task_button'],
           callback_data=f'refuse_task_{tasks_msg_id}'), width=1)
    # Если у пользователя есть ещё аккаунты, с которых он может сделать это задание, то добавляем кнопку для смены аккаунта
    if await db.accounts_for_task_other_account(tg_id, tasks_msg_id):
        complete_task.row(
            IB(text=task_completion['buttons']['change_account_button'],
               callback_data=f'back_to_start_task_{tasks_msg_id}'))

    return complete_task.as_markup()


# Клавиатура в случае, если парсер ебанулся и ничего не спарсил
async def not_parsing_builder(tasks_msg_id):
    not_parsing = BD()
    not_parsing.row(
        IB(text=task_completion['buttons']['again_check_button'],
           callback_data=f'check_complete_task_{tasks_msg_id}'),
        IB(text=task_completion['connect_to_agent_button'],
           url=f"tg://resolve?domain={config.tg_bot.support_name}"), width=1)



# Клавиатура под вводом ссылки на комментарий
async def get_link_comment_builder(tg_id, tasks_msg_id):
    get_link_comment = BD()
    get_link_comment.row(
        IB(text=task_completion['buttons']['refuse_task_button'],
           callback_data=f'refuse_task_{tasks_msg_id}'))
    # Если у пользователя есть ещё аккаунты, с которых он может сделать это задание, то добавляем кнопку для смены аккаунта
    if await db.accounts_for_task_other_account(tg_id, tasks_msg_id):
        get_link_comment.row(
            IB(text=task_completion['buttons']['change_account_button'],
               callback_data=f'back_to_start_task_{tasks_msg_id}'))
    return get_link_comment.as_markup()


# Клавиатура под работой с комментарием
async def comment_check_builder(tg_id, tasks_msg_id):
    comment_check = BD()
    comment_check.row(
        IB(text=task_completion['buttons']['connect_to_agent_button'],
           url=f"tg://resolve?domain={config.tg_bot.support_name}"),
        IB(text=task_completion['buttons']['refuse_task_button'],
           callback_data=f'refuse_task_{tasks_msg_id}'), width=1)
    # Если у пользователя есть ещё аккаунты, с которых он может сделать это задание, то добавляем кнопку для смены аккаунта
    if await db.accounts_for_task_other_account(tg_id, tasks_msg_id):
        comment_check.row(
            IB(text=task_completion['buttons']['change_account_button'],
               callback_data=f'back_to_start_task_{tasks_msg_id}'))
    return comment_check.as_markup()


# Клавиатура для сбора наград по выполненному заданию
async def finally_task_builder(tasks_msg_id):
    finally_task = BD()
    finally_task.row(
        IB(text=task_completion['buttons']['collect_reward_button'],
            callback_data=f'collect_reward_from_task_{tasks_msg_id}'))
    return finally_task.as_markup()


# Клавиатура в случае, когда пользователь не выполнил таск за 10 минут
async def clear_button_builder(tasks_msg_id):
    clear_button = BD()
    clear_button.row(
        IB(text=task_completion['buttons']['scored_button'],
           callback_data=f'task_message_scored_{tasks_msg_id}'),
        IB(text=BACK_MAIN_MENU,
           callback_data='back_to_main_menu'), width=1)
    return clear_button.as_markup()


# Клавиатура, под финальным сообщением таска
async def task_again_builder(tg_id, tasks_msg_id):
    task_again = BD()
    if await db.task_again(tg_id, tasks_msg_id):
        task_again.row(
            IB(text=task_completion['buttons']['new_account_button'],
               callback_data=f'new_account_task_{tasks_msg_id}'))
    task_again.row(
        IB(text='Ок',
           callback_data=f'delete_new_task_{tasks_msg_id}'),
        IB(text=BACK_MAIN_MENU,
            callback_data='back_to_main_menu'), width=1)
    return task_again.as_markup()


# Клавиатура под информацией о задании, когда воркер решил выполнить задние снова с другого аккаунта
async def new_account_from_task_keyboard_builder(tasks_msg_id, account):
    new_account_from_task = BD()
    if not account:
        new_account_from_task.row(
            IB(text=task_completion['buttons']['select_account_button'],
                callback_data=f'start_task_{tasks_msg_id}'))
    else:
        new_account_from_task.row(
            IB(text=task_completion['buttons']['check_task_button'],
               callback_data=f'check_complete_task_{tasks_msg_id}'))
    new_account_from_task.row(
        IB(text=task_completion['buttons']['refuse_task_button'],
            callback_data=f'refuse_for_new_task_{tasks_msg_id}'))
    return new_account_from_task.as_markup()


# Пользователь захотел сделать задание по новой, но оно было завершено, либо неактивно
async def not_again_task_builder():
    not_again_task = BD()
    not_again_task.row(
        IB(text=task_completion['buttons']['hide_task_again_button'],
           callback_data='hide_task'),
        IB(text=BACK_MAIN_MENU,
           callback_data='back_to_main_menu'), width=1)
    return not_again_task.as_markup()


# Клавиатура под уведомлением о том, что пользователь много выполнил заданий и теперь круто было бы конечно отзыв оставить вот мда
async def proposal_for_review_builder():
    proposal_for_review = BD()
    proposal_for_review.row(
        IB(text=notifications['buttons']['leave_review_button'],
           url=config.tg_bot.feedback_group),
        IB(text=notifications['buttons']['no_leave_review_button'],
           callback_data='close'), width=1)
    return proposal_for_review.as_markup()