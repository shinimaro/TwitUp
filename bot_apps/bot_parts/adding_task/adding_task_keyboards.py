from aiogram.types import InlineKeyboardButton as IB
from aiogram.types import InlineKeyboardMarkup as IM
from aiogram.utils.keyboard import InlineKeyboardBuilder as BD

from bot_apps.bot_parts.adding_task.adding_task_text import define_price
from bot_apps.other_apps.wordbank import add_task, BACK, BACK_MAIN_MENU, payment


# Клавиатура для настройки выбора действий, которые будут в задании
def select_actions_builder(actions: list = None) -> IM:
    select_actions_kb = BD()
    # Если какое-либо действие ещё не было задано
    if actions is None:
        for callback, text in add_task['buttons']['actions'].items():
            select_actions_kb.row(
                IB(text=text,
                   callback_data=callback[:-7]), width=1)
    # Если действие было задано
    else:
        for callback, text in add_task['buttons']['actions'].items():
            # Если действие было выбрано, то к кнопке плюсуется галочка
            if callback[8:-7] in actions:
                select_actions_kb.row(
                    IB(text=text + '✅',
                       callback_data=callback[:-7]), width=1)
            # Если не действие не было выбрано, то просто выводится кнопка
            else:
                select_actions_kb.row(
                    IB(text=text,
                       callback_data=callback[:-7]), width=1)
    select_actions_kb.row(
        IB(text=add_task['buttons']['continue_button'],
           callback_data='accept_settings_task'),
        IB(text=BACK_MAIN_MENU,
           callback_data='back_to_main_menu'), width=1)
    return select_actions_kb.as_markup()


# Клавиатура для настройки всех компонентов для успешного добавления задания (указать аккаунт, ссылку на пост, параметры комментария). Если на всех нужных кнопках есть зелёная галочка, то пользователь может идти дальше
def setup_all_components_builder(actions=None, accepted=None) -> IM:
    setup_all_components = BD()
    # Если пользователь задал только подписки
    if len(actions) == 1 and actions[0] == 'subscriptions':
        setup_all_components.row(
            IB(text=add_task['buttons']['profile_link_button'] + '✅' if accepted['profile_link'] or accepted['post_link'] else add_task['buttons']['profile_link_button'],
               callback_data='add_in_task_profile_link'))
    # Если пользователь указал в действиях задание для поста
    else:
        setup_all_components.row(
            IB(text=add_task['buttons']['post_link_button'] + '✅' if accepted['post_link'] else add_task['buttons']['post_link_button'],
               callback_data='add_in_task_post_link'))
        # Если пользователь добавил в действиях комментарий
        if 'comments' in actions:
            setup_all_components.row(
                IB(text=add_task['buttons']['comment_parameters_button'] + '✅' if accepted['comment_parameters'].get('one_value', False) or accepted['comment_parameters'].get('note', False) or accepted['comment_parameters'].get('only_english', False) else add_task['buttons']['comment_parameters_button'],
                   callback_data='add_in_task_comment_parameters'))

    # Проверка на то, заполнил ли пользователь все нужные поля (если все кнопочки с заданиями содержат зелёную галочку, то можно пройти дальше)
    buttons_list = list(setup_all_components.buttons)
    for button in buttons_list:
        # Если кнопочка не содержит галочку, то пользователь не пойдёт дальше
        if '✅' not in button.text:
            break
    # Если все кнопки содержат галочку, добавляется кнопка "продолжить"
    else:
        setup_all_components.row(
            IB(text=add_task['buttons']['continue_button'],
                callback_data='accept_all_settings'))

    setup_all_components.row(
        IB(text=BACK,
           callback_data='back_to_setting_task'))

    # Настройка кнопки для выхода в главное меню, чтобы переспросить у пользователя, действительно он хочет выйти
    # Если ни одна ссылка или настройка коммента не была задана, то не переспрашиваем, если настройки были заданы, то переспрашиваем, точно ли он хочет уйти
    data_for_back_main_menu = 'back_to_main_menu'
    # Проверка ссылки на аккаунт
    if (accepted['profile_link'] and 'subscriptions' in actions) or (accepted['post_link'] and 'subscriptions' in actions):
        data_for_back_main_menu = 'exactly_to_back_main_menu'
    # Проверка ссылки на пост
    elif accepted['post_link'] and ('retweets' in actions or 'likes' in actions or 'comments' in actions):
        data_for_back_main_menu = 'exactly_to_back_main_menu'
    # Проверка параметров комментария
    elif [i for i in accepted['comment_parameters'] if accepted['comment_parameters'][i]] and 'comments' in actions:
        data_for_back_main_menu = 'exactly_to_back_main_menu'
    setup_all_components.row(
        IB(text=BACK_MAIN_MENU,
           callback_data=data_for_back_main_menu))
    return setup_all_components.as_markup()


