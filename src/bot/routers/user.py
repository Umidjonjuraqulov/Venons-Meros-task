from aiogram import Router, Bot  # noqa
from aiogram.types import Message  # noqa
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext  # noqa

from src.bot.structures.fsm import User  # noqa
from src.bot.util.templates import *
from src.bot.structures.keyboards import *

from src.static.message_answers import *
from src.classes.data_classes import TaskInfo
from src.utils.utils import format_group_status  # noqa
from src.bitrix.sync.status_checks import StatusCheck
from src.bitrix.sync.utils import format_stage_changing
from src.classes.cls_const import TaskRole, StageType, AccessLevelConst as Al

from src.configuration import conf

from src.i18n.i18n import translate as _


class UserFilter(Filter):
    async def __call__(self, message: Message, access: str):
        return access in (Al.ADMIN, Al.USER)


user_router = Router(name="user")
user_router.message.filter(UserFilter())

# tasks view size in one page
tasks_lines = 10


@user_router.message(User.main_menu)
async def user_main_menu(message: Message, state: FSMContext, language: str):
    if message.text == _("b.create_task", language):
        await to_create_task(message, state, language)

    elif message.text in (_("b.my_tasks", language), _("b.observed_tasks", language)):
        tasks: list[TaskInfo] = await get_tasks_list(
            message.from_user.id,
            [TaskRole.CREATOR, TaskRole.EXECUTOR, TaskRole.CO_EXECUTOR] if message.text == _("b.my_tasks", language)
            else [TaskRole.OBSERVER, TaskRole.MANAGER]
        )
        if not tasks:
            await message.answer(MyTaskANS.NOT_TASK)
            return

        tasks_dict: dict[int, TaskInfo] = {}
        closed_tasks: dict[int, TaskInfo] = {}
        for t in tasks:
            if t.closed_date:
                closed_tasks[len(closed_tasks)+1] = t
            else:
                tasks_dict[len(tasks_dict)+1] = t

        tasks_size = len(tasks_dict)
        closed_size = len(closed_tasks)
        view_closed = False if tasks_dict else True

        if tasks_size:
            kb = build_tasks_rkb(
                1, tasks_lines, tasks_size, language, by_stage=True, c_bt=True if closed_size else False
            )
        else:
            kb = build_tasks_rkb(1, tasks_lines, closed_size, language)

        await state.set_data(
            {
                "page": 1,
                "view_mode": "active" if tasks_dict else "close",  # active | close | stage_title
                "tasks": tasks_dict,
                "tasks_page_size": (tasks_size // tasks_lines) + (1 if tasks_size % tasks_lines > 0 else 0),
                "closed_tasks": closed_tasks,
                "closed_page_size": (closed_size // tasks_lines) + (1 if closed_size % tasks_lines > 0 else 0)
            }
        )
        await state.set_state(User.my_tasks)
        await message.answer(MyTaskANS.GET_TASKS.format(
            task_list=format_task_list(closed_tasks if view_closed else tasks_dict, 1, lines=tasks_lines)),
            reply_markup=kb
        )

    elif message.text == _("b.group_status", language):
        await to_group_status(message, state, language)

    elif message.text == _("b.write_review", language):
        await message.answer(ReviewANS.TEXT, reply_markup=back_rkb(language))
        await state.set_state(User.write_review)

    else:
        await message_not_reg(message, language, kb=user_main_rkb(language))


@user_router.message(User.create_task_group)
@check_back_button
async def user_create_task_group(message: Message, state: FSMContext, language: str, access: str):
    data = await state.get_data()
    if message.text in data["groups"]:
        can_crate_status = await can_crate(message.from_user.id, message.text)
        if can_crate_status is True:
            await state.set_data({"group": message.text})
            # filter regions by task group name
            regions = await get_regions_by_task_group(message.text)
            if not regions:
                await state.set_state(User.create_task_title)
                await state.update_data({"region": None})
                await message.answer(_("task.title", language), reply_markup=back_and_cancel_rkb(language))
            else:
                await state.set_state(User.create_task_region)
                await state.update_data({"regions": regions})
                await message.answer(
                    _("choose_region", language),
                    reply_markup=build_rkb(regions, language, back=True)
                )

        else:
            await message.answer(_("max_active_tasks", language).format(group=message.text, num=can_crate_status))
    else:
        await message.answer(_("choose_group", language))


@user_router.message(User.create_task_region)
async def user_create_task_region(message: Message, state: FSMContext, language: str):
    if message.text == _("b.back", language):
        await to_user_main_menu(message, state, language)
    data = await state.get_data()
    if message.text in data["regions"]:
        await state.set_state(User.create_task_title)
        await state.update_data({"region": message.text})
        await message.answer(_("task.title", language), reply_markup=back_and_cancel_rkb(language))
    else:
        await message.answer(_("choose_region", language))


@user_router.message(User.create_task_title)
async def user_create_task_title(message: Message, state: FSMContext, language: str):
    if message.text == _("b.back", language):
        await to_create_task(message, state, language)

    elif message.text == _("b.cancel", language):
        await to_user_main_menu(message, state, language)

    elif message.text and len(message.text) <= 128:
        await state.set_state(User.create_task_description)
        await state.update_data({"title": message.text})
        await message.answer(_("task.description", language))

    else:
        await message.answer(_("task.title_not", language))


@user_router.message(User.create_task_description)
async def user_create_task_description(message: Message, state: FSMContext, language: str):
    if message.text == _("b.back", language):
        await back_to_create_task_title(message, state, language)

    elif message.text == _("b.cancel", language):
        await to_user_main_menu(message, state, language)

    elif message.text:
        await state.set_state(User.create_task_files)
        await state.update_data({"description": message.text})
        await message.answer(_("task.file", language))

    else:
        await message.answer(_("task.description", language)+"!")


@user_router.message(User.create_task_files)
async def user_create_task_file(message: Message, state: FSMContext, bot: Bot, language: str):
    data = await state.get_data()

    if message.text == _("b.back", language):
        await back_to_create_task_description(message, state, language)

    elif message.text == _("b.cancel", language):
        await to_user_main_menu(message, state, language)

    elif message.text and message.text == _("b.confirm", language) and data.get("files"):
        await to_user_main_menu(message, state, language, send_msg=_("task.upload", language))
        status = await create_task(
            bot=bot,
            title=data["title"],
            description=data["description"],
            files=data["files"],
            group=data["group"],
            region=data["region"],
            user_tg_id=message.from_user.id
        )
        if status:
            await message.answer(_("task.done", language))
        else:
            await message.answer(_("task.err", language))

    else:
        file_info = check_file(message)
        if file_info:
            if data.get("files"):
                data["files"].append(file_info)
            else:
                data["files"] = [file_info]

            await state.set_data(data)
            await message.answer(_("task.file_get", language), reply_markup=back_and_confirm_rkb(language))

        else:
            await message.answer(_("task.file", language)+"!")


@user_router.message(User.my_tasks)
async def user_my_tasks(message: Message, state: FSMContext, language: str):
    data = await state.get_data()
    page = data["page"]
    if data["view_mode"] == "active":
        page_size = data["tasks_page_size"]
        tasks: dict[int, TaskInfo] = data["tasks"]
    elif data["view_mode"] == "close":
        page_size = data["closed_page_size"]
        tasks: dict[int, TaskInfo] = data["closed_tasks"]
    else:
        if data.get("tasks_by_stages") and data["view_mode"] in data["tasks_by_stages"]:
            page_size = data["stage_count"][data["view_mode"]]
            tasks: dict[int, TaskInfo] = data["tasks_by_stages"][data["view_mode"]]
        else:
            await to_user_main_menu(message, state, language)
            return

    if message.text == _("b.back", language):
        if data["view_mode"] in ("active", "close"):
            await to_user_main_menu(message, state, language)
        else:
            msg = ""
            for stage_title, count in data["stage_count"].items():
                msg += f"{stage_title} {count}\n"

            kb = build_rkb(list(data["stage_count"].keys()), language, back=True)
            await message.answer(msg, reply_markup=kb)
            await state.update_data({"view_mode": "active"})
        return

    elif message.text == _("b.next", language):
        page += 1
        if page <= page_size:
            await state.update_data({"page": page})
            await message.answer(MyTaskANS.GET_TASKS.format(
                task_list=format_task_list(tasks, page, lines=tasks_lines)),
                reply_markup=build_tasks_rkb(page, tasks_lines, len(tasks), language)
            )
        else:
            await message.answer(MyTaskANS.NEXT_ERR)  # In normal cases the user cannot receive this message

    elif message.text == _("b.previous", language):
        if page > 1:
            page -= 1
            await state.update_data({"page": page})
            await message.answer(MyTaskANS.GET_TASKS.format(
                task_list=format_task_list(tasks, page, lines=tasks_lines)),
                reply_markup=build_tasks_rkb(page, tasks_lines, len(tasks), language)
            )
        else:
            await message.answer(MyTaskANS.PREVIOUS_ERR)  # In normal cases the user cannot receive this message

    elif message.text == _("b.closed", language):
        if data.get("closed_tasks"):
            await state.update_data({"page": 1, "view_mode": "close"})
            await message.answer(MyTaskANS.GET_TASKS.format(
                task_list=format_task_list(data["closed_tasks"], 1, lines=tasks_lines)),
                reply_markup=build_tasks_rkb(1, tasks_lines, len(data["closed_tasks"]), language)
            )
        else:
            await message.answer(MyTaskANS.CLOSED_ERR)  # In normal cases the user cannot receive this message

    elif message.text == _("b.by_stage", language):
        tasks_by_stages, stage_count = format_by_stage(tasks)
        await state.update_data({"tasks_by_stages": tasks_by_stages, "stage_count": stage_count})

        msg = ""
        for stage_title, count in stage_count.items():
            msg += f"{stage_title} {count}\n"

        kb = build_rkb(list(stage_count.keys()), language, back=True)
        await message.answer(msg, reply_markup=kb)

    elif message.text and message.text.isdigit():
        if int(message.text) in tasks:
            task_info: TaskInfo = tasks[int(message.text)]
            msg = MyTaskANS.TASK_INFO.format(
                bit_id=task_info.bit_id, task_name=task_info.title.translate(change_tag),
                description=task_info.description[0:2048].translate(change_tag),
                creator=task_info.creator, developer=task_info.developer, manager=task_info.manager,
                observers=MyTaskANS.OBSERVERS_JOIN.join(task_info.observers or []),
                group=task_info.group, region=task_info.region, stage=task_info.stage
            )

            await message.answer(
                msg,
                reply_markup=task_info_rkb(language, can_delete=task_info.can_delete)
            )
            await state.set_state(User.my_task_info)
            await state.update_data({"selected_task": tasks[int(message.text)], "task_message": msg})
        else:
            await message.answer(MyTaskANS.CHOOSE_ERR)

    elif data.get("stage_count") and message.text in data["stage_count"]:
        await state.update_data({"view_mode": message.text})
        kb = build_tasks_rkb(1, tasks_lines, data["stage_count"][message.text], language)
        await message.answer(MyTaskANS.GET_TASKS.format(
            task_list=format_task_list(data["tasks_by_stages"][message.text], 1, lines=tasks_lines)),
            reply_markup=kb
        )

    else:
        await message.answer(MyTaskANS.CHOOSE)


@user_router.message(User.my_task_info)
@check_back_button
async def user_my_task_info(message: Message, state: FSMContext, language: str, access: str):
    data = await state.get_data()
    task_info: TaskInfo = data["selected_task"]

    if message.text == _("b.get_files", language):
        files = await get_task_files(task_info.db_id)
        if not files:
            await message.answer(MyTaskANS.FILES_NONE)
            return

        for file in files:
            await send_file(file_info=file, bot=conf.bot, targets=[message.from_user.id])

    elif message.text == _("b.comments", language):
        await state.set_state(User.my_task_write_comment)
        comments = await get_tasks_comments(task_db_id=task_info.db_id)
        if comments:
            msg = format_task_comments(task_info=task_info, comments=comments)
        else:
            msg = MyTaskANS.COMMENTS_NONE

        await message.answer(msg)
        await message.answer(MyTaskANS.WRITE_COMMENT, reply_markup=back_rkb(language))

    elif message.text == _("b.change_stage", language):
        user = await conf.bitrix_db.get_user(tg_id=message.from_user.id)
        if not user[0].role_id:
            await message.answer(MyTaskANS.ROLE_NONE)
            return

        data = await state.get_data()
        task = await conf.bitrix_db.get_task(id_=data["selected_task"].db_id)
        all_stages = {s.id: s for s in await conf.bitrix_db.get_task_stage(group_id=task[0].group_id)}

        change_to = []
        can_extract = False
        main_role = await conf.bitrix_db.get_role(id_=user[0].role_id)
        admin = main_role.access_all_stage

        # get additional
        add_roles = await conf.bitrix_db.get_additional_roles(user[0].id)
        role_accesses = main_role.access

        for user_role in add_roles:
            role = await conf.bitrix_db.get_role(id_=user_role.role_id)
            if role.access_all_stage:
                admin = True
                break
            role_accesses += role.access

        if admin:
            can_extract = True
            change_to = [s.title for k, s in all_stages.items() if k != task[0].stage_id]

        else:
            for role_access in role_accesses:
                if role_access.stage_id not in all_stages:
                    continue

                st = all_stages[role_access.stage_id].title
                if role_access.stage_id == task[0].stage_id:
                    if role_access.extract is True:
                        can_extract = True

                elif (st not in change_to) and (role_access.stage_id in all_stages) and (role_access.insert is True):
                    change_to.append(st)

        if can_extract:
            await message.answer(MyTaskANS.CHANGE_STAGE, reply_markup=build_rkb(change_to, language))
            await state.set_state(User.change_stage)
        else:
            await message.answer(MyTaskANS.CHANGE_STAGE_NONE)

    elif message.text == _("b.delete_task", language) and task_info.can_delete:
        await message.answer(MyTaskANS.DELETE_CONFIRM, reply_markup=delete_config_rkb(language))
        await state.set_state(User.delete_task)

    else:
        await message_not_reg(
            message,
            language,
            task_info_rkb(language, can_delete=task_info.can_delete)
        )


@user_router.message(User.my_task_write_comment)
async def user_my_task_write_comment(message: Message, state: FSMContext, bot: Bot, language: str):
    data = await state.get_data()
    task_info: TaskInfo = data["selected_task"]
    if message.text == _("b.back", language):
        await message.answer(
            data.get("task_message"),
            reply_markup=task_info_rkb(language, can_delete=task_info.can_delete)
        )
        await state.set_state(User.my_task_info)

    else:
        if message.text:
            text = message.text
            file_info = None

        else:
            file_info = check_file(message)
            if not file_info:
                await message.answer(MyTaskANS.WRITE_COMMENT + "!")
                return

            text = file_info[3]

        await to_user_main_menu(message, state, language, send_msg=_("task.upload", language))

        status = await write_comment(
            task_db_id=task_info.db_id,
            user_tg_id=message.from_user.id,
            text=text,
            file_info=file_info,
            bot=bot
        )

        if status is True:
            await message.answer(MyTaskANS.WRITE_COMMENT_DONE)
        elif status == "exist":
            await message.answer(MyTaskANS.WRITE_COMMENT_FILE_EXIST)
        else:
            await message.answer(MyTaskANS.WRITE_COMMENT_ERR)


@user_router.message(User.group_status)
@check_back_button
async def user_group_status(message: Message, state: FSMContext, language: str, access: str):
    data = await state.get_data()
    if message.text in data["groups"]:
        group = await conf.bitrix_db.get_task_group(title=message.text)
        stages = await conf.bitrix_db.get_task_stage(group_id=group[0].id)

        msg = await format_group_status(stages[:-1], conf.bitrix_db.get_tasks_with, language)
        await message.answer(msg)

    else:
        await message.answer(_("choose_group", language))


@user_router.message(User.change_stage)
async def user_my_task_change_stage(message: Message, state: FSMContext, language: str):
    data = await state.get_data()
    task_info: TaskInfo = data["selected_task"]

    if message.text == _("b.back", language):
        await message.answer(
            data.get("task_message"),
            reply_markup=task_info_rkb(language, can_delete=task_info.can_delete)
        )
        await state.set_state(User.my_task_info)

    else:
        task = await conf.bitrix_db.get_task(id_=task_info.db_id)
        task = task[0]
        user = await conf.bitrix_db.get_user(tg_id=message.from_user.id)
        roles = conf.bitrix_db.sort_task_roles(task.task_users)
        stages = await conf.bitrix_db.get_task_stage(group_id=task.group_id)
        to_stage = [i for i in stages if i.title == message.text]

        if to_stage:
            to_stage = to_stage[0]
            checker = StatusCheck(
                conf.bitrix_db, task, user[0], roles, stages, to_stage, conf.bitrix.conf.data.current_id
            )
            check_msg = await checker.check()

            if check_msg:
                await message.answer(check_msg)

            else:
                editor = MyTaskANS.EDITOR_STAGE.format(user=user[0].full_name)
                stage_msg = format_stage_changing(stages, task.stage_id, to_stage.id)
                kb = None
                if to_stage.stage_type == StageType.TESTING:
                    kb = test_answer_ikb(task.id, language)
                    task.test_date = datetime.now()
                    if task.group.ban_hours:
                        stage_msg += "\n" + TaskNFY.TEST_WARNING.format(time=task.group.ban_hours)

                await conf.bit_sync.notify_task_users(editor + stage_msg, task, roles=roles, kb=kb)
                await to_user_main_menu(message, state, language)

                task_exit_queue = task.stage.in_queue and not to_stage.in_queue
                task.stage_id = to_stage.id

                if stages[-1].id == to_stage.id:
                    task.closed_date = datetime.now()

                if to_stage.stage_type == StageType.FIFO:
                    task_fifo = await conf.bit_sync.db.get_fifo_queue(group_id=task.group.id)
                    if not task_fifo:
                        stages_in_queue = [s.id for s in stages if s.in_queue]
                        number_of_tasks = await conf.bitrix_db.get_stage_task_counts(stage_ids=stages_in_queue)

                    else:
                        number_of_tasks = 0
                        task_fifo = [task]

                    if not task_fifo and (number_of_tasks < task.group.max_tasks):

                        next_stage = None

                        for st in stages:
                            if to_stage.sort < st.sort:
                                next_stage = st
                                break

                        if next_stage:
                            task.stage_id = next_stage.id
                            to_stage = next_stage

                await conf.bitrix_db.update_task(task=task)
                await conf.bitrix.update_task(task_id=task.bit_task_id, bit_stage_id=to_stage.bit_stage_id)

                if task_exit_queue and task.group.fifo_queue:
                    task_fifo = await conf.bitrix_db.get_fifo_queue()
                    if task_fifo:
                        task_fifo = task_fifo[0]
                        next_stage = None

                        for st in stages:
                            if task_fifo.stage.sort < st.sort:
                                next_stage = st
                                break

                        if next_stage:
                            task_fifo.stage_id = next_stage.id
                            await conf.bitrix_db.update_task(task_fifo)
                            await conf.bitrix.update_task(task_fifo.bit_task_id, bit_stage_id=next_stage.bit_stage_id)

                            msg = TaskNFY.PASSED_QUEUE.format(bit_id=task_fifo.bit_task_id, task_name=task_fifo.title)
                            await conf.bit_sync.notify_task_users(msg, task_fifo, title=False)

                            if task.group.notify:
                                file = await conf.task_export.queue_png("", "", task.group.id)
                                if file:
                                    users_notify = []
                                    for r in await conf.bitrix_db.get_roles(notify_queue=True, join_users=True):
                                        users_notify += r.users

                                    await conf.notify_manager.send_photo(
                                        file, "", tg_ids={m.tg_id for m in users_notify if m.tg_id}
                                    )
        else:
            await message.answer(MyTaskANS.STAGE_NONE)


@user_router.message(User.delete_task)
async def user_write_review_confirm(message: Message, state: FSMContext, language: str):
    data = await state.get_data()
    task_info: TaskInfo = data["selected_task"]

    if message.text == _("b.back", language):
        await message.answer(
            data.get("task_message"),
            reply_markup=task_info_rkb(language, can_delete=task_info.can_delete)
        )
        await state.set_state(User.my_task_info)

    elif message.text == _("b.delete_confirm", language) and task_info.can_delete:
        try:
            user = await conf.bitrix_db.get_user(tg_id=message.from_user.id)
            task_in_db = await conf.bitrix_db.get_task(id_=task_info.db_id)

            await conf.bit_sync.notify_task_users(
                MyTaskANS.TASK_DELETED_INFO.format(user=user[0].full_name), task_in_db[0]
            )
            await conf.bitrix.delete_task(task_info.bit_id)
            await conf.bitrix_db.delete_info(selected_model=Task, id_=task_info.db_id)

        except Exception as e:
            await message.answer(MyTaskANS.DELETE_ERROR)
            print(e)

        finally:
            await to_user_main_menu(message, state, language)

    else:
        await message_not_reg(message, language, delete_config_rkb(language))


@user_router.message(User.write_review)
@check_back_button
async def user_write_review_confirm(message: Message, state: FSMContext, language: str, access: str):
    if message.text:
        user = await conf.bitrix_db.get_user(tg_id=message.from_user.id)
        msg = ReviewANS.REVIEW_FORMAT.format(user=user[0].full_name, text=message.text.translate(change_tag))
        await conf.bot.send_message(chat_id=conf.review_chat_id, text=msg)

        await message.answer(ReviewANS.SEND)
        await to_user_main_menu(message, state, language)

    elif message.text == _("b.cancel", language):
        await to_user_main_menu(message, state, language)

    else:
        await message.answer(ReviewANS.ONLY_TEXT)
