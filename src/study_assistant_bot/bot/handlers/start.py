from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from study_assistant_bot.bot.keyboards import build_main_menu
from study_assistant_bot.config import Settings
from study_assistant_bot.enums import UserRole
from study_assistant_bot.services import UserService
from study_assistant_bot.texts import ACCESS_DENIED_TEXT, START_TEXT

router = Router(name="start")


@router.message(CommandStart())
async def handle_start(
    message: Message,
    session: AsyncSession,
    settings: Settings,
) -> None:
    telegram_user = message.from_user
    if telegram_user is None:
        return

    role = settings.role_for_user(telegram_user.id)
    if role is None:
        await message.answer(ACCESS_DENIED_TEXT)
        return

    user_service = UserService(session)
    await user_service.sync_from_telegram(telegram_user=telegram_user, role=role)

    role_text = "admin" if role == UserRole.ADMIN else "student"
    await message.answer(
        f"{START_TEXT}\n\nYour access level: <b>{role_text}</b>.",
        reply_markup=build_main_menu(),
    )
