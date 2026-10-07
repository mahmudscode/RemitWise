# 10 — Responsible AI, Privacy and Safety

Maps to the guideline's minimums (worth 5% of score, but also a trust story for upay).

| Principle | RemitWise implementation |
|---|---|
| Privacy | Synthetic data only; no real PII; data card documents assumptions. |
| Explainability | Every forecast, plan and warning shows main reasons (feature drivers/rule trace). |
| Fairness | Evaluate forecast error by regularity class, transfer size, region; report gaps; widen intervals/avoid false confidence for irregular households. |
| Security | Server-side consent enforcement, prompt-injection tests, no data leakage across households, role-based access, sanitized free text. |
| Human oversight | Family always accepts/edits/rejects; nothing auto-executes. |
| Transparency | UI separates **prediction**, **assumption**, **generated explanation**. |
| No harmful automation | No lending/approval decisions; credit-readiness (if built) is informational only. | 

## Family-specific safeguards
- **Consent-based sharing:** sender sees goal progress only by default; more only if the family opts in; revocable anytime; family can decline sender's request.
- **Anti-surveillance/coercion:** no transaction-level view for sender, no alerts to sender about family spending, no "score" of the family.
- **No manipulation:** no urgency language, no spend nudges, no hidden fees, no product pushing.
- **Informed choice:** show alternatives and trade-offs; family can ignore recommendations.

## Accounts and access
- Real sign-in (salted password hashes, hashed session tokens, rate limiting). Roles are decided on the server from the token.
- Families see only their own household; senders only what the family shares; admins only aggregates and the seeded demo households. See doc 21.

## Auto-pay safeguards (bills and EMI)
- Auto-pay applies only to mandates the family created and switched on; each has a monthly limit and an optional "confirm over limit" rule.
- Unusual bills (more than 1.8x the estimate) are **never paid automatically**; they wait for Approve / Dispute / Pay manually.
- Every mandate can be paused or cancelled at any time; actions are written to the audit log.
- Demo only: no real biller, account or money is connected.

## LLM safety
- LLM receives structured computed facts only; numbers validated post-generation; fallback to templates.
- Goal names and any user text sanitized; test with injection strings.
- Generated text labeled; never presented as a decision.
- No sensitive decision logic in prompts.

## Fairness test plan
1. Group households: regular vs irregular senders, small vs large transfers, urban vs rural.
2. Compare forecast error, interval coverage, warning precision/recall by group.
3. Report the gaps honestly; mitigation options: wider intervals, conservative allocation default, group-aware calibration.

## Known limitations to state openly
- Simulated behavior change is an assumption.
- Real remittance patterns may differ; synthetic calibration is not evidence.
- Language quality (Bangla) needs native review.
- Cultural/family dynamics vary; tool must not replace family decision-making.

## Final build additions
- **Micro-savings** is off by default, needs explicit consent, moves at most ৳100 a day, never touches the next two days of cash, and pauses automatically when a warning is amber/red or bills are at risk ("Paused to protect your bills"). By default it saves into the emergency fund or a goal. The family can additionally, with a separate consent, choose a **simulated low-risk yield pot**: synthetic money, an illustrative rate (`SIM_YIELD_RATE`, 5% a year), withdrawable in full at any time with no lock-in or fee, paused under the same risk rules, labelled "Simulated" everywhere. It is not a real investment product and not financial advice; a real product could lose value, and a real launch would need a licensed partner and regulatory review.
- **Monitoring.** Admin → Monitoring tracks rolling error and coverage, per-group flags and input drift. In production this would alert the model owner.
- **Stress test.** The model is not robust to systemic shocks (coverage falls to 26%); this is shown, not hidden.
- **Experiments are labelled.** Where an experiment is switched on without improving accuracy, the Admin screen says so.
- **Data retention and deletion.** `docs/data-retention.md`.
- **Voice** uses the device's speech APIs; a fixed set of questions is answered from numbers already on screen. No free-form LLM decisions.
- **Security checks** are basic and automated (`docs/security-check.md`); there has been no independent penetration test.
