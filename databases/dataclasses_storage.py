import asyncio
import datetime
import json
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import TypedDict, Literal, Union, Optional


class WorkersInfo(TypedDict):
    telegram_id: int
    level: str
    available_accounts: int
    priority: int
    tasks_sent_today: int
    subscriptions: bool
    likes: bool
    retweets: bool
    comments: bool


class WorkersRoundInfo(TypedDict):
    telegram_id: int
    circular_round: Literal[1, 2, 3]
    level: str
    available_accounts: int
    priority: int
    tasks_sent_today: int
    subscriptions: bool
    likes: bool
    retweets: bool
    comments: bool


@dataclass(frozen=True, slots=True)
class TaskInfo:
    executions: int
    completed_tasks: int
    in_process: int


class TaskStatus(Enum):
    WAITING_START = 'подготовка задания к началу'
    BULK_MESSAGING = 'идёт отбор пользователей'
    DOP_BULK_MESSAGING = 'происходит дополнительная рассылка задания'
    ACTIVE = 'задание выполняется'
    COMPLETED = 'задание выполнено'
    DELETED = 'задание удалено'


@dataclass(frozen=True, slots=True)
class ActiveTasks:
    task_number: int
    date_of_creation: datetime.datetime
    number_actions: int
    status: TaskStatus
    completion_percentage: int | float


@dataclass(frozen=True, slots=True)
class LinkAction:
    account_link: str | None
    post_link: str | None


@dataclass(frozen=True, slots=True)
class LinkAction:
    account_link: Optional[str]
    post_link: Optional[str]


class CommentParameter(TypedDict):
    words_count: int | None
    tags_count: int | None
    words_tags: int | None
    note: str | None
    english: bool


@dataclass(frozen=True, slots=True)
class ActionsInfo:
    type_action: dict[Literal['subscriptions', 'likes', 'retweets', 'comments'], Union[LinkAction.post_link, LinkAction.account_link]]
    comment_paremeters: CommentParameter | None


@dataclass(frozen=True, slots=True)
class ActiveTask:
    task_number: int
    date_of_creation: datetime.datetime
    status: TaskStatus
    actions_info: ActionsInfo
    executions: int
    number_completed: int
    completion_percent: int
    doing_now: int
    total_pay: int | float
    remaining_balance: int | float


@dataclass(frozen=True, slots=True)
class HistoryTask:
    task_number: int
    date_of_creation: datetime.datetime
    date_of_completed: datetime.datetime
    completion_in: datetime.timedelta
    status: TaskStatus
    actions_info: ActionsInfo
    executions: int
    completed_task: int
    completion_percent: int
    total_pay: int | float
    fines: int | float


@dataclass(frozen=True, slots=True)
class HistoryTasks:
    task_number: int
    date_of_creation: datetime.datetime
    date_of_completed: datetime.datetime
    completion_in: datetime.timedelta
    status: TaskStatus
    completed_task: int
    executions: int
    completion_percentage: int | float
    total_pay: int | float
    fines: int | float
    type_action: dict[Literal['subscriptions', 'likes', 'retweets', 'comments'], Union[LinkAction.post_link, LinkAction.account_link]] | ActionsInfo


@dataclass(frozen=True, slots=True)
class InfoIncreasedExecutions:
    executions: int
    number_completed: int
    price: int | float
    balance: int | float


@dataclass(frozen=True, slots=True)
class RemainingTaskBalance:
    status: str
    number_rewards: int | float
    number_workers: int
    balance_task: int | float
    number_sent_users: int
    remaining_task_balance: int | float


@dataclass(frozen=True, slots=True)
class FinesInfo:
    count_fines: int
    last_message: datetime.timedelta


@dataclass(frozen=True, slots=True)
class FineInfo:
    fines_id: int
    already_bought: float


@dataclass()
class AllFinesInfo:
    fines_info: FinesInfo
    fines_list: list[FineInfo]


@dataclass(frozen=True, slots=True)
class AdminPanelMainInfo:
    now_time: datetime.datetime
    admin_balance: float
    received_today: float
    spent_on_task: float
    refund_today: float
    earned_by_workers: float
    new_users: int
    new_accounts: int
    new_tasks: int
    sended_tasks: int
    completed_tasks: int
    sended_fines: int


@dataclass(frozen=True, slots=True)
class UsersList:
    tg_id: int
    username: str
    registration_date: datetime.datetime
    priority: int | None
    level: Literal['vacationers', 'prelim', 'main', 'challenger', 'champion'] | None
    number_accounts: int
    number_completed: int
    number_add_tasks: int
    number_active_tasks: int
    number_fines: int


@dataclass()
class UserAllInfo:
    telegram_id: int
    telegram_name: str
    date_join: datetime.datetime
    user_status: str
    balance: float
    count_referrals: int
    inviting_user: str | None
    total_payment: float
    total_earned: float
    spent_on_tasks: float
    total_refund: float
    total_paid: float
    number_tasks: int
    number_active_tasks: int
    sum_collected_fines: float
    sum_uncollected_fines: float
    priority: int
    level: Literal['vacationers', 'prelim', 'main', 'challenger', 'champion', 'beginner']
    active_accounts: int
    total_sent_tasks: int
    total_finished_tasks: int
    total_unfinished_tasks: int
    number_refusals_from_tasks: int
    number_hiding_tasks: int
    number_unviewed_tasks: int
    number_scored_tasks: int
    number_tasks_active_now: list[int]
    number_fines: int
    number_active_fines: int
    fines_on_priority: int
    sum_of_fines: float


@dataclass(frozen=True, slots=True)
class SentTasksInfo:
    task_id: int
    status: str
    offer_time: datetime.datetime | str
    complete_time: datetime.datetime | str


