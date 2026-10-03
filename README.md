# RemitWise

AI planner for families living on remittance income. AI Hackathon 2026 · DIU CPC × upay · Track 03.
Planning docs are in [docs/](docs/). **All data is synthetic; no real PII.**

## What is built
| Piece | Where | Notes |
|---|---|---|
| Synthetic household simulator | `backend/app/simulator.py` | 500 households (300 train, 100 calibration, 100 held-out test), ~30 months, seeded; planted festival / delay / shock patterns |
| Inflow forecaster | `backend/app/forecast.py` | LightGBM quantile models + conformal calibration → P10/P50/P90 for date and amount |
| Smart budget allocator | `backend/app/allocator.py` | Deterministic rules + greedy goal optimiser; 3 plan styles; family always decides |
| Shortfall early warning | `backend/app/risk.py` | Monte-Carlo projection + rule-trace drivers |
| Policy replay (with vs without) | `backend/app/sim.py` | Baseline vs fixed 50/30/20 vs RemitWise at 60/80/100% compliance |
| Bills, EMI and auto-pay | `backend/app/bills.py`, `live.py` | Bill vault, on-time payment, unusual-bill review, mandates with limits |
| Grounded summaries | `backend/app/explain.py` | Groq LLM → number validation → template fallback (English) |
| API with server-side consent | `backend/app/main.py` | FastAPI; sender endpoints return goal progress only |
| App | `frontend/` | Responsive app built from the Figma design in `docs/DESINE/`: family app (Home, Payments, Plan, Goals, Insights), sender view, admin console (React + Vite) |

## Run
```bash
./run.sh setup        # venv + npm install
cp .env.example backend/.env   # optional: set GROQ_API_KEY and DATABASE_URL
docker compose up -d  # optional: PostgreSQL (then set DATABASE_URL); otherwise SQLite is used
./run.sh build        # ~25s: simulate, train, evaluate, load the database
./run.sh api          # http://127.0.0.1:8000  (docs at /docs)
./run.sh web          # http://localhost:5173
./run.sh test
```
Demo: Family app → **Trigger remittance** → pick a plan → **+7 days** a few times → watch bills get paid, then try **Demo & insights → Inject unusually high bill** and review it under **Payments**.
Demo panel → scenario buttons, forecast vs actual, and the with/without comparison. Screens are described in `docs/20-ui-design-and-screens.md`.

## Accounts
Open the app and **Sign in** or **Create account** as a **Family** or a **Sender abroad** (needs the family's invite code from Goals → Sharing). The sign-in page also has one-click **demo accounts** (password `demo1234` unless you set `DEMO_PASSWORD`).
**Admin console** (platform operators; admins cannot self-register): sign in with the seeded `admin@demo.remitwise` / `demo1234` (or the `ADMIN_EMAIL` / `ADMIN_PASSWORD` you provision). The app detects the role and opens the console: platform overview, users (disable/enable), model performance, simulation sandbox, audit. Give reviewers these credentials in your submission notes; they are deliberately not shown on the sign-in page. Sessions and all user data are stored in the database, so a refresh or a new browser session keeps you signed in with your data. Details and limits: `docs/21-auth-and-accounts.md`.

## Headline results (100 held-out synthetic test households, simulated year at 80% compliance)
| | No plan | Fixed 50/30/20 | RemitWise |
|---|---|---|---|
| Shortfall days / year | 36.7 | 9.8 | 13.2 |
| Bills paid on time | 90% | 95% | 98% |
| Late fees / year | ৳504 | ৳262 | ৳101 |
| Kept in wallet after 24h | 13% | 27% | 76% |

A simple fixed rule beats RemitWise on shortfall days; RemitWise wins on bills, fees and wallet retention. Forecast timing error is 8.0 vs 10.4 days (naive), amount error 58% vs 80%, range coverage 84% / 80% (target 80%); the bill estimate is 11% vs 16% off. The shortfall warning has precision 0.72 and recall 0.73 (a simple rule: 0.95 and 0.55). These depend on the simulation's behaviour assumptions. Run `./run.sh build` to reproduce.

## Honest status
- The app and tests were verified against **SQLite**. PostgreSQL support exists (SQLAlchemy + `DATABASE_URL`, compose file included) but has **not been run** in the build environment.
- The Groq call was **not exercised** (no API key available); the validated template path is what was tested. If Groq output contains any number not in the computed facts it is discarded.
- Sign-in is real (salted hashes, hashed session tokens, rate limiting, server-side roles) but it is a hackathon implementation: no email verification or password reset, and tokens live in `localStorage`. With SQLite on free hosting, accounts reset on redeploy; use PostgreSQL to keep them.
- Behaviour change under RemitWise is a simulation **assumption** (compliance level). See `backend/artifacts/data_card.md` after `./run.sh build`.
