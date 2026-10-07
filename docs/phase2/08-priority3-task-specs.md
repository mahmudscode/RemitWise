# 08 — Priority 3 Task Specs (Tasks 11–21)

Remaining judge requests. Start only after Priority 1 and 2 are committed. Same rules: one commit per task, tests green, synthetic data only. Many are quick; 15–19 and 21 are larger and can be dropped.

---
## Task 11 — Data-retention policy and account self-deletion (quick)
**Judge 2, Responsible AI.**
- `docs/data-retention.md`: what is stored (accounts, sessions, plans, audit log, demo state), how long (sessions 30 days, audit 12 months, deleted accounts purged within 30 days), who can see it, how a family deletes its data.
- Cheap implementation: expire old sessions on startup/login; `DELETE /api/me` removes the signed-in family/sender and their data (admins and demo households excluded), with a confirmation in the UI.
- Link the policy from the README and the sign-in footer.
- **Tests:** deletion removes account, sessions, goals, state; demo/admin refused; other families untouched.
- **Commit:** `Add data-retention policy and account self-deletion`

## Task 12 — Systemic shock scenario and stress test (quick)
**Judge 1, AI/ML depth.**
- Sandbox scenario `systemic_shock`: all remittances delayed ~21 days and amounts cut 30% for the household (corridor disruption or exchange-rate shock).
- Evaluation: apply the same shock to test households; report forecast coverage, warning recall and mean lead days, shock vs normal. Save as `evaluation.json → stress`.
- Admin → Model performance: "Stress test: systemic shock" table with an honest note (not trained on shocks; the overdue-widening rule is the protection).
- **Commit:** `Add systemic shock scenario and stress test`

## Task 13 — Load and latency test (quick)
**Judge 2, Scalability.**
- `backend/scripts/load_test.py` (asyncio + httpx) or Locust: sign in demo accounts, hit home, shortfall and forecast with N concurrent users.
- Run locally (about 50 users, 60 s); record requests/s, p50/p95 latency, error rate in `docs/load-test-results.md`, with machine and database noted (SQLite vs PostgreSQL).
- Resilience check: clean error, not a crash, if the model file is missing or the database is locked.
- **Commit:** `Add load test script and record latency results`

## Task 14 — More tests and basic security checks
**Judge 2, Prototype/Security.**
- `pytest-cov`; report coverage in the README.
- New tests: role escalation to admin endpoints, household isolation for every family endpoint, login rate limit, prompt-injection strings in all free-text fields, validation of negative/huge amounts and bad dates.
- Run `pip-audit` and `npm audit`; fix simple high-severity findings; record in `docs/security-check.md`. Describe it as basic checks, not a penetration test.
- **Commit:** `Expand tests and add basic security checks`

## Task 15 — Better forecasts for irregular senders
**Judge 3, AI/ML depth.**
- Add regularity features (gap CV over last 6 transfers, longest recent gap, gap trend) and/or group-wise conformal calibration per regularity class.
- Report before/after per group (timing MAE and coverage), especially irregular senders (currently 13.7 days MAE).
- Keep the change only if overall MAE and coverage do not get worse; record the result either way in `evaluation.json → irregular_experiment`.
- **Commit:** `Improve irregular-sender forecasts with regularity features and group calibration`

## Task 16 — Sequence-model experiment (time-boxed, 1 hour)
**Judge 3, AI/ML depth.**
- Small GRU over the last N gaps/amounts, or LightGBM with lag/rolling features as a cheaper temporal variant.
- Compare with the current model on the same test households (timing MAE, amount error, coverage); show in Admin → Model performance.
- Switch only if it wins; otherwise keep LightGBM and show it as evidence ("we tried; it did not beat the baseline").
- **Commit:** `Add sequence-model experiment compared against LightGBM`

## Task 17 — Drift and fairness monitoring panel
**Judge 2, Responsible AI.**
- Admin "Monitoring" panel from recent demo events: rolling forecast error, range coverage, warning rate, input drift (PSI or mean shift vs training).
- Per-group view (regular/irregular, rural/urban); red flag when coverage < 70% or a group's error is far above the rest.
- Note: "In production this runs on real data and alerts the model owner."
- **Commit:** `Add drift and fairness monitoring panel`

## Task 18 — Adaptive household personalization
**Judge 2, Innovation.**
- Per-household online bias correction from recent forecast errors (exponentially weighted) and spending baselines that update with recent weeks.
- Show in the Why? panel: "Adjusted for your household: +2 days (your transfers have been later than predicted recently)."
- Evaluate test MAE with vs without; keep only if it helps.
- **Commit:** `Add adaptive per-household forecast correction`

## Task 19 — Voice support in Bangla and English
**Judges 1 and 2, Prototype.**
- Read aloud (🔊) on Home, the warning banner and the AI summary via `speechSynthesis` (`bn-BD` / `en-US`), with a fallback message when no Bangla voice exists.
- Voice question (🎤) via `SpeechRecognition` where available, fixed intents only (how much can I spend, when is the next transfer, which bills are due), answered from existing data as text plus speech. No free-form LLM decisions.
- Hide the mic on unsupported browsers.
- **Commit:** `Add read-aloud and simple voice questions in Bangla and English`

## Task 20 — Business KPI view and pilot plan
**Judge 3, Business impact.**
- Admin "Business KPIs (simulated)": kept-in-wallet %, digital bill payments per household per month, savings rate, and an illustrative incremental value with every assumption editable (bill-payment fee, float value per ৳ per day). No hidden constants.
- Label: "Simulated estimate. A controlled pilot would measure these."
- `docs/pilot-plan.md`: randomized treatment vs control families, KPIs, duration, sample size, success thresholds.
- **Commit:** `Add simulated business KPI view and pilot plan`

## Task 21 — Signed transaction webhook adapter
**Judge 1, Scalability.**
- `POST /api/webhooks/transactions`: documented JSON event (remittance received, cash-out, bill paid), HMAC signature check, idempotency key.
- Adapter maps events to the internal events the simulator produces so forecasts and warnings update.
- `backend/scripts/send_test_webhook.py`; tests: signed event updates a demo household, unsigned/replayed events rejected.
- Document the schema in `docs/09-api-contracts.md`.
- **Commit:** `Add signed transaction webhook adapter`

---
## Suggested order inside Priority 3
Quick wins first: 11, 12, 13, 14. Then 20 (mostly UI and a doc), 17, 21. Then the modelling experiments 15, 18, 16 (each is evidence, kept only if it helps). 19 last (browser-dependent, needs a device check).
