from datetime import datetime, timedelta
from functools import wraps
from logging import ERROR

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, BufferedInputFile


from src.utils.utils import mark_as_paid
from src.classes.cls_const import AccessLevelConst
from src.bot.util.templates import to_user_main_menu, to_registration, check_file, send_file
from src.static.message_answers import TaskNFY

from src.configuration import conf

from src.i18n.i18n import translate as _

commands_router = Router(name='commands')


def check_admin_access(func):
    @wraps(func)
    async def wrapper(message: Message, state: FSMContext, access: str, language: str, *args, **kwargs):
        try:
            if access == AccessLevelConst.ADMIN:
                await func(message, state, access, language, *args, **kwargs)

            else:
                await message.answer(_("reg.blocked", language))

        except Exception as e:
            await message.answer(f"Ошибка проверки доступа: {e}")

    return wrapper


@commands_router.message(CommandStart())
async def start_command(message: Message, state: FSMContext, access: str, language: str) -> None:
    """Start command handler."""
    if access is None:
        await to_registration(message.from_user.id, state)
        return

    if access in (AccessLevelConst.USER, AccessLevelConst.ADMIN):
        await to_user_main_menu(message, state, language)

    elif access == AccessLevelConst.CHECKING:
        await message.answer(_("reg.checking", language))

    else:  # elif status == AccessLevelConst.BLOCKED:
        await message.answer(_("reg.blocked", language))


@commands_router.message(Command("language"))
async def change_language(message: Message, state: FSMContext) -> None:
    await to_registration(message.from_user.id, state)


@commands_router.message(Command("sync"))
@check_admin_access
async def sync_bitrix(message: Message, state: FSMContext, access: str, language: str) -> None:
    await message.answer(TaskNFY.BIT_START_SYNC)
    await conf.bit_sync.sync_all()
    await message.answer(TaskNFY.BIT_SYNC)


@commands_router.message(Command("mailing"))
@check_admin_access
async def mailing_command(message: Message, state: FSMContext, access: str, language: str) -> None:
    try:
        if message.reply_to_message:
            file = check_file(message.reply_to_message)
            users = await conf.bitrix_db.get_users(with_tg_id=True)
            targets = [
                i.tg_id for i in users if i.access_level not in (AccessLevelConst.BLOCKED, AccessLevelConst.CHECKING)
            ]

            if file:
                await message.answer("🚀 Отправка рассылки")
                await send_file(file_info=file, bot=conf.bot, targets=targets)
                await message.answer("✅ Отправка рассылки завершена!")

            elif message.reply_to_message.text:
                await message.answer("🚀 Отправка рассылки")
                await conf.notify_manager.notify(msg=message.reply_to_message.text, tg_ids=targets)
                await message.answer("✅ Отправка рассылки завершена!")

            elif message.reply_to_message.poll:
                await message.answer("🚀 Отправка рассылки")
                await conf.notify_manager.forward_msg(
                    message.chat.id, message.reply_to_message.message_id, targets, protect=True, copy=False
                )
                await message.answer("✅ Отправка рассылки завершена!")

            else:
                await message.answer("Можно отправить файлы(Документ/фото/видео) или сообщения")

        else:
            await message.answer("Прикрепите сообщение которое будет отправляться!\nНужно переслать с этой командой")

    except Exception as e:
        await conf.logger.send_log(ERROR, "mailing_command", e=e)
        await message.answer("Ошибка!")


@commands_router.message(Command("update_tasks"))
@check_admin_access
async def update_tasks(message: Message, state: FSMContext, access: str, language: str) -> None:
    try:
        await message.answer("Start sync tasks")
        all_tasks = await conf.bitrix_db.get_task()

        error_tasks = []
        for task in all_tasks:
            if task.bit_task_id:
                try:
                    await conf.bit_sync.on_task_update(task_bit_id=task.bit_task_id)
                except Exception as e:
                    error_tasks.append(f"{task.bit_task_id} - error: {e}")

            else:
                error_tasks.append(f"{task.id} not found bit_id")

        await message.answer(
            "Sync tasks end" + ("Error tasks:" + "\n".join(error_tasks) if error_tasks else "")
        )

    except Exception as e:
        await conf.logger.send_log(ERROR, "update_tasks command", e=e)
        await message.answer("Ошибка!")


