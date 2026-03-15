from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from study_assistant_bot.db.models import (
    PlanItemAssignment,
    PlanItemQuestion,
    Subject,
    SubjectPlanItem,
)
from study_assistant_bot.enums import PlanLessonKind, SubjectTimetableNumberMode


class SubjectPlanImportError(Exception):
    pass


class SubjectPlanValidationError(SubjectPlanImportError):
    pass


class SubjectPlanResolutionError(SubjectPlanImportError):
    pass


class DuplicateSubjectPlanSourceError(SubjectPlanImportError):
    pass


@dataclass(slots=True)
class ValidatedSubjectReference:
    name: str
    short_name: str
    code: str
    timetable_number_mode: SubjectTimetableNumberMode | None
    timetable_number_mode_provided: bool = False


@dataclass(slots=True)
class ValidatedPlanItemAssignment:
    task_number: int | None
    title: str
    condition: str | None
    question: str | None


@dataclass(slots=True)
class ValidatedPlanItem:
    lesson_kind: PlanLessonKind
    topic_number: int
    session_number: int
    schedule_lesson_number: int | None
    topic_title: str
    questions: list[str]
    assignments: list[ValidatedPlanItemAssignment]


@dataclass(slots=True)
class ValidatedSubjectPlanFile:
    path: Path
    subject: ValidatedSubjectReference
    plan_items: list[ValidatedPlanItem]


@dataclass(slots=True)
class SubjectPlanSyncStats:
    created_plan_items: int = 0
    updated_plan_items: int = 0
    deleted_plan_items: int = 0
    created_questions: int = 0
    updated_questions: int = 0
    deleted_questions: int = 0
    created_assignments: int = 0
    updated_assignments: int = 0
    deleted_assignments: int = 0

    def merge(self, other: SubjectPlanSyncStats) -> None:
        self.created_plan_items += other.created_plan_items
        self.updated_plan_items += other.updated_plan_items
        self.deleted_plan_items += other.deleted_plan_items
        self.created_questions += other.created_questions
        self.updated_questions += other.updated_questions
        self.deleted_questions += other.deleted_questions
        self.created_assignments += other.created_assignments
        self.updated_assignments += other.updated_assignments
        self.deleted_assignments += other.deleted_assignments


@dataclass(slots=True)
class SubjectPlanImportFileResult:
    path: Path
    success: bool
    subject_name: str | None = None
    matched_by: str | None = None
    stats: SubjectPlanSyncStats = field(default_factory=SubjectPlanSyncStats)
    code_backfilled: str | None = None
    error: str | None = None
    subject_id: int | None = None


@dataclass(slots=True)
class SubjectPlanImportSummary:
    directory: Path
    files_discovered: int = 0
    imported_files: int = 0
    failed_files: int = 0
    code_backfills: int = 0
    stats: SubjectPlanSyncStats = field(default_factory=SubjectPlanSyncStats)
    file_results: list[SubjectPlanImportFileResult] = field(default_factory=list)


@dataclass(slots=True)
class ResolvedSubject:
    subject: Subject
    matched_by: str
    code_backfilled: str | None = None


