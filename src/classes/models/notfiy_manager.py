from logging import ERROR, INFO
from typing import Iterable
from io import BytesIO

from aiogram import Bot
from aiogram.types import BufferedInputFile

from src.classes.base.abc_cls import LoggerABC


class NotifyManager:
    def __init__(self,  bot: Bot, loger: LoggerABC = None):
        self.bot = bot
        self.logger = loger

    async def notify(self, msg: str, tg_ids: Iterable[int | str], kb=None, off_parse_mode=False) -> None:
        try:
            error_send_ids = []
            for tg_id in set(tg_ids):
                send_msg_len = len(msg)
                if self.bot:
                    try:
                        if len(msg) >= 4000:
                            msgs = [msg[i * 4000:i * 4000 + 4000] for i in range(send_msg_len // 4000 + 1)]
                            for i in msgs[0:5]:
                                if off_parse_mode:
                                    await self.bot.send_message(chat_id=tg_id, text=i, parse_mode=None)
                                else:
                                    await self.bot.send_message(chat_id=tg_id, text=i)
                        else:
                            if off_parse_mode:
                                await self.bot.send_message(chat_id=tg_id, text=msg, reply_markup=kb, parse_mode=None)
                            else:
                                await self.bot.send_message(chat_id=tg_id, text=msg, reply_markup=kb)

                    except Exception as _:
                        error_send_ids.append(tg_id)

            if error_send_ids:
                if isinstance(self.logger, LoggerABC):
                    self.logger.write_log(
                        INFO,
                        "NotifyManager.py -> fail send notify",
                        msg=f"to tg_id: {error_send_ids}"
                    )
                else:
                    print(f"NotifyManager.py -> fail send notify: to tg_ids: {error_send_ids}")

        except Exception as e:
            if isinstance(self.logger, LoggerABC):
                await self.logger.send_log(
                    ERROR,
                    "NotifyManager.py -> Error send notify",
                    e=e,
                    msg=f"target tg_ids: {tg_ids}"
                )
            else:
                print(f"NotifyManager.py -> fail send notify: {e} target tg_ids: {tg_ids}")

    async def send_photo(self, photo: BytesIO | BufferedInputFile, msg: str, tg_ids: Iterable[int | str]) -> None:
        try:
            file_id = None
            if isinstance(photo, BytesIO):
                photo = BufferedInputFile(photo.read(), f"pass.png")

            error_send_ids = []
            for chat_id in tg_ids:
                try:
                    if not file_id:
                        p = await self.bot.send_photo(chat_id, photo)
                        file_id = p.photo[-1].file_id

                    else:
                        await self.bot.send_photo(chat_id, photo)

                except Exception as _:
                    error_send_ids.append(chat_id)

            if error_send_ids:
                if isinstance(self.logger, LoggerABC):
                    self.logger.write_log(
                        INFO,
                        "NotifyManager.py -> fail send_photo",
                        msg=f"to tg_id: {error_send_ids}"
                    )
                else:
                    print(f"NotifyManager.py -> fail send_photo: to tg_ids: {error_send_ids}")

        except Exception as e:
            if isinstance(self.logger, LoggerABC):
                await self.logger.send_log(
                    ERROR,
                    "NotifyManager.py -> Error send_photo",
                    e=e,
                    msg=f"target tg_ids: {tg_ids}"
                )
            else:
                print(f"NotifyManager.py -> fail send_photo: {e} target tg_ids: {tg_ids}")

    async def forward_msg(
            self, from_chat_id: int | str, message_id: int | str, tg_ids: Iterable[int | str],
            protect: bool = False, copy: bool = False
    ) -> None:
        try:
            error_send_ids = []
            for chat_id in tg_ids:
                try:
                    if copy:
                        await self.bot.copy_message(chat_id, from_chat_id, message_id, protect_content=protect)

                    else:
                        await self.bot.forward_message(chat_id, from_chat_id, message_id, protect_content=protect)

                except Exception as _:
                    error_send_ids.append(chat_id)

            if error_send_ids:
                if isinstance(self.logger, LoggerABC):
                    self.logger.write_log(
                        INFO,
                        "NotifyManager.py -> fail forward_msg",
                        msg=f"to tg_id: {error_send_ids}"
                    )
                else:
                    print(f"NotifyManager.py -> fail forward_msg: to tg_ids: {error_send_ids}")

        except Exception as e:
            if isinstance(self.logger, LoggerABC):
                await self.logger.send_log(
                    ERROR,
                    "NotifyManager.py -> Error forward_msg",
                    e=e,
                    msg=f"target tg_ids: {tg_ids}"
                )
            else:
                print(f"NotifyManager.py -> fail forward_msg: {e} target tg_ids: {tg_ids}")