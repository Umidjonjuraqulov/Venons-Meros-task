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


class CustomFieldType:
    TEXT = "text"
    SELECT = "select"

    ALL = {TEXT, SELECT}


class CustomFieldStage:
    """When a custom field is asked during task creation.

    BEFORE_TITLE: right after the group/region/executor steps.
    AFTER_DESCRIPTION: after the description, before the file upload step.
    """
    BEFORE_TITLE = "before_title"
    AFTER_DESCRIPTION = "after_description"

    ALL = {BEFORE_TITLE, AFTER_DESCRIPTION}
