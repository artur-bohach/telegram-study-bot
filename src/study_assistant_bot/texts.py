from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from html import escape
import re
from typing import TYPE_CHECKING

from study_assistant_bot.enums import MainMenuSection, PlanLessonKind
from study_assistant_bot.lesson_title_parser import (
    humanize_lesson_details,
    normalize_lesson_text,
    parse_lesson_title,
    resolve_lesson_kind,
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
LECTURE_DETAILS_UNAVAILABLE_TEXT = "Для лекцій окрема картка заняття поки що не відкривається."

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

PLAN_LESSON_KIND_LABELS = {
    PlanLessonKind.LECTURE: "Лекція",
    PlanLessonKind.SEMINAR: "Семінар",
    PlanLessonKind.PRACTICAL: "ПЗ",
}
LEADING_LIST_MARKER_PATTERN = re.compile(r"^\d+[\.\)]\s*")

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


@dataclass(slots=True)
class LessonDetailsInfo:
    subject_label: str
    metadata_label: str | None
    topic_label: str | None


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
    display = _build_lesson_display_info(lesson, prefer_short_name=True)
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
    display = _build_lesson_details_info(lesson)
    details: list[str] = []
    lesson_number = get_lesson_number(lesson)

    header_parts: list[str] = []
    if lesson_number is not None:
        header_parts.append(f"{lesson_number} пара")

    header_parts.append(_format_time_range(lesson))

    details.append(f"<b>{' · '.join(header_parts)}</b>")
    details.append(f"<b>{escape(display.subject_label)}</b>")

    if display.metadata_label:
        details.append(f"<i>{escape(display.metadata_label)}</i>")

    if display.topic_label:
        details.append(escape(display.topic_label))

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


def build_seminar_questions_text(lesson: "Lesson") -> str:
    details = _build_lesson_details_info(lesson)
    lines = _build_lesson_content_header(
        title="Питання до семінару",
        details=details,
    )
    questions = list(getattr(getattr(lesson, "plan_item", None), "questions", []))

    if resolve_lesson_kind(lesson) is not PlanLessonKind.SEMINAR:
        lines.append("Питання для цього заняття зараз недоступні.")
        return "\n".join(lines)

    if getattr(lesson, "plan_item", None) is None:
        lines.append("Питання до цього семінару ще не привʼязані до заняття.")
        return "\n".join(lines)

    if not questions:
        lines.append("Питання до цього семінару ще не додані.")
        return "\n".join(lines)

    question_lines: list[str] = []
    for index, question in enumerate(questions, start=1):
        question_text = _normalize_optional_text(getattr(question, "text", None))
        if question_text is None:
            continue

        question_lines.append(f"{index}. {escape(_strip_leading_list_marker(question_text))}")

    if not question_lines:
        lines.append("Питання до цього семінару ще не додані.")
        return "\n".join(lines)

    lines.extend(question_lines)
    return "\n".join(lines)


def build_practical_assignments_text(lesson: "Lesson") -> str:
    details = _build_lesson_details_info(lesson)
    lines = _build_lesson_content_header(
        title="Практичні завдання",
        details=details,
    )
    assignments = list(getattr(getattr(lesson, "plan_item", None), "assignments", []))

    if resolve_lesson_kind(lesson) is not PlanLessonKind.PRACTICAL:
        lines.append("Практичні завдання для цього заняття зараз недоступні.")
        return "\n".join(lines)

    if getattr(lesson, "plan_item", None) is None:
        lines.append("Практичні завдання до цього заняття ще не привʼязані.")
        return "\n".join(lines)

    if not assignments:
        lines.append("Практичні завдання до цього заняття ще не додані.")
        return "\n".join(lines)

    blocks: list[str] = []
    for index, assignment in enumerate(assignments, start=1):
        assignment_block = _build_assignment_block(assignment, fallback_index=index)
        if assignment_block is not None:
            blocks.append(assignment_block)

    if not blocks:
        lines.append("Практичні завдання до цього заняття ще не додані.")
        return "\n".join(lines)

    lines.append("\n\n".join(blocks))
    return "\n".join(lines)


def get_lesson_number(lesson: "Lesson") -> int | None:
    return LESSON_NUMBER_BY_START_TIME.get(lesson.starts_at.strftime("%H:%M"))


def get_weekday_short_title(schedule_date: date) -> str:
    return WEEKDAY_SHORT_TITLES[schedule_date.weekday()]


def _build_lesson_details_info(lesson: "Lesson") -> LessonDetailsInfo:
    display = _build_lesson_display_info(lesson, prefer_short_name=False)
    metadata_label = display.detail_label
    topic_label: str | None = None
    plan_item = getattr(lesson, "plan_item", None)

    if plan_item is not None:
        plan_metadata_label, plan_topic_label = _build_plan_item_presentation(plan_item)
        if plan_metadata_label is not None:
            metadata_label = plan_metadata_label
            topic_label = plan_topic_label

    return LessonDetailsInfo(
        subject_label=display.subject_label,
        metadata_label=metadata_label,
        topic_label=topic_label,
    )


def _build_lesson_content_header(
    title: str,
    details: LessonDetailsInfo,
) -> list[str]:
    lines = [f"<b>{title}</b>", f"<b>{escape(details.subject_label)}</b>"]

    if details.metadata_label:
        lines.append(f"<i>{escape(details.metadata_label)}</i>")

    if details.topic_label:
        lines.append(escape(details.topic_label))

    lines.append("")
    return lines


def _build_lesson_display_info(
    lesson: "Lesson",
    *,
    prefer_short_name: bool,
) -> LessonDisplayInfo:
    subject_label = _get_subject_label(lesson, prefer_short_name=prefer_short_name)
    normalized_title = _normalize_optional_text(lesson.title) or ""
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

    return LessonDisplayInfo(
        subject_label=subject_label,
        detail_label=detail_label,
    )


def _get_subject_label(
    lesson: "Lesson",
    *,
    prefer_short_name: bool,
) -> str | None:
    if lesson.subject is None:
        return None

    subject_name = _normalize_optional_text(getattr(lesson.subject, "name", None))
    subject_short_name = _normalize_optional_text(getattr(lesson.subject, "short_name", None))

    if prefer_short_name:
        return subject_short_name or subject_name

    return subject_name or subject_short_name


def _build_plan_item_presentation(plan_item: object) -> tuple[str | None, str | None]:
    lesson_kind = _coerce_plan_lesson_kind(getattr(plan_item, "lesson_kind", None))
    if lesson_kind is None:
        return None, None

    lesson_kind_label = PLAN_LESSON_KIND_LABELS[lesson_kind]
    topic_number = _coerce_positive_int(getattr(plan_item, "topic_number", None))
    session_number = _coerce_positive_int(getattr(plan_item, "session_number", None))
    topic_title = _normalize_optional_text(getattr(plan_item, "topic_title", None))

    if lesson_kind is PlanLessonKind.LECTURE:
        return lesson_kind_label, None

    metadata_label = lesson_kind_label
    if topic_number is not None and session_number is not None:
        metadata_label = f"{lesson_kind_label} {topic_number}.{session_number}"

    if topic_title is None:
        return metadata_label, None

    return metadata_label, f"Тема: {topic_title}"


def _build_assignment_block(assignment: object, fallback_index: int) -> str | None:
    title = _normalize_optional_text(getattr(assignment, "title", None))
    if title is None:
        return None

    task_number = _coerce_positive_int(getattr(assignment, "task_number", None)) or fallback_index
    condition = _normalize_optional_text(getattr(assignment, "condition", None))
    question = _normalize_optional_text(getattr(assignment, "question", None))

    lines = [f"<b>Завдання {task_number}. {escape(title)}</b>"]

    if condition:
        lines.append(f"Умова: {escape(condition)}")

    if question:
        lines.append(f"Питання: {escape(question)}")

    return "\n".join(lines)


def _strip_leading_list_marker(value: str) -> str:
    stripped_value = LEADING_LIST_MARKER_PATTERN.sub("", value, count=1)
    return stripped_value or value


def _coerce_plan_lesson_kind(value: object) -> PlanLessonKind | None:
    if isinstance(value, PlanLessonKind):
        return value

    if isinstance(value, str):
        normalized_value = value.strip()
        if not normalized_value:
            return None

        try:
            return PlanLessonKind(normalized_value)
        except ValueError:
            return None

    return None


def _coerce_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if value > 0 else None

    if isinstance(value, str):
        normalized_value = value.strip()
        if normalized_value.isdigit():
            parsed_value = int(normalized_value)
            return parsed_value if parsed_value > 0 else None

    return None


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    normalized_value = normalize_lesson_text(value)
    return normalized_value or None


def _normalize_text(value: str) -> str:
    return _normalize_optional_text(value) or ""


def _same_text(left: str, right: str) -> bool:
    return _normalize_text(left).casefold() == _normalize_text(right).casefold()


def _format_location_line(location: str | None) -> str:
    if location:
        normalized_location = _normalize_text(location)
        if normalized_location not in {"?", "-", "—"} and normalized_location.casefold() != "не вказано":
            return f"Аудиторія: {escape(normalized_location)}"

    return "Аудиторія: не вказана"
