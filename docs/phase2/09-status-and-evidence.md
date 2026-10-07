# 09 — Status and Evidence (final build)

Every task from `REMITWISE_FINAL_DAY_UPDATES (2).md`, what exists, and where to verify it. Numbers are from `backend/artifacts/evaluation.json` (100 held-out synthetic test households) and are **simulated, not measured**.

| # | Task | Status | Evidence |
|---|---|---|---|
| 1 | Warning threshold, before/after | Done, plus a hybrid warning | Admin → Model performance. Before 0.72/0.73; model only tuned 0.91/0.52; **hybrid 0.90/0.59** (rule alone 0.95/0.55) |
| 2 | 60/80/100% compliance | Done | Admin table with banner; family Insights |
| 3 | Eid and medical scenarios | Done | Sandbox → Real-life scenarios; tests |
| 4 | Bangla toggle | Done | Sidebar, sign-in, sender view; Bangla summaries |
| 5 | upay colours | Done | Palette sampled from the logo; AA contrast checked |
| 6 | Faster load, guided demo | Done | Waking screen, skeletons, 5-step Guided demo (also floating bar) |
| 7 | Security code and password reset | Done, **by email** (not phone). Shown on screen in demo mode (default); emailed through SMTP when `SMTP_*` is set and `OTP_DEMO_MODE=false` | Sign-up, forgot password, Goals; tests use a fake mail server |
| 8 | Micro-savings | Done | Goals card; pauses on risk; optional **simulated** yield pot with its own consent |
| 9 | Not a budgeting app | Done | Home explainer; sign-in comparison |
| 10 | Groq path and PostgreSQL | Done | Mocked-HTTP Groq tests; **full suite run on PostgreSQL 18.6** |
| 11 | Data retention | Done | `docs/data-retention.md`, `DELETE /api/me`, purge on start-up |
| 12 | Systemic shock | Done | Sandbox button; stress table (coverage 83% to 26%) |
| 13 | Load test | Done, two rounds | `docs/load-test-results.md`: 1 worker/SQLite, then **4 workers on PostgreSQL, 300 households, mixed writes, 4,000 concurrent webhook events applied exactly once**; fixed races found on the way |
| 14 | Tests and security checks | Done | 132 tests, 74% coverage, `docs/security-check.md`, audits clean |
| 15 | Irregular senders | Built; no accuracy gain; **on by team decision** | Admin experiment card; `live_model` |
| 16 | Sequence model | Built; neither variant won; temporal features **on by team decision**, neural net not used | Admin experiment card |
| 17 | Monitoring | Done | Admin → Monitoring |
| 18 | Adaptive personalization | Built; makes timing error worse (8.03 to 8.40 days); **on by team decision** | Admin card; Why panel; `FORCE_ADAPTIVE=false` turns it off |
| 19 | Voice | Done | 🔊 / 🎤 on Home; logic tested with `node --test` |
| 20 | KPIs and pilot plan | Done (simulated) | Admin KPI card; `docs/pilot-plan.md` |
| 21 | Signed webhook | Done | `POST /api/webhooks/transactions`; schema in doc 09 |
| 22 | README | Done | "Final-day updates" section |

## Honest limits
- PostgreSQL ran locally (suite and a 4-worker load test), not on a hosted or production-scale database; `docker-compose.prod.yml` and the Render steps are written but were not run from here (`docs/production-deployment.md`).
- Groq was never called against the real service (no key); only a mocked HTTP layer.
- The email path was tested with a fake SMTP server only; no real mail provider was used from here.
- Voice output and microphone input were not tested on a device with a Bangla voice.
- Security checks are automated self-checks, not a penetration test; the load test is a one-machine smoke test.
- The yield pot is a simulation: synthetic money, an illustrative rate, no real instrument, no advice. A real one needs a licensed partner.
- Tasks 15, 16 and 18 did not improve accuracy on synthetic data; the real question belongs to a pilot.
