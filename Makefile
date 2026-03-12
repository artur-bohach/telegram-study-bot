PYTHON ?= python3.12
TIMETABLE_PATH ?= data/group-time-table (1).xls
SUBJECT_PLAN_DIR ?= data/subject_plans
RELINK_SUBJECT_CODE ?=

.PHONY: install run db-upgrade db-revision lint import-schedule import-subject-plans relink-lesson-plans

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

import-subject-plans:
	$(PYTHON) -m study_assistant_bot.scripts.import_subject_plans "$(SUBJECT_PLAN_DIR)"

relink-lesson-plans:
	$(PYTHON) -m study_assistant_bot.scripts.relink_lesson_plans $(if $(RELINK_SUBJECT_CODE),--subject-code "$(RELINK_SUBJECT_CODE)")
