# 01 — Judge Feedback Map

| # | Judge comment (Phase 1) | Criterion | Task | Visible where |
|---|---|---|---|---|
| 1 | Shortfall precision/recall 0.72/0.73 vs simple rule 0.95 precision; tune threshold, show before/after | AI/ML depth (20%) | 1 | Admin → Model performance |
| 2 | Show 60/80/100% compliance in demo; stress impact is simulated | Business impact (20%) | 2 | Admin comparison table; family Insights |
| 3 | Add scenarios: delayed remittance, Eid surge, medical/electricity bill | Problem relevance (20%) | 3 | Admin sandbox → "Real-life scenarios" |
| 4 | Bangla UI (English only today) | Prototype (15%) | 4 | EN / বাংলা toggle, sidebar and sign-in |
| 5 | Use upay brand colour and identity | Prototype (15%) | 5 | Whole app theme |
| 6 | Faster first load; make remittance → allocation → unusual bill → warning → resolution smooth | Prototype (15%) | 6 | Loading screen; Admin → Guided demo |
| 7 | Phone OTP verification and complete password reset | Responsible AI & security (5%) | 7 | Sign-up, sign-in |
| 8 | Automated micro-savings | Innovation (10%) | 8 | Goals, family settings |
| 9 | Show the differentiator is forecasting irregular arrival, not budgeting | Innovation (10%) | 9 | Home explainer; landing comparison |
| 10 | PostgreSQL untested; LLM path not exercised without key | Scalability (10%) / credibility | 10 | Test suite, README |
| 11 | Establish data-retention policies | Responsible AI (5%) | 11 | Policy doc, account deletion, sign-in footer |
| 12 | Test robustness against systemic shocks | AI/ML depth (20%) | 12 | Sandbox scenario; Admin → stress-test table |
| 13 | Concurrency, latency, resilience, high-volume testing | Scalability (10%) | 13 | Load-test script and results doc |
| 14 | Larger test coverage; formal security testing | Prototype (15%) / Security | 14 | Coverage in README; security-check doc |
| 15 | Improve prediction for irregular senders | AI/ML depth (20%) | 15 | Admin → per-group fairness table |
| 16 | Explore sequence models where they beat the baseline | AI/ML depth (20%) | 16 | Admin → model comparison |
| 17 | Fairness and model-drift monitoring | Responsible AI (5%) | 17 | Admin → Monitoring panel |
| 18 | Adaptive household personalization | Innovation (10%) | 18 | Why? panel on Home |
| 19 | Voice localization for rural users | Prototype (15%) | 19 | 🔊 / 🎤 buttons |
| 20 | Business KPIs: retention, frequency, savings, incremental revenue | Business impact (20%) | 20 | Admin → Business KPIs; pilot plan doc |
| 21 | Replace simulated events with real MFS webhooks | Scalability (10%) | 21 | Webhook endpoint, API contract doc |

## Weight view
- Largest pending upside: AI/ML depth, Business impact, Problem relevance (20% each) → Tasks 1, 2, 3 first.
- Prototype (15%) → Tasks 4, 5, 6.
- Lower-weight items (7–10) only after Priority 1 is done and committed.
- Priority 3 (11–21): highest value per hour are 12 and 20 (20%-weight criteria) and the quick wins 11, 13, 14. The modelling experiments 15, 16, 18 are kept only if they beat the current model; a documented negative result is still evidence.

## Pitch framing
Every item answers a stated judge comment. In the pitch say "you told us X; here is Y", then show the screen.
