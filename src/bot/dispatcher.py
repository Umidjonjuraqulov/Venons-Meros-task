from aiogram import Dispatcher

from src.bot.routers import routers

from src.bot.middlewares import AntispamMiddleware
from src.bot.middlewares import AccessMiddleware

from src.bot.util.user_manager import UsersManager

def get_dispatcher(users_manager: UsersManager, include: Dispatcher = None) -> Dispatcher:
    """This function set up dispatcher with routers, filters and middlewares."""
    dp = include if include else Dispatcher()
    for router in routers:
        dp.include_router(router)

    # Register middlewares
    dp.update.middleware(AntispamMiddleware())
    dp.update.middleware(AccessMiddleware(users_manager))

    return dp