@commands_router.message(Command("get_stat"))
@check_admin_access
async def update_tasks(message: Message, state: FSMContext, access: str, language: str) -> None:
    try:
        await conf.task_export.send_stat(message.from_user.id, conf.bot)

    except Exception as e:
        await conf.logger.send_log(ERROR, "update_tasks command", e=e)
        await message.answer("Ошибка!")


@commands_router.message(Command("send_stat"))
@check_admin_access
async def update_tasks(message: Message, state: FSMContext, access: str, language: str) -> None:
    try:
        await conf.task_export.send_stat(conf.notify_chat_id, conf.bot)

    except Exception as e:
        await conf.logger.send_log(ERROR, "update_tasks command", e=e)
        await message.answer("Ошибка!")


@commands_router.message(Command("all_creators_stat"))
@check_admin_access
async def update_tasks(message: Message, state: FSMContext, access: str, language: str) -> None:
    try:
        now = datetime.now()
        start = now - timedelta(days=30)
        groups = await conf.bitrix_db.get_task_group()
        for group in groups:
            msg = f"Созданные <b>{group.title}</b> задачи по исполнителям"
            stat = await conf.task_export.get_creator_stat(start, now, group.id)
            if not stat:
                continue
            for s in stat:
                msg += f"\n{s[0]} - {s[1]}"

            await message.answer(msg)

    except Exception as e:
        await conf.logger.send_log(ERROR, "update_tasks command", e=e)
        await message.answer("Ошибка!")


@commands_router.message(Command("paid"))
@check_admin_access
async def paid(message: Message, state: FSMContext, access: str, language: str) -> None:
    try:
        not_valid = []
        info = message.text.split()
        if (len(info) < 3) or (info[1] not in ("true", "false")):
            await message.answer("/paid [mode: true/false] [bit_ids, ...]")
            return

        mode = True if info[1] == "true" else False
        ids = []
        for t_id in info[2:]:
            if t_id.isdigit():
                ids.append(int(t_id))
            else:
                not_valid.append(t_id)

        await message.answer("💰В процессе...")
        errors = await mark_as_paid(ids, conf, paid=mode, db_id=False)
        not_valid += [str(i) for i in errors]
        if not_valid:
            await message.answer(f"💰Не получилось обновить статус: \n{' '.join(not_valid)}")

    except Exception as e:
        await conf.logger.send_log(ERROR, "paid command", e=e)
        await message.answer("Ошибка!")


@commands_router.message(Command("task_stage"))
@check_admin_access
async def task_stage(message: Message, state: FSMContext, access: str, language: str) -> None:
    try:
        info = message.text.split()
        if len(info) < 3:
            await message.answer("/task_stage [all|queue] [group_name] [days after close]")
            return

        if info[-1].isdigit():
            title = " ".join(info[2:-1])
            closed_days = int(info[-1])
        else:
            title = " ".join(info[2:])
            closed_days = 0

        select_type = info[1]
        group = await conf.bitrix_db.get_task_group(title=title)

        if group:
            await message.answer("⌛️В процессе...")
            file = await conf.task_export.get_task_stage_time(
                conf.bitrix, group[0].id, closed_days=closed_days, queue=True if select_type == "queue" else False
            )
            if file:
                await message.answer_document(BufferedInputFile(file.read(), f"tasks.xlsx"))

            else:
                await message.answer("😓 Нет задач в очереди")

        else:
            await message.answer(f"🧐 Подразделение `{title}` не найдено!")

    except Exception as e:
        await conf.logger.send_log(ERROR, "task_stage", e=e)
        await message.answer("Ошибка!")
