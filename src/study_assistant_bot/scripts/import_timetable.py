from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

from study_assistant_bot.config import get_settings
from study_assistant_bot.db import build_engine, build_session_factory, verify_database_ready
from study_assistant_bot.services import TimetableImportService


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Імпорт розкладу з Excel-файлу до бази даних.",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Шлях до Excel-файлу розкладу.",
    )
    return parser


async def import_timetable(path: Path) -> str:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)

    try:
        await verify_database_ready(engine)

        async with session_factory() as session:
            service = TimetableImportService(session)
            result = await service.import_from_file(path)
            await session.commit()

        return "\n".join(
            [
                "Імпорт розкладу завершено.",
                f"Файл: {path}",
                f"Знайдено занять у файлі: {result.parsed_lessons}",
                f"Створено предметів: {result.created_subjects}",
                f"Створено занять: {result.created_lessons}",
                f"Оновлено занять: {result.updated_lessons}",
                f"Без змін: {result.unchanged_lessons}",
                f"Видалено застарілих занять: {result.deleted_lessons}",
            ]
        )
    finally:
        await engine.dispose()


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    path = args.path.expanduser().resolve()

    if not path.exists():
        print(f"Файл розкладу не знайдено: {path}", file=sys.stderr)
        raise SystemExit(1)

    try:
        summary = asyncio.run(import_timetable(path))
    except Exception as exc:
        print(f"Не вдалося імпортувати розклад: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(summary)


if __name__ == "__main__":
    main()
