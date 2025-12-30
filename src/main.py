# pip install aiogram fastapi python-dotenv SQLAlchemy alembic asyncpg sqladmin itsdangerous
from pathlib import Path
import asyncio
import sys

sys.path.append(str(Path(__file__).parent.parent))

import uvicorn
from fastapi import FastAPI

from sqladmin import Admin
from src.admin import AdminAuth, all_admin_models

from src.configuration import conf
from src.bot.dispatcher import get_dispatcher
from src.fast_api.main_router import fastapi_router

tasks = []
app = FastAPI()
app.include_router(fastapi_router)

authentication_backend = AdminAuth(
    admin_user=conf.admin_login, admin_password=conf.admin_password, secret_key=conf.admin_password
)
admin = Admin(app, conf.bitrix_db.engine, authentication_backend=authentication_backend)

for admin_model in all_admin_models:
    admin.add_view(admin_model)


async def run_bot():
    dp = get_dispatcher(conf.user_manager, conf.dp)

    if conf.bot_mode == "webhook":
        webhook_info = await conf.bot.get_webhook_info()
        if webhook_info.url != conf.bot_webhook_url:
            await conf.bot.set_webhook(url=conf.bot_webhook_url)

    else:
        await conf.bot.delete_webhook(drop_pending_updates=True)
        try:
            await dp.start_polling(conf.bot)

        finally:
            # aiogram intercepts the stop signal, because of this fastapi continues to work
            exit(130)


@app.on_event("startup")
async def startup_event():
    bot_task = asyncio.create_task(run_bot())
    tasks.append(bot_task)
    await conf.setup()


@app.on_event("shutdown")
async def shutdown_event():
    await conf.cleanup()


if __name__ == "__main__":
    # uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info")
    uvicorn.run("main:app", port=8000, log_level="info")
