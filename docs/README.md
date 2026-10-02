# RemitWise — Documentation Index

AI planner for families living on remittance income.
**Event:** AI Hackathon 2026 · DIU CPC × upay · **Track:** 03 Customer Innovation & Financial Independence (with a Track 07 angle)

> Status: planning docs only. Review these, then build from them. No code exists yet.

## Reading order
| # | File | Purpose |
|---|------|---------|
| 01 | [01-hackathon-rules-summary.md](01-hackathon-rules-summary.md) | What the organizers require and how we are judged |
| 02 | [02-idea-framework.md](02-idea-framework.md) | The mandatory 9-step logic chain + problem statement |
| 03 | [03-users-and-problem.md](03-users-and-problem.md) | Personas, pain points, baseline | 
| 04 | [04-product-requirements.md](04-product-requirements.md) | Features, scope (MVP vs stretch), acceptance criteria |
| 05 | [05-ux-screens-and-flows.md](05-ux-screens-and-flows.md) | Screens and user flows for both sides |
| 06 | [06-ai-ml-design.md](06-ai-ml-design.md) | Forecasting, allocator, early warning, LLM summaries |
| 07 | [07-synthetic-data-spec.md](07-synthetic-data-spec.md) | Simulated households, planted patterns, assumptions |
| 08 | [08-architecture.md](08-architecture.md) | Layers, components, data flow |
| 09 | [09-api-contracts.md](09-api-contracts.md) | Service interfaces (described, not coded) |
| 10 | [10-responsible-ai.md](10-responsible-ai.md) | Privacy, consent, fairness, oversight |
| 11 | [11-metrics-and-evaluation.md](11-metrics-and-evaluation.md) | Numbers to show judges, experiment design |
| 12 | [12-demo-script.md](12-demo-script.md) | Step-by-step demo and fallback plan |
| 13 | [13-pitch-outline.md](13-pitch-outline.md) | Slide-by-slide pitch |
| 14 | [14-build-plan.md](14-build-plan.md) | Work breakdown, order of build, roles |
| 15 | [15-risks-and-judging-map.md](15-risks-and-judging-map.md) | Risks, mitigations, criterion-to-feature map |
| 16 | [16-post-hackathon-path.md](16-post-hackathon-path.md) | Path to real upay validation and product |
| 17 | [17-open-questions.md](17-open-questions.md) | Decisions the team must make before building |

## One-line pitch
RemitWise forecasts when the next remittance will arrive, splits each transfer into needs / savings / goals so the family never runs short, warns early about shortfalls, and lets the sender abroad follow shared goals with consent.

## Core principles (carry through every doc)
1. The family decides; the system only recommends.
2. All arithmetic lives in deterministic code; the LLM only explains computed numbers.
3. Synthetic data only; assumptions documented.
4. Prove it is smarter than a budgeting app: forecast with uncertainty + side-by-side simulated year.
