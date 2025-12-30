import asyncio
import sys
from os import getenv
from pathlib import Path
from dotenv import load_dotenv
from logging import ERROR, WARNING

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

# Import models
from src.classes.base import Singleton
from src.bitrix import BitrixAPI, BitSync
from src.db.database import BitrixDB
from src.classes.models import LogWriter, NotifyManager

from src.bot.util.user_manager import UsersManager
from src.utils.task_report import TaskExport

app_dir: Path = Path(__file__).parent.parent


class Config(Singleton):
    tasks = []

    def __init__(self):
        self.app_dir = app_dir
        self.configs_dir = app_dir / "storage"

        load_dotenv(self.configs_dir / ".env")

        # env vars
        self.db_url = getenv("DB_URL")
        self.debug = True if getenv("DEBUG", False) else False
        self.project_url = getenv("PROJECT_URL")
        self.admin_login = getenv("ADMIN_LOGIN")
        self.admin_password = getenv("ADMIN_PASSWORD")

        # Bitrix
        self.bit_rest_url = getenv("BIT_REST_URL")
        self.bit_hook_token = getenv("BIT_HOOK_TOKEN")
        self.bit_custom_paid = getenv("BIT_PAID_FILED")

        # bot
        self.notify_chat_id = getenv("NOTIFY_CHAT_ID")
        self.log_chat_id = getenv("LOG_CHAT_ID")
        self.review_chat_id = getenv("REVIEW_CHAT_ID")
        self.token = getenv("BOT_TOKEN")
        self.bot_mode = getenv("BOT_MODE")
        self.bot_webhook_path = f"/bot/{self.token}"
        self.bot_webhook_url = f"{self.project_url}{self.bot_webhook_path}"

        # Models
        self.dp = Dispatcher()
        self.bot = Bot(token=self.token, default=DefaultBotProperties(parse_mode="HTML"))

        self.logger = LogWriter(self.configs_dir / "app.log", console_level=WARNING)
        self.logger.setup(bot=self.bot, chat_id=self.log_chat_id)
        self.notify_manager = NotifyManager(bot=self.bot, loger=self.logger)

        self.bitrix_db = BitrixDB(url=self.db_url, echo=self.debug, logger=self.logger.logger)
        self.user_manager = UsersManager(user_getter=self.bitrix_db.get_user, logger=self.logger)

        self.bitrix = BitrixAPI(
            webhook_url=self.bit_rest_url,
            config_path=(self.configs_dir / "bitrix_conf.json"),
            logger=self.logger,
            max_retries=3,
            retry_delay=5
        )
        self.bit_sync = BitSync(
            bitrix_api=self.bitrix,
            db=self.bitrix_db,
            loger=self.logger
        )
        self.bit_sync.setup_task_sync(notify_manager=self.notify_manager, bot=self.bot, log_chat_id=self.log_chat_id)
        self.task_export = TaskExport(self.bitrix_db)

    async def setup(self):
        tables_exist = await self.bitrix_db.check_tables()
        if not tables_exist:
            await self.logger.send_log(
                ERROR,
                "Tables not exist",
                Exception(),
                msg="No tables found. Run 'alembic upgrade head'"
            )
            print("\n\n---------------\nNo tables found. Run 'alembic upgrade head'\n---------------\n\n")
            sys.exit("No tables found. Run 'alembic upgrade head'")

        await self.bitrix.create_session()

        bit_sync = asyncio.create_task(self.bit_sync.schedule_sync(run_hour=0, run_minute=0, chat_id=self.log_chat_id))
        task_sync = asyncio.create_task(self.bit_sync.sync_tasks(check_time=3600))
        task_test_nfy = asyncio.create_task(self.bit_sync.notify_testing(10800, 10800))
        task_auto_acceptance = asyncio.create_task(self.bit_sync.auto_acceptance_tasks([5, 6], 9, 17, 3600))
        task_export = asyncio.create_task(self.task_export.schedule_send(self.notify_chat_id, self.bot, 18))
        self.tasks += [bit_sync, task_sync, task_export, task_test_nfy, task_auto_acceptance]

    async def cleanup(self):
        for task in self.tasks:
            try:
                task.cancel()
            except Exception as e:
                await self.logger.send_log(ERROR, "conf -> cleanup", e=e)

        await self.bitrix_db.engine.dispose()
        await self.bitrix.close()


conf = Config()
