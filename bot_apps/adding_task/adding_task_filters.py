import string

from bot_apps.personal_office.personal_office_filters import correct_account
from bot_apps.wordbank import accounts, add_task


# Функция проверяет ссылку на аккаунт пользователя, а также его юзернейм, используя вспомогательную функцию correct_account
async def is_correct_profile_link(link_name: str) -> bool | str:
    if not link_name:
        return add_task['not_correct_link_profile'].format('не ссылку')
    # Если пользователь указал то, что в примере
    if link_name == 'https://twitter.com/myprofile':
        return add_task['not_correct_link_profile']

    # Пользователь ввёл ссылку
    if link_name.startswith('https://twitter.com/'):
        is_correct = await correct_account(name=link_name)
        # Если в итоге функция вернула True
        if is_correct is True:
            return link_name
        # Если в итоге функция проверки вернула текст ошибки
        else:
            return add_task['not_correct_link_profile'].format(link_name)

    # Пользователь ввёл юзернейм
    elif link_name[0] == '@':
        is_correct = await correct_account(name=link_name)
        # Если функция вернула True
        if is_correct is True:
            return f'https://twitter.com/{link_name[1:]}'
        # Если функция вернулся текст ошибки
        else:
            return add_task['not_correct_link_profile']

    # Пользователь ввёл хуй пойми что
    return add_task['not_correct_link_profile'].format(link_name)


# Проверка ссылки на корректность. Возвращает юзернейм пользователя для его сохранения
async def is_correct_post_link(link: str) -> bool | str:
    if not link:
        return False
    # Проверка начального текста введённой ссылки
    if not link.startswith('https://twitter.com/'):
        return False
    link = link[20:]

    # Проверка части с юзернеймом
    count = 0
    for i in link:
        count += 1
        if i == '/':
            # Проверка на наличие "status" в тексте и итоговую длину
            if link[count:].startswith('status/') and 5 <= len(link[:count - 1]) <= 14 and ' ' not in link[:count - 1]:
                break
            else:
                return False
        # Проверка на символы юзернейма
        if i not in string.ascii_letters + '_' + string.digits:
            return False

    # Проверка id поста
    if len(link[7 + count:]) != 19:
        return False
    for i in link[7 + count:]:
        if i not in string.digits:
            return False
    return '@' + link[:count - 1]  # Возвращает юзернейм из ссылки


# Проверка на корректность примечания для комментария
async def is_correct_note(note: str) -> dict[str | str] | str:
    if not note:
        return add_task['not_correct_note'].format('')

    # Если в примечании есть ссылка
    if 'http' in note:
        return add_task['user_add_advertising']

    # Если примечание слишком длинное
    if len(note.strip()) > 120:
        return add_task['very_long_note'].format(note)
    # Если примечание состоит из 1 буквы
    if len(note.replace(' ', '')) < 2:
        return add_task['not_correct_note'].format(note)

    note_list = [i.strip() for i in note.split()]

    # Если в тексте более 10 слов
    if len(note_list) > 10:
        return add_task['note_more_10_word'].format(note)

    # Проверка слов на символы
    for no in note_list:
        for n in no:
            if n.lower() not in string.digits + string.ascii_letters + 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя' + '!@></.`-~,\#''$%^&*()_+?:%;№"![]{|*}':
                return add_task['not_correct_note'].format(note)

        # Если слово слишком длинное
        if len(no) > 25:
            return add_task['very_long_word_in_note'].format(no, note)

    # Убираем лишние пробелы из ключевых слов
    for _ in range(5):
        if '  ' in note:
            note = note.replace('   ', ' ').replace('  ', ' ')
        else:
            break

    text = [i.strip().capitalize().replace('  ', ' ').replace('  ', ' ') + '.' for i in note.split('.')]
    text = ' '.join(text)
    return {'correct_note': text[:-1] if text[-1] == '.' else text}


# Функция для проверки введённых пользователем тэгов и слов
async def is_correct_words_or_tags(elements: str, only_english=False) -> dict[str | str] | str:
    if not elements:
        return add_task['not_correct_tags/words'].format('')

    main_dict = {'words': [], 'tags': []}
    # Если пользователь в конце указал запятую
    if elements[-1] == ',':
        elements = elements[:-1]
    # Подготовка списка объектов, убирая все пробелы в начале и конце строк
    elem = [i.strip() for i in elements.split(',')]
    # Если пользователь в сумме написал более 10 слов
    if len(elements.split()) > 10:
        return add_task['very_long_tags/words'].format(elements[:150])
    for el in elem:
        # Если пользователь написал ровно ничего
        if not el.replace(' ', ''):
            return add_task['not_correct_tags/words'].format(elements[:150])
        if el[0] != '#':
            # Проходимся по всем элементам строки и убираем пробелы
            for e in el.replace(' ', ''):
                # Если строка содержит неправильные символы
                if e.lower() not in string.digits + string.ascii_letters + 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя' + '!@></.`-~,\#$%^''&*()_+?:%;№"![]{|*}':
                    return add_task['not_correct_word'].format(el, elements[:150])
        # Так же проходимся только по тэгу
        else:
            for e in el[1:]:
                # Если тэг содержит неправильные символы
                if e not in string.digits + string.ascii_letters + '_' + 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя':
                    return add_task['not_correct_tag'].format(el, elements[:150])

        # Проверка тега на длину
        if el[0] == '#':
            if len(el[0:]) > 25:
                return add_task['very_long_tags'].format(el, elements[:150])
            # Если такого же тега нет, то добавляем
            if el not in main_dict['tags']:
                main_dict['tags'].append(el)

        # Проверка ключевого слова на количество слов в нём
        else:
            # Проверка каждого слова на длину
            for i in el.split():
                if len(i) > 25:
                    return add_task['very_long_one_word'].format(el, elements[:150])
            # Убираем лишние пробелы из ключевых слов
            for _ in range(5):
                if '  ' in el:
                    el = el.replace('   ', ' ').replace('  ', ' ')
                else:
                    break

            # Если пробелов овер много
            else:
                return add_task['not_correct_tags/words'].format(elements[:150])
            # Если такого ключевого слова нет, то добавляем
            if el not in main_dict['words']:
                main_dict['words'].append(el)

        # Финальная доп проверка на то, если пользователь указал только инглишь в комментарии, но сам добавил русские буквы
        if only_english:
            for i in elements:
                if i.lower() in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя':
                    return add_task['russian_letter_in_tags/words'].format(elements[:150])

    return main_dict
