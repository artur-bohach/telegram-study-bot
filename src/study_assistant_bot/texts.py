from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from html import escape
from typing import TYPE_CHECKING

from study_assistant_bot.enums import MainMenuSection
from study_assistant_bot.lesson_title_parser import (
    humanize_lesson_details,
    normalize_lesson_text,
    parse_lesson_title,
)

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
LESSON_NOT_FOUND_TEXT = "Не вдалося знайти це заняття."

WEEKDAY_TITLES = {
    0: "Понеділок",
    1: "Вівторок",
    2: "Середа",
    3: "Четвер",
    4: "Пʼятниця",
    5: "Субота",
    6: "Неділя",
}

WEEKDAY_SHORT_TITLES = {
    0: "Пн",
    1: "Вт",
    2: "Ср",
    3: "Чт",
    4: "Пт",
    5: "Сб",
    6: "Нд",
}

LESSON_NUMBER_BY_START_TIME = {
    "08:00": 1,
    "09:30": 2,
    "11:00": 3,
    "12:30": 4,
    "14:30": 5,
    "16:00": 6,
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


@dataclass(slots=True)
class LessonDisplayInfo:
    subject_label: str
    detail_label: str | None


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


def build_selected_day_schedule_text(
    schedule_date: date,
    lessons: Sequence["Lesson"],
) -> str:
    return _build_day_schedule_text(
        title=f"{WEEKDAY_TITLES[schedule_date.weekday()]}, {schedule_date:%d.%m}",
        schedule_date=schedule_date,
        lessons=lessons,
        empty_text="На цей день занять немає.",
        include_date_in_heading=False,
    )


def build_week_schedule_text(
    week_dates: Sequence[date],
) -> str:
    if not week_dates:
        return "<b>Тиждень</b>\n\nОберіть день тижня."

    return (
        f"<b>Тиждень {week_dates[0]:%d.%m}–{week_dates[-1]:%d.%m}</b>\n\n"
        "Оберіть день тижня."
    )


def _build_day_schedule_text(
    title: str,
    schedule_date: date,
    lessons: Sequence["Lesson"],
    empty_text: str,
    include_date_in_heading: bool = True,
) -> str:
    if include_date_in_heading:
        heading = f"<b>{title}</b>\n{WEEKDAY_TITLES[schedule_date.weekday()]}, {schedule_date:%d.%m}"
    else:
        heading = f"<b>{title}</b>"

    if not lessons:
        return f"{heading}\n\n{empty_text}"

    lesson_blocks = "\n\n".join(_format_lesson_block(lesson) for lesson in lessons)
    return f"{heading}\n\n{lesson_blocks}"


def _format_lesson_block(lesson: "Lesson") -> str:
    display = _build_lesson_display_info(lesson)
    header_parts: list[str] = []
    lesson_number = get_lesson_number(lesson)

    if lesson_number is not None:
        header_parts.append(f"{lesson_number} пара")

    header_parts.append(_format_time_range(lesson))

    lines = [f"<b>{' · '.join(header_parts)}</b>", f"<b>{escape(display.subject_label)}</b>"]

    if display.detail_label:
        lines.append(f"<i>{escape(display.detail_label)}</i>")

    lines.append(_format_location_line(lesson.location))

    return "\n".join(lines)


def _format_time_range(lesson: "Lesson") -> str:
    start_time = lesson.starts_at.strftime("%H:%M")
    if lesson.ends_at is None:
        return start_time

    end_time = lesson.ends_at.strftime("%H:%M")
    return f"{start_time}–{end_time}"


def build_lesson_details_text(lesson: "Lesson") -> str:
    display = _build_lesson_display_info(lesson)
    details: list[str] = []
    lesson_number = get_lesson_number(lesson)

    header_parts: list[str] = []
    if lesson_number is not None:
        header_parts.append(f"{lesson_number} пара")

    header_parts.append(_format_time_range(lesson))

    details.append(f"<b>{' · '.join(header_parts)}</b>")
    details.append(f"{WEEKDAY_TITLES[lesson.starts_at.weekday()]}, {lesson.starts_at:%d.%m.%Y}")
    details.append("")
    details.append(f"<b>{escape(display.subject_label)}</b>")

    if display.detail_label:
        details.append(f"<i>{escape(display.detail_label)}</i>")

    details.append(_format_location_line(lesson.location))

    return "\n".join(details)


def build_schedule_lesson_button_text(
    lesson: "Lesson",
    context: str,
) -> str:
    lesson_number = get_lesson_number(lesson)

    if lesson_number is not None:
        return f"{lesson_number} пара"

    return lesson.starts_at.strftime("%H:%M")


def build_lesson_action_placeholder_text(action: str) -> str:
    action_texts = {
        "questions": "Розділ з питаннями для заняття з’явиться трохи пізніше.",
        "file": "Робота з файлами для заняття буде додана трохи пізніше.",
        "task": "Розділ із завданнями для заняття буде доданий трохи пізніше.",
    }
    return action_texts[action]


def get_lesson_number(lesson: "Lesson") -> int | None:
    return LESSON_NUMBER_BY_START_TIME.get(lesson.starts_at.strftime("%H:%M"))


def get_weekday_short_title(schedule_date: date) -> str:
    return WEEKDAY_SHORT_TITLES[schedule_date.weekday()]


def _build_lesson_display_info(lesson: "Lesson") -> LessonDisplayInfo:
    subject_label = normalize_lesson_text(lesson.subject.name) if lesson.subject is not None else None
    normalized_title = normalize_lesson_text(lesson.title)
    parsed_title = parse_lesson_title(normalized_title)
    detail_label: str | None = None

    if parsed_title is not None:
        subject_from_title = parsed_title.subject_label
        detail_label = humanize_lesson_details(parsed_title.details)
        subject_label = subject_label or subject_from_title

    if subject_label is None:
        subject_label = normalized_title
    elif detail_label is None and not _same_text(normalized_title, subject_label):
        detail_label = normalized_title

    return LessonDisplayInfo(subject_label=subject_label, detail_label=detail_label)


def _normalize_text(value: str) -> str:
    return normalize_lesson_text(value)


def _same_text(left: str, right: str) -> bool:
    return _normalize_text(left).casefold() == _normalize_text(right).casefold()


def _format_location_line(location: str | None) -> str:
    if location:
        normalized_location = _normalize_text(location)
        if normalized_location not in {"?", "-", "—"} and normalized_location.casefold() != "не вказано":
            return f"Аудиторія: {escape(normalized_location)}"

    return "Аудиторія: не вказана"
