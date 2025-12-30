from logging import ERROR
from typing import Callable
from src.classes.models.logger import LogWriter


class UsersManager:
    def __init__(self, user_getter: Callable, logger: LogWriter, max_users: int = 100, cleanup_amount: int = 50):
        self.logger = logger
        self.user_getter = user_getter
        self.users: dict[int, tuple[str, str]] = {}
        self.not_registered = set()
        self.max_users = max_users
        self.cleanup_amount = cleanup_amount

    async def get_bot_user(self, tg_id: int) -> tuple[str, str] | None:
        if tg_id in self.users:
            return self.users[tg_id]

        elif tg_id in self.not_registered:
            return None

        try:
            user = await self.user_getter(tg_id=tg_id)
            if user:
                user = user[0]
                self.users[tg_id] = (user.access_level, user.language)
                self._cleanup_users()
                return user.access_level, user.language
            else:
                self.not_registered.add(tg_id)
                if len(self.not_registered) > self.max_users:
                    self.not_registered.clear()

                return None

        except Exception as e:
            await self.logger.send_log(ERROR, "UsersManager -> get_bot_user", e=e, msg=f"tg_id: {tg_id}")

    def _cleanup_users(self):
        if len(self.users) > self.max_users:
            # Remove the first self.cleanup_amount elements from the dictionary
            for _ in range(self.cleanup_amount):
                if self.users:
                    self.users.pop(next(iter(self.users)))

    def update_user(self, tg_id: int, access_level: str | None = None, language: str | None = None) -> None:
        exits_users = self.users.get(tg_id, (None, None))

        self.users[tg_id] = (access_level or exits_users[0], language or exits_users[1])
        if tg_id in self.not_registered:
            self.not_registered.remove(tg_id)

    def delete_user(self, tg_id: int) -> None:
        if tg_id in self.users:
            del self.users[tg_id]