# Кнопка назад при вводе ссылки
def back_button_to_setting_task_builder() -> IM:
    back_button_to_setting_task = BD()
    back_button_to_setting_task.row(
        IB(text=BACK,
           callback_data='back_accept_setting_task'))
    return back_button_to_setting_task.as_markup()


# Клавиатура под выбором комментария
def comment_parameters_builder(accepted) -> IM:
    comment_parameters = BD()
    comment_parameters.row(
        IB(text=add_task['buttons']['comment_parameters']['add_checking_button'] if not accepted['comment_parameters'].get('one_value', False) else add_task['buttons']['comment_parameters']['add_checking_button'] + '✅',
           callback_data='add_checking_comment'),
        IB(text=add_task['buttons']['comment_parameters']['add_note_button'] if not accepted['comment_parameters'].get('note', False) else add_task['buttons']['comment_parameters']['add_note_button'] + '✅',
           callback_data='add_note'),
        IB(text=add_task['buttons']['comment_parameters']['english_only_button'] if not accepted['comment_parameters'].get('only_english', False) else add_task['buttons']['comment_parameters']['english_only_button'] + '✅',
           callback_data='only_english'), width=1)
    comment_parameters.row(
        IB(text=BACK,
           callback_data='back_accept_setting_task'))
    return comment_parameters.as_markup()


# Пользователь выбирает один из 3 критериев для проверки комментария
def comment_criteria_builder(accepted) -> IM:
    comment_parameters = BD()

    comment_parameters.row(
        IB(text=add_task['buttons']['comment_parameters']['number_words_button'] if not accepted['comment_parameters']['one_value'].get('words', False) else add_task['buttons']['comment_parameters']['number_words_button'] + '✅',
           callback_data='add_in_comment_number_words'),
        IB(text=add_task['buttons']['comment_parameters']['number_tags_button'] if not accepted['comment_parameters']['one_value'].get('tags', False) else add_task['buttons']['comment_parameters']['number_tags_button'] + '✅',
           callback_data='add_in_comment_number_tags'),
        IB(text=add_task['buttons']['comment_parameters']['tags/words_button'] if not accepted['comment_parameters']['one_value'].get('tags/words', False) else add_task['buttons']['comment_parameters']['tags/words_button'] + '✅',
           callback_data='add_in_comment_tags/words'), width=1)
    # Проверка на то, было ли что-то уже задано. Если было, добавляем кнопку, чтобы отчистить заданные настройки проверки комментария
    if 'one_value' in accepted['comment_parameters'] and accepted['comment_parameters']['one_value']:
        comment_parameters.row(
            IB(text=add_task['buttons']['comment_parameters']['delete_key_parameters_button'],
               callback_data='delete_comment_key_parameters'))
    comment_parameters.row(
        IB(text=BACK,
           callback_data='back_to_comment_parameters'))
    return comment_parameters.as_markup()


# Кнопка "назад" для возвращения в меню настройки критериев комментария
def back_to_checking_comment_builder() -> IM:
    back_to_comment_criteria = BD()
    back_to_comment_criteria.row(
        IB(text=BACK,
           callback_data='back_to_checking_comment'))
    return back_to_comment_criteria.as_markup()


# Клавиатура для выбора минимального количества слов/тегов
def select_minimum_parameters_builder(type_setting='words') -> IM:
    select_minimum_parameters = BD()
    # Если ничего не указано, то выбираем выбор количества слов ("words"). Если указано "tags", то выбираем количество тэгов
    select_minimum_parameters.row(
        *[IB(text=str(i),
             callback_data=f'minimum_{"words" if type_setting == "words" else "tags"}_{i}') for i in range(1, 6)], width=1)
    select_minimum_parameters.row(
        IB(text=BACK,
           callback_data='back_to_checking_comment'))
    return select_minimum_parameters.as_markup()


# Кнопка для добавления клавиатуры под добавление примечания к комментарию
def add_note_in_comment_builder(accepted) -> IM:
    back_button = BD()
    # Если комментарий уже написан, то появляется кнопка с возможностью его удаления
    if 'note' in accepted['comment_parameters']:
        back_button.row(
            IB(text=add_task['buttons']['comment_parameters']['delete_note_button'],
               callback_data='delete_note'))
    back_button.row(
        IB(text=BACK,
           callback_data='back_to_comment_parameters'))
    return back_button.as_markup()


