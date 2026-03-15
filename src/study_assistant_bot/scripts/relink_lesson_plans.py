from __future__ import annotations

import argparse
import asyncio
import sys

from study_assistant_bot.config import get_settings
from study_assistant_bot.db import build_engine, build_session_factory, verify_database_ready
from study_assistant_bot.services import (
    LessonPlanRelinkError,
    LessonPlanRelinkService,
    LessonPlanRelinkSummary,
)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Повторне звʼязування занять з елементами навчального плану "
            "за структурованими позначками розкладу."
        ),
    )
    parser.add_argument(
        "--subject-code",
        dest="subject_code",
        help="Код предмета для relink лише в межах одного Subject.",
    )
    return parser


async def relink_lesson_plans(subject_code: str | None) -> str:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)

    try:
        await verify_database_ready(engine)
        service = LessonPlanRelinkService(session_factory)
        summary = await service.relink_lessons(subject_code=subject_code)
        return format_summary(summary)
    finally:
        await engine.dispose()


def format_summary(summary: LessonPlanRelinkSummary) -> str:
    scope_label = "усі заняття"
    if summary.subject_code is not None:
        scope_label = f"{summary.subject_name} ({summary.subject_code})"

    return "\n".join(
        [
            "Relink занять завершено.",
            f"Область: {scope_label}",
            f"Перевірено занять: {summary.scanned_lessons}",
            f"Нових звʼязків: {summary.linked_lessons}",
            f"Оновлено звʼязків: {summary.relinked_lessons}",
            f"Очищено звʼязків: {summary.cleared_lessons}",
            f"Без змін: {summary.unchanged_lessons}",
            f"Не вдалося розпарсити: {summary.parse_failures}",
            f"Без `timetable_number_mode`: {summary.missing_mode_cases}",
            f"Без збігу в плані: {summary.no_match_cases}",
            f"Неоднозначних збігів: {summary.ambiguous_match_cases}",
        ]
    )


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    try:
        summary = asyncio.run(relink_lesson_plans(subject_code=args.subject_code))
    except LessonPlanRelinkError as exc:
        print(f"Relink зупинено: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except Exception as exc:
        print(f"Не вдалося виконати relink занять: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(summary)


if __name__ == "__main__":
    main()
