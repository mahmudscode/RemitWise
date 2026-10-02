# 06 — AI/ML Design

Four AI components + one rules layer. AI depth is 20% of the score, so each must be defensible.

## A. Inflow forecaster (prediction with uncertainty)
**Task:** for each household, predict (1) days until next remittance and (2) its amount.
**Inputs (features):** history of arrival gaps and amounts, day-of-month, month/festival proximity, sender's history, recent delays, household local income, optional sender-declared intent.
**Approach options (pick one primary, keep one baseline):**
- Quantile regression with gradient boosting (e.g., LightGBM quantile objective) for timing and amount → gives P10/P50/P90.
- Alternative: probabilistic time-series (e.g., Prophet-style with intervals) or conformal prediction wrapped around any model for calibrated intervals.
- Recommendation: gradient-boosted quantile models + conformal calibration (simple, fast, explainable via feature importance).
**Baseline:** "same as last time" (same gap, same amount). 
**Outputs:** P10/P50/P90 arrival date; P10/P50/P90 amount; confidence label.
**Evaluation:** MAE/MAPE on amount, MAE in days on timing, interval coverage vs nominal (e.g., 80%), pinball loss. Group by regularity (fairness, doc 10).

## B. Smart budget allocator (optimization + rules)
**Task:** on arrival, split remittance into Needs / Savings / Goals.
**Logic (deterministic, auditable):**
1. Compute **gap** = days until next transfer using *pessimistic* bound (P90 date) so family is protected from late transfers.
2. **Needs reserve** = expected daily essential expenses × gap days (+ upcoming known bills, festival adjustment).
3. **Buffer top-up** toward target emergency months (e.g., 1→3 months).
4. Remaining surplus goes to **Goals** by priority/deadline using a simple constrained optimization (e.g., linear/greedy allocation maximizing on-track probability subject to non-negative surplus).
5. Output plan + reasons + alternative plans (conservative / balanced / goal-focused) so family chooses.
**Why AI:** allocation depends on the forecast distribution, not fixed percentages; optimizer reacts to uncertainty. Rules are kept separate from the model (guideline requirement).
**Baselines:** fixed 50/30/20; "withdraw everything."

## C. Shortfall early-warning (risk detection)
**Task:** during the cycle, estimate probability funds run out before next transfer.
**Approach:** Monte-Carlo projection of balance using spending-rate distribution (from history) and the forecast arrival distribution → probability of shortfall and run-out date range. Optionally a classifier (gradient boosting) trained on simulated cycles labeled "shortfall occurred." Alert when probability exceeds a threshold.
**Explanation:** feature attribution or rule trace → top drivers (e.g., "week-2 spending 40% above usual," "transfer expected later than usual").
**Evaluation:** precision, recall, lead time (days of warning) on test data.

## D. Grounded summary generator (GenAI)
**Task:** turn computed plan/warning/progress into simple language (Bangla-friendly target).
**Rules:**
- Prompt receives only a structured JSON of computed values; instructed to use no other numbers.
- Post-check: every numeric token in output must exist in the input; otherwise fall back to a template.
- No financial decisions made by LLM; no sensitive logic inside the prompt.
- Guard against prompt injection (sanitize any free text, e.g., goal names).
- Label output as "generated explanation."

## E. Optional: household clustering for fairness analysis
Group households by remittance regularity and size to evaluate model behavior across groups.

## Pipeline separation
Data prep → features → model inference → business rules/allocator → explanation layer → UI. Each stage independently testable and replaceable.

## Model governance
- Fixed train/validation/**clean test** split by household (no leakage across time within a household).
- Version models and data seeds; log predictions and reasons.
- Document assumptions and limitations in the app.
