from __future__ import annotations

from aiogram.types import User as TelegramUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from study_assistant_bot.db.models import User
from study_assistant_bot.enums import UserRole


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def sync_from_telegram(
        self,
        telegram_user: TelegramUser,
        role: UserRole,
    ) -> User:
        result = await self._session.execute(
            select(User).where(User.telegram_id == telegram_user.id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
                role=role,
                is_active=True,
            )
            self._session.add(user)
        else:
            user.username = telegram_user.username
            user.first_name = telegram_user.first_name
            user.last_name = telegram_user.last_name
            user.role = role
            user.is_active = True

        await self._session.flush()
        return user
