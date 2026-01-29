from datetime import datetime
from typing import Sequence

from .base import Bitrix


class Task(Bitrix):
    async def get_all_tasks(self) -> list[dict] | None:
        result = await self.call_method(
            method="tasks.task.list",
            params={"filter": {"CREATED_BY": self.conf.data.current_id}}
        )
        if result:
            return result["result"]["tasks"]

    async def get_task(self, task_id) -> dict | None:
        result = await self.call_method(method="tasks.task.get", params={"taskId": task_id})
        if result and result.get("result"):
            return result["result"]["task"]

    async def get_task_files(self, task_id) -> list[dict] | None:
        result = await self.call_method(method="task.item.getfiles", params={"taskId": task_id})
        if result:
            return result["result"]

    async def create_task(
            self, title, description, files: list[int], group_id: str,
            auditors: list[int] = None, creator_id: int = None,
            executor_id: int = None, deadline: datetime = None
    ) -> dict | None:
        created_by = creator_id if creator_id else self.conf.data.current_id

        fields = {
            "CREATED_BY": created_by,
            "RESPONSIBLE_ID": executor_id if executor_id else self.conf.data.current_id,
            "GROUP_ID": group_id,
            "TITLE": title,
            "DESCRIPTION": description,
            "UF_TASK_WEBDAV_FILES": [f"n{file_id}" for file_id in files]
        }

        if deadline:
            fields["DEADLINE"] = deadline.strftime("%Y-%m-%d")

        if auditors:
            fields["AUDITORS"] = auditors

        result = await self.call_method(
            method="tasks.task.add",
            params={
                "fields": fields
            }
        )
        if result:
            return result["result"]

    async def delete_task(self, task_id) -> None:
        result = await self.call_method(method="tasks.task.delete", params={"taskId": task_id})
        if result:
            return result["result"]

    async def update_task(
        self, task_id: int, title: str = None, description: str = None,
        bit_group_id: int = None, bit_stage_id: int = None, status_num: int = None,
        auditors: list[int] = None, responsible_id: int = None,
        custom: Sequence[tuple[str, str]] = None
    ) -> dict | None:
        """
        Updates a task
        :param custom: your custom fields
        :param task_id: *
        :param title: *
        :param description: *
        :param bit_group_id: *
        :param bit_stage_id: *
        :param auditors: list of observers_bit_id
        :param responsible_id: *
        :param status_num: user only: {2 - Ждет выполнения, 3 - Выполняется,
        4 - Ожидает контроля, 5 - Завершена, 6 - Отложена.}
        :return:
        """
        f_checking = (
            ("TITLE", title), ("DESCRIPTION", description), ("RESPONSIBLE_ID", responsible_id),
            ("GROUP_ID", bit_group_id), ("STAGE_ID", bit_stage_id), ("STATUS", status_num), ("AUDITORS", auditors)
        )

        fields = {f[0]: f[1] for f in f_checking if f[1]}
        if custom:
            for info in custom:
                fields[info[0]] = info[1]

        params = {"taskId": task_id, "fields": fields}
        result = await self.call_method(method="tasks.task.update", params=params)

        if result:
            return result["result"]

    async def get_groups(self) -> list[dict] | None:
        result = await self.call_method(
            method="sonet_group.user.groups"
        )
        if result:
            return result["result"]

    async def get_stages(self, group_id: int) -> dict | None:
        result = await self.call_method(method="task.stages.get", params={"entityId": group_id})
        if result:
            return result["result"]

    async def add_comment(self, task_id: int, message: str, creator_id: int = None) -> int | None:
        """if a comment has a file, it cannot be created on behalf of another user"""
        fields = {"POST_MESSAGE": message, "AUTHOR_ID": creator_id if creator_id else self.conf.data.current_id}
        result = await self.call_method(method="task.commentitem.add", params={"TASKID": task_id, "FIELDS": fields})

        if result:
            return result["result"]

    async def add_file_comment(self, chat_id: int, files: list[int], message) -> int | None:
        result = await self.call_method(
            method="im.disk.file.commit",
            params={
                "CHAT_ID": chat_id,
                "DISK_ID": files,
                "MESSAGE": message,
            }
        )
        return result["result"]["MESSAGE_ID"]

    async def get_comment(self, chat_id: int, message_id: int = None) -> dict | None:
        if message_id:
            result = await self.call_method(
                "im.dialog.messages.get",
                params={"DIALOG_ID": f"chat{chat_id}", "FIRST_ID": message_id, "LAST_ID": message_id}
            )
        else:
            result = await self.call_method("im.dialog.messages.get", params={"DIALOG_ID": f"chat{chat_id}"})

        if result:
            return result["result"]

    async def get_comment_fix(self, chat_id: int, message_id: int) -> dict | None:
        # Temp method (bitrix bug in FIRST_ID and LAST_ID)
        result = await self.call_method(
            "im.dialog.messages.get",
            params={"DIALOG_ID": f"chat{chat_id}", "FIRST_ID": message_id - 1, "LAST_ID": message_id + 1} # bitrix bug!?
        )

        fixed_messages = []
        for message in result["result"]["messages"]:
            if message["id"] == message_id:
                fixed_messages.append(message)
        result["result"]["messages"] = fixed_messages

        return result["result"]

    async def get_history(self, task_id: int, stage: bool = None) -> dict | None:
        fields = {}

        if stage is True:
            fields["FIELD"] = "STAGE"

        result = await self.call_method(method="tasks.task.history.list", params={"taskId": task_id, "filter": fields})
        if result:
            return result["result"]
