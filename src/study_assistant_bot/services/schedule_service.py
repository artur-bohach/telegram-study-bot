from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from study_assistant_bot.db.models import Lesson


class ScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_lessons_for_day(self, schedule_date: date) -> list[Lesson]:
        day_start, next_day_start = self._build_day_bounds(schedule_date)
        result = await self._session.execute(
            select(Lesson)
            .where(
                Lesson.starts_at >= day_start,
                Lesson.starts_at < next_day_start,
            )
            .order_by(Lesson.starts_at, Lesson.title)
        )
        return list(result.scalars())

    async def get_lessons_for_week(self, reference_date: date) -> list[Lesson]:
        week_start, week_end = self.get_week_bounds(reference_date)
        week_start_at, _ = self._build_day_bounds(week_start)
        _, week_end_at = self._build_day_bounds(week_end)

        result = await self._session.execute(
            select(Lesson)
            .where(
                Lesson.starts_at >= week_start_at,
                Lesson.starts_at < week_end_at,
            )
            .order_by(Lesson.starts_at, Lesson.title)
        )
        return list(result.scalars())

    @staticmethod
    def get_week_bounds(reference_date: date) -> tuple[date, date]:
        week_start = reference_date - timedelta(days=reference_date.weekday())
        week_end = week_start + timedelta(days=6)
        return week_start, week_end

    @staticmethod
    def _build_day_bounds(schedule_date: date) -> tuple[datetime, datetime]:
        day_start = datetime.combine(schedule_date, time.min)
        next_day_start = day_start + timedelta(days=1)
        return day_start, next_day_start
