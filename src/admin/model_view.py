import asyncio

from sqladmin import ModelView, action
from starlette.responses import RedirectResponse

from src.db.models import (
    User, Task, TaskUser, File, TaskGroup, Stage, Comment, Department, DepartmentUser, Role, RoleAccess, UserRole,
    UserGroupRules
)
from wtforms import SelectField

from src.classes.cls_const import AccessLevelConst, TaskRole, FileTypeConst, StageType, UserGroupRole
from src.utils.utils import mark_as_paid as m_paid

from src.configuration import conf

from src.i18n.locales import LANGUAGE_CHOICES
from src.i18n.i18n import translate as _

cache = {}
protected_info: dict[int, list] = {}

language_choices = [("", "Не выбран")]
language_choices += [(value, title) for title, value in LANGUAGE_CHOICES.items()]

class UserAdmin(ModelView, model=User):
    page_size = 50
    name = "Пользователь"
    name_plural = "Пользователи"
    icon = "fa-solid fa-user"
    can_create = False
    save_as_continue = False
    can_delete = False

    cache["all_users"]: dict[int, User] = {}
    cache["bit_users_select"]: list[tuple] = []

    column_labels = {
        User.full_name: "ФИО",
        User.phone: "Номер",
        User.job_title: "Должность",
        User.tg_id: "Telegram ID",
        User.bit_user_id: "Bitrix ID",
        User.access_level: "Доступ к боту",
        User.role: "Роль в Bitrix",
        User.role_id: "Роль ID",
        User.ban_time: "Блок до",
        User.max_active_tasks: "Макс. активных задач"
    }
    column_formatters = {
        User.ban_time: lambda m, a: m.ban_time.strftime("%Y.%m.%d %H:%M:%S") if m.ban_time else "",
    }

    column_searchable_list = [User.full_name]
    column_sortable_list = [User.id, User.full_name, User.tg_id, User.bit_user_id, User.role_id]
    column_list = [User.id, User.full_name, User.tg_id, User.bit_user_id, User.role, User.role_id]
    column_details_list = [
        User.id, User.full_name, User.phone, User.job_title, User.language, User.tg_id, User.bit_user_id,
        User.access_level, User.role, User.max_active_tasks, User.ban_time
    ]
    form_columns = [
        User.full_name, User.phone, User.job_title, User.tg_id, User.bit_user_id, User.access_level, User.role,
        User.max_active_tasks, User.ban_time
    ]

    form_overrides = {"access_level": SelectField, "bit_user_id": SelectField, "language": SelectField}

    form_args = {
        "access_level": {
            "choices": [
                (AccessLevelConst.CHECKING, "Ожидает доступа"),
                (AccessLevelConst.BLOCKED, "Заблокировать"),
                (AccessLevelConst.BITRIX, "Bitrix аккаунт"),
                (AccessLevelConst.USER, "Дать доступ"),
                (AccessLevelConst.ADMIN, "Администратор")
            ]
        },
        "language": {
            "choices": language_choices,
        },
        "bit_user_id": {
            "choices": cache["bit_users_select"],
            "coerce": int
        }
    }

    @staticmethod
    async def update_users():
        cache["bit_users_select"].clear()
        cache["bit_users_select"].append((0, "Выберите для изменения"))

        for user in await conf.bitrix_db.get_users():
            cache["all_users"][user.id] = user
            if user.bit_user_id:
                cache["bit_users_select"].append((user.bit_user_id, user.full_name))

    async def scaffold_form(self, rules: list[str] | None = None):
        """load users for select users for link bitrix"""
        form = await super().scaffold_form()
        if not cache["all_users"]:
            await self.update_users()

        return form

    async def on_model_change(self, data, model, is_created, request):
        if data.get("bit_user_id") and (cache["all_users"].get(model.id).bit_user_id != data.get("bit_user_id")):
            bit_user = await conf.bitrix_db.get_user(bit_id=data.get("bit_user_id"))
            await conf.bitrix_db.merge_users(from_user_id=bit_user[0].id, to_user_id=model.id)

    async def after_model_change(self, data, model, is_created, request):
        access_level = data.get("access_level")
        tg_id = data.get("tg_id")

        if not cache["all_users"].get(model.id):
            await self.update_users()

        if cache["all_users"].get(model.id).access_level != access_level and tg_id:
            if access_level in (AccessLevelConst.USER, AccessLevelConst.ADMIN):
                await conf.notify_manager.notify(_("reg.success", model.language), [tg_id])
                conf.user_manager.update_user(tg_id=tg_id, access_level=access_level)

            elif access_level == AccessLevelConst.BLOCKED:
                await conf.notify_manager.notify(_("reg.blocked", model.language), [tg_id])
                conf.user_manager.update_user(tg_id=tg_id, access_level=AccessLevelConst.BLOCKED)

            else:
                conf.user_manager.update_user(tg_id=tg_id, access_level=access_level)

        if data.get("bit_user_id") == 0:
            await conf.bitrix_db.update_user(update_to=model)

        await self.update_users()

    async def after_model_delete(self, model, request):
        if model.tg_id:
            conf.user_manager.delete_user(model.tg_id)

        await self.update_users()


