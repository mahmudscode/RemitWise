# 05 — UX Screens and Flows

Two experiences: **Family app** (receiver) and **Sender app** (abroad). Simple, Bangla-friendly, large text, minimal jargon.

## Family app screens
1. **Home / Plan** — next expected remittance (date range + amount range), current balance, "days until next transfer," plan status (green/amber/red).
2. **Remittance Arrived** — shows amount, proposed split (Needs / Savings / Goals) with plain-language reasons; buttons Accept / Adjust / Skip. Family always decides.
3. **Adjust Split** — sliders with live effect on projected shortfall risk (computed in code).
4. **Shortfall Warning** — "At this pace money may run out around day X–Y. Main reasons: …" with 1–2 suggested actions. No pressure language.
5. **Goals** — list of goals with progress bars, monthly contribution, on-track status; add goal.
6. **Sharing & Consent** — toggle what the sender can see (default: goal progress only); revoke anytime.
7. **Summary (explain)** — plain-language weekly summary with a "why am I seeing this" link.
8. **Data & Assumptions** — labels what is prediction vs assumption vs generated text.

## Sender app screens
1. **Goals Dashboard** — shared goals progress only.
2. **Send Intent (optional)** — enter planned transfer amount/date to improve forecast; shows how plan would change.
3. **Consent Status** — what the family has chosen to share.
4. **Request More Visibility** — a request the family can accept or decline.

## Admin / Demo control panel (for judges)
- Pick household, scrub simulated time, trigger events (delayed transfer, festival spike, large expense).
- Toggle **With RemitWise / Without** to show side-by-side simulated year.
- View metrics panel (doc 11).
 
## Key flows
1. **Remittance arrives → plan → accept** (core demo).
2. **Mid-month spending spike → early warning → family adjusts.**
3. **Delayed transfer → forecast interval widens → plan buffers more.**
4. **Consent: family enables/revokes sharing → sender view updates.**
5. **New goal added → allocator rebalances → summary regenerated.**

## UX rules (from Responsible AI)
- Recommend, never auto-act.
- No nudges to spend, no fees, no product pushing.
- Show uncertainty as ranges, not false precision.
- Every recommendation has a visible reason.
