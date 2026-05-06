.PHONY: migrate migrate-create migrate-down seed export-reqs dev lint test

migrate:
	uv run alembic upgrade head

migrate-create:
	uv run alembic revision --autogenerate -m "$(m)"

migrate-down:
	uv run alembic downgrade -1

seed:
	uv run python -m app.db.seed

export-reqs:
	uv export --no-dev --no-hashes --locked > requirements.txt

dev:
	uv run fastapi dev app/main.py

lint:
	uv run ruff check .

test:
	uv run pytest tests/ -v
