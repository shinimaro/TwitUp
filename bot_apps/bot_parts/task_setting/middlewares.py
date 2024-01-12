import re

from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot_apps.bot_parts.task_push.task_push_text import context_task_builder
from bot_apps.other_apps.wordbank import task_completion
from databases.database import Database

db = Database()


class CommentCheck(BaseFilter):
    """Проверка на то, что есть комментарий, ожидающий проверки"""
    def __init__(self):
        self.result = None

    async def __call__(self, message: Message) -> bool | dict[str, dict[str, str]] | int:
        self.result = await db.get_task_for_link(message.from_user.id, re.search('https://twitter\.com/([\w\d_]{3,})/status/\d{1,19}', message.text.lower()).group(1))
        # Если нет задания, которое ждёт ввода ссылки
        if isinstance(self.result, bool):
            return self.result
        # Если аккаунт в ссылке оказался не тот, который требуют задания, ожидающие ссылку на комментарий
        elif not isinstance(self.result, int):
            return {'result': {self.result['tasks_msg_id']: await self._not_correct_link_text()}}
        else:
            return {'result': self.result}

    async def _not_correct_link_text(self) -> str:
        return (await context_task_builder(self.result['tasks_msg_id'],
                                           self.result['account_name'],
                                           not_complete='comment') + task_completion['not_correct_profile_in_link'] + task_completion['dop_not_check_comment'] + f'<a href="https://twitter.com/{self.result["account_name"][1:]}/with_replies"><b>Ссылка на твои комментарии</b></a>')
