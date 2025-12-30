import asyncio
from logging import ERROR
from functools import wraps
from datetime import datetime
from typing import Iterable, Sequence, Callable

from aiogram import Bot

from .base import BaseBitSync
from .task_update import UpdateTask

from src.db.database import TaskUserRoles
from src.db.models import File, Task, TaskGroup, User, Stage
from src.utils.utils import get_file_id, send_documents
from src.classes.cls_const import TaskRole, FileTypeConst, StageType, UserGroupRole
from src.classes.models.notfiy_manager import NotifyManager
from src.static.bit_static import task_comment_filter
from src.static.message_answers import MyTaskANS, TaskNFY, StageNotify, DONT_CHOOSE_ANS, MANAGER_TEXT, change_tag

from src.bot.structures.keyboards import comment_answer_ikb

from src.i18n.i18n import translator


def keyed_lock(get_key: Callable[..., int | str]):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            key = get_key(self, *args, **kwargs)
            lock = self.locks.setdefault(key, asyncio.Lock())
            try:
                async with lock:
                    return await func(self, *args, **kwargs)
            finally:
                if not lock.locked() and self.locks.get(key) is lock:
                    self.locks.pop(key, None)

        return wrapper
    return decorator


class TaskSync(BaseBitSync):
    notify_manager: NotifyManager = None
    bot: Bot = None
    log_chat_id:  str | int = None
    skip_tasks: dict[int, int] = {}
    check_through = 5
    locks = {}

    def add_skip_task(self, task_bit_id) -> None:
        if len(self.skip_tasks) > 100:
            self.skip_tasks = dict(list(self.skip_tasks.items())[-25:])
        self.skip_tasks[task_bit_id] = 1

    def get_skip_task(self, task_bit_id) -> bool:
        """
        Tasks that are in "skip_tasks" can be rechecked via "check_through"
        :param task_bit_id:
        :return: True if you want to skip checking the task, False can be checked
        """
        miss_num_task = self.skip_tasks.get(task_bit_id)
        if miss_num_task and miss_num_task < self.check_through:
            self.skip_tasks[task_bit_id] += 1
            return True

        elif miss_num_task and miss_num_task >= self.check_through:
            self.skip_tasks[task_bit_id] = 0
        return False

    def setup_task_sync(self, notify_manager: NotifyManager,  bot: Bot, log_chat_id: str | int):
        self.notify_manager = notify_manager
        self.bot = bot
        self.log_chat_id = log_chat_id

    async def notify_task_users(
            self, message: str, task: Task,
            tg_ids: Iterable[str | int] = None, roles: TaskUserRoles = None, kb=None, title: bool = True
    ) -> None:
        """
        Send notify to send_tg_ids
        tg_ids: if not, send to all users who have the task.
        roles: If you have already received roles from the database,
        you can transfer them so as not to request them again.
        """
        if message:
            if not isinstance(roles, TaskUserRoles):
                task_users = await self.db.get_task_user(task_id=task.id)
                roles = self.db.sort_task_roles(task_users=task_users)

            if not tg_ids:
                tg_ids = {i.user.tg_id for i in task.task_users if i and i.user.tg_id}

            if title:
                notify = TaskNFY.TASK.format(
                    bit_id=task.bit_task_id,
                    task_name=task.title.translate(change_tag),
                    creator=roles.creator.user.full_name if roles.creator else DONT_CHOOSE_ANS,
                    developer=roles.executor.user.full_name if roles.executor else DONT_CHOOSE_ANS,
                    manager=roles.manager.user.full_name if roles.manager else DONT_CHOOSE_ANS,
                    observers=MyTaskANS.OBSERVERS_JOIN.join([task_user.user.full_name for task_user in roles.observers]),
                    group=task.group.title,
                    stage=task.stage.title if task.stage else None
                ) + message

            else:
                notify = message

            if self.notify_manager:
                await self.notify_manager.notify(msg=notify, tg_ids=tg_ids, kb=kb)

    async def on_task_update(self, task_bit_id: int) -> None:
        task_in_db = await self.db.get_task(task_bit_id=task_bit_id)
        if not task_in_db:
            await self.on_task_add(task_bit_id=task_bit_id)
            return

        task_in_db = task_in_db[0]
        task_in_bitrix = await self.bitrix.get_task(task_id=task_bit_id)

        if not task_in_bitrix:
            raise Exception(f"Can't get task {task_bit_id} from bitrix")

        updater = UpdateTask(task_in_bitrix, task_in_db, self)
        messages = await updater.update()

        for msg in messages:
            if msg.file and msg.file_type == "photo":
                await self.notify_manager.send_photo(msg.file, msg.message, tg_ids=msg.notify_users)

            else:
                await self.notify_task_users(
                    msg.message, task_in_db, msg.notify_users, updater.task_users_role, kb=msg.kb, title=msg.task_title
                )

    @keyed_lock(lambda self, task_bit_id: task_bit_id)
    async def on_task_add(self, task_bit_id: int):
        if self.get_skip_task(task_bit_id):
            return

        task_exist = await self.db.get_task(task_bit_id=task_bit_id)
        task_in_bitrix = await self.bitrix.get_task(task_id=task_bit_id)  # if access denied we not get task
        task_bit_group_id = int(task_in_bitrix.get("groupId", 0)) if task_in_bitrix else 0
        task_group_db = await self.db.get_task_group(bit_group_id=task_bit_group_id) if task_bit_group_id else 0
        if task_exist or (not task_in_bitrix) or (not task_bit_group_id) or (not task_group_db):
            self.add_skip_task(task_bit_id)
            return
        elif task_bit_id in self.skip_tasks:
            del self.skip_tasks[task_bit_id]

        task_group_db = task_group_db[0]
        stages = await self.db.get_task_stage(group_id=task_group_db.id)

        # find creator
        task_creator_bit_id = int(task_in_bitrix.get("createdBy"))
        task_creator_db = await self.db.get_user(bit_id=task_creator_bit_id)
        if not task_creator_db:
            await self.sync_users()
            task_creator_db = await self.db.get_user(bit_id=task_creator_bit_id)

        task_creator_db = task_creator_db[0]

        if not await self.can_crate(task_bit_id, task_group_db, stages, task_creator_db, task_in_bitrix.get("title")):
            return

        # Take a place in the database to get Task id
        task_in_db = Task(
            bit_task_id=task_bit_id,
            bit_chat_id=int(task_in_bitrix.get("chatId")),
            title=task_in_bitrix.get("title"),
            description=task_in_bitrix.get("description", "None"),
            created_date=datetime.now(),
            group_id=task_group_db.id,
            stage_id=stages[0].id  # set first stage
        )
        task_in_db = await self.db.add_task(task_in_db)

        # Error creating task
        if not task_in_db:
            return

        # create folder
        project_folder = await self.bitrix.create_folder(
            target_id=task_group_db.bit_folder_id, name=f"{task_in_db.id}_{task_in_db.title}"
        )

        await self.db.add_task_user(user_id=task_creator_db.id, task_id=task_in_db.id, role=TaskRole.CREATOR)

        # find responsible/developer/executor
        task_executor_bit_id = int(task_in_bitrix.get("responsibleId"))
        task_executor_db = await self.db.get_user(bit_id=task_executor_bit_id)
        if not task_creator_db:
            await self.sync_users()
            task_executor_db = await self.db.get_user(bit_id=task_executor_bit_id)

        task_executor_db = task_executor_db[0]
        await self.db.add_task_user(user_id=task_executor_db.id, task_id=task_in_db.id, role=TaskRole.EXECUTOR)

        bit_id_observers = set()
        manager, observers, _ = await self.get_manager_and_observers(task_in_db, task_creator_db)
        await self.db.add_task_user(user_id=manager.id, task_id=task_in_db.id, role=TaskRole.MANAGER)

        for observer in observers.values():
            await self.db.add_task_user(user_id=observer.id, task_id=task_in_db.id, role=TaskRole.OBSERVER)
            if observer.bit_user_id:
                bit_id_observers.add(observer.bit_user_id)

        if bit_id_observers:
            await self.bitrix.update_task(
                task_id=task_bit_id,
                description=f"{MANAGER_TEXT}{manager.full_name}\n{task_in_bitrix.get('description', '')}",
                auditors=list(bit_id_observers)
            )

        task_in_db.bit_folder_id = project_folder
        task_in_db = await self.db.update_task(task_in_db)

        # sync files
        files = await self.bitrix.get_task_files(task_id=task_bit_id)
        if self.bot and files and self.log_chat_id:
            for file_in_bit in files:
                try:
                    file = await self.bitrix.download_file(download_url=file_in_bit.get("DOWNLOAD_URL"))
                    file_in_tg = await get_file_id(
                        bot=self.bot, chat_id=self.log_chat_id, file=file, file_name=file_in_bit.get("NAME")
                    )
                    file_in_db = File(
                        task_id=task_in_db.id,
                        user_id=task_creator_db.id,
                        tg_file_id=file_in_tg,
                        bit_file_id=int(file_in_bit.get("FILE_ID")),
                        name=file_in_bit.get("NAME"),
                        type=FileTypeConst.DOCUMENT
                    )
                    await self.db.add_file(file_in_db)
                except Exception as e:
                    await self.logger.send_log(ERROR, "TaskSync -> on_task_add", e=e, msg="Add file error")

        # check other updates (check stages)
        await self.notify_task_users(TaskNFY.NEW_TASK, task_in_db)
        await self.on_task_update(task_bit_id=task_bit_id)

    async def on_task_comment_add(self, task_bit_id: int, message_bit_id: int) -> None:
        """return: if comment have file return {file_name: file_id}"""
        comment_in_db = await self.db.get_comment(bit_comment_id=message_bit_id)
        if comment_in_db:
            return

        task_in_db = await self.db.get_task(task_bit_id=task_bit_id)
        if not task_in_db:
            await self.on_task_add(task_bit_id=task_bit_id)

            task_in_db = await self.db.get_task(task_bit_id=task_bit_id)
            if not task_in_db:
                return

        comment_info = await self.bitrix.get_comment_fix(chat_id=task_in_db[0].bit_chat_id, message_id=message_bit_id)
        if not comment_info and comment_info.get("messages"):
            return

        all_files = comment_info["files"]
        comment_msg = comment_info["messages"][0]
        message_files = comment_msg["params"].get("FILE_ID", []) if comment_msg["params"] else []
        for filter_msg in task_comment_filter:  # skip if comment have filtered message
            if filter_msg.lower() in comment_msg["text"].lower():
                return

        user = await self.db.get_user(bit_id=int(comment_msg["author_id"]))
        if not user:
            await self.sync_users()
            user = await self.db.get_user(bit_id=int(comment_msg["author_id"]))

        files = {}
        if message_files:
            for file_info in all_files:
                if file_info["id"] in message_files:
                    files[file_info.get("name")] = [file_info.get("id"), file_info.get("urlDownload")]

        comment_in_db = await self.db.get_comment(bit_comment_id=message_bit_id)
        if comment_in_db:
            return

        add_comment = await self.db.add_comment(
            task_id=task_in_db[0].id,
            user_id=user[0].id,
            bit_comment_id=message_bit_id,
            text=MyTaskANS.COMMENT_FILE_TXT + comment_msg["text"] if files else comment_msg["text"],
        )

        tg_ids = []
        task_users_name: dict = {"observers": []}
        for task_user in task_in_db[0].task_users:
            if task_user.user.tg_id:
                tg_ids.append(task_user.user.tg_id)

            if task_user.role == TaskRole.CREATOR:
                task_users_name["creator"] = task_user.user.full_name
            elif task_user.role == TaskRole.EXECUTOR:
                task_users_name["developer"] = task_user.user.full_name
            elif task_user.role == TaskRole.OBSERVER:
                task_users_name["observers"].append(task_user.user.full_name)

        notify = TaskNFY.TASK.format(
            bit_id=task_in_db[0].bit_task_id,
            task_name=task_in_db[0].title.translate(change_tag),
            creator=task_users_name.get("creator"),
            developer=task_users_name.get("developer"),
            manager=task_users_name.get("manager"),
            observers=MyTaskANS.OBSERVERS_JOIN.join(task_users_name.get("observers")),
            group=task_in_db[0].group.title,
            stage=task_in_db[0].stage.title if task_in_db[0].stage else None,
        )

        comment_bot_msg = TaskNFY.ADD_COMMENT.format(
            author=user[0].full_name,
            text=comment_msg["text"].translate(change_tag)
        )
        notify += f"{comment_bot_msg}\n{MyTaskANS.COMMENT_FILE_TXT if files else ''}"

        tg_document_ids = []
        for file_name, file_bit_info in files.items():
            try:
                file = await self.bitrix.download_file(file_bit_id=file_bit_info[0])  # urlDownload is not working properly
                tg_file_id = await get_file_id(
                    bot=self.bot, chat_id=self.log_chat_id, file=file, file_name=file_name
                )
                tg_document_ids.append(tg_file_id)

                description = MyTaskANS.COMMENT_LIST_INFO.format(
                    name=user[0].full_name,
                    time=datetime.now().strftime("%Y.%m.%d %H:%M"),
                    text=comment_bot_msg
                )

                db_file = File(
                    task_id=task_in_db[0].id,
                    comment_id=add_comment.id,
                    user_id=user[0].id,
                    tg_file_id=tg_file_id,
                    bit_file_id=int(file_bit_info[0]),
                    name=file_name,
                    description=description,
                    type=FileTypeConst.DOCUMENT,
                )

                await self.db.add_file(db_file)

            except Exception as e:
                await self.logger.send_log(ERROR, "TaskSync -> on_task_comment_add -> sync files", e)

        # send notify
        if self.notify_manager:
            tg_ids = [i.user.tg_id for i in task_in_db[0].task_users if i.user.tg_id]

            complete_bt = True if task_in_db[0].stage.stage_type == StageType.TESTING else False
            kb = comment_answer_ikb(task_in_db[0].id, translator.default_language, complete_bt)
            if tg_document_ids:
                await send_documents(
                    documents_file_info=[tg_document_ids, notify], bot=self.bot, targets=tg_ids, kb=kb
                )
            else:
                await self.notify_manager.notify(msg=notify, tg_ids=tg_ids, kb=kb)


    async def can_crate(
            self, task_bit_id: int, group: TaskGroup, stages: Sequence[Stage], creator: User, title: str
    ) -> bool:
        if not group.max_active_tasks:
            return True

        tasks = await self.db.get_tasks_with(
            [i.id for i in stages[:-1]],
            user_id=creator.id,
            role=TaskRole.CREATOR,
        )
        max_tasks = creator.max_active_tasks or group.max_active_tasks
        if len(tasks) < max_tasks:
            return True

        else:
            await self.bitrix.delete_task(task_bit_id)

            if creator.tg_id:
                await self.notify_manager.notify(
                    StageNotify.MAX_ACTIVE_TASKS.format(task=title, group=group.title, num=max_tasks),
                    [creator.tg_id]
                )

            return False

    async def get_manager_and_observers(self, task: Task, creator: User) -> tuple[User, dict[int, User], bool]:
        manager = None
        observers: dict = {}
        newer_manager = set()
        newer_observer = set()
        without_manager = False

        group_user_rules = await self.db.get_user_group_rules(group_id=task.group.id)
        for r in group_user_rules:
            if (manager is None) and (r.manager == UserGroupRole.ALLWAYS):
                manager = r.user
                observers[r.user.id] = r.user

            elif r.manager == UserGroupRole.NEWER:
                newer_manager.add(r.user_id)

            if r.observer == UserGroupRole.ALLWAYS:
                observers[r.user.id] = r.user

            elif r.observer == UserGroupRole.NEWER:
                newer_observer.add(r.user_id)

        if (not manager) and (await self.db.get_dep_users(user_id=creator.id, head=True)):
            manager = creator

        for manager_user in await self.db.get_managers(creator.id):
            if (manager is None) and (manager_user.id not in newer_manager):
                manager = manager_user
                observers[manager_user.id] = manager_user
                await self.db.add_task_user(user_id=manager_user.id, task_id=task.id, role=TaskRole.MANAGER)

            elif manager_user.id not in newer_observer:
                observers[manager_user.id] = manager_user
                await self.db.add_task_user(user_id=manager_user.id, task_id=task.id, role=TaskRole.OBSERVER)

        if manager is None:
            manager = creator
            if not newer_manager:
                without_manager = True

        return manager, observers, without_manager
