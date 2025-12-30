import asyncio
from logging import ERROR
from datetime import datetime, timedelta

from .base import BaseBitSync
from .task_check import TaskSync
from .utils import calc_work_hours
from .status_checks import StatusCheck
from src.static.message_answers import TaskNFY
from src.bot.structures.keyboards import test_answer_ikb

from src.classes.cls_const import StageType

from src.i18n.i18n import translator


class BitSync(TaskSync, BaseBitSync):

    @staticmethod
    async def sleep_until(target_hour, target_minute=0):
        now = datetime.now()
        target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

        if now >= target_time:
            target_time += timedelta(days=1)

        sleep_duration = (target_time - now).total_seconds()
        await asyncio.sleep(sleep_duration)

    async def schedule_sync(self, run_hour: int, run_minute: int = 0, chat_id: int | str = None):
        while True:
            await self.sync_all()
            if chat_id:
                await self.notify_manager.notify(TaskNFY.BIT_SYNC, tg_ids=[chat_id])

            await self.sleep_until(run_hour, run_minute)

    async def notify_testing(self, test_before, periodicity):
        while True:
            now = datetime.now()
            if now.hour > 18:
                await self.sleep_until(target_hour=9)

            try:
                test_stages = await self.db.get_task_stage(stage_type=StageType.TESTING)
                test_stages = [i.id for i in test_stages if i.group.ban_hours]
                if not test_stages:
                    continue

                tasks = await self.db.get_tasks_with(test_stages)

                for task in tasks:
                    try:
                        if task.unlimited_test or task.closed_date or not (task.stage.stage_type == StageType.TESTING):
                            continue

                        if task.test_date and (now - task.test_date) < timedelta(seconds=test_before):
                            continue

                        roles = self.db.sort_task_roles(task.task_users)
                        tg_ids = [i.user.tg_id for i in (roles.creator, roles.manager) if i and i.user.tg_id]
                        await self.notify_task_users(
                            message=TaskNFY.CHECK_TASK, task=task,
                            roles=roles, tg_ids=tg_ids,
                            kb=test_answer_ikb(task.id, language=translator.default_language)
                        )
                    except Exception as e:
                        await self.logger.send_log(
                            ERROR, f"BitSync -> notify_testing task: {task.bit_task_id}", e=e
                        )

            except Exception as e:
                await self.logger.send_log(ERROR, "BitSync -> notify_testing", e=e)

            finally:
                await asyncio.sleep(periodicity)

    async def sync_tasks(self, check_time: int = 3600, error_sleep: int = 30):
        """
        Background recheck of tasks
        :param check_time: time (seconds) for which the tasks will be checked
        :param error_sleep: time (seconds) sleep if check error
        """
        while True:
            try:
                groups = await self.db.get_task_group()
                check_stages = []
                for group in groups:
                    stages = await self.db.get_task_stage(group_id=group.id)
                    check_stages += stages[:-1]  # skip closed tasks
                tasks = await self.db.get_tasks_with(stage_ids=[i.id for i in check_stages])

                if not tasks:
                    await asyncio.sleep(error_sleep)
                    continue

                sleep_sec = check_time / len(tasks)
                for task in tasks:
                    start = datetime.now()
                    try:
                        await self.on_task_update(task.bit_task_id)
                        sleep_now = sleep_sec - (datetime.now() - start).total_seconds()
                        if sleep_now > 0:
                            await asyncio.sleep(sleep_now)

                    except Exception as e:
                        await self.logger.send_log(
                            ERROR, f"BitSync -> sync_tasks task: {task.id} bit_id={task.bit_task_id}", e=e
                        )
                        await asyncio.sleep(error_sleep)

            except Exception as e:
                await self.logger.send_log(ERROR, "BitSync -> sync_tasks", e=e)

    async def auto_acceptance_tasks(self, weekends: list[int], start_wh, end_wh, periodicity: int = 3600) -> None:
        """Auto-acceptance of tasks that are in testing"""
        while True:
            try:
                groups = await self.db.get_task_group()
                for group in groups:
                    if not group.auto_acceptance:
                        continue

                    stages = await self.db.get_task_stage(group_id=group.id)
                    test_stages = [s for s in stages if s.stage_type == StageType.TESTING]
                    if not test_stages:
                        continue

                    tasks = await self.db.get_tasks_with(stage_ids=[i.id for i in test_stages])
                    for task in tasks:
                        try:
                            if task.unlimited_test:
                                continue

                            hours = calc_work_hours(task.test_date, datetime.now(), weekends, start_wh, end_wh)
                            if hours > group.auto_acceptance:
                                task.stage_id = stages[-1].id
                                task.closed_date = datetime.now()

                                msg = TaskNFY.AUTO_ACCEPTANCE.format(time=task.test_date.strftime('%Y.%m.%d %H:%M'))
                                await self.db.update_task(task)
                                await self.bitrix.update_task(task.bit_task_id, bit_stage_id=stages[-1].bit_stage_id)
                                await self.notify_task_users(msg, task=task)

                                try:
                                    comment_bit_id = await self.bitrix.add_comment(task.bit_task_id, msg)
                                    await self.db.add_comment(task_id=task.id, bit_comment_id=comment_bit_id, text=msg)
                                except Exception as e:
                                    await self.logger.send_log(ERROR, f"BitSync -> auto_acceptance add comment", e=e)

                                if group.ban_hours:
                                    roles = self.db.sort_task_roles(task.task_users)
                                    st = StatusCheck(
                                        self.db, task, roles.creator.user, roles, stages, stages[-1],
                                        self.bitrix.conf.data.current_id
                                    )
                                    await st.ban_accept()

                        except Exception as e:
                            await self.logger.send_log(ERROR, f"BitSync -> auto_acceptance_tasks id: {task.id}", e=e)

            except Exception as e:
                await self.logger.send_log(ERROR, "BitSync -> auto_acceptance_tasks", e=e)

            finally:
                await asyncio.sleep(periodicity)

    async def sync_all(self):
        await self.sync_users()
        await self.sync_departments()
        await self.sync_departments_users()
        await self.sync_groups()
        await self.sync_stages()
