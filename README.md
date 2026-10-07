# RemitWise

**An AI planner for families who live on remittance income.**
Built for **AI Hackathon 2026 (DIU CPC × upay), Track 03 · Team Matrix Miners**

> **All data is synthetic. No real customer data, no real money, no real banking.**
> Business impact figures are **simulated, not measured**. A real pilot would measure them.

[Live demo](https://frontend-acme-372b.vercel.app/) · [Demo video](https://youtu.be/7KCWNhKgXQs?si=4cXdWQPZ5gCs5-01) · [Planning and design docs](docs/) · [Judge access](#judge-access)

---

## Contents
1. [Overview](#1-overview)
2. [Features](#2-features)
3. [How the AI is used](#3-how-the-ai-is-used)
4. [Results](#4-results)
5. [Architecture and repository layout](#5-architecture-and-repository-layout)
6. [Quick start](#6-quick-start)
7. [Configuration](#7-configuration)
8. [Demo guide](#8-demo-guide)
9. [Testing](#9-testing)
10. [Deployment](#10-deployment)
11. [Security and responsible AI](#11-security-and-responsible-ai)
12. [Status and limitations](#12-status-and-limitations)
13. [Phase 2: response to judge feedback](#13-phase-2-response-to-judge-feedback)
14. [Documentation index](#14-documentation-index)
15. [Team](#15-team)

---

## 1. Overview

**Problem.** Millions of families in Bangladesh depend on money sent from abroad. It arrives at unpredictable times and in unpredictable amounts. Families run short before the next transfer, miss loan EMIs and bills, pay late fees, cash out everything at once and rarely save.

**Solution.** RemitWise sits inside the wallet and treats irregular remittance as a forecasting and planning problem, not a monthly-salary budgeting problem:

1. **Forecasts** when the next remittance arrives and how much, as a calibrated range with an honest confidence level.
2. **Splits** each arriving remittance into bills and EMI, daily needs, emergency savings and goals. Three plan styles, every amount editable, the family always decides.
3. **Pays bills automatically** from a protected bill vault and holds unusually high bills for review.
4. **Warns early** when money is likely to run out before the next transfer, with reasons and options.
5. **Shares progress with the sender abroad** only as far as the family consents.

**Why it is not a budgeting app.** Budget apps track what was spent. RemitWise predicts when money will *arrive* and plans around that uncertainty.

**Value.** For families: fewer missed EMIs, late fees and surprise shortfalls, and steadier saving. For the wallet provider: more digital bill payments and more money kept in the wallet.

Money movement is simulated. In production it would connect to the wallet's remittance and payment system.

---

## 2. Features

| Area | What it does |
|---|---|
| **Forecast** | Next-transfer date and amount as P10/P50/P90 ranges, widened automatically when a transfer is overdue; plain-language drivers ("Why this estimate?") |
| **Smart split** | Bills first, then needs, emergency fund and goals, with three styles and a live "chance of running short" as amounts are edited |
| **Bills and auto-pay** | Bill vault, mandates with monthly limits, expected amount from the same month last year, anomaly hold above 1.8× the estimate (approve, dispute or pay manually) |
| **Early warning** | Hybrid of a Monte-Carlo shortfall model and a simple rule, with run-out range, drivers and options (spend less, move goal money, ask the sender to send earlier) |
| **Real-life scenarios** | Delayed transfer, Eid expense surge, medical emergency, unusual electricity bill and a systemic shock, in an admin sandbox on demo households |
| **Micro-savings** | Consent-based, tiny daily amounts into the emergency fund, a goal, or an optional **simulated** yield pot; pauses automatically when bills are at risk |
| **Goals and sender view** | Shared goals with pace estimates; the sender sees only what the family granted, enforced on the server |
| **Bangla and voice** | English / বাংলা toggle on the main screens; read-aloud (🔊) and three fixed voice questions (🎤) using the browser's speech APIs |
| **Accounts and security** | Family, sender and admin roles; salted password hashes; hashed sessions; rate limits; 6-digit security codes to verify an email and reset a password; account self-deletion; data-retention policy |
| **Admin console** | Overview, users, model performance and fairness, stress test, business KPIs (simulated), monitoring and drift, simulation sandbox with a 5-step **Guided demo**, audit log |
| **Real-event adapter** | HMAC-signed transaction webhook with idempotency, safe under concurrent workers |
| **Brand and UX** | upay colours (blue `#0d56a5`, yellow `#fcd704`, sampled from the official logo, WCAG AA contrast), waking-server screen, skeleton loading |

---

## 3. How the AI is used

| Component | File | Technique |
|---|---|---|
| Synthetic households | `backend/app/simulator.py` | Seeded generator: 500 households, about 30 months, with festival, delay and shock patterns. Split by household: 300 train, 100 calibration, 100 held-out test |
| Inflow forecast | `backend/app/forecast.py` | **LightGBM quantile regression** with **conformal calibration** so stated ranges are honest |
| Shortfall warning | `backend/app/risk.py`, `live.py` | **Monte-Carlo** simulation of 1,000 futures, combined with a simple rule; threshold chosen on calibration households only |
| Allocation | `backend/app/allocator.py` | Deterministic rules and a greedy goal optimiser, deliberately separate from the ML |
| Plain-language summaries | `backend/app/explain.py` | **Groq LLM** (optional) rewrites only numbers the code computed. A number not in the facts discards the text and a validated template is used. English and Bangla |
| Policy comparison | `backend/app/sim.py` | Replays a year: no plan, fixed 50/30/20, and RemitWise at 60/80/100% compliance |
| Monitoring | `backend/app/monitoring.py` | Rolling error and coverage, per-group flags, input drift (PSI) |

**Experiments, reported honestly.** None improved accuracy on this synthetic data: sender-regularity features with group-wise calibration (irregular-sender timing error 13.73 → 13.72 days), lag/rolling features (+0.01 days), a neural net over recent gaps (+0.24 days, worse coverage) and a per-household online correction (8.03 → 8.40 days, worse). By team decision the first two and the household correction are switched on in the live model (`FORCE_*` settings); the neural net is not used. Admin → Model performance shows each result and "The model serving the app".

---

## 4. Results

Measured on **100 held-out synthetic test households** unless stated. Behaviour change under the plan is an **assumption** (the compliance level), so every business figure is simulated.

**A simulated year at 60 / 80 / 100% compliance**

| | No plan | Fixed 50/30/20 (80%) | RemitWise 60% | RemitWise 80% | RemitWise 100% |
|---|---|---|---|---|---|
| Shortfall days / year | 36.7 | 9.8 | 13.8 | 13.2 | 13.1 |
| Bills paid on time | 90% | 95% | 97% | 98% | 99% |
| Late fees / year | ৳504 | ৳262 | ৳177 | ৳101 | ৳60 |
| Kept in wallet after 24 h | 13% | 28% | 62% | 76% | 87% |

A simple fixed rule has fewer shortfall days than RemitWise; RemitWise wins on bills paid on time, late fees and wallet retention.

**Forecast quality.** Timing error 8.0 days against 10.4 for a "same as last time" guess; amount error 58% against 80%; range coverage 84% / 80% against a target of 80%.

**Shortfall warning, before and after tuning** (11,521 checkpoints)

| | Threshold | Precision | Recall | F1 | Avg. notice |
|---|---|---|---|---|---|
| Before (model only, best F1) | 0.45 | 0.72 | 0.73 | 0.72 | 6.9 days |
| Model only, precision-tuned | 0.70 | 0.91 | 0.52 | 0.66 | 3.5 days |
| **Final: hybrid (model OR simple rule)** | 0.70 | 0.90 | 0.59 | 0.71 | 3.9 days |
| Simple rule alone | – | 0.95 | 0.55 | 0.69 | 2.8 days |

The model alone, tuned for precision, loses to the simple rule on both precision and recall. The hybrid catches more shortfalls and gives more notice than the rule, at about five points less precision. The rule remains the most precise single signal.

**Stress test: systemic shock** (three consecutive transfers 21 days later each and 30% smaller)

| | Normal | Under shock |
|---|---|---|
| Timing error | 8.0 days | 20.9 days |
| Timing range coverage (target 80%) | 83% | 26% |
| Warning precision / recall | 0.88 / 0.57 | 1.00 / 0.78 |
| Average notice | 4.3 days | 2.2 days |

The forecaster was never trained on shocks, so its ranges lose most of their coverage. Warnings still fire because they read the live balance, but give less notice.

**Load and concurrency** (one laptop; client, server and database share it; see [docs/load-test-results.md](docs/load-test-results.md))

| Test | Result |
|---|---|
| 1 worker, SQLite, 50 users | 185 requests/s, 0 errors |
| 4 workers, PostgreSQL 18.6, 100 users read-only | 162 requests/s, 0 errors |
| 4 workers, PostgreSQL, 300 households, 80/20 reads and writes | 125 requests/s, p95 7.9 s, 1.2% clean "busy" (503) |
| 4,000 signed webhook events, each sent twice at once | exactly the 2,000 unique events applied, to the taka |

These runs found and fixed a connection-pool deadlock and several race conditions. This is a local test, not production scale.

---

## 5. Architecture and repository layout

```
 React + Vite (Recharts)  ──REST──▶  FastAPI  ──▶  SQLAlchemy ──▶ SQLite (default) / PostgreSQL
 family · sender · admin               │
                                       ├─ forecast.py   LightGBM + conformal
                                       ├─ risk.py       Monte-Carlo shortfall
                                       ├─ allocator.py  split and goals (rules)
                                       ├─ live.py       household engine, bills, scenarios, micro-savings
                                       ├─ explain.py    Groq + number validation + templates
                                       ├─ auth.py, mailer.py   accounts, security codes
                                       └─ monitoring.py, evaluation.py, pipeline.py
```

```
backend/        FastAPI app, models, simulator, tests, scripts (load test, webhook sender, email test)
  app/          application code
  artifacts/    generated data, trained model, evaluation.json, data_card.md
  tests/        pytest suite
  scripts/      load_test.py, send_test_webhook.py, test_email.py
frontend/       React app (Family, Sender, Admin, Bangla, voice)
docs/           product, design, evaluation and operations documents
docs/phase2/    plan, task specs and status for the on-site final
docker-compose.yml, docker-compose.prod.yml, render.yaml, run.sh
```

**Stack.** Python, FastAPI, SQLAlchemy 2, LightGBM, scikit-learn, pandas, optional Groq API; React 19, Vite, Recharts; pytest; SQLite or PostgreSQL; Vercel (frontend), Render (backend, Docker). Details: [docs/18-tech-stack.md](docs/18-tech-stack.md), [docs/08-architecture.md](docs/08-architecture.md).

---

## 6. Quick start

**Requirements:** Python 3.11+ (developed on 3.14), Node.js 20+, about 500 MB disk. No GPU. Docker is optional (PostgreSQL).

```bash
git clone https://github.com/mahmudscode/RemitWise.git
cd RemitWise
./run.sh setup        # creates backend/.venv, installs Python and npm packages
./run.sh build        # simulates 500 households, trains, evaluates, loads the database (about a minute)
```

Run in two terminals:

```bash
./run.sh api          # backend  http://127.0.0.1:8000  (API docs at /docs)
./run.sh web          # frontend http://localhost:5173
```

Other commands: `./run.sh test` (tests), `./run.sh test-pg` (tests on PostgreSQL via Docker), `npm --prefix frontend run build` (production frontend). If the page says it cannot reach the API, the API terminal is not running.

`./run.sh build` writes `backend/artifacts/remitwise.db`, `forecaster.joblib`, `evaluation.json` (all test results) and `data_card.md` (every simulation assumption).

---

## 7. Configuration

Copy `.env.example` to `backend/.env`. Never commit real secrets.

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Database. PostgreSQL: `postgresql+psycopg://USER:PASSWORD@HOST:5432/DB` | local SQLite |
| `GROQ_API_KEY`, `GROQ_MODEL` | Groq-written summaries; empty uses validated templates | empty |
| `SEED_DEMO_ACCOUNTS`, `DEMO_PASSWORD` | Demo family, sender and admin accounts | `true`, `demo1234` |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Provision your own admin (admins never self-register) | empty |
| `ALLOWED_ORIGINS` | CORS origins for deployment | empty (local only) |
| `OTP_DEMO_MODE` | `true`: security code shown on screen. `false`: only emailed (needs `SMTP_*`) | `true` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS` | Any SMTP server, to email security codes | empty |
| `WEBHOOK_SECRET` | Shared secret for the signed transaction webhook; empty disables it | empty |
| `WEB_CONCURRENCY`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_LOCK_POOL` | Workers and PostgreSQL pool sizes ([production notes](docs/production-deployment.md)) | 2, 15, 10, 10 |
| `FORCE_IRREGULAR_MODEL`, `FORCE_TEMPORAL_FEATURES`, `FORCE_ADAPTIVE` | Keep the forecasting experiments on in the live model | `true` |
| `SIM_YIELD_RATE` | Illustrative annual rate of the **simulated** yield pot | `0.05` |
| `RW_ARTIFACTS_DIR` | Where the pipeline writes artifacts | `backend/artifacts` |
| `VITE_API_URL` | Frontend: backend URL for deployed builds (unset locally; Vite proxies `/api`) | empty |

**Email setup (optional).** By default the security code is shown on screen so the demo needs no mail server. To send real emails, set `OTP_DEMO_MODE=false` and, for Gmail:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your.address@gmail.com
SMTP_PASSWORD=<16-character Google App Password>
SMTP_FROM=your.address@gmail.com
```

Gmail needs 2-Step Verification and an **App Password** (Google Account → Security). Check it with `cd backend && .venv/bin/python scripts/test_email.py you@example.com`, then restart the API.

---

## 8. Demo guide

### Judge access

| Role | Email | Password |
|---|---|---|
| Family | `rahima@demo.remitwise` | `demo1234` |
| Sender abroad | `rahim@demo.remitwise` | `demo1234` |
| Admin | `admin@demo.remitwise` | `demo1234` |

Demo accounts exist only while `SEED_DEMO_ACCOUNTS=true`; change `DEMO_PASSWORD` on a public deployment. Anyone can also create a Family account, or a Sender account with the family's invite code (Goals → Sharing).

### Five-minute path (Guided demo)
1. Sign in as **admin** → *Simulation sandbox* → **Reset household**.
2. Press the **Guided demo** steps 1 to 5 (also on a floating bar over the family app):
   1. **Remittance arrives**: the split pop-up opens.
   2. **Accept allocation**: bills reserved first, goals funded.
   3. **Unusual bill**: Payments shows a high electricity bill held for review.
   4. **Warning**: a delayed transfer plus a medical emergency; the banner explains why. Press 🔊 to hear it.
   5. **Resolution**: Plan screen, ask the sender to send earlier.
3. Switch to **বাংলা** to show the same screens in Bangla.
4. Admin → *Model performance*: warning before/after, the 60/80/100% table (labelled simulated), stress test, business KPIs; *Monitoring* for drift and fairness.

**Scenario buttons** (sandbox → *Real-life scenarios*): Delay next transfer, Eid expense surge, Medical emergency, Inject unusually high bill, Systemic shock. Open the family app to see the warning, safe-to-spend and reasons change.

---

## 9. Testing

```bash
./run.sh test                    # 134 backend tests, about 15 seconds
npm --prefix frontend test       # voice logic (node --test)
./run.sh test-pg                 # whole suite on PostgreSQL (needs Docker)
cd backend && python scripts/load_test.py --help
```

- **Coverage:** allocator invariants, summary safety (numbers validated, injection sanitised), consent and household isolation, bills and the vault, accounts and persistence, security codes (fake mail server), micro-savings and the yield pot, scenarios, guided demo, webhook signing and concurrency, monitoring, resilience, and a check that the forecaster beats its baseline. Overall statement coverage is **74%** (the offline data-generation modules are exercised by `./run.sh build`).
- **Security checks:** route-introspecting tests for missing tokens, role escalation and household isolation; `pip-audit` and `npm audit` clean. See [docs/security-check.md](docs/security-check.md). These are automated self-checks, **not** a penetration test.
- **PostgreSQL:** the whole pipeline and suite were run on PostgreSQL 18.6 (fresh database, user-space install): identical numbers, all tests passing. The suite expects a fresh database each run.
- **Groq:** tested through a mocked HTTP layer (valid output accepted, invented numbers rejected, outage falls back). Not called against the real service.

---

## 10. Deployment

- **Backend (Render):** New → Blueprint → select this repo ([render.yaml](render.yaml), Docker). Set `ALLOWED_ORIGINS` to the frontend URL, plus optional `DATABASE_URL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `GROQ_API_KEY`, `SMTP_*`.
- **Frontend (Vercel):** root `frontend`, environment variable `VITE_API_URL` = the backend URL.
- **Production-style stack:** `docker compose -f docker-compose.prod.yml up --build` (PostgreSQL + several API workers; first start loads data once).
- On free hosting the server sleeps when idle; the app shows a "Waking up the server…" screen with a retry. With SQLite, data resets on every redeploy; use PostgreSQL to keep it.

Guides: [docs/19-deployment.md](docs/19-deployment.md), [docs/production-deployment.md](docs/production-deployment.md).

---

## 11. Security and responsible AI

- **Human control.** The family decides every plan; auto-pay runs only under family mandates with limits; unusual bills always wait for the family; the AI explains and never decides.
- **Consent.** Senders see only what the family shares, enforced server-side; consent can be revoked at any time.
- **Grounded generative AI.** The LLM only rephrases numbers computed in code; any invented number discards its text; free-text inputs are sanitised against prompt injection.
- **Accounts.** Salted scrypt hashes, hashed session tokens, per-account rate limits, server-side roles, admin accounts provisioned not self-registered, security codes hashed at rest with expiry and attempt limits, no account discovery on reset, self-deletion.
- **Privacy and retention.** Admins see aggregates and masked emails only. See [docs/data-retention.md](docs/data-retention.md).
- **Fairness and drift.** Per-group error and coverage (regularity, region) and input drift are monitored; irregular senders are the group to watch.
- **Micro-savings** is off by default, needs consent, is capped at ৳100 a day, never touches the next two days of cash and pauses under risk. The **yield pot is a simulation** (synthetic money, illustrative rate, separate consent, withdraw any time): not a real product and not advice.
- **Honesty labels.** "AI estimate", "Simulated, not measured" and "Demo mode" appear where they apply.

---

## 12. Status and limitations

- Everything runs on **synthetic data**; money movement is simulated. No real upay integration, identity or payment system is connected.
- **Behaviour change** (compliance) is an assumption. A randomized pilot is designed in [docs/pilot-plan.md](docs/pilot-plan.md); no business result here is measured.
- The webhook is an **adapter tested with signed test events**, not a live upay feed.
- Security codes are shown on screen in demo mode; real email is implemented and tested against a fake mail server but **never tried against a real mail provider** from the development machine.
- The Groq call has **not been run against the real service** (no API key).
- PostgreSQL was verified locally and in a 4-worker load test, **not on a hosted or production-scale database**. Load tests ran on one laptop. Rate limits are per process.
- The forecasting experiments **did not improve accuracy**; they are on by team decision and their measured effect is shown, not hidden. The model is not robust to systemic shocks (coverage falls to 26%).
- Tokens are kept in `localStorage`; there is no multi-factor login and no independent penetration test.
- Voice output and microphone input depend on the device (a Bangla voice is needed for Bangla read-aloud).

**Next phase:** a controlled pilot with governed upay data, retraining and recalibration on real anonymised transactions, integration with upay identity, payment and remittance events, production PostgreSQL deployment and load testing, and formal security testing.

---

## 13. Phase 2: response to judge feedback

| Judge feedback | Response | Where |
|---|---|---|
| Improve the warning, show before/after (0.72/0.73 vs rule 0.95) | Tuned threshold plus a hybrid warning; full sweep | Admin → Model performance |
| Show 60/80/100% and say it is simulated | Side-by-side table with banner, in Admin and family Insights | Admin; Insights |
| Add delayed remittance, Eid, medical/electricity scenarios | All three, plus a systemic shock | Sandbox → Real-life scenarios |
| Bangla and voice for rural users | Bangla UI, read-aloud and voice questions | Language toggle; Home |
| upay brand colours and identity | Palette sampled from the official logo | Whole app |
| First load and smooth demo flow | Waking screen, skeletons, 5-step Guided demo | Admin → Guided demo |
| Phone/email verification and password reset | Emailed security codes (on-screen in demo mode), reset, self-deletion | Sign-up; Forgot password |
| Micro-savings, low-risk yield | Consent-based micro-savings with a simulated yield pot | Goals |
| "Not a budgeting app" | Explainer and comparison table | Home; sign-in |
| PostgreSQL, LLM path, load and concurrency testing | PostgreSQL run, mocked Groq tests, two load-test rounds | [docs/load-test-results.md](docs/load-test-results.md) |
| Data retention, security testing, drift and fairness monitoring | Policy, security checks, monitoring panel | [docs/data-retention.md](docs/data-retention.md), [docs/security-check.md](docs/security-check.md) |
| Irregular senders, sequence models, personalization | Built and evaluated; no accuracy gain, reported honestly | Admin → Model performance |
| Business KPIs and pilot | KPI view with editable assumptions; pilot plan | Admin; [docs/pilot-plan.md](docs/pilot-plan.md) |
| Real MFS events instead of simulation | Signed webhook adapter | [docs/09-api-contracts.md](docs/09-api-contracts.md) |
| Live pilot, real data, real integrations | **Out of scope today**: next phase | [docs/16-post-hackathon-path.md](docs/16-post-hackathon-path.md) |

Full task-by-task status with evidence: [docs/phase2/09-status-and-evidence.md](docs/phase2/09-status-and-evidence.md).

---

## 14. Documentation index

| Topic | Document |
|---|---|
| Hackathon rules, idea, users and problem | [01](docs/01-hackathon-rules-summary.md), [02](docs/02-idea-framework.md), [03](docs/03-users-and-problem.md) |
| Requirements, UX, UI design | [04](docs/04-product-requirements.md), [05](docs/05-ux-screens-and-flows.md), [20](docs/20-ui-design-and-screens.md) |
| AI/ML design, data spec, metrics | [06](docs/06-ai-ml-design.md), [07](docs/07-synthetic-data-spec.md), [11](docs/11-metrics-and-evaluation.md) |
| Architecture, API contracts, tech stack | [08](docs/08-architecture.md), [09](docs/09-api-contracts.md), [18](docs/18-tech-stack.md) |
| Responsible AI, accounts, retention | [10](docs/10-responsible-ai.md), [21](docs/21-auth-and-accounts.md), [data-retention](docs/data-retention.md) |
| Demo script, pitch, risks, path forward | [12](docs/12-demo-script.md), [13](docs/13-pitch-outline.md), [15](docs/15-risks-and-judging-map.md), [16](docs/16-post-hackathon-path.md) |
| Deployment, production, load and security | [19](docs/19-deployment.md), [production-deployment](docs/production-deployment.md), [load-test-results](docs/load-test-results.md), [security-check](docs/security-check.md) |
| Pilot design | [pilot-plan](docs/pilot-plan.md) |
| Phase 2 plan and status | [docs/phase2/](docs/phase2/) |
| Data assumptions | `backend/artifacts/data_card.md` |

---

## 15. Team

**Matrix Miners:** MD Mahmudur Rahman Supto, Sk Abu Sayeed, Shoukhinuzzaman Aditto.

Built for the AI Hackathon 2026, organised by DIU CPC with upay. RemitWise is a hackathon prototype: no real money, customer data or banking is involved.
