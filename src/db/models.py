from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Role(Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    access_all_stage: Mapped[bool] = mapped_column(default=False, unique=False, nullable=False)
    notify_queue: Mapped[bool] = mapped_column(default=False, unique=False, nullable=False)
    change_any: Mapped[bool] = mapped_column(default=False, unique=False, nullable=False)

    # relationships
    user_roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="role", uselist=True)
    users: Mapped[list["User"]] = relationship(back_populates="role")
    access: Mapped[list["RoleAccess"]] = relationship(
        back_populates="role", lazy="joined", cascade="all, delete-orphan"
    )

    def __str__(self):
        return self.name


class UserRole(Base):
    __tablename__ = "users_roles"
    id = None  # without id
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[int] = mapped_column(sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)

    # relationships
    user: Mapped["User"] = relationship(back_populates="user_roles")
    role: Mapped["Role"] = relationship(back_populates="user_roles")


class RoleAccess(Base):
    __tablename__ = "role_access"
    role_id: Mapped[int] = mapped_column(
        sa.ForeignKey("roles.id", ondelete="CASCADE"), unique=False, nullable=False
    )
    stage_id: Mapped[int] = mapped_column(
        sa.ForeignKey("stages.id", ondelete="CASCADE"), unique=False, nullable=False
    )

    extract: Mapped[bool] = mapped_column(default=False, unique=False, nullable=False)
    insert: Mapped[bool] = mapped_column(default=False, unique=False, nullable=False)

    # relationships
    role: Mapped["Role"] = relationship(back_populates="access")
    stage: Mapped["Stage"] = relationship(back_populates="roles")

user_region = sa.Table(
    "user_region",
    Base.metadata,
    sa.Column("user_id", sa.ForeignKey("users.id"), primary_key=True),
    sa.Column("region_id", sa.ForeignKey("regions.id"), primary_key=True),
)

