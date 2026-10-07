# RemitWise: Final-Day Updates (from Phase 1 judge feedback)

Repository: https://github.com/mahmudscode/RemitWise
Team: Matrix Miners (MD Mahmudur Rahman Supto, Sk Abu Sayeed, Shoukhinuzzaman Aditto)
Context: AI DEV FEST 2026 AI Hackathon, on-site final. Phase 1 score 74.7/100. These updates answer the judges' Phase 1 comments.

## Instructions for Claude Code (read first)

1. **The organizers' official on-site requirements always come first.** If the team gives you a new requirement from the organizers, do that before anything in this file.
2. **Commit after every task, separately, with the commit message given below.** Judges grade the on-site Git history (Rulebook 5.2, 5.3, 8.3). Never squash, rebase or force-push.
3. **Keep the 55 existing tests passing.** Run `cd backend && .venv/bin/python -m pytest -q` before each commit. Add tests for new backend behaviour.
4. **Don't break the demo.** After backend changes run `./run.sh build` once, then check the app starts (`./run.sh api` and `./run.sh web`).
5. **All data stays synthetic.** No real customer data, no real money movement, no real investment products.
6. **Keep the existing design language** (cards, tokens in `frontend/src/styles.css`). Keep explanations and "AI estimate" labels.
7. Do the tasks **in priority order**. Each task is independent; stop when time runs out.
8. Update `README.md` at the end (Task 22) so judges can see what changed.

---

## Priority 1: Highest score impact, fastest

### Task 1. Tune the shortfall warning threshold and show before/after
**Judge (AI/ML depth):** "Shortfall warning precision/recall is 0.72/0.73, while the simple rule achieves 0.95 precision. Improve the warning threshold and show the before/after result."

Where: `backend/app/evaluation.py` → `warning_metrics()` (currently picks the threshold that maximises F1 on calibration households, grid 0.15–0.85).

Do:
- Keep the old result as `before` (current F1-optimal threshold).
- Add a precision-focused selection: on **calibration households only**, choose the lowest threshold whose precision ≥ 0.85 (fallback: maximise F0.5). Report it on test households as `after`.
- Also store the full sweep: for every threshold in the grid, precision, recall, F1 and mean lead days on the test set (`sweep` list).
- Save in `evaluation.json` → `warning`: `before`, `after`, `sweep`, and keep `threshold` = the new chosen threshold so the live app (`main.py::_threshold()`) uses it automatically.
- Keep backward-compatible keys (`model`, `threshold_only_rule`) so nothing else breaks; `model` = `after`.

Frontend (`frontend/src/Admin.jsx`, Model performance tab):
- Add a small "Warning threshold: before vs after" table (threshold, precision, recall, F1, lead days, plus the simple rule row).
- Add a precision/recall vs threshold line chart (Recharts) from `sweep`, marking the chosen threshold.
- One honest note line: "Higher precision means fewer false alarms but some shortfalls are caught later or missed."

Acceptance: `./run.sh build` prints the new numbers; admin console shows before/after; tests pass (add a test that `after.precision >= before.precision`).
Commit: `Tune shortfall warning threshold for precision and show before/after`

### Task 2. Show 60% / 80% / 100% compliance side by side
**Judge (Business impact):** "Show results at 60%, 80%, and 100% compliance directly in the pitch/demo and emphasize that the business impact is simulated, not measured."

Where: `frontend/src/Admin.jsx` (comparison currently uses a dropdown). Data already exists in `evaluation.json` → `compare` (policy × compliance).

Do:
- Add a table showing all three compliance levels at once for RemitWise next to "No plan" and "Fixed 50/30/20": shortfall days, bills on time, late fees, kept in wallet after 24h.
- Clear banner above it: **"Simulated, not measured. Compliance is an assumption; a real pilot would measure it."**
- Add the same compact 3-column summary (bills on time, late fees, kept in wallet at 60/80/100%) to the family **Insights** page (`Insights.jsx`) with the same "simulated" label.

