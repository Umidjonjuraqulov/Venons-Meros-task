from datetime import datetime

from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram import Router, Bot

from src.bitrix.sync.status_checks import StatusCheck
from src.bitrix.sync.utils import format_stage_changing
from src.bot.structures.keyboards import back_rkb, task_info_rkb, RegCallback, CompleteTaskCallback, comment_answer_ikb
from src.bot.routers.commands import start_command
from src.bot.util.templates import can_delete
from src.bot.structures.fsm import User

from src.classes.data_classes import TaskInfo
from src.db.models import User as UserModel
from src.configuration import conf

from src.classes.cls_const import AccessLevelConst
from src.static.message_answers import MyTaskANS, DONT_CHOOSE_ANS, change_tag

from src.i18n.i18n import translate as _

other_routers = Router(name="other_routers")


@other_routers.message()
async def empty_fsm(message: Message, state: FSMContext, access: str, language: str) -> None:
    await start_command(message, state, access, language)


@other_routers.callback_query(RegCallback.filter())
async def new_user_callback(callback: CallbackQuery, bot: Bot, access: str, language: str) -> None:
    if access == AccessLevelConst.ADMIN:
        data = RegCallback.unpack(callback.data)

        if data.status in AccessLevelConst.ALL:
            user = await conf.bitrix_db.update_user(update_to=UserModel(access_level=data.status), tg_id=int(data.user_id))
            conf.user_manager.update_user(tg_id=int(data.user_id), access_level=data.status)

            if data.status in (AccessLevelConst.USER, AccessLevelConst.ADMIN):
                msg = _("reg.success", user.language)
            else:
                msg = _("reg.failed", user.language)

            await bot.send_message(data.user_id, msg)
            await callback.message.edit_reply_markup(reply_markup=None)

        else:
            await callback.answer("Error: data[0] not in AccessLevelConst.ALL")

    else:
        await callback.answer(_("reg.not_accept_users", language))


@other_routers.callback_query(CompleteTaskCallback.filter())
async def complete_task_callback(callback: CallbackQuery, bot: Bot, language: str) -> None:
    try:
        user = await conf.bitrix_db.get_user(tg_id=callback.from_user.id)
        if not user[0].role_id:
            await bot.send_message(callback.from_user.id, MyTaskANS.ROLE_NONE)
            return

        data = CompleteTaskCallback.unpack(callback.data)
        task = await conf.bitrix_db.get_task(id_=data.task_id)
        task = task[0]
        stages = await conf.bitrix_db.get_task_stage(group_id=task.group_id)
        roles = conf.bitrix_db.sort_task_roles(task.task_users)

        if task.stage_id == stages[-1].id:
            await callback.answer(MyTaskANS.TASK_CLOSED)
            await callback.message.edit_reply_markup(reply_markup=comment_answer_ikb(task.id, language))
            return

        checker = StatusCheck(
            conf.bitrix_db, task, user[0], roles, stages, stages[-1], conf.bitrix.conf.data.current_id
        )
        check_msg = await checker.check()

        if check_msg:
            await bot.send_message(callback.from_user.id, check_msg)
            await callback.answer()

        else:
            task.closed_date = datetime.now()
            task.stage_id = stages[-1].id

            editor = MyTaskANS.EDITOR_STAGE.format(user=user[0].full_name)
            stage_msg = format_stage_changing(stages, task.stage_id, stages[-1].id)

            await conf.bitrix_db.update_task(task=task)
            await conf.bitrix.update_task(task_id=task.bit_task_id, bit_stage_id=stages[-1].bit_stage_id)

            await callback.message.edit_reply_markup(reply_markup=comment_answer_ikb(task.id, language))
            await conf.bit_sync.notify_task_users(editor + stage_msg, task, roles=roles)

    except Exception as e:
        print(e)


@other_routers.callback_query()
async def confirm(callback: CallbackQuery, state: FSMContext, bot: Bot, language: str) -> None:
    info = callback.data.split("|")

    if info[0] == "answer_comment":
        await answer_comment(callback, state, bot, language)

    elif info[0] == "open_task":
        await open_task(callback, state, bot, language)


async def format_task_info(task_db_id: int) -> dict:
    task_in_db = await conf.bitrix_db.get_task(id_=task_db_id)
    task_in_db = task_in_db[0]

    task_users = await conf.bitrix_db.get_task_user(task_id=task_db_id)
    task_users_role = conf.bitrix_db.sort_task_roles(task_users=task_users)

    developer_name = task_users_role.executor.user.full_name if task_users_role.executor else DONT_CHOOSE_ANS
    creator_name = task_users_role.creator.user.full_name if task_users_role.creator else DONT_CHOOSE_ANS
    manager_name = task_users_role.manager.user.full_name if task_users_role.manager else DONT_CHOOSE_ANS
    observers = [user.user.full_name for user in task_users_role.observers]

    task = TaskInfo(
        db_id=task_in_db.id,
        bit_id=task_in_db.bit_task_id,
        title=task_in_db.title,
        description=task_in_db.description,
        group=task_in_db.group.title,
        region=task_in_db.region.name if task_in_db.region else DONT_CHOOSE_ANS,
        stage=task_in_db.stage.title if task_in_db.stage else "None",
        create_date=task_in_db.created_date,
        deadline=task_in_db.deadline,
        closed_date=task_in_db.closed_date,
        creator=creator_name,
        developer=developer_name,
        manager=manager_name,
        observers=observers,
        can_delete=can_delete(task_in_db)
    )
    msg = MyTaskANS.TASK_INFO.format(
        bit_id=task.bit_id,
        task_name=task.title.translate(change_tag), description=task.description[0:2048].translate(change_tag),
        creator=task.creator, developer=task.developer, manager=task.manager,
        observers=MyTaskANS.OBSERVERS_JOIN.join(task.observers or []),
        group=task.group, region=task.region, stage=task.stage
    )

    return {"selected_task": task, "task_message": msg}


async def answer_comment(callback: CallbackQuery, state: FSMContext, bot: Bot, language: str) -> None:
    try:
        task_db_id = int(callback.data.split("|")[1])
        data = await format_task_info(task_db_id)

        await callback.message.edit_reply_markup(reply_markup=None)
        await state.set_data(data)
        await state.set_state(User.my_task_write_comment)
        await bot.send_message(callback.from_user.id, MyTaskANS.WRITE_COMMENT, reply_markup=back_rkb(language))

    except Exception as e:
        print(e)


async def open_task(callback: CallbackQuery, state: FSMContext, bot: Bot, language: str) -> None:
    try:
        task_db_id = int(callback.data.split("|")[1])
        data = await format_task_info(task_db_id)
        task_info: TaskInfo = data["selected_task"]

        await callback.message.edit_reply_markup(reply_markup=None)
        await state.set_data(data)
        await state.set_state(User.my_task_info)
        await bot.send_message(
            callback.from_user.id, data["task_message"],
            reply_markup=task_info_rkb(language, can_delete=task_info.can_delete)
        )

    except Exception as e:
        print(e)
