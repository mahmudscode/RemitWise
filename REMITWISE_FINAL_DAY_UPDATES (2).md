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
8. Update `README.md` at the end (Task 11) so judges can see what changed.

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

## Task 11. Update README (do last)

Add a section **"Final-day updates (based on Phase 1 feedback)"** with a table: judge comment → what was built → where to see it (screen / button). Include the new before/after warning numbers and the 60/80/100% table. Keep "simulated, not measured" wording.

Commit: `Document final-day updates in README`

---

## Out of scope today (explain in the pitch, do not build)

- Live pilot with real remittance families, real compliance measurement
- Retraining on real anonymised upay data; sequence models
- Real upay payment, identity, remittance webhooks
- Production PostgreSQL deployment, load and security testing
- Real investment products for micro-savings

Pitch line: "These are our next phase, a controlled pilot with governed upay data."
