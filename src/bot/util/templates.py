from datetime import datetime
from functools import wraps
from logging import ERROR

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, BufferedInputFile, ReplyKeyboardMarkup

from src.bot.structures.fsm import User, Registration
from src.bot.structures.keyboards import user_main_rkb, build_rkb, back_and_cancel_rkb, comment_answer_ikb, choose_language
from src.static.message_answers import (
    TaskNFY, MyTaskANS, DONT_CHOOSE_ANS, MANAGER_TEXT, change_tag
)

from src.db.models import Task, File, TaskGroup, TaskUser, Region
from src.classes.data_classes import TaskInfo
from src.classes.cls_const import TaskRole, FileTypeConst, StageType

from src.configuration import conf

from src.i18n.locales import START_MESSAGE
from src.i18n.i18n import translator, translate as _


async def create_task(
        bot: Bot,
        title: str, description: str,
        files: list[str],  # [tg_file_id, file_name, file_type]
        user_tg_id: int, group: str, region: str | None,
        deadline: datetime = None,
        executor_id: int = None
) -> bool:
    try:
        # Get info task_group_db, task_user_db
        task_group_db = await conf.bitrix_db.get_task_group(title=group)
        task_group_db = task_group_db[0]
        task_region_db = await conf.bitrix_db.get_regions(group_id=task_group_db.id, name=region)
        task_region_db = task_region_db[0] if task_region_db else None
        task_user_db = await conf.bitrix_db.get_user(tg_id=user_tg_id)
        task_user_db = task_user_db[0]
        executor_user_db = await conf.bitrix_db.get_user(id_=executor_id)
        executor_user_db = executor_user_db[0] if executor_user_db and executor_id else None
        if conf.debug:
            current_user_db = task_user_db
        else:
            current_user_db = await conf.bitrix_db.get_user(bit_id=conf.bitrix.conf.data.current_id)
            current_user_db = current_user_db[0]
        executor_user_db = current_user_db if not executor_user_db else executor_user_db
        """used for the role of performer"""

        # Take a place in the database to get Task id
        task_in_db = Task(
            title=title, description=description, created_date=datetime.now(),
            deadline=deadline, group_id=task_group_db.id, region_id=task_region_db.id if task_region_db else None
        )
        task_in_db = await conf.bitrix_db.add_task(task_in_db)

        # Link users in task_users.
        await conf.bitrix_db.add_task_user(user_id=task_user_db.id, task_id=task_in_db.id, role=TaskRole.CREATOR)
        await conf.bitrix_db.add_task_user(user_id=executor_user_db.id, task_id=task_in_db.id, role=TaskRole.EXECUTOR)

        tg_id_observers = set()
        bit_id_observers = set()
        manager, observers, without_manager = await conf.bit_sync.get_manager_and_observers(task_in_db, task_user_db)
        await conf.bitrix_db.add_task_user(user_id=manager.id, task_id=task_in_db.id, role=TaskRole.MANAGER)

        for observer in observers.values():
            await conf.bitrix_db.add_task_user(user_id=observer.id, task_id=task_in_db.id, role=TaskRole.OBSERVER)

            if observer.tg_id:
                tg_id_observers.add(observer.tg_id)

            if observer.bit_user_id:
                bit_id_observers.add(observer.bit_user_id)

        # Create a project folder in Bitrix.
        project_folder = await conf.bitrix.create_folder(
            target_id=task_group_db.bit_folder_id, name=f"{task_in_db.id}_{title}"
        )

        # Download the file and upload the file to Bitrix.
        bitrix_files = []
        uploaded_files = set()
        for file_info in files:
            try:
                if file_info[1] in uploaded_files:  # skip duplicates
                    continue
                uploaded_files.add(file_info[1])

                file = await bot.download(file_info[0])
                bit_file = await conf.bitrix.upload_file(
                    folder_id=project_folder, file_name=file_info[1], file=file
                )
                bitrix_files.append(bit_file["ID"])
                file_in_db = File(
                    task_id=task_in_db.id,
                    user_id=task_user_db.id,
                    tg_file_id=file_info[0],
                    bit_file_id=int(bit_file["ID"]),
                    name=file_info[1],
                    description=file_info[3],
                    type=file_info[2]
                )
                await conf.bitrix_db.add_file(file_in_db)
            except Exception as e:
                await conf.logger.send_log(
                    ERROR, "templates.py -> create_task -> uploading files", e=e, msg=f"{file_info}"
                )

        # Create a new task in Bitrix.
        description_title = f"{MANAGER_TEXT}{manager.full_name}\n"

        task = await conf.bitrix.create_task(
            title=f"{title} | {region}" if region else title,
            description=description_title + description,
            deadline=deadline, files=bitrix_files,
            group_id=task_group_db.bit_group_id, creator_id=task_user_db.bit_user_id,
            executor_id=executor_user_db.bit_user_id if executor_user_db else None,
            auditors=list(bit_id_observers)
        )

        if not task:  # delete if task can not create
            await conf.bitrix_db.delete_info(selected_model=Task, id_=task_in_db.id)
            return False

        # Check stages
        stage_in_db = await conf.bitrix_db.get_task_stage(bit_stage_id=int(task["task"]["stageId"]))
        if not stage_in_db:
            await conf.bit_sync.sync_stages()
            stage_in_db = await conf.bitrix_db.get_task_stage(bit_stage_id=int(task["task"]["stageId"]))

        # Update Task
        task_in_db.bit_task_id = int(task["task"]["id"])
        task_in_db.bit_chat_id = int(task["task"]["chatId"])
        task_in_db.bit_folder_id = project_folder
        task_in_db.stage_id = stage_in_db[0].id
        await conf.bitrix_db.update_task(task_in_db)

        if tg_id_observers:
            msg = TaskNFY.CREATED_TASK.format(
                name=task_user_db.full_name, task_name=task_in_db.title.translate(change_tag),
                description=task_in_db.description[0:2048].translate(change_tag)
            )
            await conf.notify_manager.notify(msg=msg, tg_ids=tg_id_observers)

        if without_manager:
            warning_msg = (
                TaskNFY.WARNING_MANAGER.format(creator=task_user_db.full_name) +
                f'\n<a href="{conf.project_url}/admin/department-user/create">Прикрепить к подразделению</a>'
            )
            await conf.bitrix_db.add_task_user(user_id=task_user_db.id, task_id=task_in_db.id, role=TaskRole.MANAGER)
            # await conf.notify_manager.notify(msg=warning_msg, tg_ids=[conf.notify_chat_id])

        return True

    except Exception as e:
        await conf.logger.send_log(ERROR, "templates.py -> create_task", e=e)
        return False


