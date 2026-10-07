# RemitWise

An AI planner for families who live on remittance income. Built for **AI Hackathon 2026 (DIU CPC × upay), Track 03**.
**All data is synthetic. No real customer data, no real money, no real banking.**

- Live deployment: [https://frontend-acme-372b.vercel.app/](https://frontend-acme-372b.vercel.app/) (see [Deployment](#deployment))
- Demo video: [https://youtu.be/7KCWNhKgXQs?si=4cXdWQPZ5gCs5-01](https://youtu.be/7KCWNhKgXQs?si=4cXdWQPZ5gCs5-01)
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
| `OTP_DEMO_MODE` | backend | Simulated OTP: return the code in the response and show it on screen (no SMS is sent) | `true` |
| `WEBHOOK_SECRET` | backend | Shared secret for the signed transaction webhook; empty keeps it disabled | empty |
| `FORCE_IRREGULAR_MODEL`, `FORCE_TEMPORAL_FEATURES`, `FORCE_ADAPTIVE` | backend (build and run) | Switch the Priority 3 forecasting experiments on in the live model even though the offline rule did not require it | `true` |
| `RW_ARTIFACTS_DIR` | backend | Where `python -m app.pipeline` writes artifacts (used by `./run.sh test-pg`) | `backend/artifacts` |
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
./run.sh test        # 122 pytest tests + `npm --prefix frontend test` (voice logic), about 14 seconds
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

A simple fixed rule beats RemitWise on shortfall days; RemitWise wins on bills, fees and wallet retention. Forecast timing error is 8.0 days against 10.4 for a naive guess, amount error 58% against 80%, and range coverage 84% / 80% (target 80%). The shortfall warning was tuned for precision in the final-day update (before 0.72 / 0.73, now a hybrid of the model and the simple rule at 0.90 / 0.59; the simple rule alone: 0.95 / 0.55; see the section below). These figures depend on the simulation's behaviour assumptions, so run `./run.sh build` to reproduce them.

## 10. Other configuration and access

- **Roles.** The sign-in page lets people create a **Family** account or a **Sender abroad** account (a sender needs the family's invite code, shown under Goals → Sharing). Admins cannot self-register.
- **Persistence.** Accounts, sessions and data live in the database, so a refresh or a new browser session keeps users signed in with their data. On free hosting with SQLite, data resets on every redeploy; use PostgreSQL to keep it.
- **Privacy.** The admin sees aggregates and masked emails only. The simulation sandbox works only on the three demo households, never on real accounts. Sender endpoints return only consented fields.
- **Language.** English and বাংলা (toggle in the sidebar and on the sign-in page).
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

## Final-day updates (based on Phase 1 feedback)

| Judge comment | What was built | Where to see it |
|---|---|---|
| Warning precision/recall 0.72/0.73 vs simple rule 0.95; show before/after | Threshold re-selected on calibration households only (lowest threshold with precision ≥ 0.85), a hybrid warning (model OR simple rule) that beats the rule on recall and notice time, full threshold sweep stored | Admin → Model performance → "Warning threshold: before vs after" table and chart |
| Show 60/80/100% compliance; stress it is simulated | All three levels side by side next to "No plan" and "Fixed 50/30/20", with a "Simulated, not measured" banner; compact version for families | Admin → Model performance; family **Insights** |
| Add delayed remittance, Eid surge, medical/electricity bill scenarios | `Eid expense surge` (+40% needs for 10 days) and `Medical emergency` (৳8,000), readable warning reasons | Admin → Simulation sandbox → "Real-life scenarios" |
| Bangla UI | EN / বাংলা toggle (saved in the browser); Home, remittance pop-up, Payments, Plan, Goals, Insights, Sender, sign-in, AI summaries (Bangla template, or Groq when a key is set) | Toggle in the sidebar and sign-in page |
| Use upay brand colours | Palette sampled from the upay logo in the hackathon guideline (blue `#0d56a5`, yellow `#fcd704`), "for upay" line, WCAG AA contrast checked. The logo image is not copied | Whole app |
| Faster first load; smooth demo path | "Waking up the server…" screen with retry and an early health ping, skeleton cards on Home, **Guided demo** with 5 steps (also a floating bar over the family app) | Admin → Simulation sandbox → Guided demo |
| Phone OTP and password reset | Simulated OTP (hashed, 5-minute expiry, 5 attempts, rate-limited) and email/phone password reset that signs out every session. Demo mode shows the code on screen: no SMS is sent | Sign-up → "Verify your phone"; sign-in → "Forgot password?" |
| Automated micro-savings | Off by default, needs consent, ≤ ৳100/day, only when risk is green and bills covered, "Paused to protect your bills". Saving only, no investing | Family → Goals → Micro-savings |
| Show it is not a budgeting app | One-line explainer under Next remittance and a Budgeting app vs RemitWise comparison on the sign-in page | Home; sign-in page |
| PostgreSQL and LLM path untested | Groq path tested with a mocked HTTP layer (valid output accepted, invented numbers rejected, outage falls back). PostgreSQL test runner added | `./run.sh test`; `./run.sh test-pg` |
| Data-retention policy | [docs/data-retention.md](docs/data-retention.md); sessions, codes and audit rows expire; `DELETE /api/me` removes an account and its data | Goals → Your data; sign-in footer link |
| Systemic shocks | Sandbox button "Systemic shock" (next 3 transfers 21 days later and 30% smaller) and a stress test on the test households | Admin → Simulation sandbox; Model performance → Stress test |
| Concurrency, latency, resilience | Load-test script and results; clean 503/500 errors, app starts without the model file | [docs/load-test-results.md](docs/load-test-results.md); `backend/scripts/load_test.py` |
| More tests and security checks | Route-introspecting tests for auth, role escalation, household isolation, injection and bad input; `pip-audit` and `npm audit` clean; coverage 73% | [docs/security-check.md](docs/security-check.md) |
| Improve irregular senders | Regularity features and group-wise calibration tried; **not adopted** (gain is within noise) | Admin → Model performance → Experiment |
| Sequence models | LightGBM with lag features and a neural net over the last 6 gaps tried; **neither beat the baseline** | Admin → Model performance → Experiment |
| Fairness and drift monitoring | Rolling error and coverage, per-group flags, input drift (PSI), live warning rate | Admin → Monitoring |
| Adaptive household personalization | Online per-household forecast correction built and evaluated; **not adopted** (it made timing error worse on this data); wired to switch on automatically if a future evaluation shows a gain | Admin → Model performance → Experiment |
| Voice for rural users | 🔊 read aloud (Home, warning, AI summary) and 🎤 three fixed questions, Bangla and English, graceful fallback without a Bangla voice or microphone | Home page header |
| Business KPIs | Editable-assumption KPI card plus a randomized [pilot plan](docs/pilot-plan.md) | Admin → Model performance → Business KPIs |
| Real MFS events | Signed (HMAC) transaction webhook with idempotency; schema in [docs/09-api-contracts.md](docs/09-api-contracts.md); not a live upay feed | `POST /api/webhooks/transactions`; `backend/scripts/send_test_webhook.py` |

**Warning threshold, before vs after** (100 held-out synthetic households, 11,521 checkpoints):

| | Threshold | Precision | Recall | F1 | Avg. lead |
|---|---|---|---|---|---|
| Before (model only, best F1) | 0.45 | 0.72 | 0.73 | 0.72 | 6.9 days |
| Model only, precision-tuned | 0.70 | 0.91 | 0.52 | 0.66 | 3.5 days |
| **After: hybrid (model OR simple rule)** | 0.70 | 0.90 | 0.59 | 0.71 | 3.9 days |
| Simple rule | – | 0.95 | 0.55 | 0.69 | 2.8 days |

Higher precision means fewer false alarms but some shortfalls are caught later or missed. The model alone, tuned for precision, loses to the simple rule on both precision and recall. The hybrid (warn when the model is confident or the rule fires, threshold chosen on calibration households) catches more shortfalls (recall 0.59 vs 0.55), gives more notice (3.9 vs 2.8 days) and has a better F1 than the rule, at about 5 points less precision. The rule is still the most precise single signal.

**Simulated year at 60 / 80 / 100% compliance. Simulated, not measured:**

| | No plan | Fixed 50/30/20 (80%) | RemitWise 60% | RemitWise 80% | RemitWise 100% |
|---|---|---|---|---|---|
| Shortfall days / year | 36.7 | 9.8 | 13.8 | 13.2 | 13.1 |
| Bills on time | 90% | 95% | 97% | 98% | 99% |
| Late fees / year | ৳504 | ৳262 | ৳175 | ৳101 | ৳60 |
| Kept in wallet after 24h | 13% | 27% | 62% | 76% | 87% |

Compliance is an assumption; a real pilot would measure it.

**Stress test: systemic shock** (3 consecutive transfers 21 days later each and 30% smaller; 100 test households):

| | Normal | Under shock |
|---|---|---|
| Timing error (MAE) | 8.0 days | 20.9 days |
| Timing range coverage (target 80%) | 83% | 26% |
| Warning precision / recall (hybrid) | 0.88 / 0.57 | 1.00 / 0.78 |
| Average warning lead | 4.3 days | 2.2 days |

The forecaster was never trained on shocks, so its ranges lose most of their coverage. Warnings still fire because they read the live balance, but give less notice. A real deployment would add a corridor-level alert and retrain on shock periods.

**Load test** (laptop, one worker, SQLite, client and server on the same machine): 185 requests/s at 50 concurrent users, p50 257 ms, p95 372 ms, 0% errors; 198 requests/s at 10 users, p50 50 ms. This is a smoke test, not a production benchmark ([details](docs/load-test-results.md)).

**Experiments, reported honestly.** None improved accuracy on this synthetic data: regularity features plus group calibration (irregular-sender timing error 13.73 to 13.72 days: noise), temporal LightGBM (+0.01 days), neural net over recent gaps (+0.24 days, worse coverage), per-household adaptive correction (8.03 to 8.40 days, worse). By team decision the first two are switched on in the live model (measured effect: none, overall error 8.03 days either way) and so is the household correction (which does cost about 0.4 days; set `FORCE_ADAPTIVE=false` to turn it off). The neural net is not used. Admin → Model performance shows each result and "The model serving the app".

**Guided demo.** Admin → Simulation sandbox → *Reset household*, then steps 1 to 5: remittance arrives, accept allocation, unusual bill, warning, resolution.

**PostgreSQL.** The whole pipeline and the full test suite were run against **PostgreSQL 18.6** (a user-space install, no Docker, on a fresh database): the pipeline produced identical numbers and **119 of 119 tests passed** at the time. That run found two tests that were SQLite-specific (raw `sqlite3` access) and one that assumed an empty database; they were fixed. Reproduce with `./run.sh test-pg` (needs Docker: starts a throwaway Postgres on port 5433, builds the data, runs the suite) or point `DATABASE_URL` at any empty PostgreSQL database and run `python -m app.pipeline` then `pytest`. The suite expects a fresh database each run. Not tested: PostgreSQL at production scale, other versions.

**Out of scope (next phase):** a live pilot with real families and real compliance measurement, retraining on real anonymised upay data, real upay payment and identity integration (the webhook adapter is the bridge), production PostgreSQL at scale and formal penetration testing, real investment products. These are our next phase, a controlled pilot with governed upay data.

## Honest status

- The app and tests were verified against **SQLite** and, once, against **PostgreSQL 18.6** on a fresh database (see the PostgreSQL note above). Not run against a hosted or production-scale PostgreSQL.
- Several Priority 3 experiments did not improve accuracy; they are on by team decision and their measured effect is shown in Admin, not hidden.
- The Groq call is tested through a mocked HTTP layer; it has **not been called against the real service** (no API key was available).
- Sign-in is real (salted hashes, hashed tokens, rate limiting, server-side roles) but it is a hackathon implementation: phone OTP and password reset are simulated (no SMS is sent), and tokens live in `localStorage`.
- Behaviour change under RemitWise is a simulation **assumption** (the compliance level). Real remittance patterns may differ.
- Money movement is simulated.
