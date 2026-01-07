from datetime import datetime, timedelta
from typing import Sequence

from .utils import calc_work_hours

from src.classes.cls_const import TaskRole, StageType
from src.db.models import User, Task, Stage, TaskUser, RoleAccess, Role
from src.db.database import BitrixDB, TaskUserRoles
from src.static.message_answers import StageNotify


class StatusCheck:
    def __init__(
            self, db: BitrixDB, task: Task, change_by: User, roles: TaskUserRoles,
            stages: Sequence[Stage], to_stage: Stage, self_bitrix_id: int
    ):
        self.db = db

        self.task = task
        self.roles = roles
        self.stages = stages
        self.to_stage = to_stage
        self.change_by = change_by
        self.self_bitrix_id = self_bitrix_id

    async def check(self) -> str | None:
        """
        :return: if str: is error message or if None: ok
        """
        checks = (
            self.closed_task, self.close_from_test, self.check_queue, self.ban_accept, self.check_all_roles,
            self.to_dev, self.to_error, self.fifo_queue
        )
        for checker in checks:
            error_msg = await checker()
            if error_msg:
                return error_msg
        return None

    async def closed_task(self) -> str | None:
        """Checks if the given user can close the task. checks if the stage changes to all_stage[-1]"""
        if self.task.stage_id == self.stages[-1].id:
            if not self.change_by.role_id:
                return StageNotify.CLOSE_ERR

            changer_role = await self.db.get_role(id_=self.change_by.role_id)  # noqa role_id: int | None
            if changer_role.access_all_stage:
                self.task.closed_date = None
                await self.db.update_task(self.task)
                return None

            return StageNotify.CLOSE_ERR

    async def check_all_roles(self) -> str | None:
        main_role = await self.check_roles()
        if main_role is None:
            return None

        else:
            additional_roles = await self.db.get_additional_roles(self.change_by.id)
            checked = set()

            for a_role in additional_roles:
                if a_role.role_id in checked:
                    continue

                role = await self.db.get_role(id_=a_role.role_id)
                check = await self.check_roles(role=role)
                if check is None:
                    return None

                checked.add(a_role.role_id)

            return main_role

    async def check_roles(self, role: Role = None) -> str | None:
        """
        Check permission in roles
        2. Check the role
            2.1 Does the user have a role
            2.2 Can change other people's tasks or a task participant
            2.3 Can extract from the current stage
            2.4 Can insert into the desired stage
        """
        if not isinstance(self.change_by.role_id, int) and not role:  # 2.1
            return StageNotify.ROLE_NONE

        if isinstance(role, Role):
            changer_role = role
        else:
            changer_role = await self.db.get_role(id_=self.change_by.role_id)

        # 2.2 check if the user has access to this task (if he has "change_any" in roles or is logged into "TaskUsers")
        if not changer_role.change_any:
            has_permission = False
            for task_user in self.task.task_users:  # type: TaskUser
                if task_user.user_id == self.change_by.id:
                    has_permission = True

            if not has_permission:
                return StageNotify.NOT_TASK_USER

        if not changer_role.access_all_stage:
            role_access: dict[int, RoleAccess] = {access.stage_id: access for access in changer_role.access}
            # 2.3 Check extract ------------------------------------------------------------------------
            if not self.task.stage_id:  # if task not have status
                self.task.stage_id = self.stages[0].id
                self.task.stage = self.stages[0]

            if (self.task.stage_id not in role_access) or (not role_access[self.task.stage_id].extract):
                return StageNotify.CANT_EXTRACT.format(stage_name=self.task.stage.title)

            # 2.4 Check insert -------------------------------------------------------------------------
            if (self.to_stage.id not in role_access) or (not role_access[self.to_stage.id].insert):
                return StageNotify.CANT_INSERT.format(stage_name=self.to_stage.title)

    async def check_queue(self) -> str | None:
        """
        3.1 Check the queue of the stage itself;
        3.2 Skip if stage was inside queue
        3.3 Checks if the task limit for a group has been exceeded;
        3.4 Checks if the manager task limit has been exceeded;
        """

        # 3.1 Check the queue of the stage itself --------------------------------------------------
        if self.to_stage.max_tasks:
            num_in_stage = await self.db.get_stage_task_counts(stage_ids=[self.to_stage.id])
            if num_in_stage >= self.to_stage.max_tasks:
                return StageNotify.MAX_IN_STAGE.format(stage_name=self.to_stage.title)

        # 3.2 Skip if stage was inside queue -------------------------------------------------------
        stages_in_queue = [s.id for s in self.stages if s.in_queue]
        if self.task.stage_id in stages_in_queue:
            return None

        # check test stage | if task stage is test stage skip 3.3 and 3.4
        if self.task.stage.stage_type == StageType.TESTING:
            return None

        # 3.3 Checks if the task limit for a group has been exceeded -------------------------------
        if self.task.group.max_tasks and self.to_stage.id in stages_in_queue:
            number_of_tasks = await self.db.get_stage_task_counts(stage_ids=stages_in_queue)

            if number_of_tasks >= self.task.group.max_tasks:
                return StageNotify.GROUP_FULL.format(group_name=self.task.group.title)

        # 3.4 Checks if the manager task limit has been exceeded -----------------------------------
        if self.task.group.max_user_tasks and self.to_stage.id in stages_in_queue:
            check_user = self.roles.manager or self.roles.creator

            user_tasks_in_queue = await self.db.get_tasks_with(
                stage_ids=stages_in_queue,
                user_id=check_user.user_id,
                role=TaskRole.MANAGER if self.roles.manager else TaskRole.CREATOR
            )
            if len(user_tasks_in_queue) >= self.task.group.max_user_tasks:
                return StageNotify.CREATOR_FULL.format(name=check_user.user.full_name)

        if (
                self.task.group.max_executor_task and (not self.task.stage.in_queue) and self.to_stage.in_queue
                and self.roles.executor and self.roles.executor.user.bit_user_id != self.self_bitrix_id
        ):
            user_tasks_in_queue = await self.db.get_tasks_with(
                stage_ids=stages_in_queue,
                user_id=self.roles.executor.user_id,
                role=TaskRole.EXECUTOR
            )
            if len(user_tasks_in_queue) >= self.task.group.max_executor_task:
                return StageNotify.RESPONSIBLE_MAX

    async def ban_accept(self) -> str | None:
        if (not self.task.group.ban_hours) or self.task.unlimited_test:
            return None

        now = datetime.now()
        if self.task.test_date and (self.to_stage.id == self.stages[-1].id):  # Calc ban time
            test_date = self.task.test_date
            hours = calc_work_hours(test_date, now, [5, 6], 9, 17)

            if hours > self.task.group.ban_hours:
                ban_time = timedelta(hours=(hours - self.task.group.ban_hours))
                ban_users = [self.roles.creator.user]
                if self.roles.manager:
                    if ban_users[0].id != self.roles.manager.user.id:
                        ban_users.append(self.roles.manager.user)

                for user in ban_users:
                    if user.ban_time and user.ban_time > now:
                        user.ban_time += ban_time
                    else:
                        user.ban_time = now + ban_time
                    await self.db.update_user(update_to=user)

            return None

        elif (not self.task.stage.in_queue) and self.to_stage.in_queue and self.change_by.ban_time:  # Check ban status
            if (self.change_by.ban_time < now) or self.task.stage.stage_type == StageType.TESTING:
                return None

            changer_role = await self.db.get_role(id_=self.change_by.role_id)
            if changer_role.access_all_stage:
                return None

            return StageNotify.HAS_BAN_TIME.format(time=self.change_by.ban_time.strftime("%Y.%m.%d %H:%M"))

    async def close_from_test(self) -> str | None:
        if (
                self.task.group.close_from_test and
                (self.to_stage.id == self.stages[-1].id) and (not (self.task.stage.stage_type == StageType.TESTING))
        ):
            return StageNotify.CLOSE_FROM_TEST

    async def to_dev(self) -> str | None:
        if self.to_stage.stage_type == StageType.DEVELOP:
            # Check has executor
            if not (self.roles.executor and self.roles.executor.user.bit_user_id != self.self_bitrix_id):
                return StageNotify.RESPONSIBLE_NONE

            # # Check allocated_time
            # if not (self.task.allocated_time and self.task.allocated_time >= 60):
            #     return StageNotify.ALLOCATED_TIME_NONE

            # Check to Stage
            if not (
                    self.task.stage.in_queue or
                    self.task.stage.stage_type in (StageType.TESTING, StageType.ERROR, StageType.WAIT)
            ):
                return StageNotify.TO_DEV_ERROR.format(from_stage=self.task.stage.title)

    async def to_error(self) -> str | None:
        if self.to_stage.stage_type == StageType.ERROR and self.task.stage.stage_type != StageType.TESTING:
            return StageNotify.TO_ERROR

    async def fifo_queue(self) -> str | None:
        if self.to_stage.stage_type != StageType.FIFO:
            return

        if self.task.group.max_active_tasks:
            check_user = self.roles.manager or self.roles.creator

            user_tasks_in_queue = await self.db.get_tasks_with(
                stage_ids=[self.to_stage.id],
                user_id=check_user.user_id,
                role=TaskRole.MANAGER if self.roles.manager else TaskRole.CREATOR
            )
            if len(user_tasks_in_queue) >= self.task.group.max_active_tasks:
                return StageNotify.CREATOR_FULL.format(name=check_user.user.full_name)

        self.task.queue_date = datetime.now()
        await self.db.update_task(self.task)