async def get_tasks_list(tg_id: int, roles: list[str]) -> list[TaskInfo]:
    try:
        result = []
        user_info = await conf.bitrix_db.get_user(tg_id=tg_id)

        user_tasks: list[TaskUser] = []
        for role in roles:
            user_tasks += await conf.bitrix_db.get_task_user(user_id=user_info[0].id, role=role)

        user_tasks.sort(key=lambda x: (x.task.group_id, x.task.stage.sort if x.task.stage else 0))
        include = set()
        for task_user in user_tasks:
            if task_user.task.id in include:
                continue

            include.add(task_user.task.id)
            task_users = await conf.bitrix_db.get_task_user(task_id=task_user.task.id)
            task_users_role = conf.bitrix_db.sort_task_roles(task_users=task_users)

            developer_name = task_users_role.executor.user.full_name if task_users_role.executor else DONT_CHOOSE_ANS
            creator_name = task_users_role.creator.user.full_name if task_users_role.creator else DONT_CHOOSE_ANS
            manager_name = task_users_role.manager.user.full_name if task_users_role.manager else DONT_CHOOSE_ANS
            observers = [user.user.full_name for user in task_users_role.observers]

            # when task creating error
            result.append(
                TaskInfo(
                    db_id=task_user.task.id,
                    bit_id=task_user.task.bit_task_id,
                    title=task_user.task.title.translate(change_tag),
                    description=task_user.task.description[0:2048].translate(change_tag),
                    group=task_user.task.group.title,
                    region=task_user.task.region.name if task_user.task.region else DONT_CHOOSE_ANS,
                    stage=task_user.task.stage.title if task_user.task.stage else "None",
                    create_date=task_user.task.created_date,
                    deadline=task_user.task.deadline,
                    closed_date=task_user.task.closed_date,
                    creator=creator_name,
                    developer=developer_name,
                    manager=manager_name,
                    observers=observers,
                    can_delete=can_delete(task_user.task)
                )
            )

        return result

    except Exception as e:
        await conf.logger.send_log(ERROR, "templates.py -> get_tasks_list", e=e)


