# 01 — Hackathon Rules Summary

Source: *AI Hackathon 2026 – DIU CPC × upay – Student Project Guideline*.

## Goal of the program
Product-oriented innovation: problem discovery → AI solution design → working prototype → measurable impact → path to future validation. Not a generic chatbot, a dashboard, or a model-accuracy score.

## Program principles
- **Customer-first:** clear benefit to a customer, merchant, agent or internal user.
- **AI with purpose:** AI performs a meaningful prediction, recommendation, detection, optimization, generation or automation.
- **Build, do not only pitch:** a functional prototype is expected.
- **Privacy by design:** no production data is provided or required.
- **Future-ready:** explain how it could be validated with controlled upay data later.
- **Responsible innovation:** explainable, secure, human oversight for high-impact decisions.

## Track we chose
**Track 03 — Customer Innovation & Financial Independence** (flagship). Matching listed opportunities: Personal Savings Planner, Cash-Flow Forecasting, Financial Goal Copilot, Inclusive Financial Assistant, Financial Literacy Personalizer, Responsible Credit Readiness (optional).
Track 07 (Open Innovation) angle: two-sided sender/family product.

Track 03 rule: *empower the customer. Avoid manipulative recommendations, hidden fees, or designs that encourage unnecessary spending.*

## Mandatory deliverable before coding
One-page logic chain (9 steps) — see [02-idea-framework.md](02-idea-framework.md). Use the recommended problem statement template.

## Data rules
- Synthetic, public, or self-generated data only. Never real PII.
- Realistic but clearly synthetic; inject known patterns; **document every assumption**.
- **Keep a clean test set not used for training.**

## Architecture expectations
- Separate data preparation from model inference.
- Keep business rules distinct from ML predictions.
- Outputs traceable and explainable.
- APIs designed so a real backend can be attached later.
- **Do not put sensitive decision logic entirely inside a free-form LLM prompt.**

## Responsible AI minimums
| Principle | Minimum |
|---|---|
| Privacy | Synthetic/public/self-generated only |
| Explainability | Show main reasons behind important predictions |
| Fairness | Check behavior across relevant groups |
| Security | Consider adversarial manipulation, prompt injection, data leakage, access control |
| Human oversight | High-impact actions allow human review |
| Transparency | Separate predictions, assumptions, generated explanations |
| No harmful automation | No autonomous consequential financial decisions |

## Judging weights
| Criterion | Weight |
|---|---|
| Problem relevance | 20% |
| AI/ML depth | 20% |
| Business/customer impact | 20% |
| Prototype quality (working end-to-end) | 15% |
| Innovation | 10% |
| Scalability & integration | 10% |
| Responsible AI & security | 5% |

## "Good project" tests from the guideline
- Can you answer: **What happened? Why is it risky/important? What should upay do next?** (Track 01 wording; apply analogously.)
- Prediction connects to a practical action; measures whether the action changes behavior; gives transparent reasons.
- Product readiness: frequent/economically meaningful problem; AI beats a simple rule; clear action; measurable benefit; validatable later; privacy/fairness/security addressable; integrates into real workflow.

## Not in the PDF (confirm with organizers)
Submission format, deadline, team size, demo length, whether a live demo vs video is required, allowed LLM providers. Tracked in [17-open-questions.md](17-open-questions.md).