Acceptance: all three levels visible without using the dropdown.
Commit: `Show impact at 60, 80 and 100 percent compliance with simulated label`

### Task 3. Add judge scenarios: Eid expense surge and medical emergency
**Judge (Problem relevance):** "Add 2–3 concrete user scenarios: delayed remittance, Eid expense surge, and unexpected medical/electricity bill."

Where: `backend/app/live.py` → `scenario()`; `backend/app/main.py` scenario endpoint; `frontend/src/Admin.jsx` sandbox ("More scenarios").

Do:
- New scenario `eid_surge`: raise daily needs by ~40% for the next 10 days (e.g. temporary `need_mult` with an end day stored in state), log `eid_surge`.
- New scenario `medical`: one-off unexpected expense (default ৳8,000, reuse the `expense` path) logged as `medical_emergency`, so the warning reason reads "unexpected medical expense".
- Make sure the shortfall driver list (`risk.py` drivers / reasons) shows a readable reason for both.
- Sandbox: add buttons **"Eid expense surge"** and **"Medical emergency"**, and group the three judge scenarios (Delay next transfer, Eid surge, Medical / high electricity bill) under a heading **"Real-life scenarios"**.

Acceptance: each button changes the family app (warning or reduced safe-to-spend appears); tests for both scenarios.
Commit: `Add Eid surge and medical emergency scenarios to sandbox`

### Task 4. Bangla language toggle
**Judges 1 and 3 (Prototype):** "Add/enable Bangla UI, currently English only."

Where: new `frontend/src/i18n.js`; `App.jsx` (toggle in sidebar/top bar); main screens.

Do:
- Simple dictionary-based i18n (`t(key)`), `en` and `bn`, language saved in `localStorage` (wrap in try/catch).
- **EN | বাংলা** toggle visible in the sidebar and on the sign-in page.
- Translate at minimum: sidebar nav, Home (all card titles, warning banner, safe to spend, AI estimate badge), Remittance pop-up (split labels, buttons), Payments (status chips, review card buttons), Plan options, Goals, Sender view headings.
- Numbers can stay in Latin digits; use ৳ consistently.
- Font: `Noto Sans Bengali` (already in the font stack; add the Google Fonts link in `index.html`).
- The AI summary: if Groq is configured, request Bangla when `lang=bn`; template path should have a Bangla template too.

Acceptance: switching to বাংলা translates the full demo path (Home → remittance → payments → warning → plan → sender) with no English left on those screens except names and numbers.
Commit: `Add Bangla language toggle for main screens`

### Task 5. upay brand colours and identity
**Judge 3:** "Try to use upay's brand color and identity."

Where: `frontend/src/styles.css` `:root` tokens; `Auth.jsx`; sidebar logo.

Do:
- Change the colour tokens to upay's brand palette. **The team must confirm the exact hex values from the official upay logo** (the logo in the guideline PDF uses a yellow and a blue). Put them in `--primary`, `--navy`, and add `--brand-accent` for the yellow; keep green/amber/red status colours.
- Check text contrast stays readable (WCAG AA) on buttons and the balance card.
- Add a subtle "for upay" line next to the RemitWise logo on the sign-in page and sidebar. Do not copy the upay logo image.

Acceptance: app visibly matches upay colours; all text still readable.
Commit: `Apply upay brand colours`

### Task 6. Faster first load and smoother demo path
**Judge 3:** "Improve first-load experience. Make the main demo flow extremely smooth: remittance → allocation → unusual bill → warning → resolution."

Do:
- First load: show a friendly loading screen ("Waking up the server…") with retry while `/api/health` is not ready (Render free tier cold start). Fire a health ping as soon as the sign-in page loads.
- Add skeleton cards instead of "Collecting more history…" flashes on Home.
- Add a **"Guided demo"** panel in the admin sandbox with 5 numbered buttons that run the judge path on the selected demo household, each opening the right family screen:
  1. Remittance arrives (trigger remittance → open split pop-up)
  2. Accept allocation
  3. Unusual bill (inject high bill + advance until it appears → open Payments)
  4. Warning (delay next transfer + medical emergency → open Home)
  5. Resolution (open Plan, apply "Ask sender to send earlier")
