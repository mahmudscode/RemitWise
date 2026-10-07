# 19 — Deployment (Vercel frontend + separate backend)

Vercel hosts the **frontend only**. The Python backend (LightGBM, pandas, scikit-learn, scipy, database writes) does not fit Vercel serverless functions, so host it on a container platform (Render, Railway, Fly.io).

## 1. Backend (Render / Railway / Fly)
- Root directory: `backend`; build from `backend/Dockerfile`.
- Environment variables:
  - `GROQ_API_KEY` (optional) and `GROQ_MODEL`
  - `ALLOWED_ORIGINS` = your Vercel URL, e.g. `https://remitwise.vercel.app` (comma-separate several; no trailing slash)
  - `DATABASE_URL` (optional) = a PostgreSQL URL like `postgresql+psycopg://user:pass@host:5432/db`. If set, data is loaded into Postgres on start (about 25 s). If not set, the image uses the SQLite file built during `docker build`; demo state then resets on restart.
- Health check path: `/api/health`.

- **Accounts:** for anything beyond a demo set `SEED_DEMO_ACCOUNTS=false` and provision an admin with `ADMIN_EMAIL` / `ADMIN_PASSWORD`. Accounts and user data persist only if `DATABASE_URL` points to PostgreSQL; with the default SQLite they reset on every redeploy. See doc 21.

## 2. Frontend (Vercel)
- Project **Root Directory: `frontend`** (not the repo root).
- Framework preset: Vite. Build command `npm run build`, output `dist`.
- Environment variable: `VITE_API_URL` = the backend's **https** URL, no trailing slash. Redeploy after changing it (Vite bakes it in at build time).

## 3. Check
Open `https://<backend>/api/health` and expect `{"ok":true,...}`. Then open the Vercel site; the red "Cannot reach the API" banner should be gone.

## Common failures
| Symptom | Cause |
|---|---|
| Red banner / network errors | `VITE_API_URL` missing or wrong; not redeployed after setting it |
| CORS error in console | Vercel URL not in `ALLOWED_ORIGINS` on the backend |
| Mixed-content error | Backend URL is `http://`; use `https://` |
| First request slow | Free backend tier was asleep |
| Demo state resets | SQLite on an ephemeral disk; set `DATABASE_URL` to Postgres for persistence |

*Not yet tested on a real host: this project's dev machine has no Docker or PostgreSQL.*

## Final build: new settings
`SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`SMTP_PASSWORD`/`SMTP_FROM` (email delivery of security codes), `OTP_DEMO_MODE` (default `false`: the code is only emailed), `WEBHOOK_SECRET` (enables the signed webhook; empty keeps it off), `FORCE_IRREGULAR_MODEL`, `FORCE_TEMPORAL_FEATURES`, `FORCE_ADAPTIVE` (forecasting experiments on by team decision) and `RW_ARTIFACTS_DIR`. The free Render tier sleeps when idle; the app shows a "Waking up the server…" screen with a retry. Set `DATABASE_URL` to PostgreSQL to keep data across redeploys. Test the suite against PostgreSQL with `./run.sh test-pg` (Docker) or an empty PostgreSQL database plus `python -m app.pipeline` and `pytest`.
