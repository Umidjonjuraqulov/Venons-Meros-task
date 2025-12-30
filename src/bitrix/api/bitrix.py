from .department import Department
from .storage import Storage
from .task import Task
from .user import User


class BitrixAPI(Department, Task, Storage, User):
    pass
