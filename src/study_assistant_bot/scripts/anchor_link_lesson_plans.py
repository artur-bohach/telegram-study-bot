from __future__ import annotations

import argparse
import asyncio
import sys

from study_assistant_bot.config import get_settings
from study_assistant_bot.db import build_engine, build_session_factory, verify_database_ready
from study_assistant_bot.services import (
    LessonPlanAnchorLinkError,
    LessonPlanAnchorLinkService,
    LessonPlanAnchorLinkSummary,
)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Ручне послідовне звʼязування семінарів і практичних занять "
            "від заданого anchor."
        ),
    )
    parser.add_argument(
        "--subject-code",
        required=True,
        help="Код предмета, у межах якого виконується послідовне link-звʼязування.",
    )
    parser.add_argument(
        "--anchor-lesson-id",
        required=True,
        type=int,
        help="ID заняття `Lesson`, з якого починається послідовність.",
    )
    parser.add_argument(
        "--anchor-plan-item-id",
        required=True,
        type=int,
        help="ID елемента `SubjectPlanItem`, який є anchor для послідовності.",
    )
    return parser


async def anchor_link_lesson_plans(
    *,
    subject_code: str,
    anchor_lesson_id: int,
    anchor_plan_item_id: int,
) -> str:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)

    try:
        await verify_database_ready(engine)
        service = LessonPlanAnchorLinkService(session_factory)
        summary = await service.link_from_anchor(
            subject_code=subject_code,
            anchor_lesson_id=anchor_lesson_id,
            anchor_plan_item_id=anchor_plan_item_id,
        )
        return format_summary(summary)
    finally:
        await engine.dispose()


def format_summary(summary: LessonPlanAnchorLinkSummary) -> str:
    scope_label = "невідомий предмет"
    if summary.subject_code is not None:
        scope_label = f"{summary.subject_name} ({summary.subject_code})"

    return "\n".join(
        [
            "Anchor-link занять завершено.",
            f"Область: {scope_label}",
            f"Anchor lesson: {summary.anchor_lesson_id}",
            f"Anchor plan item: {summary.anchor_plan_item_id}",
            f"Перевірено занять: {summary.scanned_lessons}",
            f"Нових звʼязків: {summary.linked_lessons}",
            f"Оновлено звʼязків: {summary.relinked_lessons}",
            f"Пропущено: {summary.skipped_lessons}",
            (
                "Зупинено через нестачу елементів плану: "
                f"{summary.stopped_due_to_plan_end}"
            ),
        ]
    )


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    try:
        summary = asyncio.run(
            anchor_link_lesson_plans(
                subject_code=args.subject_code,
                anchor_lesson_id=args.anchor_lesson_id,
                anchor_plan_item_id=args.anchor_plan_item_id,
            )
        )
    except LessonPlanAnchorLinkError as exc:
        print(f"Anchor-link зупинено: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except Exception as exc:
        print(f"Не вдалося виконати anchor-link занять: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(summary)


if __name__ == "__main__":
    main()