class DepartmentAdmin(ModelView, model=Department):
    page_size = 25
    name = "Подразделение"
    name_plural = "Подразделения"
    icon = "fa-solid fa-city"
    can_create = True
    save_as_continue = False

    column_labels = {
        Department.name: "Название",
        "parent.name": "Подчиняется",
        Department.parent: "Подчиняется",
        Department.bit_dep_id: "Bitrix ID",
        Department.department_users: "Сотрудники"
    }

    column_searchable_list = [Department.name]
    column_list = [Department.id, Department.name, "parent.name", Department.bit_dep_id]
    column_details_list = [Department.id, Department.name, "parent.name", Department.bit_dep_id, "department_users"]
    form_columns = [Department.id, Department.name, Department.parent, Department.bit_dep_id]


class DepartmentUserAdmin(ModelView, model=DepartmentUser):
    page_size = 25
    name = "Сотрудник"
    name_plural = "Сотрудники"
    icon = "fa-solid fa-user-tie"
    can_create = True
    save_as_continue = False
    column_sortable_list = [DepartmentUser.id, "department.name", DepartmentUser.head, "user.full_name"]

    column_labels = {
        "department.name": "Название подразделения",
        "user.full_name": "user",
        DepartmentUser.head: "manager",
    }

    form_ajax_refs = {
        "user": {
            "fields": ("full_name",),
            "order_by": "full_name",
        }
    }

    column_searchable_list = ["user.full_name"]
    column_list = [Department.id, "department.name", "user.full_name", DepartmentUser.head]
    column_details_list = [Department.id, "department.name", "user.full_name", DepartmentUser.head]


class TaskGroupAdmin(ModelView, model=TaskGroup):
    page_size = 25
    name = "Группа задачи"
    name_plural = "Группа задач"
    icon = "fa-solid fa-layer-group"
    can_create = False
    save_as_continue = False
    can_delete = True

    column_labels = {
        TaskGroup.title: "Название",
        TaskGroup.bit_group_id: "Bitrix ID",
        TaskGroup.bit_folder_id: "ID Папки проекта",
        TaskGroup.max_tasks: "Задач в очереди",
        TaskGroup.max_user_tasks: "Задач менеджера в очереди",
        TaskGroup.max_executor_task: "Задач испол. в очереди",
        TaskGroup.max_active_tasks: "Задач (вне готова)",
        TaskGroup.ban_hours: "Часы для блокировки",
        TaskGroup.auto_acceptance: "Часы для авто принятия",
        TaskGroup.notify: "Уведомление FIFO",
        TaskGroup.fifo_queue: "FIFO",
        TaskGroup.analytics: "Аналитика",
        TaskGroup.close_from_test: "Завершить с теста"
    }

    column_list = [TaskGroup.id, TaskGroup.title, TaskGroup.max_tasks, TaskGroup.bit_group_id]
    column_details_list = [
        TaskGroup.id, TaskGroup.title,
        TaskGroup.max_tasks, TaskGroup.max_user_tasks, TaskGroup.max_executor_task, TaskGroup.max_active_tasks,
        TaskGroup.auto_acceptance, TaskGroup.ban_hours,
        TaskGroup.bit_group_id, TaskGroup.bit_folder_id,
        TaskGroup.fifo_queue, TaskGroup.notify, TaskGroup.analytics, TaskGroup.close_from_test
    ]
    form_columns = [
        TaskGroup.title,
        TaskGroup.max_tasks, TaskGroup.max_user_tasks, TaskGroup.max_executor_task, TaskGroup.max_active_tasks,
        TaskGroup.auto_acceptance, TaskGroup.ban_hours,
        # TaskGroup.bit_group_id, TaskGroup.bit_folder_id,
        TaskGroup.fifo_queue, TaskGroup.notify, TaskGroup.analytics, TaskGroup.close_from_test
    ]

    async def on_model_change(self, data, model, is_created, request):
        if not is_created:
            model: TaskGroup
            protected_info[model.id] = [model.title, model.max_executor_task, model.close_from_test]

    async def after_model_change(self, data, model, is_created, request):
        if not is_created:
            model: TaskGroup
            before_edit = protected_info[model.id]

            if model.title != before_edit[0] and model.title[-1] == ".":  # a secret method for changing private fields
                model.title = before_edit[0]
                await conf.bitrix_db.update_task_group(model)

            elif before_edit[1] != model.max_executor_task or before_edit[2] != model.close_from_test:
                model.max_executor_task = before_edit[1]
                model.close_from_test = before_edit[2]
                await conf.bitrix_db.update_task_group(model)


