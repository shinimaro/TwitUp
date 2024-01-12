from typing import TypeVar


# Здесь находятся основные ссылки, исполуемые при парсинге
base_links = {
    # Главная домашняя страница в твиттере
    'home_page': 'https://twitter.com/',
    # Страница, через которую предпочтительнее логиниться
    'login_page': 'https://twitter.com/i/flow/login',
    # Страница для просмотра всех наших пепещиков, но пока аккаунта нужного нет
    'followers_page': f'https://twitter.com/{"JJKcontents"}/followers'
}


# Здесь находятся блоки, которые нужны для парсинга самого профиля пользователя
profile_blocks = {
    # div блок, содержащий всю основную информацию профиля при его открыти
    'all_profile_info': 'css-175oi2r r-ymttw5 r-ttdzmv r-1ifxtd0',
    # span блоки с инфой о кол-ве подпискок и подписчиках профиля
    'sub_info_block': 'css-1qaijid r-bcqeeo r-qvutc0 r-poiln3 r-1b43r93 r-1cwl3u0 r-b88u0q',
    # div блок, содержащий информацию о том, что аккаунт в бане
    'ban_block': 'css-175oi2r r-1kihuf0 r-1jgb5lz r-764hgp r-jzhu7e r-13qz1uu r-14lw9ot r-d9fdf6 r-10x3wzx',
    # div блок, говорящий о том, что аккаунт не найден
    'not_account_block': 'css-175oi2r r-1kihuf0 r-1jgb5lz r-764hgp r-jzhu7e r-13qz1uu r-14lw9ot r-d9fdf6 r-10x3wzx'}


# Здесь находятся элементами, используемые для работы с подписками
subscribers_blocks = {
    # div блок с @username подписчика
    'username_block': 'css-1rynq56 r-dnmrzs r-1udh08x r-3s2u2q r-bcqeeo r-qvutc0 r-37j5jr r-a023e6 r-rjixqe r-16dba41 r-18u37iz r-1wvb978',
    # span блок непосредственно содержащий текст @username
    'username_text': 'css-1qaijid r-bcqeeo r-qvutc0 r-poiln3',


}

# Здесь находятся элементы, используемые для работы с постами на странице какого-либо аккаунта
post_blocks = {
    # div оболочка для любого поста на странице пользователя и не только на его, а вообще на любой странице
    'post_block': 'css-175oi2r r-eqz5dr r-16y2uox r-1wbh5a2',
    # a блок, хранящий ссылку на сам пост из блока с постом (находится там, где показывается время публикации поста)
    'time_publish': 'css-1rynq56 r-bcqeeo r-qvutc0 r-37j5jr r-a023e6 r-rjixqe r-16dba41 r-xoduu5 r-1q142lx r-1w6e6rj r-9aw3ui r-3s2u2q r-1loqt21',
    # Див в котором юзернейм автора какого-либо поста, да и вообще содержит любые юзернеймы на странице
    'username_author': 'css-1rynq56 r-dnmrzs r-1udh08x r-3s2u2q r-bcqeeo r-qvutc0 r-37j5jr r-a023e6 r-rjixqe r-16dba41 r-18u37iz r-1wvb978',
    # div блок с плашкой над постом, на которой написано "X сделал(а) репост" и ещё содержит плашку "закреплено" на посте
    'repost_tag': 'css-175oi2r r-1habvwh r-1wbh5a2 r-1777fci',
    # div блок, под которым лежит span блок с текстом поста
    'post_text': 'css-1rynq56 r-8akbws r-krxsd3 r-dnmrzs r-1udh08x r-bcqeeo r-qvutc0 r-37j5jr r-a023e6 r-rjixqe r-16dba41 r-bnwqim'}


# Здесь находятся блоки, появляющиеся при открытии комментария
comment_blocks = {
    # article блок, по которому можно определить, что это пост, ниже которого находится комментарий автора
    'commented_post': 'css-175oi2r r-1ut4w64 r-18u37iz r-1udh08x r-i023vh r-1qhn6m8 r-o7ynqc r-6416eg r-1ny4l3l r-1loqt21',
    # article блок, по которому можно определить, комментарий ли это
    'comment_block': 'css-175oi2r r-18u37iz r-1udh08x r-i023vh r-1qhn6m8 r-1ny4l3l',
    # div блок, под которым непосредственно прячется сам текст комментария (без смайликов, только текст)
    'text_comment': 'css-1rynq56 r-bcqeeo r-qvutc0 r-37j5jr r-1inkyih r-16dba41 r-bnwqim r-135wba7'}


# Здесь находятся блоки, нужные для логина в твитер аккаунт
login_blocks = {
    # Поле для ввода логина
    'username_input': '[autocomplete="username"]',
    # Поле для ввода пароля
    'password_input': '[autocomplete="current-password"]',
    # Кнопочка "далее" после ввода логина
    'next_button': 'css-175oi2r r-sdzlij r-1phboty r-rs99b7 r-lrvibr r-ywje51 r-usiww2 r-13qz1uu r-2yi16 r-1qi8awa r-ymttw5 r-1loqt21 r-o7ynqc r-6416eg r-1ny4l3l',
    # Кнопка авторизации, появляющаяся после ввода пароля
    'login_button': '[data-testid="LoginForm_Login_Button"]'}


# Здесь будут находиться другие различные блоки, не относящиеся к блокам, которые выше
other_blocks = {
    # Кнопка "опубликовать пост", которую я обычно юзаю для прогрузки страницы с комментарием,
    # а также для прогрузки домашней страницы при загрузке вебдрайвера
    'publish_button': 'css-175oi2r r-sdzlij r-1phboty r-rs99b7 r-lrvibr r-19u6a5r r-2yi16 r-1qi8awa r-ymttw5 r-o7ynqc r-6416eg r-icoktb r-1ny4l3l'}

# Здесь находятся различные скрипты, которые могу понадобитья во время парсинга
scripts = {
    # Функция для скрола вниз (стоит 2к, потому что это максимальное число,
    # на которое может опуститься вебдрайвер и не потерять постов/подписчиков
    'scroll': 'window.scrollBy(0, 2000);'}


EL = TypeVar('EL', str, bytes)


# Преобразовывает какой-то элемент в тот, который может прочитать pyppeteer
def converter(block: EL) -> EL:
    return '.' + block.replace(' ', '.')
