import asyncio

from databases.database import Database

db = Database()


class SupportName:
    last_index = -1
    lock = asyncio.Lock()

    @classmethod
    async def get_support_name(cls) -> str | None:
        """Взять name активного саппорта, либо, если все спят, дефолт саппорта"""
        async with cls.lock:
            support_names: list[str] = await db.get_active_supports_list()
            if support_names:  # Если указан хотя бы 1 сапорт
                cls._set_last_index(support_names)
                return support_names[cls.last_index]

    @classmethod
    async def get_support_id(cls) -> int:
        """Взять id активного саппорта для отправки ему сообщения"""
        async with cls.lock:
            support_ids: list[int] = await db.get_active_support_ids()
            cls._set_last_index(support_ids)
            return support_ids[cls.last_index]

    @classmethod
    def _set_last_index(cls, supports_list: list):
        """Установить индекс последнего взятого саппорта"""
        cls.last_index = (cls.last_index + 1) % len(supports_list)
