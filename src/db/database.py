import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence, Optional

from sqlalchemy import inspect, select, update, func, and_
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.sql import ColumnElement
from sqlalchemy.orm import selectinload

from .models import Base, User, Task, TaskUser, File, TaskGroup, Stage, Comment, Department, DepartmentUser, Role, \
    UserRole, UserGroupRules, Region
from src.classes.cls_const import TaskRole, StageType


@dataclass()
class TaskUserRoles:
    creator: TaskUser = None
    executor: TaskUser = None
    manager: TaskUser = None
    co_executors: list[TaskUser] = None
    observers: list[TaskUser] = None


class BitrixDB:
    def __init__(self, url: str, echo: bool = False, logger: logging.Logger = None) -> None:
        self.engine = create_async_engine(url=url, echo=echo)
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False
        )
        if logger:
            self.add_sqlalchemy_logging(logger)

    @staticmethod
    def add_sqlalchemy_logging(logger: logging.Logger):
        logging.getLogger('sqlalchemy.engine').handlers.clear()  # Clear existing handlers
        logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
        logging.getLogger('sqlalchemy.engine').addHandler(logger.handlers[0])

    async def create_tables(self):
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def check_tables(self):
        async with self.engine.begin() as connection:
            def sync_check_tables(conn):
                inspector = inspect(conn)
                tables = inspector.get_table_names()
                return len(tables) > 0

            return await connection.run_sync(sync_check_tables)

    async def select_info(self, info: Base | ColumnElement):
        async with self.session_factory() as session:
            query = select(info)
            try:
                result = await session.execute(query)
                return result.scalars().unique().all()
            except Exception as e:
                print(e)  # LOG

    async def delete_info(self, selected_model, id_: int) -> bool:
        async with self.session_factory() as session:
            try:
                async with session.begin():
                    result = await session.execute(select(selected_model).filter(selected_model.id == id_))
                    ex = result.unique().scalar_one_or_none()

                    if ex:
                        await session.delete(ex)
                    else:
                        return False

                await session.commit()
                return True

            except Exception as e:
                print(e)  # LOG
                return False

    async def add_user(self, full_name: str, access_level: str, tg_id: int = None, bit_user_id: int = None,
                       job_title: str = None, phone: str = None, language: str = None) -> Optional[User]:
        async with self.session_factory() as session:
            user = User(
                tg_id=tg_id,
                bit_user_id=bit_user_id,
                full_name=full_name,
                job_title=job_title,
                phone=phone,
                language=language,
                access_level=access_level
            )
            try:
                async with session.begin():
                    session.add(user)
                await session.commit()
                await session.refresh(user)
                return user

            except Exception as e:
                print(e)  # LOG

    async def merge_users(self, to_user_id: int, from_user_id: int) -> User | None:
        async with self.session_factory() as session:
            try:
                async with session.begin():
                    from_user = await session.get(User, from_user_id)
                    to_user = await session.get(User, to_user_id)

                    if not from_user or not to_user:
                        raise ValueError("One of the users was not found.")

                    to_user.full_name = from_user.full_name

                    # Обновить связи
                    await session.execute(
                        update(DepartmentUser).where(DepartmentUser.user_id == from_user_id).values(user_id=to_user_id)
                    )
                    await session.execute(
                        update(TaskUser).where(TaskUser.user_id == from_user_id).values(user_id=to_user_id)
                    )
                    await session.execute(
                        update(Comment).where(Comment.user_id == from_user_id).values(user_id=to_user_id)
                    )
                    await session.execute(
                        update(File).where(File.user_id == from_user_id).values(user_id=to_user_id)
                    )

                    await session.delete(from_user)

                await session.commit()
                await session.refresh(to_user)
                return to_user

            except Exception as e:
                print(e)  # LOG
                await session.rollback()

    async def get_user(self, id_: int = None, tg_id: int = None, bit_id: int = None) -> Sequence[User] | None:
        """Returns the user, if no arguments are passed then returns all users"""
        async with self.session_factory() as session:
            query = select(User)

            if id_:
                query = query.filter(User.id == id_)
            elif tg_id:
                query = query.filter(User.tg_id == tg_id)

            elif bit_id:
                query = query.filter(User.bit_user_id == bit_id)

            try:
                result = await session.execute(query)
                return result.scalars().unique().all()  # noqa
            except Exception as e:
                print(e)  # LOG

    async def get_users(
            self, with_tg_id: bool = None, with_bit_id: bool = None
    ) -> Sequence[User]:
        async with self.session_factory() as session:
            query = select(User)

            if with_tg_id is not None:
                if with_tg_id:
                    query = query.where(User.tg_id.is_not(None))
                else:
                    query = query.where(User.tg_id.is_(None))

            if with_bit_id is not None:
                if with_bit_id:
                    query = query.where(User.bit_user_id.is_not(None))
                else:
                    query = query.where(User.bit_user_id.is_(None))

            query = query.order_by(User.full_name)

            try:
                result = await session.execute(query)
                return result.scalars().unique().all()  # noqa
            except Exception as e:
                print(e)  # LOG

    async def update_user(self, update_to: User, tg_id: int = None) -> Optional[User]:
        """Updates a user with the given user_id or tg_id"""
        async with self.session_factory() as session:
            query = select(User)
            if tg_id:
                query = query.filter(User.tg_id == tg_id)

            elif update_to.id:
                query = query.filter(User.id == update_to.id)

            else:
                return

            result = await session.execute(query)
            user = result.unique().scalar_one_or_none()

            if not user:
                return

            user.tg_id = update_to.tg_id or user.tg_id

            user.bit_user_id = None if (update_to.bit_user_id == 0) or (user.bit_user_id == 0) \
                else update_to.bit_user_id or user.bit_user_id

            user.full_name = update_to.full_name or user.full_name
            user.job_title = update_to.job_title or user.job_title
            user.phone = update_to.phone or user.phone
            user.access_level = update_to.access_level or user.access_level
            user.ban_time = update_to.ban_time or user.ban_time
            user.language = update_to.language or user.language

            # set Role with name "Заказчик"
            role_result = await session.execute(select(Role).where(Role.name == "Заказчик"))
            role = role_result.unique().scalar_one_or_none()
            if role:
                user.role_id = role.id

            await session.commit()
            return user

    async def add_department(self, bit_dep_id: int, name: str, parent_id: int = None) -> Optional[Department]:
        async with self.session_factory() as session:
            department = Department(
                bit_dep_id=bit_dep_id,
                name=name,
                parent_id=parent_id
            )
            try:
                async with session.begin():
                    session.add(department)
                await session.commit()
                await session.refresh(department)
                return department

            except Exception as e:
                print(e)  # LOG

    async def get_department(
            self, id_: int = None, bit_dep_id: int = None, parent: int = None, bit_filter: bool = None
    ) -> Sequence[Department]:
        """
        bit_filter if True returns all departments with have bitrix id.
        elif False returns all departments with no bitrix id
        """
        async with self.session_factory() as session:
            query = select(Department)

            if id_:
                query = query.filter(Department.id == id_)

            elif bit_dep_id:
                query = query.filter(Department.bit_dep_id == bit_dep_id)

            elif parent:
                query = query.filter(Department.parent_id == parent)

            if bit_filter is not None:
                if bit_filter:
                    query = query.where(Department.bit_dep_id.is_not(None))
                else:
                    query = query.where(Department.bit_dep_id.is_(None))

            try:
                result = await session.execute(query)
                return result.scalars().unique().all()
            except Exception as e:
                print(e)  # LOG

    async def update_department(self, department: Department) -> Department | None:
        async with self.session_factory() as session:
            try:
                async with session.begin():
                    result = await session.execute(select(Department).filter_by(id=department.id))
                    ex: Department = result.unique().scalar_one_or_none()

                    if ex:
                        ex.name = department.name
                        ex.parent_id = department.parent_id
                    else:
                        return None

                await session.commit()
                await session.refresh(ex)
                return ex

            except Exception as e:
                print(e)  # LOG
                return None

    async def add_dep_user(self, user_id: int, head: bool, department_id: int) -> DepartmentUser:
        async with self.session_factory() as session:
            department_user = DepartmentUser(
                user_id=user_id,
                head=head,
                department_id=department_id
            )
            try:
                async with session.begin():
                    session.add(department_user)
                await session.commit()
                await session.refresh(department_user)
                return department_user

            except Exception as e:
                print(e)  # LOG

    async def get_dep_users(
            self, id_: int = None, user_id: int = None, head: bool = None, department_id: int = None
    ) -> Sequence[DepartmentUser]:
        async with self.session_factory() as session:
            query = select(DepartmentUser)
            if id_:
                query = query.filter(DepartmentUser.id == id_)
            elif user_id:
                query = query.filter(DepartmentUser.user_id == user_id)

            elif department_id:
                query = query.filter(DepartmentUser.department_id == department_id)

            if isinstance(head, bool):
                query = query.filter(DepartmentUser.head.is_(head))

            try:
                result = await session.execute(query)
                return result.scalars().unique().all()
            except Exception as e:
                print(e)  # LOG

    async def get_managers(self, user_id: int) -> list[User]:
        result = []

        for department_employee in await self.get_dep_users(user_id=user_id):
            # if its manager
            if department_employee.head:
                department = await self.get_department(id_=department_employee.department_id)
                if department[0].parent_id:
                    managers = await self.get_dep_users(department_id=department[0].parent_id, head=True)
                    result += managers
            else:
                managers = await self.get_dep_users(
                    department_id=department_employee.department_id, head=True
                )
                result += managers

        unique_managers = {manager.user.id: manager.user for manager in result}
        return list(unique_managers.values())

    async def add_task_group(self, bit_group_id: int, bit_folder_id: int, title: str) -> Optional[TaskGroup]:
        async with self.session_factory() as session:
            group = TaskGroup(
                bit_group_id=bit_group_id,
                bit_folder_id=bit_folder_id,
                title=title
            )
            try:
                async with session.begin():
                    session.add(group)
                await session.commit()
                await session.refresh(group)
                return group

            except Exception as e:
                print(e)  # LOG

    async def get_task_group(
            self, id_: int = None, bit_group_id: int = None, title: str = None,
            notify: bool = None, analytics: bool = None
    ) -> Sequence[TaskGroup] | None:
        async with self.session_factory() as session:
            query = select(TaskGroup)

            if id_:
                query = query.filter(TaskGroup.id == id_)
            elif bit_group_id:
                query = query.filter(TaskGroup.bit_group_id == bit_group_id)
            elif title:
                query = query.filter(TaskGroup.title == title)

            if isinstance(notify, bool):
                query = query.filter(TaskGroup.notify.is_(notify))

            if isinstance(analytics, bool):
                query = query.filter(TaskGroup.analytics.is_(analytics))

            try:
                result = await session.execute(query)
                return result.scalars().unique().all()
            except Exception as e:
                print(e)  # LOG

    async def update_task_group(self, group: TaskGroup) -> TaskGroup | None:
        async with self.session_factory() as session:
            try:
                async with session.begin():
                    result = await session.execute(select(TaskGroup).filter_by(id=group.id))
                    existing_group: TaskGroup = result.unique().scalar_one_or_none()

                    if existing_group:
                        existing_group.title = group.title
                        existing_group.max_executor_task = group.max_executor_task
                        existing_group.close_from_test = group.close_from_test

                    else:
                        print(f"Task with id {group.id} not found")  # LOG
                        return None

                await session.commit()
                await session.refresh(existing_group)
                return existing_group

            except Exception as e:
                print(e)  # LOG
                return None

    async def get_regions(self, group_id: int = None, name: str = None) -> list[Region]:
        async with self.session_factory() as session:
            query = select(Region)
            if group_id:
                query = query.filter(Region.task_group_id == group_id)
            if name:
                query = query.filter(Region.name == name)
            try:
                result = await session.execute(query)
                return result.scalars().unique().all()
            except Exception as e:
                print(e)  # LOG

    async def add_task_stage(self, group_id: int, bit_stage_id: int, bit_sort: int, title: str) -> Optional[Stage]:
        async with self.session_factory() as session:
            stage = Stage(
                group_id=group_id,
                bit_stage_id=bit_stage_id,
                sort=bit_sort,
                title=title
            )
            try:
                async with session.begin():
                    session.add(stage)
                await session.commit()
                await session.refresh(stage)
                return stage

            except Exception as e:
                print(e)  # LOG

    async def get_task_stage(
            self, id_: int = None, group_id: int = None, bit_stage_id: int = None, title: str = None,
            stage_type: str = None
    ) -> Sequence[Stage]:
        async with self.session_factory() as session:
            query = select(Stage)
            if id_:
                query = query.filter(Stage.id == id_)
            elif bit_stage_id:
                query = query.filter(Stage.bit_stage_id == bit_stage_id)
            elif title:
                query = query.filter(Stage.title == title)
            elif group_id:
                query = query.filter(Stage.group_id == group_id)
            else:
                query = query.order_by(Stage.group_id)

            if isinstance(stage_type, str):
                query = query.filter(Stage.stage_type == stage_type)

            query = query.order_by(Stage.sort)

            try:
                result = await session.execute(query)
                return result.scalars().unique().all()
            except Exception as e:
                print(e)  # LOG

    async def update_task_stage(self, task_stage: Stage) -> Stage | None:
        async with self.session_factory() as session:
            try:
                async with session.begin():
                    result = await session.execute(select(Stage).filter_by(id=task_stage.id))
                    ex: Stage = result.unique().scalar_one_or_none()

                    if ex:
                        ex.sort = task_stage.sort
                        ex.title = task_stage.title
                    else:
                        return None

                await session.commit()
                await session.refresh(ex)
                return ex

            except Exception as e:
                print(e)  # LOG
                return None

    async def get_stage_task_counts(self, stage_ids: list[int]) -> int:
        async with self.session_factory() as session:
            query = select(func.count(Task.id)).where(Task.stage_id.in_(stage_ids))

            try:
                result = await session.execute(query)
                count = result.scalar()
                return count
            except Exception as e:
                print(e)  # LOG

    async def get_tasks_with(
            self, stage_ids: list[int], user_id: Optional[int] = None, role: Optional[str] = None
    ) -> Sequence[Task]:

        async with self.session_factory() as session:
            query = select(Task).join(Task.task_users)

            # Apply stage_id filter
            if stage_ids:
                query = query.where(Task.stage_id.in_(stage_ids))

            # Apply user_id and role filter
            if user_id and role:
                query = query.where(and_(TaskUser.user_id == user_id, TaskUser.role == role))
            elif user_id:
                query = query.where(TaskUser.user_id == user_id)
            elif role:
                query = query.where(TaskUser.role == role)

            query = query.order_by(Task.stage_id)

            try:
                result = await session.execute(query)
                tasks = result.scalars().unique().all()
                return tasks
            except Exception as e:
                print(e)  # LOG
                return []

    async def add_task(self, task: Task) -> Optional[Task]:
        async with self.session_factory() as session:
            try:
                async with session.begin():
                    session.add(task)
                await session.commit()
                await session.refresh(task)
                return task

            except Exception as e:
                print(e)  # LOG

    async def get_task(self, id_: int = None, task_bit_id: int = None) -> Sequence[Task] | None:
        async with self.session_factory() as session:
            query = select(Task)

            if id_:
                query = query.filter(Task.id == id_)
            elif task_bit_id:
                query = query.filter(Task.bit_task_id == task_bit_id)

            try:
                result = await session.execute(query)
                return result.scalars().unique().all()
            except Exception as e:
                print(e)  # LOG

    async def update_task(self, task: Task) -> Optional[Task]:
        async with self.session_factory() as session:
            try:
                async with session.begin():
                    result = await session.execute(select(Task).filter_by(id=task.id))
                    existing_task: Task = result.unique().scalar_one_or_none()

                    if existing_task:
                        existing_task.bit_task_id = task.bit_task_id
                        existing_task.bit_chat_id = task.bit_chat_id
                        existing_task.bit_folder_id = task.bit_folder_id
                        existing_task.title = task.title
                        existing_task.description = task.description
                        existing_task.created_date = task.created_date
                        existing_task.queue_date = task.queue_date
                        existing_task.deadline = task.deadline
                        existing_task.test_date = task.test_date
                        existing_task.group_id = task.group_id
                        existing_task.stage_id = task.stage_id
                        existing_task.closed_date = task.closed_date
                        existing_task.allocated_time = task.allocated_time
                        existing_task.unlimited_test = task.unlimited_test
                        existing_task.paid = task.paid
                    else:
                        print(f"Task with id {task.id} not found")  # LOG
                        return None

                await session.commit()
                await session.refresh(existing_task)
                return existing_task

            except Exception as e:
                print(e)  # LOG
                return None

    async def add_task_user(self, user_id: int, task_id: int, role: str) -> Optional[TaskUser]:
        async with self.session_factory() as session:
            task_user = TaskUser(
                user_id=user_id,
                task_id=task_id,
                role=role
            )
            try:
                async with session.begin():
                    session.add(task_user)
                await session.commit()
                await session.refresh(task_user)
                return task_user

            except Exception as e:
                print(e)  # LOG

    async def get_task_user(
            self, id_: int = None, user_id: int = None, task_id: int = None, role: str = None
    ) -> Sequence[TaskUser]:

        async with self.session_factory() as session:
            query = select(TaskUser)

            if id_:
                query = query.filter(TaskUser.id == id_)
            elif user_id:
                query = query.filter(TaskUser.user_id == user_id)

            elif task_id:
                query = query.filter(TaskUser.task_id == task_id)

            if role:
                query = query.filter(TaskUser.role == role)

            query = query.order_by(TaskUser.id)

            try:
                result = await session.execute(query)
                return result.scalars().unique().all()  # noqa
            except Exception as e:
                print(e)  # LOG

    @staticmethod
    def sort_task_roles(task_users: Sequence[TaskUser]) -> TaskUserRoles:
        creator = None
        executor = None
        manager = None
        co_executors = []
        observers = []

        for user in task_users:
            if user.role == TaskRole.CREATOR:
                creator = user

            elif user.role == TaskRole.EXECUTOR:
                executor = user

            elif user.role == TaskRole.CO_EXECUTOR:
                co_executors.append(user)

            elif user.role == TaskRole.OBSERVER:
                observers.append(user)

            elif user.role == TaskRole.MANAGER:
                manager = user

        return TaskUserRoles(
            creator=creator, executor=executor, manager=manager, co_executors=co_executors, observers=observers
        )

    async def update_task_user(self, task_user: TaskUser) -> Optional[TaskUser]:
        async with self.session_factory() as session:
            try:
                async with session.begin():
                    result = await session.execute(select(TaskUser).filter_by(id=task_user.id))
                    ex: TaskUser = result.unique().scalar_one_or_none()

                    if ex:
                        ex.user_id = task_user.user_id
                        ex.role = task_user.role

                    else:
                        return None

                await session.commit()
                await session.refresh(ex)
                return ex

            except Exception as e:
                print(e)  # LOG
                return None

    async def add_file(self, file: File) -> File:
        async with self.session_factory() as session:
            try:
                async with session.begin():
                    session.add(file)
                await session.commit()
                await session.refresh(file)
                return file

            except Exception as e:
                print(e)  # LOG

    async def get_files(self, task_id: int = None, file_name: str = None) -> Sequence[File]:
        async with self.session_factory() as session:
            query = select(File)
            if task_id:
                query = query.filter(File.task_id == task_id).order_by(File.id)

            if file_name:
                query = query.filter(File.name == file_name)

            try:
                result = await session.execute(query)
                return result.scalars().unique().all()
            except Exception as e:
                print(e)  # LOG

    async def add_comment(self, task_id: int, bit_comment_id: int, text: str, user_id: int = None) -> Comment:
        async with self.session_factory() as session:
            comment = Comment(
                user_id=user_id,
                task_id=task_id,
                bit_comment_id=bit_comment_id,
                created_date=datetime.now(),
                text=text)
            try:
                async with session.begin():
                    session.add(comment)
                await session.commit()
                await session.refresh(comment)
                return comment

            except Exception as e:
                print(e)  # LOG

    async def get_comment(self, task_id: int = None, bit_comment_id: int = None) -> Sequence[Comment]:
        async with self.session_factory() as session:
            if bit_comment_id:
                query = (
                    select(Comment).filter(Comment.bit_comment_id == bit_comment_id).options(selectinload(Comment.user))
                )
            else:
                query = (
                    select(Comment).filter(Comment.task_id == task_id).options(selectinload(Comment.user))
                )

            try:
                result = await session.execute(query.order_by(Comment.created_date))
                return result.scalars().unique().all()
            except Exception as e:
                print(e)  # LOG

    async def get_role(
            self, id_: int = None, name: str = None, notify_queue: bool = None, change_any: bool = None
    ) -> Role:
        async with self.session_factory() as session:
            if id_:
                query = select(Role).filter(Role.id == id_)
            elif name:
                query = select(Role).filter(Role.name == name)
            else:
                query = select(Role)

            if isinstance(notify_queue, bool):
                query = query.filter(Role.notify_queue.is_(notify_queue))

            if isinstance(change_any, bool):
                query = query.filter(Role.change_any.is_(change_any))

            try:
                result = await session.execute(query)
                return result.unique().scalar_one_or_none()
            except Exception as e:
                print(e)  # LOG

    async def get_roles(
            self, notify_queue: bool = None, change_any: bool = None, join_users: bool = False
    ) -> Sequence[Role]:

        async with self.session_factory() as session:
            query = select(Role)

            if join_users:
                query = query.options(selectinload(Role.users))

            if isinstance(notify_queue, bool):
                query = query.filter(Role.notify_queue.is_(notify_queue))

            if isinstance(change_any, bool):
                query = query.filter(Role.change_any.is_(change_any))

            try:
                result = await session.execute(query)
                return result.scalars().unique().all()
            except Exception as e:
                print(e)  # LOG

    async def get_additional_roles(self, user_id: int) -> Sequence[UserRole] | None:
        async with self.session_factory() as session:
            query = select(UserRole).filter(UserRole.user_id == user_id)

            try:
                result = await session.execute(query)
                return result.scalars().unique().all()
            except Exception as e:
                print(e)  # LOG

    async def get_closed_tasks(self, start, end, group_id: int = None) -> Sequence[Task] | None:
        async with self.session_factory() as session:
            query = select(Task).where(and_(Task.closed_date >= start, Task.closed_date <= end))

            if isinstance(group_id, int):
                query = query.filter(Task.group_id == group_id)

            query = query.order_by(Task.closed_date).order_by(Task.stage_id)

            try:
                result = await session.execute(query)
                return result.scalars().unique().all()
            except Exception as e:
                print(e)  # LOG

    async def get_created_tasks(self, start, end, group_id: int = None) -> Sequence[Task] | None:
        async with self.session_factory() as session:
            query = select(Task).where(and_(Task.created_date >= start, Task.created_date <= end))

            if isinstance(group_id, int):
                query = query.filter(Task.group_id == group_id)

            query = query.order_by(Task.created_date).order_by(Task.stage_id)

            try:
                result = await session.execute(query)
                return result.scalars().unique().all()
            except Exception as e:
                print(e)  # LOG

    async def get_fifo_queue(self, group_id: int = None, limit: int | None = 1) -> Sequence[Task] | None:
        stage = await self.get_task_stage(group_id=group_id, stage_type=StageType.FIFO)

        if not stage:
            return []

        async with self.session_factory() as session:
            query = (
                select(Task)
                .where(Task.stage_id == stage[0].id)
                .order_by(Task.queue_date)
                .limit(limit)
            )

            try:
                result = await session.execute(query)
                return result.scalars().unique().all()
            except Exception as e:
                print(e)  # LOG

    async def get_user_group_rules(
            self, user_id: int = None, group_id: int = None, observer: str = None, manager: str = None
    ) -> Sequence[UserGroupRules] | None:
        async with self.session_factory() as session:
            query = select(UserGroupRules)

            if user_id:
                query = query.filter(UserGroupRules.user_id == user_id)

            if group_id:
                query = query.filter(UserGroupRules.group_id == group_id)

            if observer:
                query = query.filter(UserGroupRules.observer == observer)

            if manager:
                query = query.filter(UserGroupRules.manager == manager)

            try:
                result = await session.execute(query)
                return result.scalars().unique().all()
            except Exception as e:
                print(e)  # LOG