- Each step must succeed reliably from a freshly reset household (add a test for the backend steps).

Acceptance: from "Reset household", the 5 buttons show the full story without manual time-travel guessing.
Commit: `Add guided demo path and faster first-load screen`

---

## Priority 2: Security and innovation (if time remains)

### Task 7. Phone OTP verification (simulated) and password reset
**Judge 1 (Responsible AI & security):** "Implement phone OTP verification and complete password reset workflows."

Where: `backend/app/auth.py`, `backend/app/db.py`, `backend/app/main.py` (`/api/auth/*`), `frontend/src/Auth.jsx`.

Do:
- Add optional `phone` to users (migration-safe for existing SQLite: add column if missing).
- `POST /api/auth/otp/request` → generate 6-digit code, store **hashed** with 5-minute expiry and max 5 attempts; rate-limited. In demo mode return the code in the response as `demo_code` and show it on screen ("Demo: no SMS is sent").
- `POST /api/auth/otp/verify` → marks phone verified.
- Password reset: `POST /api/auth/reset/request` (by email or phone, sends OTP the same way) and `POST /api/auth/reset/confirm` (code + new password, invalidates all sessions).
- Frontend: "Verify phone" step after sign-up, "Forgot password?" link on sign-in.
- Tests: expiry, wrong-code lockout, reset invalidates old token.

Acceptance: full flows work in demo mode; tests pass.
Commit: `Add simulated phone OTP verification and password reset`

### Task 8. Automated micro-savings (round-up to goals)
**Judge 1 (Innovation):** "Introduce automated micro-savings options…"

Responsible version: **save, do not invest** (no yield products, no financial advice).

Do:
- Family setting "Micro-savings": when on, at each day end move a small amount (e.g. round spending up to the next ৳10, or 1% of safe-to-spend surplus) into the emergency fund or a chosen goal, **only if** the shortfall risk is green and bills are covered.
- Pause automatically when a warning is amber/red; show "Paused to protect your bills".
- Show "Micro-saved this month: ৳X" on Goals and in the AI summary facts.
- Off by default; family must turn it on (consent).

Acceptance: toggle works, pauses on risk, totals shown; tests for the pause rule.
Commit: `Add consent-based micro-savings that pause when bills are at risk`

### Task 9. Stronger "not a budgeting app" message in the product
**Judge 3 (Innovation):** "Demonstrate that the core differentiator is forecasting irregular remittance arrival + planning around uncertainty."

Do:
- On Home, under the Next remittance card, a one-line explainer: "Budget apps track what you spent. RemitWise predicts when money will arrive and plans around that uncertainty."
- On the sign-in / landing page, a 3-point comparison: Budgeting app vs RemitWise (fixed salary vs irregular income; past spending vs future arrival; one number vs calibrated range).

Commit: `Explain forecasting-first difference from budgeting apps`

### Task 10. Exercise the Groq LLM path and PostgreSQL in tests (cheap credibility)
**Judge 3:** "PostgreSQL has not been tested, and the external LLM path has not been exercised without an API key."

Do:
- Add a test that mocks the Groq HTTP call and checks: valid output is accepted, output with an invented number is rejected and falls back to the template.
- Add a `docker-compose` service or CI note to run the test suite against PostgreSQL (`DATABASE_URL`), and run it once if Docker is available. If it can't run here, document the exact command in the README.

Commit: `Test LLM path with mocked Groq and document PostgreSQL test run`

---

## Priority 3: Remaining judge requests (do only if time remains)

These cover every other buildable item from the Phase 1 feedback. Same rules: one commit per task, tests passing, synthetic data only.

### Task 11. Data-retention policy (quick)
**Judge 2 (Responsible AI):** "Establish data-retention policies."

