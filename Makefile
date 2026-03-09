PYTHON ?= python3.12
TIMETABLE_PATH ?= data/group-time-table (1).xls

.PHONY: install run db-upgrade db-revision lint import-schedule

install:
	$(PYTHON) -m pip install -e .[dev]

run:
	$(PYTHON) -m study_assistant_bot

db-upgrade:
	$(PYTHON) -m alembic upgrade head

db-revision:
	$(PYTHON) -m alembic revision --autogenerate -m "$(m)"

lint:
	$(PYTHON) -m ruff check .

import-schedule:
	$(PYTHON) -m study_assistant_bot.scripts.import_timetable "$(TIMETABLE_PATH)"
