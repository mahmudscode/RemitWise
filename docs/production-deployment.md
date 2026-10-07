# Production-style deployment (PostgreSQL + several workers)

What is built and what you still have to do yourself.

## Built and tested
- **Production stack:** [docker-compose.prod.yml](../docker-compose.prod.yml): PostgreSQL 16 with a volume and health check, the API image with `WEB_CONCURRENCY` workers and an HTTP health check. Needs Docker; the compose file itself was **not run here** (no Docker on this machine), but the same components were: `python -m app.bootstrap` and `uvicorn --workers 4` against PostgreSQL 18.6 (see `load-test-results.md`).
- **Safe start-up:** `start.sh` runs `python -m app.bootstrap`, which loads the synthetic data only when the database is empty (under a lock), so restarts and redeploys never wipe data, and several containers can start together.
- **Connection pooling:** per worker, `DB_POOL_SIZE` + `DB_MAX_OVERFLOW` connections (default 15 + 10) with pre-ping and recycling, plus `DB_LOCK_POOL` (default 10) for locks. Keep `workers x (pool + overflow + lock pool)` below PostgreSQL `max_connections` (the compose file sets 200; 4 x 35 = 140).
- **Concurrency safety:** PostgreSQL advisory locks serialise writes per household and sign-up across all workers and containers; webhook events are idempotent by primary key.
- **Overload behaviour:** `503` with `Retry-After`, never a crash.

## Steps to put it on real infrastructure (needs your accounts)
1. Create a managed PostgreSQL (Neon, Supabase, Render PostgreSQL, RDS...). Copy its URL in the form `postgresql+psycopg://USER:PASSWORD@HOST:5432/DB`.
2. Render (see `render.yaml`): set `DATABASE_URL`, `ALLOWED_ORIGINS`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `SEED_DEMO_ACCOUNTS=false`, `WEB_CONCURRENCY` (the free plan has little CPU; use 1 or 2 there). Or self-host with `docker compose -f docker-compose.prod.yml up --build` after creating `.env` with `POSTGRES_PASSWORD` and the other values.
3. First start loads the data (about a minute); check `/api/health` shows `"db":"postgresql+psycopg"`.
4. Frontend: Vercel with `VITE_API_URL` set to the API URL.
5. Run the suite against that database before going live: point `DATABASE_URL` at an **empty** PostgreSQL database, run `python -m app.pipeline`, then `pytest` (the tests expect a fresh database).

## Not done (honest)
- No hosted PostgreSQL deployment was made from here (no account or credentials), and the compose stack was not run.
- No test at real production volume, across several machines, or with real upay traffic.
- Rate limits are per process; no Redis. No managed secrets, backups, monitoring or alerting.
