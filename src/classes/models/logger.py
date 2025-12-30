import logging
import traceback
from pathlib import Path
from logging import Logger, ERROR, INFO

from aiogram import Bot

from src.classes.base import Singleton
from src.classes.base.abc_cls import LoggerABC


class LogWriter(Singleton, LoggerABC):
    log_path: Path
    logger: Logger
    bot: Bot = None
    chat_id: int | str = None

    def __init__(self, log_path: Path, console_level: int = INFO, file_level: int = ERROR):  # noqa
        pass

    def init(self,  log_path: Path, console_level: int = INFO, file_level: int = ERROR):
        self.log_path = log_path
        """Set up and return a configured logger."""
        logging.basicConfig(level=console_level)
        file_handler = logging.FileHandler(self.log_path)
        file_handler.setLevel(level=file_level)  # Save to file those logs that are higher than log_level.
        log_format = """
----------------------------------------------------------------------------------------------------
%(asctime)s - %(name)s - %(levelname)s - %(message)s
----------------------------------------------------------------------------------------------------
"""
        formatter = logging.Formatter(log_format)
        file_handler.setFormatter(formatter)
        self.logger = logging.getLogger()
        self.logger.addHandler(file_handler)

    def setup(self, bot: Bot, chat_id: int | str) -> None:
        self.bot = bot
        self.chat_id = chat_id

    async def send_log(self, log_level: int, name: str, e: Exception = None, msg: str = "Not message"):
        send_msg = (f"traceback: {traceback.format_exc()}{name}\nType: {type(e)}\nException: {e}\n"
                    f"Args: {e.args if e else None}\nmsg: {msg}")
        send_msg_len = len(send_msg)
        if self.bot and self.chat_id:
            try:
                if len(send_msg) >= 4000:
                    msgs = [send_msg[i*4000:i*4000+4000] for i in range(send_msg_len//4000+1)]
                    for i in msgs:
                        await self.bot.send_message(
                            chat_id=self.chat_id,
                            text=i,
                            parse_mode=None
                        )
                else:
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=send_msg,
                        parse_mode=None
                    )
            except Exception as send_e:
                self.write_log(ERROR, "class Logger -> async send log", send_e)

        self.write_log(log_level, name, e, msg)

    def write_log(self, log_level: int, name: str, e: Exception = None, msg: str = "None") -> None:
        self.logger.log(
            log_level,
            f"traceback: {traceback.format_exc()}{name}\nType: {type(e)}\nException: {e}\n"
            f"Args: {e.args if e else None}\nmsg: {msg}"
        )
