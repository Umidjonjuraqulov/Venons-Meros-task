class AccessLevelConst:
    CHECKING = "checking"
    BLOCKED = "blocked"
    BITRIX = "bitrix"
    USER = "user"
    ADMIN = "admin"

    ALL = {ADMIN, USER, CHECKING, BITRIX, BLOCKED}


class FileTypeConst:
    DOCUMENT = "document"
    PHOTO = "photo"
    VIDEO = "video"
    VIDEO_NOTE = "video_note"
    VOICE = "voice"

    ALL = {DOCUMENT, PHOTO, VIDEO, VIDEO_NOTE, VOICE}


class TaskRole:
    CREATOR = "creator"
    EXECUTOR = "executor"
    CO_EXECUTOR = "co_executor"
    OBSERVER = "observer"
    MANAGER = "manager"


class StageType:
    DEVELOP = "dev"
    WAIT = "wait"
    FIFO = "fifo"
    TESTING = "test"
    ERROR = "error"

    ALL = {DEVELOP, WAIT, FIFO, TESTING, ERROR}


class UserGroupRole:
    ALLWAYS = "allways"
    NEWER = "newer"

    ALL = {ALLWAYS, NEWER}