Do:
- Add `docs/data-retention.md`: what is stored (accounts, sessions, plans, audit log, demo state), how long (e.g. sessions 30 days, audit 12 months, deleted accounts purged in 30 days), who can see it, and how a family deletes its data.
- Implement the parts that are cheap: expire sessions older than the limit on startup/login; an endpoint `DELETE /api/me` that deletes the signed-in family/sender account and its data (admin and demo households excluded), with a confirmation in the UI.
- Link the policy from the README and the sign-in page footer.

Commit: `Add data-retention policy and account self-deletion`

### Task 12. Systemic shock scenario (quick)
**Judge 1 (AI/ML depth):** "Test robustness against unexpected systemic shocks."

Do:
- New sandbox scenario `systemic_shock`: all remittances delayed ~21 days **and** amounts cut 30% for the selected household (simulates a remittance-corridor disruption or exchange-rate shock).
- In `evaluation.py`, add a **shock stress test** on the test households: apply the same shock and report forecast coverage, warning recall and mean lead days under shock vs normal. Save as `evaluation.json` → `stress`.
- Show a "Stress test: systemic shock" table in Admin → Model performance, with an honest note (the model was not trained on shocks; the widening rule for overdue transfers is what protects families).

Commit: `Add systemic shock scenario and stress test`

### Task 13. Load and latency test (quick)
**Judge 2 (Scalability):** "Concurrency, latency, resilience and high-volume transaction testing."

Do:
- Add `backend/tests/load/locustfile.py` (Locust) or a simple `asyncio + httpx` script `backend/scripts/load_test.py` that signs in the demo accounts and hits `/api/home`, `/api/shortfall`, `/api/forecast` with N concurrent users.
- Run it locally (e.g. 50 concurrent users, 60 s) and save results (requests/s, p50/p95 latency, error rate) to `docs/load-test-results.md`.
- Add one resilience check: the API returns a clean error (not a crash) if the model file is missing or the DB is locked.

Commit: `Add load test script and record latency results`

### Task 14. More automated tests and basic security checks
**Judge 2 (Prototype / Security):** "Larger automated test coverage" and "formal security testing".

Do:
- Add `pytest-cov`; report coverage in the README.
- New tests: role escalation (sender/family cannot call admin endpoints), household isolation for every family endpoint, rate-limit on login, prompt-injection strings in all free-text fields, input validation (negative amounts, huge numbers, bad dates).
- Run `pip-audit` (backend) and `npm audit` (frontend); fix high-severity issues if simple, record results in `docs/security-check.md`.

Commit: `Expand tests and add basic security checks`

### Task 15. Better forecasts for irregular senders
**Judge 3 (AI/ML depth):** "Improve prediction for irregular senders."

Where: `backend/app/forecast.py`, `evaluation.py`.

Do:
- Add sender-regularity features (gap coefficient of variation over last 6 transfers, longest recent gap, trend of gaps) and/or **group-wise conformal calibration** (separate calibration offsets per regularity class: regular / semi / irregular) so ranges are honest for each group.
- Report before/after on the fairness check: timing error and range coverage **per group**, especially irregular senders (currently 13.7 days MAE).
- Keep the change only if it does not make overall MAE or coverage worse; record the result either way in `evaluation.json` → `irregular_experiment`.

Commit: `Improve irregular-sender forecasts with regularity features and group calibration`

### Task 16. Optional sequence-model experiment
**Judge 3 (AI/ML depth):** "Explore stronger temporal or sequence models where they demonstrably outperform the existing baseline."

Do (time-boxed, 1 hour max):
- A small sequence model over each household's last N gaps/amounts (e.g. a GRU in PyTorch, or LightGBM with lag/rolling features as a cheaper "temporal" variant).
- Compare against the current model on the same test households (timing MAE, amount error, coverage). Show the comparison in Admin → Model performance.
- **Only switch to it if it wins.** Otherwise keep LightGBM and show the experiment as evidence ("we tried; it did not beat the baseline").

Commit: `Add sequence-model experiment compared against LightGBM`

### Task 17. Model-drift and fairness monitoring panel
**Judge 2 (Responsible AI):** "Fairness and model-drift monitoring."

