#!/bin/sh
set -e

echo "==> Alembic migrations"
alembic upgrade head

echo "==> Seed demo data"
python scripts/seed_demo.py

echo "==> Train RF model (if missing)"
python -m ml.train

PORT="${PORT:-8000}"
echo "==> Starting uvicorn on 0.0.0.0:${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
