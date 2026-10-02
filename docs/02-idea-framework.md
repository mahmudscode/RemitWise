# 02 — Idea Development Framework (One-Page Logic Chain)

| Step | Question | RemitWise answer |
|---|---|---|
| 1. User | Who has the problem? | Receiving family in Bangladesh who depend on remittance (primary); the worker abroad who sends it (secondary). |
| 2. Problem | What is hard/costly/risky? | Remittance arrives irregularly in varying amounts and is usually cashed out at once. Families run short before the next transfer, save little, and the sender cannot see whether shared goals are on track. |
| 3. Why now | Why can AI help? | Time-series forecasting with uncertainty and optimization are mature; LLMs can explain plans in plain (Bangla-friendly) language; wallet transaction data makes inflow/outflow patterns observable. |
| 4. Solution | What are we building? | A two-sided planner: forecast next remittance → split it into needs/savings/goals → early shortfall warning → consent-based shared goals → plain-language summaries. |
| 5. AI role | What does the model do? | Prediction (arrival date + amount range), optimization (allocation), anomaly/risk detection (shortfall), generation (grounded explanations). |
| 6. Impact | What improves? | Fewer shortfall days, higher savings rate, longer emergency buffer, more remittance retained in wallet beyond 24h. |
| 7. Data | What can we simulate? | Synthetic households with irregular remittances, local income, recurring expenses, planted festival spikes, delayed transfers, one-off shocks. See doc 07. |
| 8. Validation | How do we know it works? | Offline: forecast error vs naive baseline on held-out test set. Experiment: simulated year with vs without RemitWise. Warning precision/recall. |
| 9. Scale | What changes with real data? | Retrain forecaster on anonymized/aggregated upay inflow data; calibrate allocation rules; governance and consent flows. See doc 16. |

## Problem statement (official template)
For **families who depend on remittance from relatives abroad**, **irregular, unpredictable inflows combined with immediate full cash-outs** cause **recurring shortfalls and no long-term saving, while senders lack visibility into shared goals**. We will build **an AI remittance planner** that uses **synthetic household cash-flow data** to **forecast incoming transfers, recommend how to allocate each one, warn of shortfalls early, and track consent-based shared goals**, with success measured by **forecast accuracy, reduction in simulated shortfall days, increase in savings rate, and share of remittance retained in the wallet**.

## Why this is not "just a budgeting app"
- Budgeting apps assume fixed income; RemitWise forecasts *irregular* income with uncertainty.
- Allocation is driven by the forecast gap until the next transfer, not fixed percentages.
- Two-sided consent model (sender + family).
- Proven by a side-by-side simulated year.
