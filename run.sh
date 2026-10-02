#!/usr/bin/env bash
# RemitWise helper.   ./run.sh setup | build | api | web | test
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
  *) echo "usage: ./run.sh setup|build|api|web|test" ;;
esac
