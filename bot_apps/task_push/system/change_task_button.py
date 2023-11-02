from databases.database import db


# Функция по управлению кнопокой и приоритетом, в случаях, когда пользователь ни один раз совершает нехорошие действия
async def change_task_buttons(tasks_msg_id,
                              ignore_task: bool = None,
                              hiding_task: bool = None,
                              refuse_task: bool = None,
                              scored_task: bool = None) -> None:
    # Если пользователь проигнорировал задание
    if ignore_task:
        # Проверяем его последние выполнения заданий
        check = await db.
        # Если он проигнорил уже более 5 заданий подряд
        # if check:
            # Понижаем рейтинг
            # Выключаем кнопку
            # Высылаем сообщение о том, что кнопка была выключена
    # Если пользователь скрыл задание
    elif hiding_task:
        pass
    # Если пользователь отказался от задания
    elif refuse_task:
        pass
    # Если пользователь
    elif scored_task:
        pass