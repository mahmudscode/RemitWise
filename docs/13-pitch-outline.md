# 13 — Pitch Outline

Audience: technical, business and executive judges. Aim ~8 slides + live demo; adapt to time limit.

1. **Title & one-liner** — RemitWise: AI planner for families living on remittance income. Track 03.
2. **Problem** — Millions of Bangladeshi households depend on irregular remittance; cash-out-all, run short, no savings; sender blind to shared goals. Use the problem statement template.
3. **User & why now** — Rahima and Karim; AI can forecast irregular income with uncertainty and explain in simple language.
4. **Solution** — the 5 pieces: forecast, allocator, early warning, shared goals, plain-language summaries. (Then go to live demo.)
5. **AI under the hood** — quantile forecaster + conformal intervals; optimizer on forecast gap; Monte-Carlo risk; grounded LLM with number validation. Rules separate from ML.
6. **Results** — table: forecast vs naive, shortfall days with/without, savings/buffer, wallet retention, warning precision/recall. Clearly mark measured vs assumed.
7. **Value to upay** — money stays in wallet longer, more digital transactions, retention, differentiated Track-03 offering.
8. **Responsible AI** — family decides, consent-based sharing, no manipulation, fairness cut, synthetic data.
9. **Path to product** — controlled validation with anonymized/aggregated data → POC → pilot; readiness checklist.
10. **Close** — ask: feedback and a path to controlled validation.

## Speaker notes principles 
- Lead with a person, then the number.
- One claim per slide, evidence on the slide.
- Say what is assumed out loud; it builds credibility.
- Map slides to judging criteria (doc 15).

## Final build: "you told us X, we built Y"
Open with the Phase 1 comments and the screen that answers each:
- *Warning precision 0.72 vs rule 0.95* → threshold tuned on calibration data and a hybrid warning; show the before/after table and chart, state the precision trade-off openly.
- *Show 60/80/100% and say it is simulated* → the side-by-side table with the banner.
- *Concrete scenarios* → Eid surge, medical emergency, delayed transfer, systemic shock.
- *Bangla, upay identity, faster first load, smooth demo path* → the toggle, brand colours, waking screen and Guided demo.
- *Security and responsible AI* → email security codes and password reset (really emailed when SMTP is configured; on-screen in demo mode), data-retention policy and self-deletion, monitoring panel, security checks (basic, not a pentest).
- *Innovation and business* → consent-based micro-savings with an optional simulated yield pot (answers the "low-risk yield" suggestion; not a real product), KPI view with editable assumptions, pilot plan.
- *Scalability* → signed webhook adapter, load-test numbers (laptop, one worker), PostgreSQL run.
Be upfront: several experiments (irregular-sender features, sequence models, per-household correction) did not improve accuracy on synthetic data; we show the result and say a pilot is the real test.
Close: "These are our next phase, a controlled pilot with governed upay data."
