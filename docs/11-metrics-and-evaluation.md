# 11 — Metrics and Evaluation

Judges reward measured impact, not only model accuracy. Show all of these on a **clean test set** never used for training.

## Headline metrics
| # | Metric | Compared against | Target (to set after first run) |
|---|---|---|---|
| 1 | Remittance timing error (days, MAE) | "Same as last time" | Clearly lower, e.g., ≥20% better |
| 2 | Remittance amount error (MAPE/MAE) | "Same as last time" | Clearly lower |
| 3 | Interval coverage (does 80% range contain truth ~80%?) | Nominal | Within a few points of 80% |
| 4 | Simulated shortfall days per household per year | Without RemitWise | Large reduction (e.g., ≥40%) |
| 5 | Savings rate & months of emergency buffer after a simulated year | Without RemitWise | Positive buffer vs near zero |
| 6 | Share of remittance retained in wallet beyond 24h | Without RemitWise | Significant increase (upay value) |
| 7 | Warning quality: precision, recall, average lead time | Threshold-only rule | Report all three | 

*Targets are placeholders; set honestly after the first run — do not tune to the test set.*

## Experiment design: simulated year with vs without
- Same households, same remittance and shock sequences.
- Policy A: baseline behavior (cash out quickly, no plan).
- Policy B: follows RemitWise with a **compliance assumption** (e.g., 60% / 80% / 100%).
- Report results across compliance levels (sensitivity) so claims are not cherry-picked.
- Also compare against a **fixed-rule budget (50/30/20)** to show the system beats simple rules.

## Fairness cuts
Every headline metric split by regularity class, transfer size, region. Highlight the worst group and what we did.

## Product/business view (upay)
- Retained balance-days in wallet.
- Estimated increase in wallet transactions (from retained funds spent digitally) — state as assumption.
- Retention proxy: households active across all months.

## Reporting rules
- Separate **measured** (test set) from **assumed** (behavior change).
- State dataset size, seeds, split method.
- Keep a one-slide results table and a deeper evaluation page.

## Acceptance bar before demo
- Forecaster beats baseline on test set (both timing and amount) or we honestly report where it does not and why.
- Intervals reasonably calibrated.
- With/without comparison reproducible from one command/button.

## Final build: updated results (see README "Final-day updates")
All figures come from `backend/artifacts/evaluation.json`, measured on 100 held-out synthetic test households unless stated.
- **Shortfall warning.** Threshold chosen on calibration households only. Before: model only, best F1 (0.45): precision 0.72 / recall 0.73. Model only, precision-tuned (0.70): 0.91 / 0.52. **Final: hybrid (model OR the simple rule) at 0.70: 0.90 / 0.59, F1 0.71, 3.9 days of notice.** The simple rule alone: 0.95 / 0.55, 2.8 days. The hybrid is better on recall, notice and F1, worse on precision.
- **Compliance sensitivity (60 / 80 / 100%).** RemitWise bills on time 97 / 98 / 99%, late fees ৳177 / ৳101 / ৳60, kept in wallet 62 / 76 / 87% (no plan: 90%, ৳504, 13%). **Simulated, not measured.**
- **Stress test (systemic shock).** Timing error 8.0 to 20.9 days, timing coverage 83% to 26%, hybrid warning recall 0.57 to 0.78 with notice falling from 4.3 to 2.2 days. The forecaster was not trained on shocks.
- **Monitoring.** Rolling error and coverage per 30 days, per-group flags (coverage < 70% or error > 1.5x other groups), input drift via PSI. Irregular senders (timing error ~13.7 days, coverage ~77%) are flagged.
- **Experiments** (irregular-sender features, temporal/sequence models, per-household correction): none improved overall accuracy; results and the live model's own numbers are stored under `irregular_experiment`, `sequence_experiment`, `adaptive` and `live_model`.
- **Business KPIs** are a simulated estimate with editable assumptions; the randomized pilot design is in `docs/pilot-plan.md`.
- **Reporting rule kept:** measured vs assumed is labelled on every screen.
