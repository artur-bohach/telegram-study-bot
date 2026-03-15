from __future__ import annotations

from dataclasses import dataclass
import re

from study_assistant_bot.enums import PlanLessonKind

LESSON_TYPE_LABELS = {
    "Сем": "Семінар",
    "Пз": "ПЗ",
    "Лк": "Лекція",
    "Дод": "Додаткове заняття",
}

LESSON_KIND_BY_TOKEN = {
    "Сем": PlanLessonKind.SEMINAR,
    "Пз": PlanLessonKind.PRACTICAL,
    "Лк": PlanLessonKind.LECTURE,
}

LESSON_TITLE_PATTERN = re.compile(r"^(?P<subject>.+?)\s*\[(?P<details>[^\]]+)\]\s*$")
LESSON_DETAILS_PATTERN = re.compile(
    r"^(?P<kind>\S+)(?:\s+т\.(?P<topic>\d+))?(?:/з\.(?P<session>\d+))?$"
)
STRICT_LESSON_DETAILS_PATTERN = re.compile(
    r"^(?P<kind>\S+)\s+т\.(?P<topic>\d+)/з\.(?P<timetable_number>\d+)$"
)


@dataclass(slots=True)
class ParsedLessonTitle:
    subject_label: str
    details: str


@dataclass(slots=True)
class ParsedLessonIdentity:
    lesson_kind: PlanLessonKind
    topic_number: int
    timetable_number: int


@dataclass(slots=True)
class LessonIdentityParseResult:
    identity: ParsedLessonIdentity | None
    failure_reason: str | None = None


def normalize_lesson_text(value: str) -> str:
    return " ".join(value.split())


def parse_lesson_title(title: str) -> ParsedLessonTitle | None:
    normalized_title = normalize_lesson_text(title)
    parsed_match = LESSON_TITLE_PATTERN.match(normalized_title)
    if parsed_match is None:
        return None

    return ParsedLessonTitle(
        subject_label=normalize_lesson_text(parsed_match.group("subject")),
        details=normalize_lesson_text(parsed_match.group("details")),
    )


def humanize_lesson_details(details: str) -> str:
    normalized_details = normalize_lesson_text(details)
    parsed_match = LESSON_DETAILS_PATTERN.match(normalized_details)
    if parsed_match is None:
        return normalized_details

    parts = [LESSON_TYPE_LABELS.get(parsed_match.group("kind"), parsed_match.group("kind"))]
    topic_number = parsed_match.group("topic")
    session_number = parsed_match.group("session")

    if topic_number is not None:
        parts.append(f"Тема {topic_number}")

    if session_number is not None:
        parts.append(f"Заняття {session_number}")

    return " · ".join(parts)


def parse_lesson_kind(title: str) -> PlanLessonKind | None:
    parsed_title = parse_lesson_title(title)
    if parsed_title is None:
        return None

    parsed_match = LESSON_DETAILS_PATTERN.match(parsed_title.details)
    if parsed_match is None:
        return None

    return LESSON_KIND_BY_TOKEN.get(parsed_match.group("kind"))


def resolve_lesson_kind(lesson: object) -> PlanLessonKind | None:
    plan_item = getattr(lesson, "plan_item", None)
    if plan_item is not None:
        lesson_kind = getattr(plan_item, "lesson_kind", None)
        if isinstance(lesson_kind, PlanLessonKind):
            return lesson_kind

        if isinstance(lesson_kind, str):
            normalized_kind = lesson_kind.strip()
            if normalized_kind:
                try:
                    return PlanLessonKind(normalized_kind)
                except ValueError:
                    pass

    title = getattr(lesson, "title", None)
    if not isinstance(title, str):
        return None

    return parse_lesson_kind(title)


def parse_lesson_identity(title: str) -> LessonIdentityParseResult:
    parsed_title = parse_lesson_title(title)
    if parsed_title is None:
        return LessonIdentityParseResult(identity=None, failure_reason="missing_title_pattern")

    parsed_match = STRICT_LESSON_DETAILS_PATTERN.match(parsed_title.details)
    if parsed_match is None:
        return LessonIdentityParseResult(
            identity=None,
            failure_reason="missing_topic_or_timetable_number",
        )

    lesson_kind = LESSON_KIND_BY_TOKEN.get(parsed_match.group("kind"))
    if lesson_kind is None:
        return LessonIdentityParseResult(identity=None, failure_reason="unsupported_kind")

    return LessonIdentityParseResult(
        identity=ParsedLessonIdentity(
            lesson_kind=lesson_kind,
            topic_number=int(parsed_match.group("topic")),
            timetable_number=int(parsed_match.group("timetable_number")),
        )
    )
