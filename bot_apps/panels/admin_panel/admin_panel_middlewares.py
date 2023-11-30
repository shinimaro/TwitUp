from aiogram.types import CallbackQuery

from config import load_config

config = load_config()


class AdminMidelware:
    """Мидлваря для пропуска админа в его панель"""
    def __call__(self, callback: CallbackQuery) -> bool:
        if callback.from_user.id in list(config.tg_bot.admin_ids.values()):
            return True
        return False
