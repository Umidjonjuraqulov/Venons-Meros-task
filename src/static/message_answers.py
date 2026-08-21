DONT_CHOOSE_ANS = "Не определён"

# ------------------------------------ My tasks -----------------------------------------------------------------------
class MyTaskANS:
    GET_TASKS = "Список задач:\n{task_list}⬇️<b>Для подробности выберите задачу</b>:"
    NOT_TASK = "Нет задач."
    NEXT_ERR = "Больше нет задач!"  # In normal cases the user cannot receive this message
    PREVIOUS_ERR = "Вы в начале списка задач!"  # In normal cases the user cannot receive this message
    CLOSED_ERR = "Нет завершенных задач!"  # In normal cases the user cannot receive this message
    CHOOSE = "Введите № задачи или выберите действие!"
    CHOOSE_ERR = "Нету задачи с таким номером!"
    OBSERVERS_JOIN = "\n🕵️‍♂️ "

    FILES_NONE = "Файлов нет!"

    # Comments
    COMMENTS_LIST = "💬Комментарии:\n{comments_list}"
    COMMENT_LIST_INFO = "<b>----------------------------------------\n<i>👤{name}</i></b>\n<i>🕑{time}</i>\n\n✍️{text}\n"
    COMMENTS_NONE = "К этой задаче не комментариев!"
    WRITE_COMMENT = "🖌Отправьте текст /фото/видео/файл"
    WRITE_COMMENT_DONE = "✅Комментарий отправлен"
    WRITE_COMMENT_FILE_EXIST = "Этот файл уже загружен❗️"
    WRITE_COMMENT_ERR = "❌Ошибка отправки комментария"
    COMMENT_FILE_TXT = "📌Прикрепил файл📁\n"

    # Change stage
    EDITOR_STAGE = "👤<b>{user}</b> сменил стадию:\n\n"
    CHANGE_STAGE = "⬇️Выберите стадию для изменения"
    STAGE_NONE = "❗️Выберите из предложенных стадий"
    CHANGE_STAGE_NONE = "Вы не можете перенести задачу с текущего статуса"
    ROLE_NONE = "У вас нет прав для изменения стадии"
    TASK_CLOSED = "✅Задача уже завершена"

    DELETE_CONFIRM = "⚠️Вы точно хотите удалить задачу?"
    TASK_DELETED_INFO = "🗑Удалена пользователем: <b>{user}</b>"
    DELETE_ERROR = "❌Ошибка удаления, попробуйте позже"

    TASK_INFO = """📋#Задача_{bit_id}: <b>{task_name}</b>
📒Описание: {description}
----------------------------------------
🗓 Дата создания: <b>{created_date}</b>
👤 Заказчик: <b>{creator}</b>
👨🏻‍💻 Исполнитель: <b>{developer}</b>
👨‍💼 Менеджер: <b>{manager}</b>
🕵️‍♂️ Наблюдатели: <b>{observers}</b>
🏢 Подразделение: <b>{group}</b>
📍 Регион: <b>{region}</b>
🔍 Текущий статус: <b>{stage}</b>
"""
    LIST_INFO = """--------------- <b>{id}</b> ---------------
📋 {name}
🗓 Создана: <b>{created_date}</b>
👤 Заказчик: <b>{creator}</b>
👨🏻‍💻 Исполнитель: <b>{developer}</b>
🎯 Статус: {stage}\n\n"""


