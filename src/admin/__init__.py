from .auth import AdminAuth

from .model_view import (
    UserAdmin,
    DepartmentAdmin,
    DepartmentUserAdmin,
    TaskGroupAdmin,
    StageAdmin,
    RoleAdmin,
    UserRoleAdmin,
    RoleAccessAdmin,
    TaskAdmin,
    UserGroupRulesAdmin,
    TaskUserAdmin,
    FileAdmin,
    CommentAdmin
)

all_admin_models = [
    UserAdmin,
    DepartmentAdmin,
    DepartmentUserAdmin,
    TaskGroupAdmin,
    StageAdmin,
    RoleAdmin,
    UserRoleAdmin,
    RoleAccessAdmin,
    TaskAdmin,
    UserGroupRulesAdmin,
    TaskUserAdmin,
    FileAdmin,
    CommentAdmin
]
