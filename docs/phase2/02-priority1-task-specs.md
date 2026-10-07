# 02 — Priority 1 Task Specs (Tasks 1–6)

Each task: goal, scope, behaviour, acceptance, tests, commit.

---
## Task 1 — Tune shortfall warning threshold; show before/after
**Goal:** Raise warning precision toward the simple rule's 0.95 while being honest about the recall trade-off.

**Where:** backend evaluation module (`warning_metrics`); admin Model performance tab; `evaluation.json`.

**Behaviour**
- Keep the current F1-optimal result as `before`.
- New `after`: on calibration households only, lowest threshold with precision ≥ 0.85; fallback to maximising F0.5. Reported on test households.
- `sweep`: for every threshold in the grid (0.15–0.85) → precision, recall, F1, mean lead days on the test set.
- `evaluation.json → warning` holds `before`, `after`, `sweep`; `threshold` = the new chosen value so the live app uses it automatically.
- Backward-compatible keys kept (`model` = `after`, `threshold_only_rule`).

**UI (Admin → Model performance)**
- Table "Warning threshold: before vs after": threshold, precision, recall, F1, lead days, plus the simple-rule row.
- Line chart: precision and recall vs threshold, chosen threshold marked.
- Honest note: "Higher precision means fewer false alarms but some shortfalls are caught later or missed."

**Acceptance:** build prints new numbers; admin shows before/after; tests pass.
**Tests:** `after.precision >= before.precision`; threshold selection uses calibration data only (no test leakage).
**Commit:** `Tune shortfall warning threshold for precision and show before/after`

---
## Task 2 — 60 / 80 / 100% compliance side by side
**Goal:** Remove the dropdown dependency; make the "simulated" caveat unmissable.

**Behaviour**
- Admin: one table with RemitWise at 60%, 80%, 100% next to "No plan" and "Fixed 50/30/20". Columns: shortfall days, bills on time, late fees, kept in wallet after 24h.
- Banner above: **"Simulated, not measured. Compliance is an assumption; a real pilot would measure it."**
- Family Insights: compact 3-column summary (bills on time, late fees, kept in wallet at 60/80/100%) with the same label.
- Data source: existing `compare` block in `evaluation.json` (no new modelling).

**Acceptance:** all three levels visible without touching the dropdown.
**Commit:** `Show impact at 60, 80 and 100 percent compliance with simulated label`

---
## Task 3 — Eid surge and medical emergency scenarios
**Goal:** Concrete, relatable stress cases for judges.

**Behaviour**
- `eid_surge`: daily needs ≈ +40% for the next 10 days via a temporary multiplier with an end day kept in state; event logged as `eid_surge`.
- `medical`: one-off unexpected expense (default ৳8,000) through the existing expense path; logged as `medical_emergency`.
- Shortfall drivers/reasons show readable text for both (e.g. "unexpected medical expense", "Eid spending surge").
- Sandbox: new buttons "Eid expense surge" and "Medical emergency"; group with "Delay next transfer" under heading **"Real-life scenarios"**.

**Acceptance:** each button visibly changes the family app (warning or lower safe-to-spend).
**Tests:** one per scenario (state change, log entry, reason text, multiplier expires after 10 days).
**Commit:** `Add Eid surge and medical emergency scenarios to sandbox`

---
## Task 4 — Bangla language toggle
**Goal:** Full demo path usable in Bangla.

**Behaviour**
- Dictionary-based translation, `en` and `bn`; choice persisted in browser storage (guarded; must work if storage fails).
- **EN | বাংলা** toggle in sidebar and on sign-in.
- Minimum coverage: sidebar nav; Home (card titles, warning banner, safe to spend, AI-estimate badge); remittance pop-up (split labels, buttons); Payments (status chips, review buttons); Plan options; Goals; Sender view headings.
- Latin digits allowed; ৳ used consistently. Bengali font loaded.
- AI summary: Bangla when selected (LLM request if configured; Bangla template for fallback path).

**Acceptance:** Home → remittance → payments → warning → plan → sender shows no English except names and numbers.
**Review item:** a Bangla-speaking teammate proofreads wording before commit.
**Commit:** `Add Bangla language toggle for main screens`

---
## Task 5 — upay brand colours and identity
**Behaviour**
- Update colour tokens to upay palette (yellow + blue per logo): primary, navy, new brand-accent; keep green/amber/red status colours.
- Verify WCAG AA contrast on buttons and balance card.
- Subtle "for upay" line beside the RemitWise logo on sign-in and sidebar. Do **not** copy the upay logo image.

**Blocker:** exact hex values must be confirmed from the official upay logo (see doc 07).
**Acceptance:** app visibly matches upay colours; all text readable.
**Commit:** `Apply upay brand colours`

---
## Task 6 — Faster first load and guided demo path
**Behaviour**
- Cold-start screen: "Waking up the server…" with retry while health is not ready; health ping fires as soon as sign-in loads.
- Skeleton cards replace "Collecting more history…" flashes on Home.
- Admin sandbox **Guided demo** with 5 numbered buttons on the selected household, each opening the right family screen:
  1. Remittance arrives → split pop-up
  2. Accept allocation
  3. Unusual bill (inject high bill, advance until it appears) → Payments
  4. Warning (delay next transfer + medical emergency) → Home
  5. Resolution → Plan, apply "Ask sender to send earlier"
- Each step must work from a freshly reset household.

**Acceptance:** from "Reset household", the five buttons tell the full story with no manual time-travel.
**Tests:** backend test running steps 1–5 in order on a reset household.
**Commit:** `Add guided demo path and faster first-load screen`
