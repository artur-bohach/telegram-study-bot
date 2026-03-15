from __future__ import annotations

from datetime import date

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from study_assistant_bot.db.models import Lesson
from study_assistant_bot.enums import PlanLessonKind
from study_assistant_bot.lesson_title_parser import resolve_lesson_kind
from study_assistant_bot.texts import build_schedule_lesson_button_text, get_weekday_short_title


class LessonDetailsCallback(CallbackData, prefix="lesson"):
    lesson_id: int
    context: str
    context_date: str


class LessonActionCallback(CallbackData, prefix="lesson_action"):
    action: str
    lesson_id: int
    context: str
    context_date: str


class LessonContentCallback(CallbackData, prefix="lesson_content"):
    kind: str
    lesson_id: int
    context: str
    context_date: str


class WeekDayCallback(CallbackData, prefix="week_day"):
    context_date: str


def build_day_schedule_keyboard(
    lessons: list[Lesson],
    context: str,
    context_date: date,
    week_dates: list[date] | None = None,
    selected_date: date | None = None,
) -> InlineKeyboardMarkup | None:
    if not lessons and not week_dates:
        return None

    builder = InlineKeyboardBuilder()

    if week_dates:
        builder.row(
            *[
                InlineKeyboardButton(
                    text=_build_week_day_button_text(week_date, selected_date),
                    callback_data=WeekDayCallback(context_date=week_date.isoformat()).pack(),
                )
                for week_date in week_dates
            ]
        )

    openable_lessons = [
        lesson
        for lesson in lessons
        if resolve_lesson_kind(lesson) is not PlanLessonKind.LECTURE
    ]
    if not openable_lessons and not week_dates:
        return None

    lesson_buttons = [
        InlineKeyboardButton(
            text=build_schedule_lesson_button_text(lesson=lesson, context=context),
            callback_data=LessonDetailsCallback(
                lesson_id=lesson.id,
                context=context,
                context_date=context_date.isoformat(),
            ).pack(),
        )
        for lesson in openable_lessons
    ]
    for row_start in range(0, len(lesson_buttons), 3):
        builder.row(*lesson_buttons[row_start : row_start + 3])

    return builder.as_markup()


def build_week_picker_keyboard(week_dates: list[date]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        *[
            InlineKeyboardButton(
                text=get_weekday_short_title(week_date),
                callback_data=WeekDayCallback(context_date=week_date.isoformat()).pack(),
            )
            for week_date in week_dates
        ]
    )
    return builder.as_markup()


def build_lesson_details_keyboard(
    lesson: Lesson,
    context: str,
    context_date: date,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    lesson_kind = resolve_lesson_kind(lesson)

    builder.button(
        text="Питання",
        callback_data=(
            LessonContentCallback(
                kind="questions",
                lesson_id=lesson.id,
                context=context,
                context_date=context_date.isoformat(),
            )
            if lesson_kind is PlanLessonKind.SEMINAR
            else LessonActionCallback(
                action="questions",
                lesson_id=lesson.id,
                context=context,
                context_date=context_date.isoformat(),
            )
        ),
    )
    builder.button(
        text="Файл",
        callback_data=LessonActionCallback(
            action="file",
            lesson_id=lesson.id,
            context=context,
            context_date=context_date.isoformat(),
        ),
    )
    builder.button(
        text="Завдання",
        callback_data=(
            LessonContentCallback(
                kind="assignments",
                lesson_id=lesson.id,
                context=context,
                context_date=context_date.isoformat(),
            )
            if lesson_kind is PlanLessonKind.PRACTICAL
            else LessonActionCallback(
                action="task",
                lesson_id=lesson.id,
                context=context,
                context_date=context_date.isoformat(),
            )
        ),
    )
    builder.button(
        text="Назад",
        callback_data=LessonActionCallback(
            action="back",
            lesson_id=lesson.id,
            context=context,
            context_date=context_date.isoformat(),
        ),
    )

    builder.adjust(2, 2)
    return builder.as_markup()


def build_lesson_content_keyboard(
    lesson_id: int,
    context: str,
    context_date: date,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Назад",
        callback_data=LessonDetailsCallback(
            lesson_id=lesson_id,
            context=context,
            context_date=context_date.isoformat(),
        ),
    )
    return builder.as_markup()


def _build_week_day_button_text(
    week_date: date,
    selected_date: date | None,
) -> str:
    base_text = get_weekday_short_title(week_date)
    if selected_date == week_date:
        return f"· {base_text}"

    return base_text
