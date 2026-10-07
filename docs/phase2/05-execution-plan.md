# 05 — Execution Plan

Total on-site time is unknown; use relative boxes and stop when time ends. Re-check the organizers' requirements first.

## Order and time boxes
| Step | Task | Box | Suggested owner |
|---|---|---|---|
| 0 | Read organizer requirements; confirm repo clean, tests green | 15 min | All |
| 1 | Task 1 threshold + chart | 60 min | Backend/ML |
| 2 | Task 2 compliance table | 30 min | Frontend |
| 3 | Task 3 scenarios | 45 min | Backend + Frontend |
| 4 | Task 6 guided demo + loading | 60 min | Full-stack |
| 5 | Task 4 Bangla | 75 min | Frontend + Bangla reviewer |
| 6 | Task 5 upay colours | 30 min | Frontend (needs hex values) |
| 7 | Tasks 7–10 as time allows (9 and 10 are cheapest) | rest | Split |
| 8 | Task 11 README | 20 min | Whoever finishes first |
| 9 | Rehearse demo end to end, both languages | 30 min | All |

Parallelism: backend (1, 3) and frontend (2, 5) can run at once. Task 6 depends on Task 3 (medical scenario). Task 4 touches many files, so do it when others are merged to avoid conflicts.

## Commit discipline
- One task, one commit, message exactly as in docs 02–04.
- Before each commit: run the backend test suite; confirm green.
- No squash, rebase or force-push. Push after each commit so history is visible.
- Different team members commit their own work so history shows all contributors.

## Stop rules
- If a task is half done at its time box, finish minimally, commit working state, move on.
- Never leave the demo broken: if a change breaks start-up, revert that commit forward (new commit), not by rewriting history.
- Freeze new features before the rehearsal step.

## Definition of done (per task)
Acceptance met, tests added and passing, app starts, label wording intact, commit made.
