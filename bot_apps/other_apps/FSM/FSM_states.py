from aiogram.filters.state import State, StatesGroup


# Различные состояния аккаунта
class FSMAccounts(StatesGroup):
    accounts_menu = State()
    add_account = State()
    rename_account = State()
    add_first_account = State()
    check_account = State()


# Пользователь может оставить отзыв
class FSMReview(StatesGroup):
    leaving_a_review = State()


# Пользователь создаёт промокод
class FSMPromocode(StatesGroup):
    create_promocode = State()


# Пользователь переходит в меню создания задания
class FSMAddTask(StatesGroup):
    add_task = State()
    add_profile_link = State()
    add_post_link = State()
    add_comment_parameters = State()
    add_note = State()
    add_quantity_users = State()


class FSMPersonalTask(StatesGroup):
    add_executions = State()


class FSMAdmin(StatesGroup):
    input_user = State()
    input_user_balance = State()
    input_user_priority = State()
    input_fines_priority = State()
    input_fines_stb = State()
    input_message_from_bot = State()
    input_task_id = State()
    input_fines_id = State()
    input_dop_distribution = State()
    input_add_executions = State()
    input_reduce_exections = State()
    input_link_to_profile = State()
    input_link_to_post = State()
    input_user_to_send = State()
    neutral_state = State()
    input_priority_change = State()
    input_first_fine = State()
    input_subsequent_fines = State()
    input_fines_prority = State()
    input_task_fines = State()
    input_new_admin = State()

    input_new_support = State()

    input_level_limits_tasks = State()
    input_level_limits_accounts = State()
    input_need_for_level_tasks = State()
    input_need_for_level_accounts = State()

    input_price_to_subscriptions = State()
    input_price_to_likes = State()
    input_price_to_retweets = State()
    input_price_to_comments = State()
    input_price_to_commission = State()


class FSMSupport(StatesGroup):
    input_user = State()
    input_user_balance = State()
    input_user_priority = State()
    input_fines_priority = State()
    input_fines_stb = State()
    input_message_from_bot = State()
    input_task_id = State()
    input_task_id_for_accept = State()
    input_fines_id = State()
    input_dop_distribution = State()
    input_add_executions = State()
    input_reduce_exections = State()
    input_link_to_profile = State()
    input_link_to_post = State()
    input_user_to_send = State()
    neutral_state = State()
    input_priority_change = State()
    input_first_fine = State()
    input_subsequent_fines = State()
    input_fines_prority = State()
    input_task_fines = State()
