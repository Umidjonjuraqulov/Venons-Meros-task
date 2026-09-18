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
    CommentAdmin,
    RegionAdmin,
    CustomFieldAdmin,
    CustomFieldOptionAdmin,
    TaskCustomValueAdmin
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
    CommentAdmin,
    RegionAdmin,
    CustomFieldAdmin,
    CustomFieldOptionAdmin,
    TaskCustomValueAdmin
]
