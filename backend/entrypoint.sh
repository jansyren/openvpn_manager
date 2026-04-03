#!/bin/sh
set -e
uv run alembic upgrade head
uv run python -m app.cli ensure-admin
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
