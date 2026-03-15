from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
import re

from python_calamine import CalamineSheet, load_workbook
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from study_assistant_bot.db.models import Lesson, Subject

WEEKDAY_LABELS = {"Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"}
TIME_RANGE_PATTERN = re.compile(r"(?P<start>\d{2}:\d{2})-(?P<end>\d{2}:\d{2})")


class TimetableImportError(Exception):
    pass


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
    unchanged_lessons: int = 0
    deleted_lessons: int = 0


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

        scoped_lessons = await self._load_scoped_existing_lessons(parsed_lessons, subjects)
        existing_lessons = {
            self._build_lesson_key(
                subject_id=lesson.subject_id,
                starts_at=lesson.starts_at,
                ends_at=lesson.ends_at,
            ): lesson
            for lesson in scoped_lessons
        }
        imported_lesson_keys: set[tuple[int, datetime, datetime | None]] = set()

        for parsed_lesson in parsed_lessons:
            subject = subjects[parsed_lesson.subject_name]
            lesson_key = self._build_lesson_key(
                subject_id=subject.id,
                starts_at=parsed_lesson.starts_at,
                ends_at=parsed_lesson.ends_at,
            )
            imported_lesson_keys.add(lesson_key)
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
                result.unchanged_lessons += 1

        for lesson in scoped_lessons:
            lesson_key = self._build_lesson_key(
                subject_id=lesson.subject_id,
                starts_at=lesson.starts_at,
                ends_at=lesson.ends_at,
            )
            if lesson_key in imported_lesson_keys:
                continue

            await self._session.delete(lesson)
            result.deleted_lessons += 1

        await self._session.flush()
        return result

    async def _get_or_create_subjects(
        self,
        parsed_lessons: list[ParsedTimetableLesson],
    ) -> tuple[dict[str, Subject], int]:
        subject_names = sorted({lesson.subject_name for lesson in parsed_lessons})
        result = await self._session.execute(
            select(Subject).where(
                or_(
                    Subject.short_name.in_(subject_names),
                    Subject.name.in_(subject_names),
                )
            )
        )
        matched_subjects = list(result.scalars())
        subjects_by_short_name: dict[str, list[Subject]] = {}
        subjects_by_name: dict[str, list[Subject]] = {}

        for subject in matched_subjects:
            if subject.short_name:
                subjects_by_short_name.setdefault(subject.short_name, []).append(subject)

            subjects_by_name.setdefault(subject.name, []).append(subject)

        subjects: dict[str, Subject] = {}
        created_subjects = 0

        for subject_name in subject_names:
            subject = self._resolve_existing_subject(
                subject_name=subject_name,
                short_name_matches=subjects_by_short_name.get(subject_name, []),
                name_matches=subjects_by_name.get(subject_name, []),
            )

            if subject is None:
                subject = Subject(
                    name=subject_name,
                    short_name=subject_name,
                )
                self._session.add(subject)
                created_subjects += 1
            elif subject.short_name is None:
                subject.short_name = subject_name

            subjects[subject_name] = subject

        await self._session.flush()
        return subjects, created_subjects

    async def _load_scoped_existing_lessons(
        self,
        parsed_lessons: list[ParsedTimetableLesson],
        subjects: dict[str, Subject],
    ) -> list[Lesson]:
        imported_dates = {lesson.starts_at.date() for lesson in parsed_lessons}
        subject_ids = [subject.id for subject in subjects.values()]
        min_imported_date = min(imported_dates)
        max_imported_date = max(imported_dates)
        scope_start = datetime.combine(min_imported_date, time.min)
        scope_end = datetime.combine(max_imported_date + timedelta(days=1), time.min)

        result = await self._session.execute(
            select(Lesson).where(
                Lesson.subject_id.in_(subject_ids),
                Lesson.starts_at >= scope_start,
                Lesson.starts_at < scope_end,
            )
        )
        return [
            lesson
            for lesson in result.scalars()
            if lesson.starts_at.date() in imported_dates
        ]

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
    def _resolve_existing_subject(
        subject_name: str,
        short_name_matches: list[Subject],
        name_matches: list[Subject],
    ) -> Subject | None:
        if len(short_name_matches) > 1:
            raise TimetableImportError(
                "Знайдено кілька предметів з однаковою короткою назвою "
                f"`{subject_name}`. Імпорт розкладу зупинено."
            )

        if len(name_matches) > 1:
            raise TimetableImportError(
                "Знайдено кілька предметів з однаковою назвою "
                f"`{subject_name}`. Імпорт розкладу зупинено."
            )

        short_name_match = short_name_matches[0] if short_name_matches else None
        name_match = name_matches[0] if name_matches else None

        if (
            short_name_match is not None
            and name_match is not None
            and short_name_match.id != name_match.id
        ):
            raise TimetableImportError(
                "Назва предмета з розкладу неоднозначно співпала з різними записами "
                f"у `Subject.short_name` та `Subject.name`: `{subject_name}`."
            )

        return short_name_match or name_match

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
