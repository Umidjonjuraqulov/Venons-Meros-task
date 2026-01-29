from logging import ERROR

from asyncio import sleep
from random import uniform
from fastapi import Request, APIRouter

from aiogram.types import Update

from src.db.models import Task

from src.configuration import conf
from .task_report_api import fastapi_router as task_report_router


fastapi_router = APIRouter()

# include sub-routers so their endpoints appear in the app's OpenAPI schema
fastapi_router.include_router(task_report_router)

in_checking: dict[str, list] = {"ONTASKUPDATE": [], "ONTASKDELE": [], "ONTASKCOMMENTADD": []}


@fastapi_router.post("/bitrix")
async def root_post(request: Request):
    try:
        form_data = await request.form()
        data_dict = {key: value for key, value in form_data.items()}

    except Exception as e:
        return {"error": str(e)}

    try:
        if data_dict.get("auth[application_token]") == conf.bit_hook_token:
            match data_dict.get("event"):
                # Bitrix sometimes sends two hooks to the same event (namely when manually dragging a task in Kanban)
                case "ONTASKUPDATE":
                    task_bit_id = int(data_dict.get("data[FIELDS_BEFORE][ID]", 0))
                    if not task_bit_id:
                        return

                    # if now checking, sleep
                    if task_bit_id in in_checking["ONTASKUPDATE"]:
                        in_checking["ONTASKUPDATE"].append(task_bit_id)
                        await sleep(uniform(4.0, 6.0))

                        # if many handlers > 1 skip
                        if in_checking["ONTASKUPDATE"].count(task_bit_id) > 1:
                            in_checking["ONTASKUPDATE"].remove(task_bit_id)

                        else:
                            await conf.bit_sync.on_task_update(task_bit_id=task_bit_id)
                            in_checking["ONTASKUPDATE"].remove(task_bit_id)

                    else:
                        in_checking["ONTASKUPDATE"].append(task_bit_id)
                        await conf.bit_sync.on_task_update(task_bit_id=task_bit_id)
                        in_checking["ONTASKUPDATE"].remove(task_bit_id)

                case "ONTASKADD":
                    task_bit_id = int(data_dict.get("data[FIELDS_AFTER][ID]", 0))

                    if task_bit_id and (not (task_bit_id in in_checking["ONTASKUPDATE"])):
                        await conf.bit_sync.on_task_add(task_bit_id=task_bit_id)

                case "ONTASKDELETE":
                    await sleep(1)  # when task deleted from bot
                    task_bit_id = int(data_dict.get("data[FIELDS_BEFORE][ID]", 0))
                    if not task_bit_id:
                        return

                    task_in_db = await conf.bitrix_db.get_task(task_bit_id=task_bit_id)
                    if task_in_db:
                        await conf.bitrix_db.delete_info(selected_model=Task, id_=task_in_db[0].id)

                case "ONTASKCOMMENTADD":
                    await conf.bit_sync.on_task_comment_add(
                        task_bit_id=int(data_dict.get("data[FIELDS_AFTER][TASK_ID]")),
                        message_bit_id=int(data_dict.get("data[FIELDS_AFTER][MESSAGE_ID]"))
                    )

        return {"stage": "success"}

    except Exception as e:
        await conf.logger.send_log(
            ERROR,
            "@fastapi_router.post(\"/bitrix\")",
            msg=f"{data_dict=}",
            e=e
        )
        return {"stage": "error", "message": str(e)}


@fastapi_router.post(conf.bot_webhook_path, include_in_schema=False)
async def webhook(update: dict):
    try:
        tg_update = Update(**update)
        return await conf.dp.feed_update(
            bot=conf.bot, update=tg_update
        )

    except Exception as e:
        await conf.logger.send_log(ERROR, "@fastapi_router -> telegram webhook", e=e, msg=str(e))