async def get_task_files(task_db_id: int) -> list:
    files = await conf.bitrix_db.get_files(task_id=task_db_id)
    return [[i.tg_file_id, i.name, i.type, i.description] for i in files]


def format_task_list(tasks: dict[int, TaskInfo], page: int, lines: int = 10) -> str:
    result = ""
    for index, info in list(tasks.items())[lines*page-lines:lines*page]:
        result += MyTaskANS.LIST_INFO.format(
            id=index, name=f"№{info.bit_id} - {info.title[:50].translate(change_tag)}",
            creator=info.creator, developer=info.developer, stage=info.stage
        )

    return result


async def get_tasks_comments(task_db_id: int) -> list[list[str]]:
    try:
        result = []
        comments = await conf.bitrix_db.get_comment(task_id=task_db_id)
        for comment in comments:
            result.append(
                [
                    comment.user.full_name if comment.user_id else "-",
                    comment.created_date.strftime("%Y.%m.%d %H:%M"),
                    comment.text
                ]
            )

        return result
    except Exception as e:
        await conf.logger.send_log(ERROR, "templates -> get_tasks_comments", e=e)
        return []


def format_task_comments(
        task_info: TaskInfo, comments: list[list[str]], previous_page: int = 1, msg_len: int = 3072
) -> str:
    title = TaskNFY.TASK.format(
        bit_id=task_info.bit_id,
        task_name=task_info.title.translate(change_tag),
        creator=task_info.creator,
        developer=task_info.developer,
        manager=task_info.manager or DONT_CHOOSE_ANS,
        observers=MyTaskANS.OBSERVERS_JOIN.join(task_info.observers) if task_info.observers else DONT_CHOOSE_ANS,
        group=task_info.group,
        region=task_info.region,
        stage=task_info.stage
    )
    comments = comments[::-1]
    comments_number = len(comments)
    title_size = len(title)
    page = 0
    result = ""

    for i in range(comments_number):
        comment = MyTaskANS.COMMENT_LIST_INFO.format(
            name=comments[i][0], time=comments[i][1], text=comments[i][2].translate(change_tag)
        )

        if len(result) + len(comment) + title_size < msg_len:
            result = comment + result
        else:
            page += 1
            if page == previous_page:
                if result:
                    return title + MyTaskANS.COMMENTS_LIST.format(comments_list=result)
                else:  # if last comment is very large
                    return title + MyTaskANS.COMMENTS_LIST.format(
                        comments_list=comment[:msg_len - title_size]+"...✍️"
                    )
            result = comment  # Start new page with the current comment

    # If loop finishes and result is still not returned
    if page + 1 == previous_page:
        return title + MyTaskANS.COMMENTS_LIST.format(comments_list=result)

    # If no matching page found, return an empty response or some error message
    return ""


