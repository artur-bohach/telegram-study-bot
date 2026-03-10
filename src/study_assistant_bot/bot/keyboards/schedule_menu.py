from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from study_assistant_bot.enums import ScheduleMenuAction


def build_schedule_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()

    builder.add(KeyboardButton(text=ScheduleMenuAction.TODAY.value))
    builder.add(KeyboardButton(text=ScheduleMenuAction.TOMORROW.value))
    builder.add(KeyboardButton(text=ScheduleMenuAction.WEEK.value))
    builder.add(KeyboardButton(text=ScheduleMenuAction.BACK.value))

    builder.adjust(2, 1, 1)
    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Оберіть період",
    )
