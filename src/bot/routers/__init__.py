"""This package is used for a bot routers implementation."""
from .commands import commands_router
from .registration import registration_router
from .user import user_router
from .other import other_routers
routers = (commands_router, registration_router, user_router, other_routers)
