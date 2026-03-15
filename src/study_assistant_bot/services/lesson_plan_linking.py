from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from study_assistant_bot.db.models import Lesson, Subject, SubjectPlanItem
from study_assistant_bot.enums import PlanLessonKind, SubjectTimetableNumberMode
from study_assistant_bot.lesson_title_parser import parse_lesson_identity, parse_lesson_kind

SEQUENCE_ELIGIBLE_KINDS = {
    PlanLessonKind.SEMINAR,
    PlanLessonKind.PRACTICAL,
}


class LessonPlanRelinkError(Exception):
    pass


class LessonPlanAnchorLinkError(Exception):
    pass


@dataclass(slots=True)
class LessonPlanRelinkSummary:
    scanned_lessons: int = 0
    linked_lessons: int = 0
    relinked_lessons: int = 0
    cleared_lessons: int = 0
    unchanged_lessons: int = 0
    parse_failures: int = 0
    missing_mode_cases: int = 0
    no_match_cases: int = 0
    ambiguous_match_cases: int = 0
    subject_code: str | None = None
    subject_name: str | None = None


@dataclass(slots=True)
class LessonPlanAnchorLinkSummary:
    scanned_lessons: int = 0
    linked_lessons: int = 0
    relinked_lessons: int = 0
    skipped_lessons: int = 0
    stopped_due_to_plan_end: int = 0
    subject_code: str | None = None
    subject_name: str | None = None
    anchor_lesson_id: int | None = None
    anchor_plan_item_id: int | None = None


class LessonPlanRelinkService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def relink_lessons(
        self,
        subject_code: str | None = None,
    ) -> LessonPlanRelinkSummary:
        async with self._session_factory() as session:
            async with session.begin():
                subject: Subject | None = None
                if subject_code is not None:
                    subject = await _resolve_subject_by_code(
                        session,
                        subject_code,
                        error_type=LessonPlanRelinkError,
                    )

                lessons = await self._load_lessons(session, subject_id=subject.id if subject else None)
                plan_item_lookups = await self._load_plan_item_lookups(
                    session,
                    subject_id=subject.id if subject else None,
                )

                summary = LessonPlanRelinkSummary(
                    scanned_lessons=len(lessons),
                    subject_code=subject.code if subject is not None else None,
                    subject_name=subject.name if subject is not None else None,
                )

                for lesson in lessons:
                    parse_result = parse_lesson_identity(lesson.title)
                    if parse_result.identity is None:
                        summary.parse_failures += 1
                        self._clear_lesson_link(lesson, summary)
                        continue

                    timetable_number_mode = _resolve_timetable_number_mode(lesson.subject)
                    if timetable_number_mode is None:
                        summary.missing_mode_cases += 1
                        self._clear_lesson_link(lesson, summary)
                        continue

                    if timetable_number_mode is SubjectTimetableNumberMode.SESSION:
                        matches = plan_item_lookups["session"].get(
                            (
                                lesson.subject_id,
                                parse_result.identity.lesson_kind,
                                parse_result.identity.topic_number,
                                parse_result.identity.timetable_number,
                            ),
                            [],
                        )
                    else:
                        matches = plan_item_lookups["schedule"].get(
                            (
                                lesson.subject_id,
                                parse_result.identity.lesson_kind,
                                parse_result.identity.topic_number,
                                parse_result.identity.timetable_number,
                            ),
                            [],
                        )

                    if not matches:
                        summary.no_match_cases += 1
                        self._clear_lesson_link(lesson, summary)
                        continue

                    if len(matches) > 1:
                        summary.ambiguous_match_cases += 1
                        self._clear_lesson_link(lesson, summary)
                        continue

                    self._set_lesson_link(lesson, matches[0], summary)

                await session.flush()
                return summary

    async def _load_lessons(
        self,
        session: AsyncSession,
        subject_id: int | None,
    ) -> list[Lesson]:
        query = (
            select(Lesson)
            .options(
                selectinload(Lesson.plan_item),
                selectinload(Lesson.subject),
            )
            .order_by(Lesson.id)
        )

        if subject_id is not None:
            query = query.where(Lesson.subject_id == subject_id)

        result = await session.execute(query)
        return list(result.scalars())

    async def _load_plan_item_lookups(
        self,
        session: AsyncSession,
        subject_id: int | None,
    ) -> dict[str, dict[tuple[int, PlanLessonKind, int, int], list[SubjectPlanItem]]]:
        query = select(SubjectPlanItem).order_by(SubjectPlanItem.id)
        if subject_id is not None:
            query = query.where(SubjectPlanItem.subject_id == subject_id)

        result = await session.execute(query)
        session_lookup: dict[tuple[int, PlanLessonKind, int, int], list[SubjectPlanItem]] = {}
        schedule_lookup: dict[tuple[int, PlanLessonKind, int, int], list[SubjectPlanItem]] = {}

        for plan_item in result.scalars():
            session_lookup_key = (
                plan_item.subject_id,
                plan_item.lesson_kind,
                plan_item.topic_number,
                plan_item.session_number,
            )
            session_lookup.setdefault(session_lookup_key, []).append(plan_item)

            if plan_item.schedule_lesson_number is not None:
                schedule_lookup_key = (
                    plan_item.subject_id,
                    plan_item.lesson_kind,
                    plan_item.topic_number,
                    plan_item.schedule_lesson_number,
                )
                schedule_lookup.setdefault(schedule_lookup_key, []).append(plan_item)

        return {
            "session": session_lookup,
            "schedule": schedule_lookup,
        }

    @staticmethod
    def _clear_lesson_link(
        lesson: Lesson,
        summary: LessonPlanRelinkSummary,
    ) -> None:
        if lesson.subject_plan_item_id is None:
            summary.unchanged_lessons += 1
            return

        lesson.subject_plan_item_id = None
        summary.cleared_lessons += 1

    @staticmethod
    def _set_lesson_link(
        lesson: Lesson,
        plan_item: SubjectPlanItem,
        summary: LessonPlanRelinkSummary,
    ) -> None:
        if lesson.subject_plan_item_id == plan_item.id:
            summary.unchanged_lessons += 1
            return

        if lesson.subject_plan_item_id is None:
            lesson.subject_plan_item_id = plan_item.id
            summary.linked_lessons += 1
            return

        lesson.subject_plan_item_id = plan_item.id
        summary.relinked_lessons += 1


