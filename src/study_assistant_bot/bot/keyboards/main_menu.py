from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from study_assistant_bot.enums import MainMenuSection


def build_main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()

    for section in MainMenuSection:
        builder.add(KeyboardButton(text=section.value))

    builder.adjust(2, 2, 1)
    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Choose a section",
    )