class StageAdmin(ModelView, model=Stage):
    page_size = 25
    name = "Стадия задачи"
    name_plural = "Стадии задач"
    icon = "fa-solid fa-angles-right"
    can_create = False
    can_edit = True
    save_as_continue = True
    can_delete = True

    column_labels = {
        Stage.group: "Группа задачи",
        Stage.title: "Название",
        Stage.sort: "Позиция в Bitrix",
        Stage.bit_stage_id: "Bitrix ID",
        Stage.tasks: "Задачи",
        Stage.max_tasks: "Максимум задач",
        Stage.in_queue: "Включить в очередь",
        Stage.stage_type: "Тип стадии"
    }

    column_default_sort = [(Stage.group_id, False), (Stage.sort, False)]

    column_list = [Stage.id, Stage.group, Stage.title, Stage.sort, Stage.max_tasks, Stage.in_queue]
    column_details_list = [
        Stage.id, Stage.group, Stage.title, Stage.sort, Stage.bit_stage_id, Stage.tasks, Stage.max_tasks,
        Stage.in_queue, Stage.stage_type
    ]
    form_columns = [
        Stage.id, Stage.group, Stage.title, Stage.sort, Stage.bit_stage_id, Stage.max_tasks,
        Stage.in_queue, Stage.stage_type
    ]

    form_overrides = {"stage_type": SelectField}
    form_args = {
        "stage_type": {
            "choices": [
                ("", "Обычная стадия"),
                (StageType.FIFO, "Очередь FIFO"),
                (StageType.TESTING, "Тестовая"),
                (StageType.DEVELOP, "Разработка"),
                (StageType.WAIT, "Ожидание"),
                (StageType.ERROR, "Ошибка")
            ]
        }
    }


