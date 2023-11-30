from aiogram.filters.state import State, StatesGroup


# Различные состояния аккаунта
class FSMAccounts(StatesGroup):
    accounts_menu = State()
    add_account = State()
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