@dataclass(frozen=True, slots=True)
class UserTasksInfo:
    task_id: int
    status: TaskStatus
    date_of_creation: datetime.datetime
    date_of_completed: datetime.datetime
    count_executions: int


@dataclass(frozen=True, slots=True)
class UserAccount:
    account_name: str
    account_status: Literal['active', 'inactive', 'deleted']
    total_executions: int
    adding_time: datetime.datetime


@dataclass(frozen=True, slots=True)
class UserFines:
    fines_id: int
    fines_type: str
    date_added: datetime.datetime
    contents_fine: str
    time_left: datetime.timedelta | None
    stb_left: datetime.timedelta | None


@dataclass(frozen=True, slots=True)
class UserPayments:
    payment_date: datetime.datetime
    amount_pay: float
    issued_by_stb: float
    token: str


@dataclass(frozen=True, slots=True)
class AllTasks:
    task_id: int
    date_of_creation: datetime.datetime
    status: TaskStatus
    executions: int
    completion_percent: int
    completed_tasks: int
    doing_now: int
    total_pay: float
    remaining_balance: float


@dataclass(frozen=True, slots=True)
class TaskAllInfo:
    task_id: int
    telegram_id: int
    status: TaskStatus
    round: int | None
    completed_tasks: int
    executions: int
    completion_percent: int
    doing_now: int
    balance: float
    price: float
    total_pay: float
    remaining_balance: float
    actions_link: LinkAction
    actions: dict[Literal['subscriptions', 'likes', 'retweets', 'comments'], Union[LinkAction.post_link, LinkAction.account_link]]
    comment_parameters: CommentParameter
    total_sent: int
    number_not_viewed: int
    number_more: int
    number_hidden: int
    number_start_task: int
    number_refuse: int
    number_refuse_late: int
    number_scored: int
    number_fully_completed: int
    number_process_subscriptions: int
    number_process_likes: int
    number_process_retweets: int
    number_process_comments: int
    number_waiting_link: int
    date_of_creation: datetime.datetime
    date_of_completed: datetime.datetime
    completion_in: datetime.timedelta
    average_duration: datetime.timedelta


@dataclass(frozen=True, slots=True)
class UsersPerformTask:
    tg_id: int
    telegram_name: str
    status: str
    date_of_sent: datetime.datetime


@dataclass(frozen=True, slots=True)
class RealPricesTask:
    subscriptions: float
    likes: float
    retweets: float
    comments: float
    commission: float


class PriorityChange(TypedDict):
    completing_task: int
    re_execution: int
    max_re_execution: int
    complete_others: int
    downtime_more_20_min: int
    ignore_more_20_min: int
    ignore_more_40_min: int
    ignore_more_60_min: int
    refuse: int
    refuse_late: int
    scored_on_task: int
    ignore_many_times: int
    hidden_many_times: int
    refuse_many_times: int
    scored_many_times: int


@dataclass(frozen=True, slots=True)
class AwardsCut:
    first_fine: Optional[int]
    subsequent_fines: Optional[int]


class AllLevelsLimits(TypedDict):
    tasks_per_day: int | Literal['-']
    max_accs_on_taks: int
    need_task_for_level: int | Literal['-']
    need_accs_for_level: int | Literal['-']


class AllInfoLimits(TypedDict):
    champion: AllLevelsLimits
    challenger: AllLevelsLimits
    main: AllLevelsLimits
    prelim: AllLevelsLimits
    vacationers: AllLevelsLimits
    beginner: AllLevelsLimits


@dataclass(frozen=True, slots=True)
class AdminInfo:
    telegram_id: int
    telegram_name: str
    admin_balance: float


@dataclass(frozen=True, slots=True)
class SupportInfo:
    telegram_id: int
    telegram_name: str
    support_balance: float
    active_status: bool
    main_support: bool


@dataclass(frozen=True, slots=True)
class SupportPanelInfo:
    status: bool
    main_support: bool
    active_tasks: int
    number_offers: int
    active_workers: int


class InfoForDeleteTask(TypedDict):
    telegram_id: int
    message_id: int
    status: str


@dataclass(frozen=True, slots=True)
class FinesPartInfo:
    sum_fines: float
    cut: int
    cut_flag: bool
    remaining_amount: float


@dataclass(frozen=True, slots=True)
class AuthorTaskInfo:
    task_id: int
    links: LinkAction


@dataclass(frozen=True, slots=True)
class InfoForMainMenu:
    total_sent_task: int
    number_accounts: int
    number_sent_tasks: int
    number_completed_tasks: int
    priority: int
    top_priority: bool
    sum_fines_stb: float
    awards_cut: int
    sum_fines_priority: int


@dataclass(frozen=True, slots=True)
class GeneratedWalletInfo:
    wallet_id: int
    valid_until: datetime.timedelta


@dataclass()
class GetWalletIdLock:
    wallet_id_lock = asyncio.Lock()


@dataclass()
class WaitingStartTask:
    waiting_time: int = 60  # Используется в начальном ожидании при старте таска, а также в бд для проверки того, можно ли засчитывать данное задание за удалённое


@dataclass(frozen=True, slots=True)
class PaymentData:
    transaction_id: int
    wallet_id: int
    amount: Decimal
    issued_by_stb: Decimal
    payment_date: datetime.datetime
    token: Literal['USDT', 'USDC', 'BUSD']


@dataclass(frozen=True, slots=True)
class AccountRequirements:
    min_followers: int
    min_following: int
    min_creation_date: datetime.date


@dataclass(frozen=True, slots=True)
class AccountDetails:
    avatar: bool
    followers: int
    following: int
    creation_date: int
    check_posts: bool