class User(Base):
    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(sa.BigInteger, unique=True, nullable=True)
    bit_user_id: Mapped[int] = mapped_column(unique=False, nullable=True)
    full_name: Mapped[str] = mapped_column(unique=False, nullable=False)
    job_title: Mapped[str] = mapped_column(unique=False, nullable=True)
    phone: Mapped[str] = mapped_column(unique=False, nullable=True)
    language: Mapped[str] = mapped_column(unique=False, nullable=True)
    access_level: Mapped[str] = mapped_column(unique=False, nullable=False)  # bot_access
    role_id: Mapped[int] = mapped_column(
        sa.ForeignKey("roles.id", ondelete="SET NULL"), unique=False, nullable=True
    )
    max_active_tasks: Mapped[int] = mapped_column(sa.Integer, unique=False, nullable=True)
    ban_time: Mapped[datetime | None] = mapped_column(sa.DateTime, unique=False, nullable=True)
    group_id: Mapped[int] = mapped_column(
        sa.ForeignKey("task_groups.id", ondelete="SET NULL"), unique=False, nullable=True
    )

    # relationships
    departments: Mapped[list["DepartmentUser"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    tasks: Mapped[list["TaskUser"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    comments: Mapped[list["Comment"]] = relationship(back_populates="user")
    files: Mapped[list["File"]] = relationship(back_populates="user")
    role: Mapped["Role"] = relationship(back_populates="users")
    user_roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="user", uselist=True)
    users_group_roles: Mapped[list["UserGroupRules"]] = relationship(
        "UserGroupRules", back_populates="user", uselist=True
    )
    group: Mapped["TaskGroup"] = relationship(back_populates="users")
    regions: Mapped[list["Region"]] = relationship(secondary=user_region, back_populates="users")

    def __str__(self):
        return self.full_name


class Department(Base):
    """
    In Bitrix24, there may be no managers or employees within a department.
    If a department does not have a parent_id, it is the main one.
    """
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    bit_dep_id: Mapped[int] = mapped_column(unique=True, nullable=True)
    name: Mapped[str] = mapped_column(unique=False, nullable=False)
    parent_id: Mapped[int] = mapped_column(
        sa.ForeignKey("departments.id", ondelete="SET NULL"), unique=False, nullable=True
    )

    # relationships
    # Recursive relation for parent department
    parent: Mapped["Department"] = relationship(remote_side=[id], back_populates="children")
    # Recursive relation for child departments
    children: Mapped[list["Department"]] = relationship(back_populates="parent")
    department_users: Mapped[list["DepartmentUser"]] = relationship(
        back_populates="department", cascade="all, delete-orphan"
    )

    def __str__(self):
        return self.name


class DepartmentUser(Base):
    """One employee can be located in many departments."""
    __tablename__ = "department_users"

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), unique=False, nullable=False
    )
    department_id: Mapped[int] = mapped_column(
        sa.ForeignKey("departments.id", ondelete="CASCADE"), unique=False, nullable=False
    )
    head: Mapped[bool] = mapped_column(unique=False, nullable=False)

    # relationships
    user: Mapped["User"] = relationship(back_populates="departments", lazy="joined")
    department: Mapped["Department"] = relationship(back_populates="department_users")

    def __str__(self):
        return f"{'Manager - ' if self.head else ''}{self.user.full_name}"


class TaskGroup(Base):
    __tablename__ = "task_groups"

    bit_group_id: Mapped[int] = mapped_column(sa.Integer, unique=True, nullable=False)
    bit_folder_id: Mapped[int] = mapped_column(sa.Integer, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(sa.String, unique=False, nullable=False)
    max_tasks: Mapped[int] = mapped_column(sa.Integer, unique=False, nullable=True)
    max_user_tasks: Mapped[int] = mapped_column(sa.Integer, unique=False, nullable=True)
    max_executor_task: Mapped[int] = mapped_column(sa.Integer, unique=False, nullable=True)
    max_active_tasks: Mapped[int] = mapped_column(sa.Integer, unique=False, nullable=True)
    ban_hours: Mapped[int] = mapped_column(sa.Integer, unique=False, nullable=True)
    auto_acceptance: Mapped[int] = mapped_column(sa.Integer, unique=False, nullable=True)
    fifo_queue: Mapped[bool] = mapped_column(default=False, unique=False, nullable=False)
    analytics: Mapped[bool] = mapped_column(default=False, unique=False, nullable=False)
    notify: Mapped[bool] = mapped_column(default=False, unique=False, nullable=False)
    close_from_test: Mapped[bool] = mapped_column(default=False, unique=False, nullable=False)
    assign_executor: Mapped[bool] = mapped_column(default=False, unique=False, nullable=False)

    # relationships
    stages: Mapped[list["Stage"]] = relationship(back_populates="group", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="group", cascade="all, delete-orphan")
    regions: Mapped[list["Region"]] = relationship(back_populates="task_group", cascade="all, delete-orphan")
    users_group_roles: Mapped[list["UserGroupRules"]] = relationship(
        "UserGroupRules", back_populates="group", uselist=True
    )
    users: Mapped[list["User"]] = relationship(back_populates="group")

    def __str__(self):
        return self.title


class Stage(Base):
    __tablename__ = "stages"

    group_id: Mapped[int] = mapped_column(
        sa.ForeignKey("task_groups.id", ondelete="CASCADE"), unique=False, nullable=False
    )
    bit_stage_id: Mapped[int] = mapped_column(unique=False, nullable=False)
    sort: Mapped[int] = mapped_column(unique=False, nullable=False)
    title: Mapped[str] = mapped_column(unique=False, nullable=False)
    max_tasks: Mapped[int] = mapped_column(sa.Integer, unique=False, nullable=True)
    in_queue: Mapped[bool] = mapped_column(default=False, unique=False, nullable=False)
    stage_type: Mapped[str] = mapped_column(unique=False, nullable=True)

    # relationships
    group: Mapped["TaskGroup"] = relationship(back_populates="stages", lazy="joined")
    tasks: Mapped[list["Task"]] = relationship(back_populates="stage")
    roles: Mapped[list["RoleAccess"]] = relationship(back_populates="stage", cascade="all, delete-orphan")

    def __str__(self):
        return f"{self.title} - {self.group.title}"


class Task(Base):
    __tablename__ = "tasks"

    bit_task_id: Mapped[int] = mapped_column(unique=True, nullable=True)
    bit_chat_id: Mapped[int] = mapped_column(unique=True, nullable=True)
    bit_folder_id: Mapped[int] = mapped_column(unique=True, nullable=True)
    title: Mapped[str] = mapped_column(unique=False, nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, unique=False, nullable=False)
    created_date: Mapped[datetime] = mapped_column(sa.DateTime, unique=False, nullable=False)
    queue_date: Mapped[datetime] = mapped_column(sa.DateTime, unique=False, nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(sa.DateTime, unique=False, nullable=True)
    test_date: Mapped[datetime | None] = mapped_column(sa.DateTime, unique=False, nullable=True)
    closed_date: Mapped[datetime | None] = mapped_column(sa.DateTime, unique=False, nullable=True)
    allocated_time: Mapped[int] = mapped_column(sa.Integer, unique=False, nullable=True)
    paid: Mapped[bool] = mapped_column(default=False, unique=False, nullable=False)
    unlimited_test: Mapped[bool] = mapped_column(default=False, unique=False, nullable=False)

    stage_id: Mapped[int] = mapped_column(
        sa.ForeignKey("stages.id", ondelete="SET NULL"), unique=False, nullable=True
    )
    group_id: Mapped[int] = mapped_column(
        sa.ForeignKey("task_groups.id", ondelete="CASCADE"), unique=False, nullable=False
    )
    region_id: Mapped[int] = mapped_column(
        sa.ForeignKey("regions.id", ondelete="SET NULL"), unique=False, nullable=True
    )

    # relationships
    task_users: Mapped[list["TaskUser"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="joined"
    )
    stage: Mapped["Stage"] = relationship(back_populates="tasks", lazy="joined")
    group: Mapped["TaskGroup"] = relationship(back_populates="tasks", lazy="joined")
    files: Mapped[list["File"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    comments: Mapped[list["Comment"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    region: Mapped["Region"] = relationship(back_populates="tasks", lazy="joined")

    def __str__(self):
        return self.title


class TaskUser(Base):
    __tablename__ = "task_users"

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), unique=False, nullable=False
    )
    task_id: Mapped[int] = mapped_column(
        sa.ForeignKey("tasks.id", ondelete="CASCADE"), unique=False, nullable=False
    )
    role: Mapped[str] = mapped_column(unique=False, nullable=False)

    # relationships
    user: Mapped["User"] = relationship(back_populates="tasks", lazy="joined")
    task: Mapped["Task"] = relationship(back_populates="task_users", lazy="joined")

    def __str__(self):
        return f"{self.role} - {self.user.full_name}"


class File(Base):
    __tablename__ = "files"

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL"), unique=False, nullable=True
    )
    task_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("tasks.id", ondelete="CASCADE"), unique=False, nullable=False
    )
    comment_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("comments.id", ondelete="CASCADE"), unique=False, nullable=True
    )
    tg_file_id: Mapped[str] = mapped_column(sa.String, unique=True, nullable=False)
    bit_file_id: Mapped[int] = mapped_column(sa.Integer, unique=True, nullable=True)
    name: Mapped[str] = mapped_column(sa.String, unique=False, nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, unique=False, nullable=True)
    type: Mapped[str] = mapped_column(sa.String, unique=False, nullable=False)

    # relationships
    task: Mapped["Task"] = relationship(back_populates="files")
    user: Mapped["User"] = relationship(back_populates="files")
    comment: Mapped["Comment"] = relationship(back_populates="files")

    def __str__(self):
        return self.name


class Comment(Base):
    __tablename__ = "comments"

    task_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("tasks.id", ondelete="CASCADE"), unique=False, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), unique=False, nullable=True
    )
    bit_comment_id: Mapped[int] = mapped_column(sa.Integer, unique=True, nullable=False)
    created_date: Mapped[datetime] = mapped_column(sa.DateTime, unique=False, nullable=False)
    text: Mapped[str] = mapped_column(sa.Text, unique=False, nullable=False)

    # relationships
    task: Mapped["Task"] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship(back_populates="comments")
    files: Mapped[list["File"]] = relationship(back_populates="comment", cascade="all, delete-orphan")

    def __str__(self):
        return self.text


class UserGroupRules(Base):
    __tablename__ = "users_group_roles"
    id = None  # without id
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_id: Mapped[int] = mapped_column(sa.ForeignKey("task_groups.id", ondelete="CASCADE"), primary_key=True)

    observer: Mapped[str] = mapped_column(unique=False, nullable=True)
    manager: Mapped[str] = mapped_column(unique=False, nullable=True)

    # relationships
    user: Mapped["User"] = relationship(back_populates="users_group_roles", lazy="joined")
    group: Mapped["TaskGroup"] = relationship(back_populates="users_group_roles")


class Region(Base):
    __tablename__ = "regions"
    name: Mapped[str] = mapped_column(unique=False, nullable=False)
    task_group_id: Mapped[int] = mapped_column(sa.ForeignKey("task_groups.id", ondelete="CASCADE"), nullable=False)

    # relationships
    task_group: Mapped["TaskGroup"] = relationship(lazy="joined")
    tasks: Mapped[list["Task"]] = relationship(back_populates="region", lazy="joined")
    users: Mapped[list["User"]] = relationship(secondary=user_region, back_populates="regions")


    def __str__(self):
        return self.name