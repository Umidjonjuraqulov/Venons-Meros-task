import re
import asyncio
import aiohttp
from io import BytesIO
from pathlib import Path
from logging import ERROR
from typing import BinaryIO, Union, IO

from .base import Bitrix


class Storage(Bitrix):

    @staticmethod
    def sanitize_directory_name(directory_name):
        sanitized_name = re.sub(r'[^a-zA-Zа-яА-Я0-9_\-]', '_', directory_name)
        return sanitized_name

    async def create_folder(self, target_id: int, name: str, subfolder=True) -> int | None:
        """
        :param target_id: id of the folder/storage in which the folder will be created
        :param name: folder name
        :param subfolder: create in subfolder
        :return: ID of the created folder
        """
        async def check_exits(folder_name, target_folder: int, sub=True) -> str | None:
            method = "disk.folder.getchildren" if sub else "disk.storage.getchildren"
            storages = await self.call_method(method=method, params={"id": target_folder})
            for storage in storages.get("result"):
                if storage["NAME"].lower() == folder_name.lower():
                    return storage["ID"]

        name = self.sanitize_directory_name(name)[0:128]
        try:
            exits = await check_exits(folder_name=name, target_folder=target_id, sub=subfolder)
            if exits:
                return int(exits)

            if subfolder:
                folder = await self.call_method(
                    method="disk.folder.addsubfolder", params={"id": target_id, "data": {"NAME": name}}
                )
            else:
                folder = await self.call_method(
                    method="disk.storage.addfolder", params={"id": target_id, "data": {"NAME": name}}
                )

            return int(folder.get("result").get("ID"))

        except Exception as e:
            await self.write_log(
                log_level=ERROR,
                name="class Storage(Bitrix) -> async def create_folder",
                e=e,
                msg=f"{target_id=}, {name=}, {subfolder=}"
            )

    async def upload_file(self, folder_id: int, file_name: str, file: Union[Path, BinaryIO]) -> dict:
        try:
            # Get a link to download the file
            upload_info = await self.call_method(method="disk.folder.uploadfile", params={"id": folder_id})
            upload_url = upload_info.get("result").get("uploadUrl")
            field_name = upload_info.get("result").get("field")

            # Upload the file to the received URL
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()

                if isinstance(file, Path):
                    with open(file, 'rb') as f:
                        form.add_field(field_name, f, filename=file.name)
                        async with session.post(upload_url, data=form) as response:
                            response.raise_for_status()
                            result = await response.json()
                elif isinstance(file, (BytesIO, IO)):
                    form.add_field(field_name, file, filename=file_name)
                    async with session.post(upload_url, data=form) as response:
                        response.raise_for_status()
                        result = await response.json()
                else:
                    return {}

                return result["result"]
        except Exception as e:
            await self.write_log(
                log_level=ERROR,
                name="class Storage(Bitrix) -> async def upload_file",
                e=e,
                msg=f"{folder_id=}, {file_name=}"
            )

    async def get_file(self, file_bit_id: int) -> dict | None:
        result = await self.call_method(method="disk.file.get", params={"id": file_bit_id})
        if result:
            return result.get("result")

    async def download_file(self, file_bit_id: int = None, download_url: str = None) -> bytes | None:
        try:
            if file_bit_id:
                file = await self.get_file(file_bit_id=file_bit_id)
                file_url = file.get("DOWNLOAD_URL")

            elif download_url:
                file_url = self.conf.data.domain+download_url

            else:
                return

            async with aiohttp.ClientSession() as session:
                for attempt in range(3):
                    try:
                        async with session.get(
                            file_url, timeout=aiohttp.ClientTimeout(total=60)
                        ) as response:
                            if response.status != 200:
                                raise Exception(f"Failed to download file: {response.status}")

                            return await response.read()

                    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                        await asyncio.sleep(5)

            raise Exception("Failed to download file after multiple attempts")

        except Exception as e:
            await self.write_log(
                log_level=ERROR,
                name="class Storage(Bitrix) -> async def download_file",
                e=e,
                msg=f"{file_bit_id=}"
            )

