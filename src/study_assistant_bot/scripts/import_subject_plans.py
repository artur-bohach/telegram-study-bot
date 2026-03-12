from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

from study_assistant_bot.config import get_settings
from study_assistant_bot.db import build_engine, build_session_factory, verify_database_ready
from study_assistant_bot.services import SubjectPlanImportSummary, SubjectPlanImportService

MATCH_LABELS = {
    "code": "код",
    "name": "назва",
    "short_name": "коротка назва",
}


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Імпорт навчальних планів з JSON-файлів до бази даних.",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Шлях до каталогу з JSON-файлами навчальних планів.",
    )
    return parser


async def import_subject_plans(path: Path) -> SubjectPlanImportSummary:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)

    try:
        await verify_database_ready(engine)
        service = SubjectPlanImportService(session_factory)
        return await service.import_from_directory(path)
    finally:
        await engine.dispose()


def format_summary(summary: SubjectPlanImportSummary) -> str:
    lines = [
        "Імпорт навчальних планів завершено.",
        f"Каталог: {summary.directory}",
        f"Знайдено файлів: {summary.files_discovered}",
        f"Успішно імпортовано: {summary.imported_files}",
        f"Файлів з помилками: {summary.failed_files}",
        f"Заповнено кодів предметів: {summary.code_backfills}",
        f"Планові заняття: +{summary.stats.created_plan_items} ~{summary.stats.updated_plan_items} -{summary.stats.deleted_plan_items}",
        f"Питання: +{summary.stats.created_questions} ~{summary.stats.updated_questions} -{summary.stats.deleted_questions}",
        f"Практичні завдання: +{summary.stats.created_assignments} ~{summary.stats.updated_assignments} -{summary.stats.deleted_assignments}",
    ]

    if summary.file_results:
        lines.append("")
        lines.append("Файли:")

        for result in summary.file_results:
            if result.success:
                match_label = MATCH_LABELS.get(result.matched_by or "", result.matched_by or "-")
                lines.append(
                    f"- Успіх: {result.path.name} -> {result.subject_name} "
                    f"(співставлення: {match_label})"
                )
                lines.append(
                    f"  Планові заняття: +{result.stats.created_plan_items} "
                    f"~{result.stats.updated_plan_items} -{result.stats.deleted_plan_items}"
                )
                lines.append(
                    f"  Питання: +{result.stats.created_questions} "
                    f"~{result.stats.updated_questions} -{result.stats.deleted_questions}"
                )
                lines.append(
                    f"  Практичні завдання: +{result.stats.created_assignments} "
                    f"~{result.stats.updated_assignments} "
                    f"-{result.stats.deleted_assignments}"
                )

                if result.code_backfilled:
                    lines.append(f"  Заповнено Subject.code: {result.code_backfilled}")
            else:
                lines.append(f"- Помилка: {result.path.name} -> {result.error}")

    return "\n".join(lines)


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    path = args.path.expanduser().resolve()

    if not path.exists():
        print(f"Каталог з планами не знайдено: {path}", file=sys.stderr)
        raise SystemExit(1)

    if not path.is_dir():
        print(f"Очікувався каталог з планами, а не файл: {path}", file=sys.stderr)
        raise SystemExit(1)

    try:
        summary = asyncio.run(import_subject_plans(path))
    except Exception as exc:
        print(f"Не вдалося імпортувати навчальні плани: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(format_summary(summary))

    if summary.failed_files:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
