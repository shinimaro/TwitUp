# Здесь находятся основные ссылки, исполуемые при парсинге
from typing import TypeVar

base_links = {
    # Главная домашняя страница в твиттере
    'home_page': 'https://twitter.com/',
    # Страница, через которую предпочтительнее логиниться
    'login_page': 'https://twitter.com/i/flow/login',
    # Страница для просмотра всех наших пепещиков, но пока аккаунта нужного нет
    'followers_page': f'https://twitter.com/{None}/followers'
}



# Здесь находятся элементами, используемые для работы с подписками
subscribers_blocks = {
    # div блок с @username подписчика
    'username_block': 'css-901oao css-1hf3ou5 r-18u37iz r-37j5jr r-1wvb978 r-a023e6 r-16dba41 r-rjixqe r-bcqeeo r-qvutc0',
    # span блок непосредственной содержащий текст @username
    'username_text': 'css-901oao css-16my406 r-poiln3 r-bcqeeo r-qvutc0',


}

# Здесь находятся элементы, используемые для работы с постами на странице какого-либо аккаунта
post_blocks = {
    # Оболочка для любого поста на странице пользователя и не только на его, а вообще на любой странице
    'post_block': 'css-1dbjc4n r-1loqt21 r-18u37iz r-1ny4l3l r-1udh08x r-1qhn6m8 r-i023vh r-o7ynqc r-6416eg',
    # Достаёт ссылку на сам пост из блока с постом (находится там, где показывается время публикации поста)
    'time_publish': 'css-4rbku5 css-18t94o4 css-901oao r-14j79pv r-1loqt21 r-xoduu5 r-1q142lx r-1w6e6rj r-37j5jr r-a023e6 r-16dba41 r-9aw3ui r-rjixqe r-bcqeeo r-3s2u2q r-qvutc0',
    # Достаёт юзернейм автора какого-либо поста
    'username_author': 'css-901oao css-1hf3ou5 r-14j79pv r-18u37iz r-37j5jr r-1wvb978 r-a023e6 r-16dba41 r-rjixqe r-bcqeeo r-qvutc0',
    # Плашка, на которой написано "N пользователь сделал репост"
    'repost_tag': 'css-1dbjc4n r-1habvwh r-1wbh5a2 r-1777fci',
    # div блок, под которым лежит span блок с текстом поста
    'post_text': 'css-901oao css-cens5h r-18jsvk2 r-37j5jr r-a023e6 r-16dba41 r-rjixqe r-bcqeeo r-bnwqim r-qvutc0'}


# Здесь находятся блоки, появляющиеся при открытии комментария
comment_blocks = {
    # Article блк, по которому можно определить, комментарий ли это
    'comment_block': 'css-1dbjc4n r-18u37iz r-1ny4l3l r-1udh08x r-1qhn6m8 r-i023vh',
    # div блок, под которым непосредственно прячется сам текст комментария (без смайликов, только текст)
    'text_comment': 'css-901oao r-18jsvk2 r-37j5jr r-1inkyih r-16dba41 r-135wba7 r-bcqeeo r-bnwqim r-qvutc0'}


# Здесь находятся блоки, нужные для логина в твитер аккаунт
login_blocks = {
    # Поле для ввода логина
    'username_input': '[autocomplete="username"]',
    # Поле для ввода пароля
    'password_input': '[autocomplete="current-password"]',
    # Кнопочка "далее" после ввода логина
    'next_button': 'css-18t94o4 css-1dbjc4n r-sdzlij r-1phboty r-rs99b7 r-ywje51 r-usiww2 r-2yi16 r-1qi8awa r-1ny4l3l r-ymttw5 r-o7ynqc r-6416eg r-lrvibr r-13qz1uu',
    # Кнопка авторизации, появляющаяся после ввода пароля
    'login_button': '[data-testid="LoginForm_Login_Button"]'}

# Здесь будут находиться другие различные блоки, не относящиеся к блокам, которые выше
other_blocks = {
    # Кнопка "опубликовать пост", которую я обычно юзаю для прогрузки страницы с комментарием,
    # а также для прогрузки домашней страницы при загрузке вебдрайвера
    'publish_button': 'css-1dbjc4n r-l5o3uw r-42olwf r-sdzlij r-1phboty r-rs99b7 r-19u6a5r r-2yi16 r-1qi8awa r-icoktb r-1ny4l3l r-ymttw5 r-o7ynqc r-6416eg r-lrvibr'}

# Здесь находятся различные скрипты, которые могу понадобитья во время парсинга
scripts = {
    # Функция для скрола вниз (стоит 2к, потому что это максимальное число,
    # на которое может опуститься вебдрайвер и не потерять постов/подписчиков
    'scroll': 'window.scrollBy(0, 2000);'}


EL = TypeVar('EL', str, bytes)


# Преобразовывает какой-то элемент в тот, который может прочитать pyppeteer
def converter(block: EL) -> EL:
    return '.' + block.replace(' ', '.')

