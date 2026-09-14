.PHONY: setup db migrate dev test test-integration lint format check

setup:
	python3 -m venv .venv
	.venv/bin/pip install -c requirements.lock -e '.[dev]'
	.venv/bin/python scripts/init_env.py

db:
	docker compose up -d --wait postgres

migrate:
	.venv/bin/alembic upgrade head

dev:
	.venv/bin/uvicorn cofrap.main:app --reload --host 127.0.0.1 --port 8000

test:
	.venv/bin/pytest tests/unit -q

test-integration:
	docker compose --profile test up -d --wait postgres-test
	.venv/bin/pytest --integration -q

lint:
	.venv/bin/ruff check src functions tests migrations scripts
	.venv/bin/ruff format --check src functions tests migrations scripts

format:
	.venv/bin/ruff format src functions tests migrations scripts
	.venv/bin/ruff check --fix src functions tests migrations scripts

check: lint test

.PHONY: functions-up functions-build functions-down
functions-build:
	docker compose -f compose.yaml -f compose.functions.yaml build

functions-up:
	docker compose -f compose.yaml -f compose.functions.yaml up -d --build --wait

functions-down:
	docker compose -f compose.yaml -f compose.functions.yaml down
