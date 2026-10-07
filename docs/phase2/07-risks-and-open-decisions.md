# 07 — Risks and Open Decisions

## Open items the team must confirm
| Item | Needed for | Owner |
|---|---|---|
| Exact upay brand hex values (yellow, blue) from the official logo | Task 5 | Team |
| Any new on-site organizer requirement | Everything | Team lead |
| Bangla reviewer for translations | Task 4 | Native speaker on team |
| Docker available on site? | Task 10 PostgreSQL run | Team |
| Groq key available? (affects Bangla AI summary path) | Task 4 | Team |

## Risks
| Risk | Mitigation |
|---|---|
| Time runs out mid-list | Strict priority order; each task independent; commit after each |
| Higher precision looks like worse recall | Show full sweep, state trade-off, report lead days |
| Bangla touches many files, merge conflicts | Do it after other frontend tasks merge; single owner |
| Render cold start during judging | Loading screen plus early health ping; open the app before presenting |
| Guided demo fails from a dirty state | Each step tested from reset; always press Reset first |
| Brand mimicry concerns | Colours only, a "for upay" text line, no logo image copied |
| Overclaiming | Keep "Simulated, not measured", "AI estimate", "Demo: no SMS is sent"; never claim untested PostgreSQL |
| Broken demo after late change | Freeze before rehearsal; fix forward with a new commit |

## Out of scope (state in pitch, do not build)
- Live pilot with real families; real compliance measurement
- Retraining on real anonymised upay data; sequence models
- Real upay payment, identity, remittance webhooks
- Production PostgreSQL deployment, load and security testing
- Real investment products for micro-savings

**Pitch line:** "These are our next phase, a controlled pilot with governed upay data."