Do:
- In Admin, a "Monitoring" panel computed from recent live/demo events: rolling forecast error, range coverage, warning rate, and input drift (PSI or simple mean shift of key features vs training data).
- Per-group breakdown (regular / irregular senders, rural / urban) with a red flag when coverage drops below 70% or a group's error is far above the others.
- Text note: "In production this runs on real data and alerts the model owner."

Commit: `Add drift and fairness monitoring panel`

### Task 18. Adaptive household personalization
**Judge 2 (Innovation):** "Adaptive household-level personalization that learns from changing remittance and spending behaviour."

Do:
- Per-household adaptive layer on top of the global model: an exponentially weighted correction of the forecast using that household's recent forecast errors (online bias correction), and spending baselines that update with recent weeks.
- Show it in the Why? panel: "Adjusted for your household: +2 days (your transfers have been later than predicted recently)."
- Evaluate: test-set MAE with vs without the adaptive layer; keep only if it helps.

Commit: `Add adaptive per-household forecast correction`

### Task 19. Voice support (Bangla and English)
**Judges 1 and 2 (Prototype):** "Voice localization for non-tech-savvy rural users."

Do (browser APIs, no paid service):
- **Read aloud:** a 🔊 button on Home, the warning banner and the AI summary using the Web Speech API `speechSynthesis` (`lang` = `bn-BD` or `en-US`, fallback message if no Bangla voice on the device).
- **Voice question:** a 🎤 button using `SpeechRecognition` where available, supporting a few intents mapped to existing data (no free-form LLM decisions): "কত টাকা খরচ করতে পারি / how much can I spend", "পরের টাকা কবে আসবে / when is the next transfer", "কোন বিল বাকি / which bills are due". Answer with text + speech.
- Hide the mic gracefully on browsers without support.

Commit: `Add read-aloud and simple voice questions in Bangla and English`

### Task 20. upay KPI and incremental revenue view
**Judge 3 (Business impact):** "Establish business KPIs: wallet retention, transaction frequency, savings behaviour, customer retention and incremental revenue."

Do:
- Admin → new "Business KPIs (simulated)" card: kept-in-wallet %, digital bill payments per household per month, savings rate, and an **illustrative incremental value** estimate with every assumption shown as an editable input (e.g. bill-payment fee per transaction, float value per ৳ kept per day). No hidden constants.
- Label clearly: "Simulated estimate. A controlled pilot would measure these."
- Add a short `docs/pilot-plan.md`: randomized pilot design (treatment vs control families), KPIs above, duration, sample size estimate, success thresholds.

Commit: `Add simulated business KPI view and pilot plan`

### Task 21. Webhook adapter for real MFS events
**Judge 1 (Scalability):** "Replace simulated transaction events with actual MFS core-banking webhooks."

Do:
- `POST /api/webhooks/transactions` that accepts a documented JSON event (remittance received, cash-out, bill paid) with **HMAC signature verification** and idempotency key.
- An adapter that converts the event into the same internal events the simulator produces, so forecasts and warnings update.
- A small script `backend/scripts/send_test_webhook.py` and a test showing a signed event updates a demo household; unsigned events are rejected.
- Document the event schema in `docs/09-api-contracts.md`.

Commit: `Add signed transaction webhook adapter`

---

## Task 22. Update README (do last)

Add a section **"Final-day updates (based on Phase 1 feedback)"** with a table: judge comment → what was built → where to see it (screen / button). Include the new before/after warning numbers, the 60/80/100% table, stress-test and load-test results. Keep "simulated, not measured" wording.

Commit: `Document final-day updates in README`

---

## Out of scope today (explain in the pitch, do not build)

- Live pilot with real remittance families, real compliance measurement
- Retraining on real anonymised upay data
- Real upay payment and identity integration (the webhook adapter in Task 21 is the bridge)
- Production PostgreSQL deployment at scale and formal penetration testing
- Real investment products for micro-savings

Pitch line: "These are our next phase, a controlled pilot with governed upay data."
