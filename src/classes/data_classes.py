from datetime import datetime
from dataclasses import dataclass


@dataclass()
class BitrixConfigData:
    current_id: int
    current_full_name: str
    user_storage_id: int


@dataclass()
class TaskInfo:
    db_id: int
    bit_id: int
    title: str
    description: str
    group: str
    stage: str
    create_date: datetime
    deadline: datetime | None
    closed_date: datetime | None
    creator: str
    developer: str
    manager: str | None
    observers: list[str] | None
    can_delete: bool
