from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User

from study_assistant_bot.config import Settings
from study_assistant_bot.texts import ACCESS_DENIED_TEXT

logger = logging.getLogger(__name__)


class AccessMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        self._allowed_ids = settings.allowed_telegram_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")

        if not isinstance(user, User):
            return await handler(event, data)

        if user.id in self._allowed_ids:
            return await handler(event, data)

        logger.warning("Blocked unauthorized access attempt from telegram_id=%s", user.id)

        if isinstance(event, Message):
            await event.answer(ACCESS_DENIED_TEXT)
            return None

        if isinstance(event, CallbackQuery):
            await event.answer(ACCESS_DENIED_TEXT, show_alert=True)
            return None

        return None
