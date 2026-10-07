# Phase 2 (On-Site Final) — Planning Docs

Planning only. No code in these files. They turn the Phase 1 judge feedback (score 74.7/100) into an executable plan for the on-site final. Source: `REMITWISE_FINAL_DAY_UPDATES (2).md` (updated: now 22 tasks in three priority tiers).

Team: Matrix Miners — MD Mahmudur Rahman Supto, Sk Abu Sayeed, Shoukhinuzzaman Aditto.

## Index
| File | Purpose |
|---|---|
| 00-README.md | This index and the ground rules |
| 01-judge-feedback-map.md | Each judge comment → task → criterion it lifts |
| 02-priority1-task-specs.md | Tasks 1–6: scope, where, acceptance, tests, commit message |
| 03-priority2-task-specs.md | Tasks 7–10: security, micro-savings, positioning, LLM/Postgres tests |
| 04-readme-and-pitch-updates.md | Task 22 (README) and pitch/demo changes |
| 08-priority3-task-specs.md | Tasks 11–21: retention, shock test, load test, security checks, forecasting experiments, monitoring, voice, KPIs, webhook |
| 09-status-and-evidence.md | Final status of all 22 tasks with where to verify each |
| 05-execution-plan.md | Order, time boxes, owners, commit discipline, stop rules |
| 06-test-and-verification-plan.md | Tests to add, pre-commit checks, demo smoke checklist |
| 07-risks-and-open-decisions.md | Risks, open items the team must confirm, out of scope |

## Ground rules (apply to every task)
1. Organizers' on-site requirements override everything in these docs.
2. One commit per task, with the exact message given. Judges grade Git history (Rulebook 5.2, 5.3, 8.3). No squash, rebase or force-push.
3. The existing backend tests must keep passing (132 at the end); new backend behaviour gets tests.
4. Do not break the demo: rebuild once after backend changes, then confirm API and web start.
5. All data synthetic. No real customer data, money movement or investment products.
6. Keep the existing design language, explanations and "AI estimate" labels.
7. Work in priority order. Tasks are independent; stop when time runs out.
8. Business impact is always labelled **"Simulated, not measured."**

## Relation to earlier docs
Builds on docs 01–21. Most relevant: 06 (AI/ML design), 11 (metrics), 12 (demo script), 13 (pitch), 15 (risks and judging map), 20 (UI), 21 (auth).