# ------------------------------------ Notify -------------------------------------------------------------------------
class TaskNFY:
    TASK = """📋#Задача_{bit_id}: <b>{task_name}</b>
----------------------------------------
🗓 Дата создания: <b>{created_date}</b>
👤 Заказчик: <b>{creator}</b>
👨🏻‍💻 Исполнитель: <b>{developer}</b>
👨‍💼 Менеджер: <b>{manager}</b>
🕵️‍♂️ Наблюдатели: <b>{observers}</b>
🏢 Подразделение: <b>{group}</b>
📍 Регион: <b>{region}</b>
🔍 Текущий статус: <b>{stage}</b>
----------------------------------------
"""
    PASSED_QUEUE = """📋#Задача_{bit_id}: <b>{task_name}</b>
----------------------------------------
✅ Задача перенесена из очереди
"""

    NEW_TASK = "🆕 Создано новая задача с Bitrix"
    CREATED_TASK = (
        "👤<b>{name}</b>\n📖Создал задачу: <b>{task_name}</b>\n"
        "🗓 Дата создания: <b>{created_date}</b>\n📒Описание: {description}"
    )
    CHANGE_GROUP = "🏢 Подразделение: <b>{from_} ➡️ {to}</b>"
    TASK_RESPONSIBLE = "👨🏻‍💻<b>{name}</b> назначен исполнителем\n"
    ADD_AUDITOR = "🕵️‍♂️<b>{name}</b> назначен наблюдателем\n"
    ADD_CO_EXECUTOR = "🕵️‍♂️<b>{name}</b> назначен соисполнителем\n"
    DEL_AUDITOR = "🕵️‍♂️<b>{name}</b> удалён из наблюдателей\n"
    DEL_CO_EXECUTOR = "🕵️‍♂️<b>{name}</b> удалён из соисполнителей\n"
    ADD_COMMENT = "💬Добавлен комментарий\n👤<b>{author}</b>\n\n\n✍️{text}"
    BIT_SYNC = "🔄Синхронизация с bitrix завершена!"
    BIT_START_SYNC = "Синхронизация с bitrix..."
    CHECK_TASK = "ℹ️Пожалуйста проверьте и закройте задачу!"
    AUTO_ACCEPTANCE = "ℹ️На тестирование с {time}\n\n" \
        "❗️Задача перенесена в готово, так как она долго оставалась на тестировании без проверки."
    TEST_WARNING = "⚠️ Проверьте задачу в течение <b>{time}ч</b>, чтобы избежать задержек в проведении следующих задач."

    WARNING_MANAGER = "👤<b>{creator}</b> не привязан к подразделению или нет менеджера с привязанной bitrix"


MANAGER_TEXT = "👨‍💼 Менеджер: "  # use in description_title in bitrix
CREATOR_TEXT = "👤 Заказчик: "  # use in description_title in bitrix if creator not have bitrix id


class StageNotify:
    CHANGER_NONE = "❗️Пользователь, изменивший задачу, не найден"
    CHECK_ERROR = "❗️Ошибка проверки статуса, обратитесь администраторам бота\n"

    # Closed task error
    CLOSE_ERR = "❗️Нельзя изменить статус готовых задач\n"

    # Roles
    ROLE_NONE = "❗️Вам <b>не выдан роль</b>, обратитесь администраторам бота\n"
    NOT_TASK_USER = "❗️Вы <b>не участвуете</b> в этой задаче\n"
    CANT_EXTRACT = "❗️У вас нет разрешения на <b>извлечение</b> этой задачи из стадии <b>{stage_name}</b>\n"
    CANT_INSERT = "❗️У вас нет разрешения на <b>вставку</b> этой задачи в стадию <b>{stage_name}</b>\n"

    # Queue
    MAX_IN_STAGE = "❗️Вы превысили <b>максимальное</b> количество задач для стадии <b>{stage_name}</b>\n"
    GROUP_FULL = "🏢<b>{group_name}</b> - превышен лимит выполняемых задач❗️\n"
    CREATOR_FULL = "❗️Нельзя сменить статус, у <b>{name}</b> превышен лимит задач!\n"
    HAS_BAN_TIME = "❗️Вы не можете провести задачи до <b>{time}</b>\nТак как долго не приняли задачу с тестирования\n"
    CLOSE_FROM_TEST = "❗️Завершить задачи можно только с тестирования\n"
    RESPONSIBLE_MAX = "❗️Превышен лимит исполнителя в очереди\n"
    RESPONSIBLE_NONE = "❗️Не выбран исполнитель\n"
    ALLOCATED_TIME_NONE = "❗️Не выделено время на разработку\n"
    TO_DEV_ERROR = "❗️Нельзя переместить задачу на <b>разработку</b> со стадии <b>{from_stage}</b>"
    TO_ERROR = "❗️Можно переместить задачу в <b>ошибку</b> только с <b>тестирования</b>"
    MAX_ACTIVE_TASKS = (
        "🗑Задача <b>{task}</b> удалена, "
        "так как вы превысили лимит активных задач <b>({num})</b> в подразделении <b>{group}</b>"
        "\n\nℹ️Чтобы создать новую задачу, вам необходимо удалить или перевести на оценку свои старые задачи"
    )


class ReviewANS:
    REVIEW_FORMAT = "👤{user}\n\n✍️{text}"
    TEXT = "✍️Напишите отзыв"
    ONLY_TEXT = "🔤Отправьте только текст!"
    SEND = "✅Отправлено"


change_tag = str.maketrans({
    "<": "&lt;",
    ">": "&gt;"
})
