.PHONY: sync dev check lint typecheck test infra-up infra-down

sync:
	uv sync --locked

dev:
	uv run --locked uvicorn app.main:app --app-dir apps/api --reload --host 127.0.0.1

check: lint typecheck test

lint:
	uv run --locked ruff check .
	uv run --locked ruff format --check .

typecheck:
	uv run --locked mypy

test:
	uv run --locked pytest -q --cov --cov-report=term-missing --cov-report=xml

infra-up:
	docker compose up -d --wait --wait-timeout 90

infra-down:
	docker compose down
