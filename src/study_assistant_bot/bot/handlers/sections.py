from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from study_assistant_bot.bot.keyboards import build_main_menu
from study_assistant_bot.enums import MainMenuSection
from study_assistant_bot.texts import SECTION_PLACEHOLDER_TEXTS, UNKNOWN_MESSAGE_TEXT

router = Router(name="sections")

SECTION_TITLES = {section.value for section in SECTION_PLACEHOLDER_TEXTS}


@router.message(F.text.in_(SECTION_TITLES))
async def handle_main_menu_section(message: Message) -> None:
    if message.text is None:
        return

    section = MainMenuSection(message.text)
    await message.answer(
        SECTION_PLACEHOLDER_TEXTS[section],
        reply_markup=build_main_menu(),
    )


@router.message()
async def handle_unknown_message(message: Message) -> None:
    await message.answer(
        UNKNOWN_MESSAGE_TEXT,
        reply_markup=build_main_menu(),
    )