class SubjectPlanImportService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def import_from_directory(self, directory_path: Path | str) -> SubjectPlanImportSummary:
        directory = Path(directory_path).expanduser().resolve()
        file_paths = sorted(
            (path for path in directory.glob("*.json") if path.is_file()),
            key=lambda path: path.name,
        )
        summary = SubjectPlanImportSummary(
            directory=directory,
            files_discovered=len(file_paths),
        )
        processed_subjects: dict[int, Path] = {}

        for file_path in file_paths:
            try:
                validated_file = self._load_validated_file(file_path)
                result = await self._import_validated_file(validated_file, processed_subjects)
            except SubjectPlanImportError as exc:
                result = SubjectPlanImportFileResult(
                    path=file_path,
                    success=False,
                    error=str(exc),
                )
            except Exception as exc:
                result = SubjectPlanImportFileResult(
                    path=file_path,
                    success=False,
                    error=f"{type(exc).__name__}: {exc}",
                )

            summary.file_results.append(result)

            if result.success:
                summary.imported_files += 1
                summary.stats.merge(result.stats)

                if result.subject_id is not None:
                    processed_subjects[result.subject_id] = result.path

                if result.code_backfilled:
                    summary.code_backfills += 1
            else:
                summary.failed_files += 1

        return summary

    def _load_validated_file(self, file_path: Path) -> ValidatedSubjectPlanFile:
        try:
            raw_data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SubjectPlanValidationError(
                f"Невалідний JSON: {exc.msg} (рядок {exc.lineno}, стовпчик {exc.colno})."
            ) from exc

        if not isinstance(raw_data, dict):
            raise SubjectPlanValidationError("Кореневий JSON-обʼєкт має бути словником.")

        raw_subject = raw_data.get("subject")
        if not isinstance(raw_subject, dict):
            raise SubjectPlanValidationError("Поле `subject` має бути обʼєктом.")

        subject = ValidatedSubjectReference(
            name=self._require_text(raw_subject.get("name"), "subject.name"),
            short_name=self._require_text(raw_subject.get("short_name"), "subject.short_name"),
            code=self._require_text(raw_subject.get("code"), "subject.code"),
            timetable_number_mode=self._parse_optional_timetable_number_mode(
                raw_subject.get("timetable_number_mode"),
                field_name="subject.timetable_number_mode",
            ),
            timetable_number_mode_provided="timetable_number_mode" in raw_subject,
        )

        raw_plan_items = raw_data.get("plan_items")
        if not isinstance(raw_plan_items, list):
            raise SubjectPlanValidationError("Поле `plan_items` має бути списком.")

        plan_items: list[ValidatedPlanItem] = []
        seen_item_keys: set[tuple[PlanLessonKind, int, int]] = set()

        for index, raw_item in enumerate(raw_plan_items, start=1):
            item = self._validate_plan_item(raw_item, index=index)
            item_key = (item.lesson_kind, item.topic_number, item.session_number)

            if item_key in seen_item_keys:
                raise SubjectPlanValidationError(
                    "У файлі дублюється планове заняття з однаковими "
                    "`lesson_kind`, `topic_number`, `session_number`."
                )

            seen_item_keys.add(item_key)
            plan_items.append(item)

        return ValidatedSubjectPlanFile(
            path=file_path,
            subject=subject,
            plan_items=plan_items,
        )

    def _validate_plan_item(self, raw_item: Any, index: int) -> ValidatedPlanItem:
        if not isinstance(raw_item, dict):
            raise SubjectPlanValidationError(
                f"Елемент `plan_items[{index}]` має бути обʼєктом."
            )

        lesson_kind = self._parse_lesson_kind(
            raw_item.get("lesson_kind"),
            field_name=f"plan_items[{index}].lesson_kind",
        )
        topic_number = self._parse_positive_int(
            raw_item.get("topic_number"),
            field_name=f"plan_items[{index}].topic_number",
        )
        session_number = self._parse_positive_int(
            raw_item.get("session_number"),
            field_name=f"plan_items[{index}].session_number",
        )
        schedule_lesson_number = self._parse_optional_positive_int(
            raw_item.get("schedule_lesson_number"),
            field_name=f"plan_items[{index}].schedule_lesson_number",
        )
        topic_title = self._require_text(
            raw_item.get("topic_title"),
            field_name=f"plan_items[{index}].topic_title",
        )

        raw_questions = raw_item.get("questions", [])
        if not isinstance(raw_questions, list):
            raise SubjectPlanValidationError(
                f"Поле `plan_items[{index}].questions` має бути списком."
            )

        questions = [
            self._require_text(
                raw_question,
                field_name=f"plan_items[{index}].questions[{question_index}]",
            )
            for question_index, raw_question in enumerate(raw_questions, start=1)
        ]

        raw_assignments = raw_item.get("assignments", [])
        if not isinstance(raw_assignments, list):
            raise SubjectPlanValidationError(
                f"Поле `plan_items[{index}].assignments` має бути списком."
            )

        if lesson_kind is not PlanLessonKind.PRACTICAL and raw_assignments:
            raise SubjectPlanValidationError(
                f"Поле `plan_items[{index}].assignments` дозволене лише для `practical`."
            )

        assignments = [
            self._validate_assignment(
                raw_assignment,
                item_index=index,
                assignment_index=assignment_index,
            )
            for assignment_index, raw_assignment in enumerate(raw_assignments, start=1)
        ]

        return ValidatedPlanItem(
            lesson_kind=lesson_kind,
            topic_number=topic_number,
            session_number=session_number,
            schedule_lesson_number=schedule_lesson_number,
            topic_title=topic_title,
            questions=questions,
            assignments=assignments,
        )

    def _validate_assignment(
        self,
        raw_assignment: Any,
        item_index: int,
        assignment_index: int,
    ) -> ValidatedPlanItemAssignment:
        if not isinstance(raw_assignment, dict):
            raise SubjectPlanValidationError(
                f"Елемент `plan_items[{item_index}].assignments[{assignment_index}]` "
                "має бути обʼєктом."
            )

        raw_task_number = raw_assignment.get("task_number")
        task_number: int | None
        if raw_task_number in (None, ""):
            task_number = None
        else:
            task_number = self._parse_positive_int(
                raw_task_number,
                field_name=(
                    f"plan_items[{item_index}].assignments[{assignment_index}].task_number"
                ),
            )

        return ValidatedPlanItemAssignment(
            task_number=task_number,
            title=self._require_text(
                raw_assignment.get("title"),
                field_name=f"plan_items[{item_index}].assignments[{assignment_index}].title",
            ),
            condition=self._normalize_optional_text(
                raw_assignment.get("condition"),
                field_name=f"plan_items[{item_index}].assignments[{assignment_index}].condition",
            ),
            question=self._normalize_optional_text(
                raw_assignment.get("question"),
                field_name=f"plan_items[{item_index}].assignments[{assignment_index}].question",
            ),
        )

    async def _import_validated_file(
        self,
        validated_file: ValidatedSubjectPlanFile,
        processed_subjects: dict[int, Path],
    ) -> SubjectPlanImportFileResult:
        async with self._session_factory() as session:
            async with session.begin():
                resolved_subject = await self._resolve_subject(session, validated_file.subject)

                if resolved_subject.subject.id in processed_subjects:
                    existing_path = processed_subjects[resolved_subject.subject.id]
                    raise DuplicateSubjectPlanSourceError(
                        "Знайдено друге джерело для того самого предмета: "
                        f"{existing_path.name} і {validated_file.path.name}."
                    )

                stats = await self._sync_subject_plan(
                    session=session,
                    subject=resolved_subject.subject,
                    plan_items=validated_file.plan_items,
                )

            return SubjectPlanImportFileResult(
                path=validated_file.path,
                success=True,
                subject_name=resolved_subject.subject.name,
                matched_by=resolved_subject.matched_by,
                stats=stats,
                code_backfilled=resolved_subject.code_backfilled,
                subject_id=resolved_subject.subject.id,
            )

    async def _resolve_subject(
        self,
        session: AsyncSession,
        subject_reference: ValidatedSubjectReference,
    ) -> ResolvedSubject:
        code_matches = await self._find_subjects_by_field(
            session=session,
            field_name="code",
            value=subject_reference.code,
        )
        if code_matches:
            subject = self._require_single_match(
                code_matches,
                lookup_label=f"кодом `{subject_reference.code}`",
            )
            return await self._finalize_subject_match(
                session=session,
                subject=subject,
                subject_reference=subject_reference,
                matched_by="code",
            )

        name_matches = await self._find_subjects_by_field(
            session=session,
            field_name="name",
            value=subject_reference.name,
        )

        short_name_matches = await self._find_subjects_by_field(
            session=session,
            field_name="short_name",
            value=subject_reference.short_name,
        )

        name_subject: Subject | None = None
        short_name_subject: Subject | None = None

        if name_matches:
            name_subject = self._require_single_match(
                name_matches,
                lookup_label=f"назвою `{subject_reference.name}`",
            )

        if short_name_matches:
            short_name_subject = self._require_single_match(
                short_name_matches,
                lookup_label=f"короткою назвою `{subject_reference.short_name}`",
            )

        if name_subject is not None and short_name_subject is not None:
            if name_subject.id != short_name_subject.id:
                raise SubjectPlanResolutionError(
                    "JSON `subject.name` і `subject.short_name` вказують на різні "
                    "предмети в базі. Імпорт зупинено."
                )

            return await self._finalize_subject_match(
                session=session,
                subject=name_subject,
                subject_reference=subject_reference,
                matched_by="name",
            )

        if name_subject is not None:
            return await self._finalize_subject_match(
                session=session,
                subject=name_subject,
                subject_reference=subject_reference,
                matched_by="name",
            )

        if short_name_subject is not None:
            return await self._finalize_subject_match(
                session=session,
                subject=short_name_subject,
                subject_reference=subject_reference,
                matched_by="short_name",
            )

        raise SubjectPlanResolutionError(
            "Не вдалося знайти відповідний `Subject` за `code`, `name` або `short_name`."
        )

    async def _find_subjects_by_field(
        self,
        session: AsyncSession,
        field_name: str,
        value: str,
    ) -> list[Subject]:
        if field_name == "code":
            column = Subject.code
        elif field_name == "name":
            column = Subject.name
        elif field_name == "short_name":
            column = Subject.short_name
        else:
            raise ValueError(f"Unsupported subject field: {field_name}")

        result = await session.execute(
            select(Subject).where(column == value).order_by(Subject.id)
        )
        return list(result.scalars())

    def _require_single_match(
        self,
        subjects: list[Subject],
        lookup_label: str,
    ) -> Subject:
        if len(subjects) > 1:
            raise SubjectPlanResolutionError(
                f"Знайдено кілька предметів за {lookup_label}. Імпорт зупинено."
            )

        return subjects[0]

    async def _finalize_subject_match(
        self,
        session: AsyncSession,
        subject: Subject,
        subject_reference: ValidatedSubjectReference,
        matched_by: str,
    ) -> ResolvedSubject:
        if subject.code:
            if subject.code != subject_reference.code:
                raise SubjectPlanResolutionError(
                    "Код предмета в базі конфліктує з кодом у JSON: "
                    f"`{subject.code}` != `{subject_reference.code}`."
                )

            code_backfilled = None
        else:
            subject.code = subject_reference.code
            code_backfilled = subject_reference.code

        await self._ensure_subject_identity_available(
            session=session,
            subject=subject,
            subject_reference=subject_reference,
        )
        subject.name = subject_reference.name
        subject.short_name = subject_reference.short_name
        if subject_reference.timetable_number_mode_provided:
            subject.timetable_number_mode = subject_reference.timetable_number_mode

        return ResolvedSubject(
            subject=subject,
            matched_by=matched_by,
            code_backfilled=code_backfilled,
        )

    async def _ensure_subject_identity_available(
        self,
        session: AsyncSession,
        subject: Subject,
        subject_reference: ValidatedSubjectReference,
    ) -> None:
        result = await session.execute(
            select(Subject)
            .where(Subject.id != subject.id)
            .where(
                or_(
                    Subject.name == subject_reference.name,
                    Subject.short_name == subject_reference.short_name,
                )
            )
            .order_by(Subject.id)
        )
        conflicting_subjects = list(result.scalars())

        for conflicting_subject in conflicting_subjects:
            if conflicting_subject.name == subject_reference.name:
                raise SubjectPlanResolutionError(
                    "Неможливо нормалізувати предмет: повна назва вже зайнята іншим "
                    f"`Subject` (`{subject_reference.name}`)."
                )

            if conflicting_subject.short_name == subject_reference.short_name:
                raise SubjectPlanResolutionError(
                    "Неможливо нормалізувати предмет: коротка назва вже зайнята іншим "
                    f"`Subject` (`{subject_reference.short_name}`)."
                )

    async def _sync_subject_plan(
        self,
        session: AsyncSession,
        subject: Subject,
        plan_items: list[ValidatedPlanItem],
    ) -> SubjectPlanSyncStats:
        result = await session.execute(
            select(SubjectPlanItem)
            .options(
                selectinload(SubjectPlanItem.questions),
                selectinload(SubjectPlanItem.assignments),
            )
            .where(SubjectPlanItem.subject_id == subject.id)
        )
        existing_items = list(result.scalars())
        existing_by_key = {
            self._build_plan_item_key(
                lesson_kind=item.lesson_kind,
                topic_number=item.topic_number,
                session_number=item.session_number,
            ): item
            for item in existing_items
        }
        imported_keys: set[tuple[PlanLessonKind, int, int]] = set()
        stats = SubjectPlanSyncStats()

        for validated_item in plan_items:
            item_key = self._build_plan_item_key(
                lesson_kind=validated_item.lesson_kind,
                topic_number=validated_item.topic_number,
                session_number=validated_item.session_number,
            )
            imported_keys.add(item_key)
            plan_item = existing_by_key.get(item_key)

            if plan_item is None:
                plan_item = SubjectPlanItem(
                    subject_id=subject.id,
                    lesson_kind=validated_item.lesson_kind,
                    topic_number=validated_item.topic_number,
                    session_number=validated_item.session_number,
                    schedule_lesson_number=validated_item.schedule_lesson_number,
                    topic_title=validated_item.topic_title,
                )
                session.add(plan_item)
                existing_by_key[item_key] = plan_item
                stats.created_plan_items += 1
            else:
                changed = False

                if plan_item.schedule_lesson_number != validated_item.schedule_lesson_number:
                    plan_item.schedule_lesson_number = validated_item.schedule_lesson_number
                    changed = True

                if plan_item.topic_title != validated_item.topic_title:
                    plan_item.topic_title = validated_item.topic_title
                    changed = True

                if changed:
                    stats.updated_plan_items += 1

            await self._sync_questions(
                session=session,
                plan_item=plan_item,
                questions=validated_item.questions,
                stats=stats,
            )
            await self._sync_assignments(
                session=session,
                plan_item=plan_item,
                assignments=validated_item.assignments,
                stats=stats,
            )

        for item_key, plan_item in existing_by_key.items():
            if item_key in imported_keys:
                continue

            stats.deleted_plan_items += 1
            stats.deleted_questions += len(plan_item.questions)
            stats.deleted_assignments += len(plan_item.assignments)
            await session.delete(plan_item)

        return stats

    async def _sync_questions(
        self,
        session: AsyncSession,
        plan_item: SubjectPlanItem,
        questions: list[str],
        stats: SubjectPlanSyncStats,
    ) -> None:
        existing_by_order = {
            question.order_index: question for question in plan_item.questions
        }
        imported_indexes: set[int] = set()

        for order_index, question_text in enumerate(questions, start=1):
            imported_indexes.add(order_index)
            existing_question = existing_by_order.get(order_index)

            if existing_question is None:
                plan_item.questions.append(
                    PlanItemQuestion(order_index=order_index, text=question_text)
                )
                stats.created_questions += 1
                continue

            if existing_question.text != question_text:
                existing_question.text = question_text
                stats.updated_questions += 1

        for order_index, existing_question in existing_by_order.items():
            if order_index in imported_indexes:
                continue

            await session.delete(existing_question)
            stats.deleted_questions += 1

    async def _sync_assignments(
        self,
        session: AsyncSession,
        plan_item: SubjectPlanItem,
        assignments: list[ValidatedPlanItemAssignment],
        stats: SubjectPlanSyncStats,
    ) -> None:
        existing_by_order = {
            assignment.order_index: assignment for assignment in plan_item.assignments
        }
        imported_indexes: set[int] = set()

        for order_index, validated_assignment in enumerate(assignments, start=1):
            imported_indexes.add(order_index)
            existing_assignment = existing_by_order.get(order_index)

            if existing_assignment is None:
                plan_item.assignments.append(
                    PlanItemAssignment(
                        order_index=order_index,
                        task_number=validated_assignment.task_number,
                        title=validated_assignment.title,
                        condition=validated_assignment.condition,
                        question=validated_assignment.question,
                    )
                )
                stats.created_assignments += 1
                continue

            changed = False

            if existing_assignment.task_number != validated_assignment.task_number:
                existing_assignment.task_number = validated_assignment.task_number
                changed = True

            if existing_assignment.title != validated_assignment.title:
                existing_assignment.title = validated_assignment.title
                changed = True

            if existing_assignment.condition != validated_assignment.condition:
                existing_assignment.condition = validated_assignment.condition
                changed = True

            if existing_assignment.question != validated_assignment.question:
                existing_assignment.question = validated_assignment.question
                changed = True

            if changed:
                stats.updated_assignments += 1

        for order_index, existing_assignment in existing_by_order.items():
            if order_index in imported_indexes:
                continue

            await session.delete(existing_assignment)
            stats.deleted_assignments += 1

    @staticmethod
    def _build_plan_item_key(
        lesson_kind: PlanLessonKind,
        topic_number: int,
        session_number: int,
    ) -> tuple[PlanLessonKind, int, int]:
        return lesson_kind, topic_number, session_number

    @staticmethod
    def _parse_lesson_kind(value: Any, field_name: str) -> PlanLessonKind:
        normalized_value = SubjectPlanImportService._require_text(value, field_name)

        try:
            return PlanLessonKind(normalized_value)
        except ValueError as exc:
            raise SubjectPlanValidationError(
                f"Поле `{field_name}` має бути одним із: lecture, seminar, practical."
            ) from exc

    @staticmethod
    def _parse_positive_int(value: Any, field_name: str) -> int:
        if isinstance(value, bool):
            raise SubjectPlanValidationError(
                f"Поле `{field_name}` має бути цілим числом."
            )

        try:
            parsed_value = int(value)
        except (TypeError, ValueError) as exc:
            raise SubjectPlanValidationError(
                f"Поле `{field_name}` має бути цілим числом."
            ) from exc

        if parsed_value <= 0:
            raise SubjectPlanValidationError(
                f"Поле `{field_name}` має бути додатним цілим числом."
            )

        return parsed_value

    @staticmethod
    def _parse_optional_positive_int(value: Any, field_name: str) -> int | None:
        if value in (None, ""):
            return None

        return SubjectPlanImportService._parse_positive_int(value, field_name)

    @staticmethod
    def _parse_optional_timetable_number_mode(
        value: Any,
        field_name: str,
    ) -> SubjectTimetableNumberMode | None:
        if value is None:
            return None

        normalized_value = SubjectPlanImportService._require_text(value, field_name)

        try:
            return SubjectTimetableNumberMode(normalized_value)
        except ValueError as exc:
            raise SubjectPlanValidationError(
                f"Поле `{field_name}` має бути одним із: session, schedule."
            ) from exc

    @staticmethod
    def _require_text(value: Any, field_name: str) -> str:
        if not isinstance(value, str):
            raise SubjectPlanValidationError(
                f"Поле `{field_name}` має бути непорожнім рядком."
            )

        normalized_value = SubjectPlanImportService._normalize_text(value)
        if not normalized_value:
            raise SubjectPlanValidationError(
                f"Поле `{field_name}` має бути непорожнім рядком."
            )

        return normalized_value

    @staticmethod
    def _normalize_optional_text(value: Any, field_name: str) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise SubjectPlanValidationError(
                f"Поле `{field_name}` має бути рядком або null."
            )

        normalized_value = SubjectPlanImportService._normalize_text(value)
        return normalized_value or None

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(value.split())
