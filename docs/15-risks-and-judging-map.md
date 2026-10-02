# 15 — Risks and Judging Map

## Criterion → how RemitWise earns it
| Criterion (weight) | Evidence we will show |
|---|---|
| Problem relevance (20%) | Remittance centrality in Bangladesh; clear persona; baseline pain (shortfall before next transfer); fits Track 03 "financial independence." |
| AI/ML depth (20%) | Irregular-income forecasting with calibrated uncertainty; optimization reacting to distribution; Monte-Carlo risk + drivers; grounded GenAI with validation. |
| Business/customer impact (20%) | Shortfall days, savings, buffer, wallet retention (upay value); economics framed as assumptions with sensitivity. |
| Prototype quality (15%) | Working two-sided end-to-end demo, scenario toggles, with/without view. |
| Innovation (10%) | Two-sided consent-based sender–family product; uncertainty-aware allocation. |
| Scalability & integration (10%) | Layered architecture, adapter for real data, stable API contracts, post-hackathon pathway. |
| Responsible AI & security (5%) | Consent, no surveillance, fairness cuts, injection tests, human oversight. |
 
## Risks and mitigations
| Risk | Likelihood | Mitigation |
|---|---|---|
| Seen as "just a budgeting app" (main risk) | High | Lead with irregular forecast + uncertainty; show naive and fixed-rule comparisons; side-by-side year. |
| Synthetic results look rigged | Medium | Honest assumptions, compliance sensitivity, clean test set, fairness cut shown. |
| Forecast does not beat naive baseline on some groups | Medium | Report honestly, widen intervals, conservative default; frame as fairness finding. |
| LLM hallucinated numbers | Medium | Structured facts only, number validation, template fallback. |
| Consent leak to sender | Low/High impact | Server-side filter, tests, audit log. |
| Demo failure (network/LLM) | Medium | Offline mode, cached text, backup video. |
| Scope creep | High | MVP frozen; stretch only after core works. |
| Bangla output quality | Medium | Native review; English fallback; keep simple vocabulary. |
| Over-claiming impact | Medium | Separate measured vs assumed on every results slide. |
| Perceived coercion/surveillance | Medium | Progress-only default, family control, explicit design rationale. |

## Product readiness checklist (guideline §13) — self-assessment
- [ ] Problem frequent/economically meaningful — yes (remittance households)
- [ ] AI beats a simple rule — to be shown by baselines
- [ ] Clear action after prediction — accept/adjust plan, respond to warning
- [ ] Measurable business benefit — wallet retention, shortfall days
- [ ] Validatable with real data later — inflow timing/amount data
- [ ] Privacy/fairness/explainability/security addressed — doc 10
- [ ] Integrates into real workflow — adapter + API contracts
