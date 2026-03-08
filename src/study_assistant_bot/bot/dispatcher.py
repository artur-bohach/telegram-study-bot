from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aiogram import Dispatcher

from study_assistant_bot.bot.handlers import ROUTERS
from study_assistant_bot.bot.middlewares import AccessMiddleware, DatabaseSessionMiddleware
from study_assistant_bot.config import Settings


def build_dispatcher(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher["settings"] = settings

    dispatcher.update.outer_middleware(AccessMiddleware(settings))
    dispatcher.update.outer_middleware(DatabaseSessionMiddleware(session_factory))

    for router in ROUTERS:
        dispatcher.include_router(router)

    return dispatcher
