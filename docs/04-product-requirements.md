# 04 — Product Requirements

## Scope tiers
- **MVP (must demo):** F1–F6.
- **Stretch (final-day flexibility):** S1–S5.

## MVP features
### F1 — Synthetic household simulator
Generate N households with irregular remittance, local income, recurring expenses, planted events. Reproducible via seed. Spec: doc 07.
**Acceptance:** at least 200 households × 24 months; planted patterns verifiable; test split held out.

### F2 — Remittance inflow forecast
Predict next arrival date and amount with an uncertainty range (not a single number).
**Acceptance:** beats "same as last time" on both timing and amount on held-out households; intervals' coverage reported.

### F3 — Smart budget allocator
When a remittance arrives, recommend a split into **needs / savings / goals** based on the forecast gap to the next transfer (use the pessimistic bound for needs).
**Acceptance:** produces plan with reasons; family can accept, edit or reject; never auto-executes.

### F4 — Shortfall early warning
Flag when current spending pace will exhaust funds before the expected next transfer, with top drivers.
**Acceptance:** warning shows projected run-out date range, drivers, and a suggested action; precision/recall measured on test data.

### F5 — Shared family goals (consent-based) 
Goals visible to both sides as progress only (percent/amount), not transactions, unless the family opts in to share more.
**Acceptance:** consent state required from both sides; revocable anytime; sender view never exposes spending detail by default.

### F6 — Plain-language summaries
LLM-generated explanation of plan, warnings and progress, grounded only in computed numbers supplied to it.
**Acceptance:** every number in the text is traceable to a computed field; assumptions and predictions labeled separately; Bangla-friendly output as target.

## Stretch features
- S1: New goals on demand (education, emergency, business).
- S2: Second income source.
- S3: Delayed-transfer scenario toggle in demo.
- S4: New family member / changed expenses.
- S5: Voice input / Bangla UI (Inclusive Assistant).
- S6: "What if" simulator (e.g., "what if transfer is 2 weeks late?").
- S7: Responsible credit-readiness signal (explainable, no lending decisions) — only if time allows.

## Out of scope
Real money movement, real lending decisions, real PII, real upay integration, product upsell or fee features.

## Non-functional requirements
- Deterministic and reproducible results (seeded).
- Every output carries its reasons (explainability).
- Business rules separate from ML predictions.
- LLM never computes numbers; prompt-injection resistant.
- Works end-to-end offline for demo reliability (cached LLM responses as fallback).
