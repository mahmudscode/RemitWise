# 17 — Open Questions (decide before building)

## Organizer / logistics (not in the PDF)
1. Submission deadline, demo length, live demo vs recorded video?
2. Team size and roles; are non-DIU members allowed?
3. Are external LLM APIs allowed? Any restrictions on hosted services?
4. Required deliverables beyond prototype + pitch (report, repo, video, one-page logic chain)?
5. How is the "final-day flexibility" twist delivered (new requirement announced on the day)?

## Product decisions
6. UI languages: English only, Bangla, or both for the demo? Voice input in scope?
7. Platform: web only, or mobile-style web app? (Recommend mobile-style web, two windows for the two sides.)
8. Which currency/country archetypes for senders (Gulf, Malaysia, etc.)? Keep generic or named?
9. Allocation defaults: target emergency buffer months (1, 2 or 3)? Default plan option shown first?
10. Warning threshold: how sensitive  (higher recall vs fewer false alarms)?
11. Include the optional credit-readiness signal? (Recommend: no, unless core is finished.)
12. Should the sender be able to enter "send intent" to improve forecast? (Recommend: yes, optional.)

## Technical decisions
13. Forecaster: gradient-boosted quantile + conformal (recommended) vs probabilistic time-series model.
14. Storage: SQLite (simple demo) vs PostgreSQL.
15. LLM provider and fallback strategy; Bangla quality acceptable?
16. Compliance assumptions to present in the with/without experiment (e.g., 60/80/100%).
17. Dataset size and time horizon (default 300 households × 24 months).

## Evidence decisions
18. Which fairness cohorts do we publish?
19. How do we phrase impact claims so measured vs assumed is unmistakable?
20. Do we get any native-speaker review of Bangla text before the demo?

## How to use this file
Answer inline (add "Decision:" under each), then treat answers as locked for the build.
