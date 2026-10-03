# RemitWise

An AI planner for families who live on remittance income. Built for **AI Hackathon 2026 (DIU CPC × upay), Track 03**.
**All data is synthetic. No real customer data, no real money, no real banking.**

- Live deployment: [https://frontend-acme-372b.vercel.app/](https://frontend-acme-372b.vercel.app/) (see [Deployment](#deployment))
- Demo video: [https://youtu.be/7KCWNhKgXQs?si=4cXdWQPZ5gCs5-01](https://youtu.be/7KCWNhKgXQs?si=4cXdWQPZ5gCs5-01)
- Narration subtitles and screenshots: [demo/](demo/)
- Planning and design docs: [docs/](docs/)

## 1. Project overview

**Problem.** Millions of families in Bangladesh depend on money sent by relatives abroad. It arrives at unpredictable times and in unpredictable amounts. Families run short before the next transfer, miss loan EMIs and bills, pay late fees, cash out everything at once and rarely save.

**Solution.** RemitWise sits inside the wallet and does four things:
1. **Forecasts** when the next remittance will arrive and how much it will be, as a range with an honest confidence level.
2. **Splits** each arriving remittance into bills and EMI, daily needs, emergency savings and goals. The family sees three plan styles, can edit any amount, and always decides.
3. **Pays bills automatically** from a protected bill vault, and holds unusually high bills for the family to review.
4. **Warns early** if money is likely to run out before the next transfer, with reasons and options, and lets a sender abroad see only what the family chooses to share.

**Purpose.** Fewer missed EMIs and late fees, fewer surprise shortfalls and steadier saving for the family. For the wallet provider, more bill payments and more money kept in the wallet.

## 2. Features and how the AI is used

| Feature | Where | AI / logic |
|---|---|---|
| Synthetic household simulator | `backend/app/simulator.py` | Seeded generator: 500 households, about 30 months, with festival, delay and shock patterns (split by household: 300 train, 100 calibration, 100 held-out test) |
| Inflow forecast (date and amount) | `backend/app/forecast.py` | **LightGBM quantile regression** (P10/P50/P90) plus **conformal calibration**, so the stated range is honest |
| Shortfall early warning | `backend/app/risk.py` | **Monte-Carlo** simulation of 1,000 futures (spending and arrival day) gives the probability and run-out date, with rule-trace reasons |
| Smart split and goal allocation | `backend/app/allocator.py` | Deterministic business rules and a greedy goal optimiser, kept separate from the ML; three plan styles |
| Bills, EMI and auto-pay | `backend/app/bills.py`, `live.py` | Bill vault, mandates with monthly limits, expected amount from the same month last year, **anomaly flag** above 1.8× the estimate (auto-pay paused until the family decides) |
| With vs without comparison | `backend/app/sim.py` | Policy replay: no plan, fixed 50/30/20 rule and RemitWise at 60/80/100% compliance |
| Plain-language summaries | `backend/app/explain.py` | **Groq LLM** rewrites only numbers the code computed. Any number not in the facts discards the text and a template is used instead |
| Sender view with consent | `backend/app/main.py` | Sender sees only the goal progress, savings total and bill status the family granted, enforced on the server |
| Accounts and roles | `backend/app/auth.py` | Family, sender and admin roles, salted password hashes, hashed session tokens, rate limiting |
| Admin console | `frontend/src/Admin.jsx` | Platform overview, users (disable, enable, delete), model performance and fairness, simulation sandbox on demo households, audit log |

Money movement is **simulated**. In production it would connect to the wallet's remittance and payment system.

## 3. Technology stack

- **Languages:** Python 3.14, JavaScript (React 19).
- **Backend:** FastAPI, Uvicorn, SQLAlchemy 2, pydantic.
- **ML and data:** LightGBM, scikit-learn, SciPy, NumPy, pandas, joblib.
- **LLM:** Groq API (default model `llama-3.3-70b-versatile`), optional.
- **Database:** SQLite by default; PostgreSQL via `DATABASE_URL`.
- **Frontend:** React, Vite, Recharts, built from the Figma design in `docs/DESINE/`.
- **Testing:** pytest, httpx.
- **Hosting:** Vercel (frontend), Render (backend, Docker), optional Docker Compose for PostgreSQL.

Full details: [docs/18-tech-stack.md](docs/18-tech-stack.md).

## 4. Requirements

- Python 3.11 or newer (developed on 3.14) with `venv` and `pip`
- Node.js 20 or newer (developed on 26) with `npm`
- About 500 MB of disk for the virtual environment and dependencies, plus about 40 MB for the generated database
- Optional: Docker (PostgreSQL), a Groq API key
- No GPU needed. The build step takes about 40 seconds on a laptop.

## 5. Installation and setup

```bash
git clone https://github.com/mahmudscode/RemitWise.git
cd RemitWise
./run.sh setup                      # creates backend/.venv, installs Python and npm packages
cp .env.example backend/.env        # optional: edit values (see section 6)
./run.sh build                      # simulates 500 households, trains, evaluates, loads the database
```

`./run.sh build` writes `backend/artifacts/remitwise.db` (data and demo accounts), `forecaster.joblib` (trained model), `evaluation.json` (test results) and `data_card.md` (data assumptions).

Optional PostgreSQL instead of SQLite:
```bash
docker compose up -d
# then set DATABASE_URL in backend/.env (see section 6) and re-run ./run.sh build
```

## 6. Environment variables

Copy `.env.example` to `backend/.env`. Placeholders only; never commit real secrets.

| Variable | Where | Purpose | Default |
|---|---|---|---|
| `DATABASE_URL` | backend | Database. For PostgreSQL: `postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME` | local SQLite file |
| `GROQ_API_KEY` | backend | Enables Groq-written summaries. Leave empty to use validated templates | empty |
| `GROQ_MODEL` | backend | Groq model name | `llama-3.3-70b-versatile` |
| `SEED_DEMO_ACCOUNTS` | backend | Create the demo family, sender and admin accounts | `true` (use `false` outside a demo) |
| `DEMO_PASSWORD` | backend | Password for the demo accounts | `demo1234` |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | backend | Provision your own admin (admins can never self-register). Leave empty to skip | empty |
| `ALLOWED_ORIGINS` | backend | Comma-separated frontend URLs allowed by CORS in deployment, e.g. `https://your-app.vercel.app` | empty (local only) |
| `VITE_API_URL` | frontend (`frontend/.env`) | Backend URL for deployed builds. Leave unset locally; the Vite dev server proxies `/api` | empty |

## 7. Run and build commands

Use two terminals and keep both open.

```bash
./run.sh api      # backend: http://127.0.0.1:8000  (interactive API docs at /docs)
./run.sh web      # frontend: http://localhost:5173
```

Other commands: `./run.sh build` (regenerate data and retrain), `./run.sh test` (tests), `npm --prefix frontend run build` (production frontend into `frontend/dist`).
The root `package.json` also forwards `npm run dev` and `npm run build` to the frontend.

If the page says the backend is not running, the API terminal is not started (or port 8000 is taken).

## 8. Live deployment URL

**[https://frontend-acme-372b.vercel.app/](https://frontend-acme-372b.vercel.app/)**

Sign-in details for judges are in section 11.

## 9. Testing instructions

**Automated:**
```bash
./run.sh test        # 55 pytest tests, about 6 seconds
```
They cover allocator invariants (plans never overspend), summary safety (numbers validated, injection text sanitised), consent and household isolation, bills and the vault, sign-up, sign-in and persistence after a restart, admin endpoints, and a check that the forecaster beats a naive baseline. Tests use a temporary copy of the database, so demo data is untouched.

**Manual walkthrough (about 5 minutes):**
1. Sign in as the family demo account. Home shows the forecast, safe to spend and the projected balance.
2. Open **Demo clock** in the sidebar and click **Trigger remittance**. Switch between the three plan styles, open **Why this split?**, use **Adjust amounts** and watch the chance of running short change, then **Accept plan**.
3. Click **+7 days** twice and open **Payments** to see bills paid from the vault.
4. Sign in as admin, open **Simulation sandbox**, click **Inject unusually high bill**, open the family app, advance a week and use **Payments** to approve or dispute the held bill.
5. In the sandbox, click **Delay next transfer**, advance days in the family app until the amber early-warning banner appears, then open **See options** on the Plan page.
6. In **Goals**, share a goal and click **Preview sender view** to confirm the sender sees only what was shared.
7. Admin console, **Model performance**: forecast and warning metrics, fairness cuts and the with/without comparison.

**Evidence.** Headline results on 100 held-out synthetic households (a simulated year at 80% compliance):

| | No plan | Fixed 50/30/20 | RemitWise |
|---|---|---|---|
| Shortfall days / year | 36.7 | 9.8 | 13.2 |
| Bills paid on time | 90% | 95% | 98% |
| Late fees / year | ৳504 | ৳262 | ৳101 |
| Kept in wallet after 24h | 13% | 27% | 76% |

A simple fixed rule beats RemitWise on shortfall days; RemitWise wins on bills, fees and wallet retention. Forecast timing error is 8.0 days against 10.4 for a naive guess, amount error 58% against 80%, and range coverage 84% / 80% (target 80%). The shortfall warning has precision 0.72 and recall 0.73 (a simple rule: 0.95 and 0.55). These figures depend on the simulation's behaviour assumptions, so run `./run.sh build` to reproduce them.

## 10. Other configuration and access

- **Roles.** The sign-in page lets people create a **Family** account or a **Sender abroad** account (a sender needs the family's invite code, shown under Goals → Sharing). Admins cannot self-register.
- **Persistence.** Accounts, sessions and data live in the database, so a refresh or a new browser session keeps users signed in with their data. On free hosting with SQLite, data resets on every redeploy; use PostgreSQL to keep it.
- **Privacy.** The admin sees aggregates and masked emails only. The simulation sandbox works only on the three demo households, never on real accounts. Sender endpoints return only consented fields.
- **Language.** English only.
- **Data card.** `backend/artifacts/data_card.md` lists every simulation assumption.

### Deployment
- **Backend on Render:** New → Blueprint → pick this repo ([render.yaml](render.yaml), Docker). Set `ALLOWED_ORIGINS` to your Vercel URL, and optionally `DATABASE_URL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `GROQ_API_KEY`.
- **Frontend on Vercel:** root directory `frontend`, environment variable `VITE_API_URL` set to the Render URL.
- Walk-through: [docs/19-deployment.md](docs/19-deployment.md).

## 11. Judge access

| Role | Email | Password |
|---|---|---|
| Family | `rahima@demo.remitwise` | `demo1234` |
| Sender abroad | `rahim@demo.remitwise` | `demo1234` |
| Admin | `admin@demo.remitwise` | `demo1234` |

The admin opens the admin console automatically. The demo accounts exist only while `SEED_DEMO_ACCOUNTS=true`; on a public deployment, change `DEMO_PASSWORD` and provision your own admin.

## Honest status

- The app and tests were verified against **SQLite**. PostgreSQL support exists (SQLAlchemy and `DATABASE_URL`, compose file included) but has **not been run**.
- The Groq call was **not exercised** (no API key was available). The validated template path is what was tested.
- Sign-in is real (salted hashes, hashed tokens, rate limiting, server-side roles) but it is a hackathon implementation: no email verification or password reset, and tokens live in `localStorage`.
- Behaviour change under RemitWise is a simulation **assumption** (the compliance level). Real remittance patterns may differ.
- Money movement is simulated.
