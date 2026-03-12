from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from study_assistant_bot.db.models import Lesson, Subject, SubjectPlanItem
from study_assistant_bot.lesson_title_parser import parse_lesson_identity


class LessonPlanRelinkError(Exception):
    pass


@dataclass(slots=True)
class LessonPlanRelinkSummary:
    scanned_lessons: int = 0
    linked_lessons: int = 0
    relinked_lessons: int = 0
    cleared_lessons: int = 0
    unchanged_lessons: int = 0
    parse_failures: int = 0
    no_match_cases: int = 0
    ambiguous_match_cases: int = 0
    subject_code: str | None = None
    subject_name: str | None = None


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
                    subject = await self._resolve_subject_by_code(session, subject_code)

                lessons = await self._load_lessons(session, subject_id=subject.id if subject else None)
                plan_item_lookup = await self._load_plan_item_lookup(
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

                    lookup_key = (
                        lesson.subject_id,
                        parse_result.identity.lesson_kind,
                        parse_result.identity.topic_number,
                        parse_result.identity.session_number,
                    )
                    matches = plan_item_lookup.get(lookup_key, [])

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

    async def _resolve_subject_by_code(
        self,
        session: AsyncSession,
        subject_code: str,
    ) -> Subject:
        result = await session.execute(
            select(Subject).where(Subject.code == subject_code).order_by(Subject.id)
        )
        subjects = list(result.scalars())

        if not subjects:
            raise LessonPlanRelinkError(
                f"Не вдалося знайти предмет з кодом `{subject_code}`."
            )

        if len(subjects) > 1:
            raise LessonPlanRelinkError(
                f"Знайдено кілька предметів з кодом `{subject_code}`. Relink зупинено."
            )

        return subjects[0]

    async def _load_lessons(
        self,
        session: AsyncSession,
        subject_id: int | None,
    ) -> list[Lesson]:
        query = (
            select(Lesson)
            .options(selectinload(Lesson.plan_item))
            .order_by(Lesson.id)
        )

        if subject_id is not None:
            query = query.where(Lesson.subject_id == subject_id)

        result = await session.execute(query)
        return list(result.scalars())

    async def _load_plan_item_lookup(
        self,
        session: AsyncSession,
        subject_id: int | None,
    ) -> dict[tuple[int, object, int, int], list[SubjectPlanItem]]:
        query = select(SubjectPlanItem).order_by(SubjectPlanItem.id)
        if subject_id is not None:
            query = query.where(SubjectPlanItem.subject_id == subject_id)

        result = await session.execute(query)
        lookup: dict[tuple[int, object, int, int], list[SubjectPlanItem]] = {}

        for plan_item in result.scalars():
            lookup_key = (
                plan_item.subject_id,
                plan_item.lesson_kind,
                plan_item.topic_number,
                plan_item.session_number,
            )
            lookup.setdefault(lookup_key, []).append(plan_item)

        return lookup

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
