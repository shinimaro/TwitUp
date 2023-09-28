from bot_apps.databases.database import db
from bot_apps.databases.database import Database
from urllib.parse import quote


# Функция для формирования реферальных ссылок с текстом в кнопки
async def ref_link_constructor(tg_id):
    # Берём существующий промокод, созданный пользователем
    promocode = await db.get_promocode(tg_id)
    # await db.disconnect()
    # Билдим текст, который нам нужен
    url_base = 'https://t.me/share/url?url=https%3A%2F%2Ft.me%2Fparserochek_bot%3Fstart%3Dr_'
    text_part = quote('\nВ этом боте можно быстро раскрутить свой твиттер')
    encoded_promocode = quote(promocode)
    # И добавляем всё это в текст, который будет в реферальной ссылке
    return f'{url_base}{encoded_promocode}&text={text_part}'


# Функция для формирования ссылки без текста
async def ref_link_no_text(tg_id):
    # Берём промокод
    promocode = await db.get_promocode(tg_id)
    # Суём промокод в ссылку для старта бота
    return f'https://t.me/parserochek_bot?start=r_{promocode}'