async def write_comment(
        task_db_id: int, user_tg_id: int, text: str, file_info: list = None, bot: Bot = None
) -> bool | str:
    try:
        user = await conf.bitrix_db.get_user(tg_id=user_tg_id)
        user = user[0]
        task = await conf.bitrix_db.get_task(id_=task_db_id)
        if not task:
            return False
        task = task[0]

        if not file_info:
            if not user.bit_user_id:
                bit_text = MyTaskANS.COMMENT_LIST_INFO.format(name=user.full_name, time=datetime.now(), text=text)
            else:
                bit_text = text

            comment_id = await conf.bitrix.add_comment(
                task_id=task.bit_task_id, message=bit_text, creator_id=user.bit_user_id
            )

            if not comment_id:
                return False

            await conf.bitrix_db.add_comment(task_id=task.id, user_id=user.id, bit_comment_id=comment_id, text=text)

        else:
            # check duplicates
            exits = await conf.bitrix_db.get_files(task_id=task_db_id, file_name=file_info[1])
            if exits:
                return "exist"

            text = TaskNFY.ADD_COMMENT.format(
                author=user.full_name,
                text=f"{file_info[3] or ''}\n{MyTaskANS.COMMENT_FILE_TXT}".translate(change_tag)
            )
            file = await bot.download(file_info[0])
            bit_file = await conf.bitrix.upload_file(folder_id=task.bit_folder_id, file_name=file_info[1], file=file)
            bit_file_id = int(bit_file.get("ID"))

            comment_id = await conf.bitrix.add_file_comment(
                chat_id=task.bit_chat_id, files=[bit_file_id], message=text
            )

            if not comment_id:
                return False

            comment_in_db = await conf.bitrix_db.add_comment(
                task_id=task.id, user_id=user.id, bit_comment_id=comment_id,
                text=f"{file_info[3] or ''}\n{MyTaskANS.COMMENT_FILE_TXT}"
            )

            file_in_db = File(
                task_id=task.id,
                user_id=user.id,
                tg_file_id=file_info[0],
                bit_file_id=bit_file_id,
                name=file_info[1],
                description=text,
                type=file_info[2],
                comment_id=comment_in_db.id
            )
            await conf.bitrix_db.add_file(file_in_db)

        tg_ids = []
        task_users_name: dict = {"observers": []}
        for task_user in task.task_users:
            if task_user.user.tg_id:
                tg_ids.append(task_user.user.tg_id)

            if task_user.role == TaskRole.CREATOR:
                task_users_name["creator"] = task_user.user.full_name
            elif task_user.role == TaskRole.EXECUTOR:
                task_users_name["developer"] = task_user.user.full_name
            elif task_user.role == TaskRole.MANAGER:
                task_users_name["manager"] = task_user.user.full_name
            elif task_user.role == TaskRole.OBSERVER:
                task_users_name["observers"].append(task_user.user.full_name)

        observers = (
            MyTaskANS.OBSERVERS_JOIN.join(task_users_name["observers"])
            if task_users_name.get("observers")
            else DONT_CHOOSE_ANS
        )
        notify = TaskNFY.TASK.format(
            bit_id=task.bit_task_id,
            task_name=task.title.translate(change_tag),
            creator=task_users_name.get("creator"),
            developer=task_users_name.get("developer"),
            manager=task_users_name.get("manager"),
            observers=observers,
            group=task.group,
            region=task.region,
            stage=task.stage
        )
        notify += text if file_info else TaskNFY.ADD_COMMENT.format(
            author=user.full_name, text=text.translate(change_tag)
        )
        kb = comment_answer_ikb(
            task_db_id=task_db_id,
            language=translator.default_language,
            complete_bt=True if task.stage.stage_type == StageType.TESTING else False,
        )

        if not file_info:
            await conf.notify_manager.notify(msg=notify, tg_ids=tg_ids, kb=kb)

        else:
            file_info[3] = notify
            await send_file(file_info, bot, tg_ids, kb=kb)

        return True

    except Exception as e:
        await conf.logger.send_log(ERROR, "templates -> write_comment", e=e)
        return False


async def get_file_id(bot: Bot, chat_id: int | str, file: bytes, file_name: str, delete=True) -> str:
    """delete: if True, delete the file from chat"""
    file = BufferedInputFile(file=file, filename=file_name)
    message = await bot.send_document(chat_id=chat_id, document=file)
    file_id = message.document.file_id

    if delete:
        await bot.delete_message(chat_id=chat_id, message_id=message.message_id)

    return file_id


