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