class TaskAdmin(ModelView, model=Task):
    page_size = 25
    name = "Задача"
    name_plural = "Задачи"
    icon = "fa-solid fa-list-check"
    can_create = False
    save_as_continue = False

    column_labels = {
        Task.title: "Название",
        Task.description: "Описание",
        Task.created_date: "Создано",
        Task.queue_date: "Дата в очереди",
        Task.deadline: "Срок",
        Task.test_date: "На тестирование с",
        Task.closed_date: "Выполнено в",
        Task.bit_task_id: "ID Задачи",
        Task.bit_folder_id: "ID Папки в Bitrix",
        Task.bit_chat_id: "ID чата в Bitrix",
        Task.group: "Группа задачи",
        Task.stage_id: "ID стадии",
        Task.stage: "Текущая стадия",
        Task.task_users: "Участники",
        Task.files: "Файлы",
        Task.comments: "Комментарии",
        Task.allocated_time: "Выделенное время",
        Task.unlimited_test: "Безлимитный тест",
        Task.paid: "Оплачено"
    }
    column_formatters = {
        Task.title: lambda m, a: m.title if len(m.title) < 50 else f"{m.title[:50]}...",
        Task.created_date: lambda m, a: m.created_date.strftime("%d.%m.%Y") if m.created_date else "",
        Task.queue_date: lambda m, a: m.queue_date.strftime("%d.%m.%Y %H:%M") if m.queue_date else "",
        Task.deadline: lambda m, a: m.deadline.strftime("%d.%m.%Y") if m.deadline else "",
        Task.test_date: lambda m, a: m.deadline.strftime("%d.%m.%Y") if m.test_date else "",
        Task.closed_date: lambda m, a: m.closed_date.strftime("%d.%m.%Y") if m.closed_date else ""
    }

    # view list
    column_searchable_list = [Task.title, Task.stage_id]
    column_default_sort = [(Task.id, True)]
    column_sortable_list = [
        Task.id, Task.stage_id, Task.paid, Task.created_date, Task.queue_date, Task.deadline, Task.closed_date
    ]

    column_list = [
        Task.id, Task.title, Task.stage, Task.stage_id, Task.paid,
        Task.created_date, Task.queue_date, Task.deadline, Task.closed_date
    ]

    # view
    column_details_list = [
        Task.id, Task.bit_task_id, Task.bit_folder_id, Task.bit_chat_id, Task.title, Task.description, Task.task_users,
        Task.created_date, Task.queue_date, Task.deadline, Task.test_date, Task.closed_date, Task.allocated_time,
        Task.group, Task.stage,
        Task.files, Task.comments, Task.unlimited_test, Task.paid
    ]
    form_columns = [
        Task.title, Task.description, Task.bit_folder_id, Task.bit_chat_id, Task.group, Task.stage,
        Task.queue_date, Task.test_date, Task.closed_date, Task.allocated_time, Task.unlimited_test, Task.paid
    ]

    @action(
        name="mark_as_paid",
        label="Отметить как оплачено",
        confirmation_message="Отметить эти как оплачено?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def mark_as_paid(self, request):
        pks = request.query_params.get("pks", "").split(",")
        if pks:
            try:
                conf.tasks.append(
                    asyncio.create_task(m_paid([int(i) for i in pks], conf))
                )
            except Exception as e:
                print(e)

        referer = request.headers.get("Referer")

        if referer:
            return RedirectResponse(referer)
        else:
            return RedirectResponse(request.url_for("admin:list", identity=self.identity))


class TaskUserAdmin(ModelView, model=TaskUser):
    page_size = 25
    name = "Пользователи задачи"
    name_plural = "Пользователи задач"
    icon = "fa-solid fa-user-check"
    can_create = True
    save_as_continue = False

    column_labels = {
        TaskUser.task: "Задача",
        TaskUser.user: "Пользователь",
        TaskUser.role: "Роль"
    }

    form_overrides = {"role": SelectField}

    form_args = {
        "role": {
            "choices": [
                (TaskRole.OBSERVER, "Наблюдатель"),
                (TaskRole.CREATOR, "Создатель"),
                (TaskRole.EXECUTOR, "Выполняющий"),
                (TaskRole.MANAGER, "Менеджер"),
                (TaskRole.CO_EXECUTOR, "Соисполнитель")
            ]
        }
    }

    form_ajax_refs = {
        "user": {
            "fields": ("full_name",),
            "order_by": "full_name",
        },
        "task": {
            "fields": ("title",),
            "order_by": "title",
        }
    }

    column_searchable_list = ["user.full_name"]
    column_list = [TaskUser.id, TaskUser.task, TaskUser.user, TaskUser.role]
    column_sortable_list = [TaskUser.role]
    column_details_list = [TaskUser.id, TaskUser.task, TaskUser.user, TaskUser.role]
    form_columns = [TaskUser.id, TaskUser.task, TaskUser.user, TaskUser.role]


class FileAdmin(ModelView, model=File):

    page_size = 25
    name = "Файл"
    name_plural = "Файлы"
    icon = "fa-solid fa-file"
    can_create = False
    save_as_continue = False

    column_labels = {
        File.task: "Задача",
        File.user: "Пользователь",
        File.name: "Название",
        File.description: "Описание",
        File.type: "Тип файла",
        File.bit_file_id: "Bit file ID",
        File.tg_file_id: "Telegram file ID",
        File.comment: "Комментарий (от Bitrix)"
    }

    form_overrides = {"type": SelectField}

    form_args = {
        "type": {
            "choices": [
                (FileTypeConst.DOCUMENT, "Документ"),
                (FileTypeConst.PHOTO, "Фото"),
                (FileTypeConst.VIDEO, "Видео"),
                (FileTypeConst.VIDEO_NOTE, "Видео кружок"),
                (FileTypeConst.VOICE, "Голосовой")
            ]
        }
    }

    form_ajax_refs = {
        "task": {
            "fields": ("title",),
            "order_by": "title",
        }
    }

    column_list = [File.id, File.task, File.name, File.user]
    column_searchable_list = [File.name]

    column_details_list = [
        File.task, File.user, File.name, File.description, File.type, File.bit_file_id, File.tg_file_id, File.comment
    ]
    form_columns = [
        File.task, File.user, File.name, File.description, File.type, File.bit_file_id, File.tg_file_id, File.comment
    ]


class CommentAdmin(ModelView, model=Comment):
    name = "Комментарий"
    name_plural = "Комментарии"
    icon = "fa-solid fa-message"
    can_create = False
    save_as_continue = False

    column_labels = {
        Comment.task: "Задача",
        Comment.user: "Пользователь",
        Comment.text: "Комментарий",
        File.description: "Описание",
        File.type: "Тип файла",
        File.bit_file_id: "Bit file ID",
        File.tg_file_id: "Telegram file ID",
        File.comment: "Комментарий (от Bitrix)"
    }

    form_ajax_refs = {
        "task": {
            "fields": ("title",),
            "order_by": "title",
        }
    }

    column_list = [Comment.id, Comment.task, Comment.user, Comment.text]
    column_searchable_list = [Comment.text]

    column_details_list = [
        Comment.id, Comment.task, Comment.text, Comment.user, Comment.bit_comment_id, Comment.created_date
    ]
    form_columns = [
        Comment.id, Comment.task, Comment.text, Comment.user, Comment.bit_comment_id, Comment.created_date
    ]


class RoleAdmin(ModelView, model=Role):
    name = "Роль"
    name_plural = "Роли"
    icon = "fa-solid fa-address-card"
    can_create = True
    save_as_continue = False

    column_labels = {
        Role.name: "Название",
        Role.notify_queue: "Получение уведомлений при завершение",
        Role.change_any: "Изменять любые задачи",
        Role.access_all_stage: "Доступ ко всем стадиям",
        Role.users: "Пользователи",
        Role.access: "Права"
    }

    column_list = [Role.id, Role.name]

    column_details_list = [Role.id, Role.name, Role.access_all_stage, Role.change_any, Role.notify_queue, Role.users]
    form_columns = [Role.name, Role.access_all_stage, Role.change_any, Role.notify_queue]


class RoleAccessAdmin(ModelView, model=RoleAccess):
    name = "Пава роли"
    name_plural = "Права ролей"
    icon = "fa-solid fa-key"
    page_size = 100
    can_create = True
    save_as_continue = False

    column_labels = {
        RoleAccess.insert: "Вставлять",
        RoleAccess.extract: "Извлекать",
        RoleAccess.role: "Роль",
        RoleAccess.stage: "Статус"
    }

    column_list = [RoleAccess.id, RoleAccess.role, RoleAccess.stage, RoleAccess.insert, RoleAccess.extract]
    column_sortable_list = [RoleAccess.id, RoleAccess.insert, RoleAccess.extract]
    column_default_sort = [(RoleAccess.role_id, False), (RoleAccess.stage_id, False)]

    column_details_list = [RoleAccess.id, RoleAccess.role, RoleAccess.stage, RoleAccess.insert, RoleAccess.extract]
    form_columns = [RoleAccess.role, RoleAccess.stage, RoleAccess.insert, RoleAccess.extract]


class UserRoleAdmin(ModelView, model=UserRole):
    page_size = 100
    name = "Доп. роль"
    name_plural = "Доп. роли"
    icon = "fa-solid fa-elevator"
    can_create = True
    save_as_continue = False
    column_sortable_list = ["user.full_name", "role.name"]

    column_labels = {
        "user.full_name": "Пользователь",
        "role.name": "Роль"
    }

    form_ajax_refs = {
        "user": {
            "fields": ("full_name",),
            "order_by": "full_name",
        }
    }

    column_searchable_list = ["user.full_name"]
    column_list = ["user.full_name", "role.name"]
    column_details_list = ["user.full_name", "role.name"]


class UserGroupRulesAdmin(ModelView, model=UserGroupRules):
    page_size = 25
    name = "Пользователь и группа"
    name_plural = "Пользователи и группы"
    icon = "fa-solid fa-user-group"
    can_create = True
    can_edit = True
    save_as_continue = True
    can_delete = True

    column_sortable_list = ["user.full_name", "group.title"]

    column_labels = {
        "user.full_name": "Пользователь",
        "group.title": "Группа"
    }

    form_ajax_refs = {
        "user": {
            "fields": ("full_name",),
            "order_by": "full_name",
        }
    }

    column_searchable_list = ["user.full_name"]
    column_list = ["user.full_name", "group.title"]
    column_details_list = ["user.full_name", "group.title"]

    form_overrides = {"observer": SelectField, "manager": SelectField}
    form_args = {
        "observer": {
            "choices": [
                ("", "Обычный"),
                (UserGroupRole.NEWER, "Никогда"),
                (UserGroupRole.ALLWAYS, "Всегда"),
            ]
        },
        "manager": {
            "choices": [
                ("", "Обычный"),
                (UserGroupRole.NEWER, "Никогда"),
                (UserGroupRole.ALLWAYS, "Всегда"),
            ]
        }
    }
