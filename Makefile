PYTHON ?= python3.12

.PHONY: install run db-upgrade db-revision lint

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
