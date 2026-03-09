from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
import re

from python_calamine import CalamineSheet, load_workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from study_assistant_bot.db.models import Lesson, Subject

WEEKDAY_LABELS = {"Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"}
TIME_RANGE_PATTERN = re.compile(r"(?P<start>\d{2}:\d{2})-(?P<end>\d{2}:\d{2})")


@dataclass(slots=True)
class ParsedTimetableLesson:
    subject_name: str
    title: str
    starts_at: datetime
    ends_at: datetime
    location: str | None
    notes: str | None


@dataclass(slots=True)
class TimetableImportResult:
    parsed_lessons: int = 0
    created_subjects: int = 0
    created_lessons: int = 0
    updated_lessons: int = 0
    skipped_lessons: int = 0


class TimetableImportService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def import_from_file(self, file_path: Path | str) -> TimetableImportResult:
        path = Path(file_path)
        parsed_lessons = self._parse_workbook(path)
        result = TimetableImportResult(parsed_lessons=len(parsed_lessons))

        if not parsed_lessons:
            return result

        subjects, created_subjects = await self._get_or_create_subjects(parsed_lessons)
        result.created_subjects = created_subjects

        existing_lessons = await self._load_existing_lessons(parsed_lessons, subjects)

        for parsed_lesson in parsed_lessons:
            subject = subjects[parsed_lesson.subject_name]
            lesson_key = self._build_lesson_key(
                subject_id=subject.id,
                starts_at=parsed_lesson.starts_at,
                ends_at=parsed_lesson.ends_at,
            )
            lesson = existing_lessons.get(lesson_key)

            if lesson is None:
                lesson = Lesson(
                    subject_id=subject.id,
                    title=parsed_lesson.title,
                    starts_at=parsed_lesson.starts_at,
                    ends_at=parsed_lesson.ends_at,
                    location=parsed_lesson.location,
                    notes=parsed_lesson.notes,
                )
                self._session.add(lesson)
                existing_lessons[lesson_key] = lesson
                result.created_lessons += 1
                continue

            if self._update_existing_lesson(lesson, parsed_lesson):
                result.updated_lessons += 1
            else:
                result.skipped_lessons += 1

        await self._session.flush()
        return result

    async def _get_or_create_subjects(
        self,
        parsed_lessons: list[ParsedTimetableLesson],
    ) -> tuple[dict[str, Subject], int]:
        subject_names = sorted({lesson.subject_name for lesson in parsed_lessons})
        result = await self._session.execute(
            select(Subject).where(Subject.name.in_(subject_names))
        )
        subjects = {subject.name: subject for subject in result.scalars()}
        created_subjects = 0

        for subject_name in subject_names:
            if subject_name in subjects:
                continue

            subject = Subject(name=subject_name)
            self._session.add(subject)
            subjects[subject_name] = subject
            created_subjects += 1

        await self._session.flush()
        return subjects, created_subjects

    async def _load_existing_lessons(
        self,
        parsed_lessons: list[ParsedTimetableLesson],
        subjects: dict[str, Subject],
    ) -> dict[tuple[int, datetime, datetime], Lesson]:
        subject_ids = [subject.id for subject in subjects.values()]
        starts_at_values = [lesson.starts_at for lesson in parsed_lessons]
        ends_at_values = [lesson.ends_at for lesson in parsed_lessons]

        result = await self._session.execute(
            select(Lesson).where(
                Lesson.subject_id.in_(subject_ids),
                Lesson.starts_at >= min(starts_at_values),
                Lesson.ends_at <= max(ends_at_values),
            )
        )
        existing_lessons: dict[tuple[int, datetime, datetime], Lesson] = {}

        for lesson in result.scalars():
            lesson_key = self._build_lesson_key(
                subject_id=lesson.subject_id,
                starts_at=lesson.starts_at,
                ends_at=lesson.ends_at,
            )
            existing_lessons[lesson_key] = lesson

        return existing_lessons

    def _parse_workbook(self, file_path: Path) -> list[ParsedTimetableLesson]:
        workbook = load_workbook(file_path)
        parsed_lessons: list[ParsedTimetableLesson] = []

        try:
            for sheet_name in workbook.sheet_names:
                sheet = workbook.get_sheet_by_name(sheet_name)
                parsed_lessons.extend(self._parse_sheet(sheet))
        finally:
            workbook.close()

        return parsed_lessons

    def _parse_sheet(self, sheet: CalamineSheet) -> list[ParsedTimetableLesson]:
        rows = sheet.to_python()
        parsed_lessons: list[ParsedTimetableLesson] = []
        column_dates: dict[int, date] = {}

        for row in rows:
            first_cell = self._normalize_cell(row[0]) if row else ""

            if first_cell in WEEKDAY_LABELS:
                column_dates = self._extract_column_dates(row)
                continue

            if not column_dates or not first_cell:
                continue

            time_range = self._parse_time_range(first_cell)
            if time_range is None:
                continue

            start_time, end_time = time_range
            for column_index, cell_value in enumerate(row[1:], start=1):
                lesson_text = self._normalize_cell(cell_value)
                lesson_date = column_dates.get(column_index)

                if not lesson_text or lesson_date is None:
                    continue

                parsed_lessons.append(
                    self._parse_lesson_cell(
                        lesson_text=lesson_text,
                        lesson_date=lesson_date,
                        start_time=start_time,
                        end_time=end_time,
                    )
                )

        return parsed_lessons

    def _extract_column_dates(self, row: list[object]) -> dict[int, date]:
        column_dates: dict[int, date] = {}

        for column_index, cell_value in enumerate(row[1:], start=1):
            date_text = self._normalize_cell(cell_value)
            if not date_text:
                continue

            column_dates[column_index] = datetime.strptime(date_text, "%d.%m.%Y").date()

        return column_dates

    def _parse_lesson_cell(
        self,
        lesson_text: str,
        lesson_date: date,
        start_time: time,
        end_time: time,
    ) -> ParsedTimetableLesson:
        lines = [self._normalize_text(line) for line in lesson_text.splitlines()]
        non_empty_lines = [line for line in lines if line]

        if not non_empty_lines:
            raise ValueError("Lesson cell is empty after normalization.")

        title = non_empty_lines[0]
        subject_name = self._extract_subject_name(title)
        location: str | None = None
        notes_parts: list[str] = []

        for line in non_empty_lines[1:]:
            if location is None and line.casefold().startswith("ауд."):
                location = self._normalize_text(line[4:])
                continue

            notes_parts.append(line)

        return ParsedTimetableLesson(
            subject_name=subject_name,
            title=title,
            starts_at=datetime.combine(lesson_date, start_time),
            ends_at=datetime.combine(lesson_date, end_time),
            location=location or None,
            notes="\n".join(notes_parts) or None,
        )

    @staticmethod
    def _update_existing_lesson(
        lesson: Lesson,
        parsed_lesson: ParsedTimetableLesson,
    ) -> bool:
        changed = False

        if lesson.title != parsed_lesson.title:
            lesson.title = parsed_lesson.title
            changed = True

        if lesson.location != parsed_lesson.location:
            lesson.location = parsed_lesson.location
            changed = True

        if lesson.notes != parsed_lesson.notes:
            lesson.notes = parsed_lesson.notes
            changed = True

        return changed

    @staticmethod
    def _extract_subject_name(title: str) -> str:
        subject_name = title.split("[", maxsplit=1)[0]
        return TimetableImportService._normalize_text(subject_name)

    @staticmethod
    def _build_lesson_key(
        subject_id: int,
        starts_at: datetime,
        ends_at: datetime | None,
    ) -> tuple[int, datetime, datetime | None]:
        return subject_id, starts_at, ends_at

    @staticmethod
    def _normalize_cell(value: object) -> str:
        if value is None:
            return ""

        raw_text = str(value).replace("\r\n", "\n").replace("\r", "\n")
        lines = [TimetableImportService._normalize_text(line) for line in raw_text.split("\n")]
        non_empty_lines = [line for line in lines if line]
        return "\n".join(non_empty_lines)

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(value.strip().split())

    @staticmethod
    def _parse_time_range(value: str) -> tuple[time, time] | None:
        match = TIME_RANGE_PATTERN.search(value)
        if match is None:
            return None

        start_time = datetime.strptime(match.group("start"), "%H:%M").time()
        end_time = datetime.strptime(match.group("end"), "%H:%M").time()
        return start_time, end_time
