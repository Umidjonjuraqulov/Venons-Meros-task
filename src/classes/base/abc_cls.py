from abc import ABC, abstractmethod

from pathlib import Path
from aiogram import Bot


class LoggerABC(ABC):
    @abstractmethod
    def init(self, log_path: Path):
        pass

    @abstractmethod
    def setup(self, bot: Bot, chat_id: int | str) -> None:
        pass

    @abstractmethod
    async def send_log(self, log_level: int, name: str, e: Exception = None, msg: str = "Not message"):
        pass

    def write_log(self, log_level: int, name: str, e: Exception = None, msg: str = "Not message") -> None:
        pass
