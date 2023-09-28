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


# Пользователь переходит в меню выполнения задания
class FSMAddTask(StatesGroup):
    add_task = State()
    add_profile_link = State()
    add_post_link = State()
    add_comment_parameters = State()
    add_note = State()
    add_quantity_users = State()
