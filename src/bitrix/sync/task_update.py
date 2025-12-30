import asyncio
from io import BytesIO
from logging import ERROR
from typing import Sequence, Literal
from datetime import datetime
from dataclasses import dataclass, field

from src.static.message_answers import StageNotify, TaskNFY
from src.bot.structures.keyboards import test_answer_ikb
from src.classes.cls_const import TaskRole, StageType
from src.utils.task_report import TaskExport

from .base import BaseBitSync
from .status_checks import StatusCheck
from .utils import format_stage_changing

from src.db.models import User, Task, Stage, TaskUser


from src.i18n.i18n import translator

@dataclass()
class UpdateMessage(BaseBitSync):
    message: str = ""
    notify_users: set = field(default_factory=set)
    task_title: bool = True
    file: BytesIO | None = None
    file_type: Literal["document", "photo", "video", "audio"] | None = None
    kb = None


class UpdateTask:
    def __init__(self, bit_task: dict, db_task: Task, bit_sync: BaseBitSync):
        self.bit_sync = bit_sync
        self.db_task = db_task
        self.bit_task = bit_task

        self.bitrix_update: dict = {}
        self.update_task = False
        self.messages: list[UpdateMessage] = [UpdateMessage()]  # notify messages

        self.change_by: User | None = None
        self.all_stages: Sequence[Stage] = []
        self.task_users_role = self.bit_sync.db.sort_task_roles(self.db_task.task_users)

        self.bit_sync_users_status = False

    async def update(self) -> list[UpdateMessage]:
        await self.load_data()

        tasks = (
            self._check_group(),
            self._check_stage(),
            self._check_deadline(),
            self._check_time_estimate(),
            self._check_executor(), self._check_co_executor(), self._check_observers(),
        )

        for i in tasks:
            try:
                await i
            except Exception as e:
                await self.bit_sync.logger.send_log(ERROR, f"Update task {self.db_task.id} error {i.__name__}", e)

        if self.update_task:
            await self.bit_sync.db.update_task(self.db_task)

        if self.bitrix_update:
            await self.bit_sync.bitrix.update_task(self.db_task.bit_task_id, **self.bitrix_update)

        return self.messages

    async def load_data(self):
        self.all_stages, self.change_by = await asyncio.gather(
            self.bit_sync.db.get_task_stage(group_id=self.db_task.group_id),
            self.get_chane_by()
        )

    async def _check_group(self):
        group = self.bit_task.get("groupId", "0")
        group = int(group) if group.isdigit() else 0

        if self.db_task.group.bit_group_id != group:
            new_group = await self.bit_sync.db.get_task_group(bit_group_id=group) if group else None
            if new_group:
                self.messages[0].message += TaskNFY.CHANGE_GROUP.format(
                    from_=self.db_task.group, to=new_group[0]
                )
                self.all_stages = await self.bit_sync.db.get_task_stage(group_id=new_group[0].id)
                self.db_task.group_id = new_group[0].id
                self.db_task.group = new_group[0]
                self.db_task.stage_id = self.all_stages[0].id
                self.db_task.stage = self.all_stages[0]
                self.update_task = True

            else:
                self.bitrix_update["bit_group_id"] = self.db_task.group.bit_group_id

    async def _check_stage(self):
        now_bit_stage_id = int(self.bit_task.get("stageId"))
        db_bit_stage_id = self.db_task.stage.bit_stage_id if self.db_task.stage else None
        if db_bit_stage_id == now_bit_stage_id:
            return

        if not isinstance(self.db_task.stage_id, int):
            self.db_task.stage_id = self.all_stages[0].id
            self.db_task.stage = self.all_stages[0]

            self.bitrix_update["bit_stage_id"] = self.all_stages[0].bit_stage_id
            self.update_task = True
            return

        if not self.change_by:
            error_msg = StageNotify.CHANGER_NONE
            stage_now = self.db_task.stage
        else:
            stage_now = await self.bit_sync.db.get_task_stage(bit_stage_id=now_bit_stage_id)
            if not stage_now:
                await self.bit_sync.sync_stages()
                stage_now = await self.bit_sync.db.get_task_stage(bit_stage_id=now_bit_stage_id)
            stage_now = stage_now[0]

            try:
                checker = StatusCheck(
                    db=self.bit_sync.db, task=self.db_task, change_by=self.change_by, roles=self.task_users_role,
                    stages=self.all_stages, to_stage=stage_now,
                    self_bitrix_id=self.bit_sync.bitrix.conf.data.current_id
                )
                error_msg = await checker.check()

            except Exception as e:
                error_msg = f"{StageNotify.CHECK_ERROR}\n{e}"
                await self.bit_sync.logger.send_log(
                    ERROR,
                    "TaskSync -> on_task_update -> checker.check(): Task check failed",
                    e=e,
                    msg=f"{self.db_task.bit_task_id=}, {self.db_task.id=}, {self.db_task.stage_id=}"
                        f", {stage_now.id=}"
                )

        if error_msg:  # if the check fails (We get an error message)
            self.bitrix_update["bit_stage_id"] = self.db_task.stage.bit_stage_id

            if self.change_by and isinstance(self.change_by.tg_id, int):
                self.messages.append(UpdateMessage(error_msg, {self.change_by.tg_id}))

        else:
            self.messages[0].message += format_stage_changing(self.all_stages, self.db_task.stage_id, stage_now.id)
            task_exit_queue = self.db_task.stage.in_queue and not stage_now.in_queue
            self.db_task.stage_id = stage_now.id
            self.update_task = True

            if stage_now.id == self.all_stages[-1].id or stage_now.stage_type == StageType.TESTING:
                if stage_now.stage_type == StageType.TESTING:
                    self.messages[0].kb = test_answer_ikb(self.db_task.id, language=translator.default_language)
                    self.db_task.test_date = datetime.now()

                    if self.db_task.group.ban_hours:
                        self.messages[0].message += "\n" + TaskNFY.TEST_WARNING.format(
                            time=self.db_task.group.ban_hours
                        )

                else:
                    self.db_task.closed_date = datetime.now()

            if stage_now.stage_type == StageType.FIFO:
                task_fifo = await self.bit_sync.db.get_fifo_queue(group_id=self.db_task.group.id)
                if not task_fifo:
                    stages_in_queue = [s.id for s in self.all_stages if s.in_queue]
                    number_of_tasks = await self.bit_sync.db.get_stage_task_counts(stage_ids=stages_in_queue)

                else:
                    number_of_tasks = 0
                    task_fifo = [self.db_task]

                if not task_fifo and (number_of_tasks < self.db_task.group.max_tasks):
                    next_stage = None

                    for st in self.all_stages:
                        if stage_now.sort < st.sort:
                            next_stage = st
                            break

                    if next_stage:
                        self.db_task.stage_id = next_stage.id
                        await self.bit_sync.db.update_task(self.db_task)
                        await self.bit_sync.bitrix.update_task(
                            self.db_task.bit_task_id, bit_stage_id=next_stage.bit_stage_id
                        )

            if task_exit_queue and self.db_task.group.fifo_queue:
                task_fifo = await self.bit_sync.db.get_fifo_queue(group_id=self.db_task.group.id)
                if task_fifo:
                    task_fifo = task_fifo[0]
                    next_stage = None

                    for st in self.all_stages:
                        if task_fifo.stage.sort < st.sort:
                            next_stage = st
                            break

                    if next_stage:
                        msg = TaskNFY.PASSED_QUEUE.format(bit_id=task_fifo.bit_task_id, task_name=task_fifo.title)
                        tg_ids = {i.user.tg_id for i in task_fifo.task_users if i and i.user.tg_id}
                        self.messages.append(UpdateMessage(msg, task_title=False, notify_users=tg_ids))

                        task_fifo.stage_id = next_stage.id
                        await self.bit_sync.db.update_task(task_fifo)
                        await self.bit_sync.bitrix.update_task(
                            task_fifo.bit_task_id, bit_stage_id=next_stage.bit_stage_id
                        )

                        if self.db_task.group.notify:
                            file = await TaskExport.s_queue_png(self.bit_sync.db, self.db_task.group_id)
                            if file:
                                users_notify = []
                                for r in await self.bit_sync.db.get_roles(notify_queue=True, join_users=True):
                                    users_notify += r.users

                                self.messages.append(
                                    UpdateMessage(
                                        msg, {m.tg_id for m in users_notify if m.tg_id},
                                        task_title=False, file=file, file_type="photo")
                                )

    async def _check_deadline(self):
        # check deadline
        if self.bit_task.get("deadline"):
            deadline_in_bit = datetime.fromisoformat(self.bit_task["deadline"]).astimezone().replace(tzinfo=None)
            if deadline_in_bit != self.db_task.deadline:
                self.db_task.deadline = deadline_in_bit
                self.update_task = True

    async def _check_time_estimate(self):
        if self.bit_task.get("timeEstimate") and self.bit_task["timeEstimate"].isdigit():
            if self.db_task.allocated_time != int(self.bit_task["timeEstimate"]):
                self.db_task.allocated_time = int(self.bit_task["timeEstimate"])
                self.update_task = True

    async def _check_executor(self):
        # check executor/developer/responsible
        responsible_id = int(self.bit_task.get("responsibleId", 0))

        if not self.task_users_role.executor or (
                self.task_users_role.executor.user.bit_user_id != responsible_id
        ):
            new_responsible = await self.get_user_by_bit_id(bit_id=responsible_id)
            if not new_responsible:
                return

            # check max_executor_task in group
            if (
                    self.db_task.group.max_executor_task and self.db_task.stage.in_queue
                    and new_responsible.bit_user_id != self.bit_sync.bitrix.conf.data.current_id
            ):
                user_tasks_in_queue = await self.bit_sync.db.get_tasks_with(
                    stage_ids=[i.id for i in self.all_stages if i.in_queue],
                    user_id=new_responsible.id,
                    role=TaskRole.EXECUTOR
                )
                if len(user_tasks_in_queue) >= self.db_task.group.max_executor_task:
                    self.bitrix_update["responsible_id"] = self.bit_sync.bitrix.conf.data.current_id
                    new_responsible = await self.get_user_by_bit_id(bit_id=self.bit_sync.bitrix.conf.data.current_id)
                    self.messages[0].message += StageNotify.RESPONSIBLE_MAX

            self.messages[0].message += TaskNFY.TASK_RESPONSIBLE.format(name=new_responsible.full_name)
            if self.task_users_role.executor:
                self.task_users_role.executor.user_id = new_responsible.id
                await self.bit_sync.db.update_task_user(self.task_users_role.executor)
            else:
                await self.bit_sync.db.add_task_user(new_responsible.id, self.db_task.id, role=TaskRole.EXECUTOR)

    async def _check_co_executor(self):
        # check co_executor/co_developer/accomplices
        accomplices = {t.user.bit_user_id: t for t in self.task_users_role.co_executors}

        if accomplices != self.bit_task.get("accomplices"):
            for accomplice in self.bit_task.get("accomplices"):
                if int(accomplice) in accomplices:
                    # We delete them from the list because they exist in bitrix,
                    # and those that remain are not in bitrix then we delete them from the database
                    del accomplices[int(accomplice)]

                else:  # check new co_executor/co_developer/accomplices
                    new_co_executor = await self.get_user_by_bit_id(bit_id=int(accomplice))
                    if not new_co_executor:
                        continue

                    self.messages[0].message += TaskNFY.ADD_CO_EXECUTOR.format(name=new_co_executor.full_name)
                    task_user = await self.bit_sync.db.add_task_user(
                        user_id=new_co_executor.id, task_id=self.db_task.id, role=TaskRole.CO_EXECUTOR
                    )
                    self.task_users_role.co_executors.append(task_user)

            # check to del co_executor/co_developer/accomplices
            for del_auditor in accomplices.values():
                await self.bit_sync.db.delete_info(selected_model=TaskUser, id_=del_auditor.id)
                self.messages[0].message += TaskNFY.DEL_CO_EXECUTOR.format(name=del_auditor.user.full_name)

    async def _check_observers(self):
        auditors = {t.user.bit_user_id: t for t in self.task_users_role.observers}

        if auditors != self.bit_task.get("auditors"):
            for auditor in self.bit_task.get("auditors"):
                if int(auditor) in auditors:  # for find to del auditors/OBSERVERs
                    del auditors[int(auditor)]

                else:   # check new auditors/OBSERVER
                    new_auditor = await self.get_user_by_bit_id(bit_id=int(auditor))
                    if not new_auditor:
                        continue

                    self.messages[0].message += TaskNFY.ADD_AUDITOR.format(name=new_auditor.full_name)
                    task_user = await self.bit_sync.db.add_task_user(
                        user_id=new_auditor.id, task_id=self.db_task.id, role=TaskRole.OBSERVER
                    )
                    self.task_users_role.observers.append(task_user)

            # check to del auditors/OBSERVERs
            for del_auditor in auditors.values():
                await self.bit_sync.db.delete_info(selected_model=TaskUser, id_=del_auditor.id)
                self.messages[0].message += TaskNFY.DEL_AUDITOR.format(name=del_auditor.user.full_name)
        # -----------------------------------------------------------------------------------------------

    async def get_chane_by(self) -> User | None:
        changed_bit_id = int(self.bit_task.get("changedBy", 0))

        if changed_bit_id:
            change_by = await self.get_user_by_bit_id(bit_id=changed_bit_id)
            return change_by

    async def get_user_by_bit_id(self, bit_id: int) -> User | None:
        user = await self.bit_sync.db.get_user(bit_id=bit_id)
        if user:
            return user[0]
        if not self.bit_sync_users_status:
            self.bit_sync_users_status = True
            await self.bit_sync.sync_users()
            user = await self.bit_sync.db.get_user(bit_id=bit_id)
            if user:
                return user[0]
        return None
