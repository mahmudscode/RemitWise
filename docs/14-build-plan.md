# 14 — Build Plan

Dates unknown (see open questions). Plan expressed in phases; compress or expand to fit the time box. Build order is chosen so a demo-able slice exists early.

## Phase 0 — Alignment (before any code)
- Review and approve these docs.
- Resolve open questions (doc 17).
- Fix scope: MVP = F1–F6.

## Phase 1 — Data foundation
- Data simulator with planted patterns + data card.
- Train/validation/clean-test split by household and time.
- Baselines computed (naive forecast, fixed-rule budget, cash-out-all).
**Exit:** reproducible dataset; baseline metrics produced.

## Phase 2 — Intelligence core 
- Forecaster (quantile) + calibration; beat baseline.
- Allocator rules + optimizer; three plan options.
- Shortfall risk engine (Monte-Carlo) + drivers.
**Exit:** offline evaluation report shows results vs baselines.

## Phase 3 — Services
- API layer with contracts from doc 09.
- Consent service and audit log.
- Explanation service with number validation and template fallback.
**Exit:** all endpoints callable; sender responses consent-filtered.

## Phase 4 — Experience
- Family app, sender app, demo control panel.
- Core flow first: arrival → plan → accept; then warning; then goals/consent.
**Exit:** end-to-end demo script runs without manual patching.

## Phase 5 — Proof & polish
- With/without simulation, compliance sensitivity, fairness cuts.
- Prompt-injection and consent-leak tests.
- Demo rehearsal, backup video, pitch deck.

## Phase 6 — Final-day flexibility
- Add-goal, second income, delay toggle, new family member rehearsed.
- Freeze; no risky changes in last hours.

## Suggested roles (adapt to team size)
| Role | Owns |
|---|---|
| Data/ML | Simulator, forecaster, risk engine, evaluation |
| Backend | Allocator, APIs, consent, audit, LLM service |
| Frontend/UX | Family, sender, demo panel, Bangla-friendly copy |
| Product/Pitch | Docs, metrics story, deck, demo script, Q&A |

## Priority if time runs out (cut from bottom)
1. Forecast + allocator + warning working end-to-end (core value).
2. Shared goals with consent.
3. With/without comparison.
4. Grounded summaries.
5. Fairness cuts.
6. Stretch features (voice, Bangla UI, credit readiness).

## Definition of done (per feature)
Works in demo flow · reasons visible · tested on edge case · documented assumptions · no unvalidated numbers from the LLM.
