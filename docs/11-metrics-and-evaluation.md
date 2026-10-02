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
