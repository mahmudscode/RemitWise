#!/usr/bin/env sh
# If a PostgreSQL DATABASE_URL is provided, load the synthetic data into it on start (deterministic, ~25s).
if [ -n "$DATABASE_URL" ]; then
  python -m app.pipeline
fi
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
