from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from html import escape
from typing import TYPE_CHECKING

from study_assistant_bot.enums import MainMenuSection

if TYPE_CHECKING:
    from study_assistant_bot.db.models import Lesson

ACCESS_DENIED_TEXT = (
    "Access denied. This bot is configured for a small fixed list of trusted Telegram users."
)

START_TEXT = (
    "Welcome to the study assistant.\n\n"
    "This is the initial project foundation for a shared university workflow. "
    "Choose a section from the menu below."
)

UNKNOWN_MESSAGE_TEXT = (
    "Use the menu below to open one of the available sections. "
    "More workflows will be added in future phases."
)

SCHEDULE_MENU_TEXT = "Оберіть, який розклад показати."
SCHEDULE_BACK_TEXT = "Головне меню."

WEEKDAY_TITLES = {
    0: "Понеділок",
    1: "Вівторок",
    2: "Середа",
    3: "Четвер",
    4: "Пʼятниця",
    5: "Субота",
    6: "Неділя",
}

SECTION_PLACEHOLDER_TEXTS = {
    MainMenuSection.SUBJECTS: (
        "Subjects is not implemented yet.\n\n"
        "This section will later contain the shared list of university subjects and materials."
    ),
    MainMenuSection.TASKS: (
        "Tasks is not implemented yet.\n\n"
        "This section will later track deadlines, homework, and helper-admin coordination."
    ),
    MainMenuSection.FILES: (
        "Files is not implemented yet.\n\n"
        "This section will later hold uploaded seminar files, notes, and study attachments."
    ),
    MainMenuSection.AI: (
        "AI is not implemented yet.\n\n"
        "This section is reserved for future AI-assisted study workflows."
    ),
}


def build_today_schedule_text(
    schedule_date: date,
    lessons: Sequence["Lesson"],
) -> str:
    return _build_day_schedule_text(
        title="Сьогодні",
        schedule_date=schedule_date,
        lessons=lessons,
        empty_text="На сьогодні занять немає.",
    )


def build_tomorrow_schedule_text(
    schedule_date: date,
    lessons: Sequence["Lesson"],
) -> str:
    return _build_day_schedule_text(
        title="Завтра",
        schedule_date=schedule_date,
        lessons=lessons,
        empty_text="На завтра занять немає.",
    )


def build_week_schedule_text(
    week_start: date,
    week_end: date,
    lessons: Sequence["Lesson"],
) -> str:
    heading = f"<b>Тиждень {week_start:%d.%m}-{week_end:%d.%m}</b>"

    if not lessons:
        return f"{heading}\n\nНа цей тиждень занять немає."

    lessons_by_day: dict[date, list["Lesson"]] = {}
    for lesson in lessons:
        lesson_date = lesson.starts_at.date()
        lessons_by_day.setdefault(lesson_date, []).append(lesson)

    parts = [heading]
    for lesson_date in sorted(lessons_by_day):
        day_heading = f"<b>{WEEKDAY_TITLES[lesson_date.weekday()]}, {lesson_date:%d.%m}</b>"
        parts.append("")
        parts.append(day_heading)
        parts.append("\n".join(_format_lesson_block(lesson) for lesson in lessons_by_day[lesson_date]))

    return "\n".join(parts)


def _build_day_schedule_text(
    title: str,
    schedule_date: date,
    lessons: Sequence["Lesson"],
    empty_text: str,
) -> str:
    heading = f"<b>{title} • {WEEKDAY_TITLES[schedule_date.weekday()]}, {schedule_date:%d.%m}</b>"

    if not lessons:
        return f"{heading}\n\n{empty_text}"

    lesson_blocks = "\n\n".join(_format_lesson_block(lesson) for lesson in lessons)
    return f"{heading}\n\n{lesson_blocks}"


def _format_lesson_block(lesson: "Lesson") -> str:
    title = escape(lesson.title)
    time_range = _format_time_range(lesson)
    if lesson.location:
        location = escape(lesson.location)
        return f"{time_range} — {title}\nауд. {location}"

    return f"{time_range} — {title}"


def _format_time_range(lesson: "Lesson") -> str:
    start_time = lesson.starts_at.strftime("%H:%M")
    if lesson.ends_at is None:
        return start_time

    end_time = lesson.ends_at.strftime("%H:%M")
    return f"{start_time}-{end_time}"
