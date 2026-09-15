.PHONY: db-up db-down db-logs migrate migrate-create app-run test clean

# --- Docker / Infra ---
db-up:
	docker compose up -d

db-down:
	docker compose stop

db-logs:
	docker compose logs -f postgres

# --- Alembic Migrations ---
migrate:
	uv run alembic upgrade head

# Использование: make migrate-create msg="add_new_table"
migrate-create:
	uv run alembic revision --autogenerate -m "$(msg)"

# --- Application ---
run-bot:
	uv run python -m bot.main

# --- Tests & Linters ---
test:
	uv run pytest