async def to_registration(tg_id: int | str, state: FSMContext) -> None:
    await state.set_state(Registration.language)
    await conf.bot.send_message(tg_id, START_MESSAGE, reply_markup=choose_language(back_bt=False))


async def to_create_task(message: Message, state: FSMContext, language: str) -> None:
    groups = await conf.bitrix_db.select_info(TaskGroup.title)
    await state.set_data({"groups": groups})
    await state.set_state(User.create_task_group)
    await message.answer(_("choose_group", language), reply_markup=build_rkb(groups, language))


async def to_create_task_executor(message: Message, state: FSMContext, language: str) -> None:
    data = await state.get_data()
    group_title = data.get("group")
    region_title = data.get("region")
    group: TaskGroup = await conf.bitrix_db.get_group_by_title(group_title)
    db_users = await conf.bitrix_db.get_users_by_region_and_group(group_title=group_title, region_title=region_title)
    if not group.assign_executor or not db_users:
        await state.set_state(User.create_task_title)
        await message.answer(_("task.title", language), reply_markup=back_and_cancel_rkb(language))
    else:
        users = []
        users_id_by_index = {}
        for index, user in enumerate(db_users, start=1):
            if user.bit_user_id:
                users.append(f"{index}. {user.full_name.strip()}")
                users_id_by_index[index] = user.id
        await state.update_data({"users": users, "users_id_by_index": users_id_by_index})
        await state.set_state(User.create_task_executor)
        await message.answer(_("task.choose_executor", language), reply_markup=build_rkb(users, language))


async def to_group_status(message: Message, state: FSMContext, language: str) -> None:
    groups = await conf.bitrix_db.select_info(TaskGroup.title)
    await state.set_data({"groups": groups})
    await state.set_state(User.group_status)
    await message.answer(_("choose_group", language), reply_markup=build_rkb(groups, language))


async def back_to_create_task_title(message: Message, state: FSMContext, language: str) -> None:
    data = await state.get_data()
    if data.get("group"):
        await state.set_state(User.create_task_title)
        await message.answer(_("task.title", language), reply_markup=back_and_cancel_rkb(language))

    else:
        await to_create_task(message, state, language)


async def back_to_create_task_description(message: Message, state: FSMContext, language: str) -> None:
    data = await state.get_data()
    if not data.get("group"):
        await to_create_task(message, state, language)

    elif not data.get("title"):
        await back_to_create_task_title(message, state, language)

    else:
        await state.update_data({"files": []})
        await state.set_state(User.create_task_description)
        await message.answer(_("task.description", language), reply_markup=back_and_cancel_rkb(language))


async def message_not_reg(message: Message, language: str, kb: ReplyKeyboardMarkup = None) -> None:
    await message.answer(_("choose", language), reply_markup=kb)


async def to_user_main_menu(message: Message, state: FSMContext, language: str, send_msg: str = None) -> None:
    await state.clear()
    await message.answer(send_msg if send_msg else _("menu", language), reply_markup=user_main_rkb(language))
    await state.set_state(User.main_menu)


def check_back_button(func):
    @wraps(func)
    async def wrapper(message: Message, state: FSMContext, language: str, access: str, *args, **kwargs):
        if message.text and (message.text in (_("b.back", language), _("b.cancel", language))):
            await state.clear()
            await to_user_main_menu(message, state, language)
            return

        else:
            await func(message, state, language, access, *args, **kwargs)
    return wrapper


