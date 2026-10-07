#!/usr/bin/env bash
# RemitWise helper.   ./run.sh setup | build | api | web | test | test-pg
set -e
cd "$(dirname "$0")"
case "$1" in
  setup)
    python3 -m venv backend/.venv
    backend/.venv/bin/pip install -q pandas numpy scikit-learn scipy lightgbm fastapi "uvicorn[standard]" sqlalchemy "psycopg[binary]" groq pytest httpx python-dotenv joblib
    (cd frontend && npm install) ;;
  build) (cd backend && .venv/bin/python -m app.pipeline) ;;          # generate data, train, evaluate, load DB
  api)   (cd backend && .venv/bin/uvicorn app.main:app --port 8000) ;;
  web)   (cd frontend && npm run dev) ;;
  test)  (cd backend && .venv/bin/python -m pytest -q) ;;
  test-pg)  # the whole test suite against PostgreSQL (needs Docker): builds the data in Postgres first, then runs pytest
    docker compose --profile test up -d db-test
    until docker compose --profile test exec -T db-test pg_isready -U remitwise -d remitwise_test >/dev/null 2>&1; do sleep 1; done
    export DATABASE_URL="postgresql+psycopg://remitwise:remitwise@localhost:5433/remitwise_test"
    export RW_ARTIFACTS_DIR="$(mktemp -d)"
    rc=0
    (cd backend && .venv/bin/python -m app.pipeline && .venv/bin/python -m pytest -q) || rc=$?
    docker compose --profile test rm -sf db-test >/dev/null 2>&1
    exit $rc ;;
  *) echo "usage: ./run.sh setup|build|api|web|test|test-pg" ;;
esac
