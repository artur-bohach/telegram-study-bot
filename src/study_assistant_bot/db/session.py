from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def ensure_sqlite_directory(database_url: str) -> None:
    url = make_url(database_url)

    if url.get_backend_name() != "sqlite":
        return

    database_path = url.database
    if not database_path or database_path == ":memory:":
        return

    Path(database_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def to_sync_database_url(database_url: str) -> str:
    url = make_url(database_url)

    if "+" not in url.drivername:
        return database_url

    sync_driver_name = url.drivername.split("+", maxsplit=1)[0]
    return str(url.set(drivername=sync_driver_name))


def build_engine(database_url: str) -> AsyncEngine:
    ensure_sqlite_directory(database_url)
    return create_async_engine(database_url, future=True)


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def verify_database_ready(engine: AsyncEngine) -> None:
    required_tables = {
        "alembic_version",
        "lessons",
        "plan_item_assignments",
        "plan_item_questions",
        "subject_plan_items",
        "subjects",
        "users",
    }

    async with engine.connect() as connection:
        def check_tables(sync_connection: object) -> None:
            table_names = set(inspect(sync_connection).get_table_names())
            missing_tables = required_tables - table_names

            if missing_tables:
                missing = ", ".join(sorted(missing_tables))
                raise RuntimeError(
                    "Database is not initialized. Run `alembic upgrade head` before "
                    f"starting the bot. Missing tables: {missing}."
                )

        await connection.run_sync(check_tables)