def check_file(message: Message) -> list[str]:
    """
    :param message: Message instance from Aiogram
    :return: list [tg_file_id, tg_file_name, tg_file_type, caption: str | None]
    """
    if message.document:
        file_id = message.document.file_id
        file_unique_id = message.document.file_unique_id
        result = [file_id, f"{file_unique_id}_{message.document.file_name}", FileTypeConst.DOCUMENT]
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_unique_id = message.photo[-1].file_unique_id
        result = [file_id, f"photo_{file_unique_id}.jpg", FileTypeConst.PHOTO]
    elif message.video:
        file_id = message.video.file_id
        file_unique_id = message.video.file_unique_id
        result = [file_id, f"video_{file_unique_id}.mp4", FileTypeConst.VIDEO]
    elif message.video_note:
        file_id = message.video_note.file_id
        file_unique_id = message.video_note.file_unique_id
        result = [file_id, f"video_note{file_unique_id}.mp4", FileTypeConst.VIDEO_NOTE]
    elif message.voice:
        file_id = message.voice.file_id
        file_unique_id = message.voice.file_unique_id
        result = [file_id, f"voice_{file_unique_id}.mp3", FileTypeConst.VOICE]

    else:
        return []

    result.append(message.caption)
    return result


async def send_file(file_info: list[str], bot: Bot, targets: list[int | str], kb=None) -> None:
    """file_info: list [tg_file_id, tg_file_name, tg_file_type, caption: str | None]"""
    try:
        if file_info[2] == FileTypeConst.DOCUMENT:
            send_method = bot.send_document
        elif file_info[2] == FileTypeConst.PHOTO:
            send_method = bot.send_photo
        elif file_info[2] == FileTypeConst.VIDEO:
            send_method = bot.send_video
        elif file_info[2] == FileTypeConst.VIDEO_NOTE:
            send_method = bot.send_video_note
        elif file_info[2] == FileTypeConst.VOICE:
            send_method = bot.send_voice
        else:
            await conf.logger.send_log(ERROR, "templates -> send_file", msg="unknown file type")
            raise

        caption = file_info[3][0:1000] if file_info[3] else None
        if caption and len(caption) > 1000:
            caption += "...✍️"

        error_send_ids = []
        for target in set(targets):
            try:
                if file_info[2] == FileTypeConst.VIDEO_NOTE:
                    await send_method(target, file_info[0])

                else:
                    await send_method(target, file_info[0], caption=caption, reply_markup=kb)
            except Exception as _:  # noqa
                error_send_ids.append(target)

        if error_send_ids:
            await conf.logger.send_log(
                ERROR, "templates -> send_file", msg=f"can't send file for users: {error_send_ids}"
            )

    except Exception as e:
        await conf.logger.send_log(ERROR, "templates -> send_file", e=e)


def format_by_stage(tasks: dict[int, TaskInfo]) -> tuple[dict[str, dict[int, TaskInfo]], dict[str, int]]:
    tasks_by_stages: dict[str, dict[int, TaskInfo]] = {}
    stage_count: dict[str, int] = {}

    for task in tasks.values():
        if task.stage in stage_count:
            stage_count[task.stage] += 1
            task_stage_num = stage_count[task.stage]
        else:
            stage_count[task.stage] = 1
            task_stage_num = 1
            tasks_by_stages[task.stage] = {}

        tasks_by_stages[task.stage][task_stage_num] = task

    return tasks_by_stages, stage_count


async def can_crate(tg_id: int, group_name: str) -> int | bool:
    group = await conf.bitrix_db.get_task_group(title=group_name)
    if not group[0].max_active_tasks:
        return True

    user = await conf.bitrix_db.get_user(tg_id=tg_id)
    stages = await conf.bitrix_db.get_task_stage(group_id=group[0].id)
    tasks = await conf.bitrix_db.get_tasks_with([i.id for i in stages[:-1]], user_id=user[0].id, role=TaskRole.CREATOR)

    max_tasks = user[0].max_active_tasks or group[0].max_active_tasks
    if len(tasks) < max_tasks:
        return True

    else:
        return max_tasks


def can_delete(task: Task) -> bool:
    if task.stage and (task.stage.in_queue or task.test_date or task.closed_date):
        return False

    return True


async def get_regions_by_task_group(task_group_name: str) -> list[str]:
    group = await conf.bitrix_db.get_task_group(title=task_group_name)
    if not group:
        return []

    regions = await conf.bitrix_db.get_regions(group_id=group[0].id)
    return [region.name for region in regions]