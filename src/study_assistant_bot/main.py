from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from study_assistant_bot.bot import build_dispatcher
from study_assistant_bot.config import get_settings
from study_assistant_bot.db import build_engine, build_session_factory, verify_database_ready
from study_assistant_bot.logging import setup_logging


async def start_bot() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    try:
        settings.validate_runtime()
    except ValueError as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from exc

    logger.info(
        "Starting study assistant with admin_users=%s student_users=%s",
        len(settings.admin_telegram_ids),
        len(settings.student_telegram_ids),
    )

    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    bot: Bot | None = None

    try:
        await verify_database_ready(engine)

        bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dispatcher = build_dispatcher(settings=settings, session_factory=session_factory)

        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    except RuntimeError as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from exc
    finally:
        if bot is not None:
            await bot.session.close()
        await engine.dispose()


def run() -> None:
    asyncio.run(start_bot())
