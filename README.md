# Telegram Study Assistant

A production-minded Python foundation for a shared Telegram bot that helps two trusted users manage university study data together.

The current scope is intentionally small: configuration, logging, database setup, Alembic migrations, access control, a `/start` command, and placeholder menu sections for future features.

## Planned Product Direction

- Shared study workspace for one student and one helper/admin
- Schedule and subject tracking
- Tasks, files, reminders, and AI-assisted flows in later phases
- Clear separation between bot handlers, services, and database models

## Suggested Project Structure

```text
.
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── data/
├── src/
│   └── study_assistant_bot/
│       ├── bot/
│       │   ├── handlers/
│       │   ├── keyboards/
│       │   └── middlewares/
│       ├── db/
│       │   └── models/
│       ├── services/
│       ├── config.py
│       ├── enums.py
│       ├── logging.py
│       └── main.py
├── .env.example
├── alembic.ini
├── Makefile
└── pyproject.toml
```

## Tech Stack

- Python 3.12
- aiogram 3.x
- SQLAlchemy 2.x
- Alembic
- SQLite by default
- pydantic-settings

## Current Foundation

- Bot entrypoint with polling
- Environment-based settings
- Basic structured logging
- Async SQLAlchemy engine and session factory
- Initial models: `User`, `Subject`, `Lesson`
- Subject plan storage: `SubjectPlanItem`, `PlanItemQuestion`, `PlanItemAssignment`
- Role model for `student` and `admin`
- Whitelist-based Telegram access control
- Reply-keyboard main menu with placeholder handlers:
  - Schedule
  - Subjects
  - Tasks
  - Files
  - AI
- Initial Alembic migration

## Local Setup

1. Create and activate a Python 3.12 virtual environment.
2. Install dependencies:

```bash
make install
```

3. Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

4. Run the initial migration:

```bash
make db-upgrade
```

5. Start the bot locally:

```bash
make run
```

You can also start it directly with:

```bash
python3.12 -m study_assistant_bot
```

## Імпорт розкладу

Після застосування міграцій розклад можна імпортувати з Excel-файлу вручну:

```bash
make import-schedule
```

За замовчуванням використовується файл `data/group-time-table (1).xls`.

Щоб передати інший файл, вкажіть шлях окремо:

```bash
make import-schedule TIMETABLE_PATH="data/my-timetable.xls"
```

Імпорт:

- створює `Subject`, якщо предмета ще немає;
- створює `Lesson` для нових пар;
- не дублює вже імпортовані заняття при повторному запуску;
- оновлює назву, аудиторію та примітки, якщо вони змінилися в тому самому занятті.

## Імпорт навчальних планів

Після імпорту розкладу та застосування актуальних міграцій можна імпортувати JSON-плани
предметів:

```bash
make import-subject-plans
```

За замовчуванням використовується каталог `data/subject_plans`.

Щоб передати інший каталог, вкажіть його окремо:

```bash
make import-subject-plans SUBJECT_PLAN_DIR="data/my-subject-plans"
```

Особливості імпорту:

- обробляються лише `*.json` у корені каталогу без вкладених папок;
- кожен файл імпортується у власній транзакції;
- `Subject` має вже існувати в базі після попереднього кроку імпорту розкладу;
- повторний запуск не створює дублікати;
- JSON вважається джерелом істини для планових занять, питань і практичних завдань;
- за успішного імпорту для відповідного предмета видаляються застарілі записи, яких уже немає у файлі.

## Environment Variables

- `BOT_TOKEN`: Telegram bot token
- `ADMIN_TELEGRAM_IDS`: comma-separated Telegram IDs with admin access
- `STUDENT_TELEGRAM_IDS`: comma-separated Telegram IDs with student access
- `DATABASE_URL`: async SQLAlchemy database URL
- `LOG_LEVEL`: logging level, for example `INFO`

## Notes

- The bot expects database migrations to be applied before startup.
- `Subject` and `Lesson` are modeled as shared study data, not user-owned data.
- Future features should be added behind the existing service and handler boundaries rather than inside the entrypoint.