# Клавиатура для переспроса у пользователя, точно ли он хочет уйти
def do_you_really_want_to_leave_builder() -> IM:
    do_you_really_want_to_leave_kb = BD()
    do_you_really_want_to_leave_kb.row(
        IB(text=add_task['buttons']['comment_parameters']['leave_button'],
           callback_data='back_to_main_menu'),
        IB(text=add_task['buttons']['comment_parameters']['back_to_setting_button'],
           callback_data='accept_settings_task'))
    return do_you_really_want_to_leave_kb.as_markup()


# Клавиатура под блоком, сообщающим о том, что пользователь ни разу не пополнял свой аккаунт
def not_payments_builder() -> IM:
    not_payments = BD()
    not_payments.row(
        IB(text=payment['buttons']['pay_button'],
           callback_data='first_pay_from_add_task'),
        IB(text=add_task['buttons']['back_setting_button'],
           callback_data='back_accept_setting_task'),
        IB(text=BACK_MAIN_MENU,
           callback_data='back_to_main_menu'), width=1)
    return not_payments.as_markup()


# Клавиатура под блоком, сообщающим пользователю о том, что у него не хватает баланса на добавление задания
def not_money_keyboard_builder(balance_flag=False) -> IM:
    not_money_keyboard = BD()
    not_money_keyboard.row(
        IB(text=payment['buttons']['pay_button'],
           callback_data='pay_from_add_task'))
    # Если у пользователя хватает баланса для добавления минимального количества выполнений и мы просто предлагаем ему изменить количество воркеров
    if balance_flag:
        not_money_keyboard.row(
            IB(text=add_task['buttons']['other_number_user_button'],
               callback_data='accept_all_settings'))
    not_money_keyboard.row(
        IB(text=add_task['buttons']['back_setting_button'],
           callback_data='back_accept_setting_task'),
        IB(text=BACK_MAIN_MENU,
           callback_data='back_to_main_menu'), width=1)
    return not_money_keyboard.as_markup()


# Клавиатура под добавлением количества пользователей, которые должны выполнить задание
async def add_number_user_builder(balance, data) -> IM:
    add_number_user = BD()
    prices = await define_price(data['setting_actions'])
    max_executions = int(balance // prices)
    # Если у юзера хватает баланса на 6 выполнений, то ставим кнопку его макса
    if max_executions >= 6:
        add_number_user.row(
            IB(text=add_task['buttons']['choice_max_button'].format(max_executions),
               callback_data=f'choice_execute_{max_executions}'))
    # Если у юзера хватает баланса на минимум, то ставим кнопку минимума
    if max_executions >= 5:
        add_number_user.row(
            IB(text=add_task['buttons']['choice_min_button'],
               callback_data=f'choice_execute_5'))
    add_number_user.row(
        IB(text=payment['buttons']['pay_button'],
           callback_data='pay_from_add_task'),
        IB(text=BACK,
           callback_data='back_accept_setting_task'), width=1)
    return add_number_user.as_markup()


# Клавиатура под последним принятием всех настроек
def final_add_task_builder() -> IM:
    final_add_task = BD()
    final_add_task.row(
        IB(text=add_task['buttons']['add_task'],
           callback_data='add_finally_task'),
        IB(text=add_task['buttons']['other_number_user_button'],
           callback_data='accept_all_settings'),
        IB(text=add_task['buttons']['back_setting_button'],
           callback_data='back_accept_setting_task'),
        IB(text=BACK_MAIN_MENU,
           callback_data='back_to_main_menu'), width=1)
    return final_add_task.as_markup()


# Клавиатура для добавления нового задания и для перевода пользователя в главное меню
def add_task_keyboad_builder(task_id) -> IM:
    add_task_keyboad = BD()
    add_task_keyboad.row(
        IB(text=add_task['buttons']['go_to_task'],
           callback_data=f'open_active_task_{task_id}'),
        IB(text=add_task['buttons']['add_task_again'],
           callback_data='add_task'),
        IB(text=BACK_MAIN_MENU,
           callback_data='back_to_main_menu'), width=1)
    return add_task_keyboad.as_markup()


# Клавиатура под сообщением о том, что линк не найден
def not_existing_link_builder() -> IM:
    not_existing_link = BD()
    not_existing_link.row(
        IB(text=add_task['buttons']['back_setting_button'],
           callback_data='back_accept_setting_task'),
        IB(text=BACK_MAIN_MENU,
           callback_data='back_to_main_menu'), width=1)
    return not_existing_link.as_markup()


# Клавиатура под уведомлением о завершении таска
def completed_task_keyboard_builder() -> IM:
    completed_task_keyboard = BD()
    completed_task_keyboard.row(
        IB(text=add_task['buttons']['add_task_again'],
           callback_data='add_task'),
        IB(text=payment['buttons']['pay_button'],
           callback_data='pay'),
        IB(text=BACK_MAIN_MENU,
           callback_data='back_to_main_menu'), width=1)
    return completed_task_keyboard.as_markup()
