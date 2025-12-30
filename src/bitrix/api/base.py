import asyncio
import aiohttp

from pathlib import Path
from dataclasses import dataclass
from logging import ERROR

from src.classes.base.data_save import BaseDataSave
from src.classes.base.abc_cls import LoggerABC


@dataclass
class BitrixConfigData:
    domain: str
    current_id: int
    current_full_name: str
    user_storage_id: int


class BitrixConf(BaseDataSave):
    _config: dict
    data: BitrixConfigData = None

    def __init__(self, config_path: Path) -> None:
        BaseDataSave.init(self=self, config_path=config_path)
        if self._config:
            self.data = BitrixConfigData(**self._config)

    def set_data(self, data: BitrixConfigData) -> None:
        self._config = data.__dict__
        self.data = data
        self.save_config()

    def get_data(self) -> BitrixConfigData | None:
        if not self._config:
            return None
        else:
            return BitrixConfigData(**self._config)


class Bitrix:
    """Before using it, be sure to create a session"""
    session: aiohttp.ClientSession = None

    def __init__(self, webhook_url: str, config_path: Path, logger: LoggerABC = None, max_retries=3, retry_delay=5):
        self.webhook_url = webhook_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay  # delay between attempts in seconds

        self.conf = BitrixConf(config_path=config_path)
        self.logger = logger

    async def write_log(self, log_level: int, name: str, e: Exception = None, msg: str = "None") -> None:
        if isinstance(self.logger, LoggerABC):
            await self.logger.send_log(log_level, f"Bitrix API - {name}", e=e, msg=msg)
        else:
            print(f"Bitrix API - {name}\nType: {type(e)}\nException: {e}\nArgs: {e.args if e else None}\nmsg: {msg}")

    async def create_session(self) -> None:
        try:
            if self.session is None:
                self.session = aiohttp.ClientSession()

            if not self.conf.data:
                s = await self.configurate()
                self.conf.set_data(s)

        except Exception as e:
            await self.write_log(ERROR, "create_session", e)

    async def close(self) -> None:
        try:
            if self.session and not self.session.closed:
                await self.session.close()

        except Exception as e:
            await self.write_log(ERROR, "close_session", e)

    async def _make_request(self, url, params):
        if self.session is None:
            await self.create_session()
        for attempt in range(self.max_retries):
            try:
                async with self.session.post(url, json=params) as response:
                    vot_error = await response.text()
                    response.raise_for_status()
                    return await response.json()
            except (aiohttp.ClientError, aiohttp.ClientResponseError, asyncio.TimeoutError) as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    try:
                        error_text = await response.text()
                    except Exception as e_get_error:
                        error_text = f"Can not get error text. Exception: {e_get_error}"
                    msg = (
                        f"\n------------------------------------------------------------\n"
                        f"url={url}\nparams={params}\nError response body:{error_text}\n"
                        f"------------------------------------------------------------"
                    )
                    await self.write_log(ERROR, "_make_request", e, msg)

    async def call_method(self, method: str, params: dict = None) -> dict:
        """
        Calls the Bitrix24 API method.

        :param method: Name of the API method.
        :param params: Method parameters.
        :return: API response in the form of a dictionary.
        """
        url = f"{self.webhook_url}{'' if self.webhook_url[-1] == '/' else '/'}{method}.json"
        return await self._make_request(url, params)

    async def configurate(self) -> BitrixConfigData:
        domain = self.webhook_url[:self.webhook_url.index("/rest")]
        current = await self.call_method(method="user.current")
        current = current.get("result")
        full_name = (current.get("NAME") + " " + current.get("LAST_NAME")).strip()

        async def get_user_storage_id(f_name) -> str | None:
            """
            getting the storage id to create a folder where task files will be stored
            doc: https://dev.1c-bitrix.ru/rest_help/disk/storage/disk_storage_getlist.php
            """
            index = 1
            all_storages = []
            while True:
                storages = await self.call_method(method="disk.storage.getlist", params={"sort": "ID", "start": index})
                if storages:
                    all_storages += storages["result"]
                    index += 50
                    if len(storages["result"]) < 50:
                        break

            for storage in all_storages:
                if storage["NAME"] == f_name:
                    return storage["ID"]

        user_storage_id = await get_user_storage_id(full_name)

        return BitrixConfigData(
            domain=domain,
            current_id=int(current["ID"]),
            current_full_name=full_name,
            user_storage_id=int(user_storage_id)
        )