class LessonPlanAnchorLinkService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def link_from_anchor(
        self,
        *,
        subject_code: str,
        anchor_lesson_id: int,
        anchor_plan_item_id: int,
    ) -> LessonPlanAnchorLinkSummary:
        async with self._session_factory() as session:
            async with session.begin():
                subject = await _resolve_subject_by_code(
                    session,
                    subject_code,
                    error_type=LessonPlanAnchorLinkError,
                )
                anchor_lesson = await self._load_anchor_lesson(
                    session,
                    subject_id=subject.id,
                    lesson_id=anchor_lesson_id,
                )
                anchor_lesson_kind = self._require_sequence_lesson_kind(anchor_lesson)
                anchor_plan_item = await self._load_anchor_plan_item(
                    session,
                    subject_id=subject.id,
                    plan_item_id=anchor_plan_item_id,
                )

                if anchor_plan_item.lesson_kind != anchor_lesson_kind:
                    raise LessonPlanAnchorLinkError(
                        "Якірна пара не збігається за типом заняття: "
                        f"`{anchor_lesson_kind.value}` != `{anchor_plan_item.lesson_kind.value}`."
                    )

                lessons = await self._load_future_lessons(session, anchor_lesson=anchor_lesson)
                plan_items = await self._load_future_plan_items(
                    session,
                    subject_id=subject.id,
                    anchor_plan_item_id=anchor_plan_item.id,
                )

                summary = LessonPlanAnchorLinkSummary(
                    subject_code=subject.code,
                    subject_name=subject.name,
                    anchor_lesson_id=anchor_lesson.id,
                    anchor_plan_item_id=anchor_plan_item.id,
                )

                plan_item_index = 0

                for lesson in lessons:
                    summary.scanned_lessons += 1
                    lesson_kind = parse_lesson_kind(lesson.title)
                    if lesson_kind not in SEQUENCE_ELIGIBLE_KINDS:
                        summary.skipped_lessons += 1
                        continue

                    if plan_item_index >= len(plan_items):
                        summary.stopped_due_to_plan_end += 1
                        continue

                    plan_item = plan_items[plan_item_index]
                    if lesson_kind != plan_item.lesson_kind:
                        raise LessonPlanAnchorLinkError(
                            "Послідовність втратила узгодження за типом заняття "
                            f"на lesson_id={lesson.id} і plan_item_id={plan_item.id}."
                        )

                    if lesson.subject_plan_item_id == plan_item.id:
                        summary.skipped_lessons += 1
                    elif lesson.subject_plan_item_id is None:
                        lesson.subject_plan_item_id = plan_item.id
                        summary.linked_lessons += 1
                    else:
                        lesson.subject_plan_item_id = plan_item.id
                        summary.relinked_lessons += 1

                    plan_item_index += 1

                await session.flush()
                return summary

    async def _load_anchor_lesson(
        self,
        session: AsyncSession,
        *,
        subject_id: int,
        lesson_id: int,
    ) -> Lesson:
        result = await session.execute(
            select(Lesson)
            .options(selectinload(Lesson.plan_item))
            .where(Lesson.id == lesson_id, Lesson.subject_id == subject_id)
        )
        lesson = result.scalar_one_or_none()
        if lesson is None:
            raise LessonPlanAnchorLinkError(
                f"Не вдалося знайти anchor lesson `{lesson_id}` у межах вибраного предмета."
            )

        return lesson

    async def _load_anchor_plan_item(
        self,
        session: AsyncSession,
        *,
        subject_id: int,
        plan_item_id: int,
    ) -> SubjectPlanItem:
        result = await session.execute(
            select(SubjectPlanItem).where(
                SubjectPlanItem.id == plan_item_id,
                SubjectPlanItem.subject_id == subject_id,
            )
        )
        plan_item = result.scalar_one_or_none()
        if plan_item is None:
            raise LessonPlanAnchorLinkError(
                f"Не вдалося знайти anchor plan item `{plan_item_id}` у межах вибраного предмета."
            )

        if plan_item.lesson_kind not in SEQUENCE_ELIGIBLE_KINDS:
            raise LessonPlanAnchorLinkError(
                "Anchor plan item має бути семінаром або практичним заняттям."
            )

        return plan_item

    async def _load_future_lessons(
        self,
        session: AsyncSession,
        *,
        anchor_lesson: Lesson,
    ) -> list[Lesson]:
        result = await session.execute(
            select(Lesson)
            .options(selectinload(Lesson.plan_item))
            .where(Lesson.subject_id == anchor_lesson.subject_id)
            .where(
                or_(
                    Lesson.starts_at > anchor_lesson.starts_at,
                    and_(
                        Lesson.starts_at == anchor_lesson.starts_at,
                        Lesson.id >= anchor_lesson.id,
                    ),
                )
            )
            .order_by(Lesson.starts_at, Lesson.id)
        )
        return list(result.scalars())

    async def _load_future_plan_items(
        self,
        session: AsyncSession,
        *,
        subject_id: int,
        anchor_plan_item_id: int,
    ) -> list[SubjectPlanItem]:
        result = await session.execute(
            select(SubjectPlanItem)
            .where(
                SubjectPlanItem.subject_id == subject_id,
                SubjectPlanItem.id >= anchor_plan_item_id,
            )
            .order_by(SubjectPlanItem.id)
        )

        return [
            plan_item
            for plan_item in result.scalars()
            if plan_item.lesson_kind in SEQUENCE_ELIGIBLE_KINDS
        ]

    @staticmethod
    def _require_sequence_lesson_kind(lesson: Lesson) -> PlanLessonKind:
        lesson_kind = parse_lesson_kind(lesson.title)
        if lesson_kind not in SEQUENCE_ELIGIBLE_KINDS:
            raise LessonPlanAnchorLinkError(
                "Anchor lesson має бути семінаром або практичним заняттям з "
                "розпізнаваним типом у назві."
            )

        return lesson_kind


async def _resolve_subject_by_code(
    session: AsyncSession,
    subject_code: str,
    *,
    error_type: type[Exception],
) -> Subject:
    result = await session.execute(
        select(Subject).where(Subject.code == subject_code).order_by(Subject.id)
    )
    subjects = list(result.scalars())

    if not subjects:
        raise error_type(f"Не вдалося знайти предмет з кодом `{subject_code}`.")

    if len(subjects) > 1:
        raise error_type(
            f"Знайдено кілька предметів з кодом `{subject_code}`. Операцію зупинено."
        )

    return subjects[0]


def _resolve_timetable_number_mode(subject: Subject | None) -> SubjectTimetableNumberMode | None:
    if subject is None:
        return None

    timetable_number_mode = subject.timetable_number_mode
    if isinstance(timetable_number_mode, SubjectTimetableNumberMode):
        return timetable_number_mode

    if isinstance(timetable_number_mode, str):
        normalized_value = timetable_number_mode.strip()
        if normalized_value:
            try:
                return SubjectTimetableNumberMode(normalized_value)
            except ValueError:
                return None

    return None
