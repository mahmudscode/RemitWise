#!/usr/bin/env sh
# Production start: load data on the first start only (never wipe an existing database), then serve with several workers.
if [ -n "$DATABASE_URL" ]; then
  python -m app.bootstrap || exit 1
fi
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" --timeout-keep-alive 30
