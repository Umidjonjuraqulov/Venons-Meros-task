import asyncio
from typing import Sequence
from logging import ERROR

from aiogram import Bot
from aiogram.types import InputMediaDocument, BufferedInputFile

from src.db.models import Stage, Task

from src.i18n.i18n import translate as _


async def get_file_id(bot: Bot, chat_id: int | str, file: bytes, file_name: str, delete=True) -> str:
    """delete: if True, delete the file from chat"""
    file = BufferedInputFile(file=file, filename=file_name)
    message = await bot.send_document(chat_id=chat_id, document=file)
    file_id = message.document.file_id

    if delete:
        await bot.delete_message(chat_id=chat_id, message_id=message.message_id)

    return file_id


async def send_documents(documents_file_info: list, bot: Bot, targets: list[int | str], kb=None) -> None:
    """file_info: list [[tg_file_id, tg_file_id, tg_file_id...], caption: str | None]"""
    files = []
    for file_id in documents_file_info[0]:
        files.append(InputMediaDocument(media=file_id))

    for target in set(targets):
        if isinstance(documents_file_info[1], str):
            await bot.send_message(chat_id=target, text=documents_file_info[1][0:4000], reply_markup=kb)

        if len(files) > 10:
            media_groups = [files[i:i + 10] for i in range(0, len(files), 10)]
            for media_group in media_groups:
                await bot.send_media_group(chat_id=target, media=media_group)
        else:
            await bot.send_media_group(chat_id=target, media=files)


async def format_group_status(all_stages: Sequence[Stage], get_tasks_with, language: str) -> str:
    stages_info = ""
    max_in_group = all_stages[0].group.max_tasks
    free = max_in_group if max_in_group else 0

    queue_stages = {s.id for s in all_stages if s.in_queue} if free else set()

    for stage in all_stages:
        icon = "❇️"
        tasks_in_stage = await get_tasks_with(stage_ids=[stage.id])

        if stage.id in queue_stages:
            free -= len(tasks_in_stage) if all_stages[0].group.max_tasks else 0
            icon = "✴️"

        stages_info += f"{icon}{stage.title} <b>{len(tasks_in_stage)}</b>\n"

    return _("group_status", language).format(
        group=all_stages[0].group.title,
        stages_info=stages_info,
        free=free if max_in_group else "♾",
        max=max_in_group if max_in_group else "♾"
    )


async def mark_as_paid(
        ids: Sequence[int], conf, filed_code: str = None, interval: int = 2, paid: bool = True, db_id: bool = True
) -> set[int]:

    filed_code = conf.bit_custom_paid if filed_code is None else filed_code
    errored = set()
    for id_ in ids:
        try:
            task: Sequence[Task] = await conf.bitrix_db.get_task(
                id_=id_ if db_id else None, task_bit_id=None if db_id else id_
            )
            if not task:
                errored.add(id_)
                continue
            elif task[0].paid is paid:
                continue

            task_in_db = task[0]
            status = await conf.bitrix.update_task(
                task_in_db.bit_task_id, custom=[(filed_code, "True" if paid else "")]
            )
            if status:
                task_in_db.paid = paid
                await conf.bitrix_db.update_task(task_in_db)
            else:
                errored.add(task_in_db.id)

        except Exception as e:
            conf.logger.send_log(ERROR, "mark_as_paid", e, f"task_db_id: {id_}")

        finally:
            await asyncio.sleep(interval)

    if errored:
        conf.logger.send_log(ERROR, "mark_as_paid", msg=f"task_db_ids: {[id_ for id_ in errored]}")
    return errored
