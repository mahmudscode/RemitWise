# 06 — Test and Verification Plan

## Pre-commit checklist
1. Backend test suite passes (55 existing + new).
2. After backend changes: rebuild artifacts once; confirm new numbers print.
3. API and web both start.
4. Visual check of the changed screen in light of "AI estimate" and "simulated" labels.

## New tests by task
| Task | Test |
|---|---|
| 1 | `after.precision >= before.precision`; threshold chosen on calibration only; sweep covers whole grid; old keys still present |
| 3 | Eid surge raises needs ~40% and expires after 10 days; medical adds expense and logs event; reason text readable |
| 6 | Guided steps 1–5 succeed in order from a reset household |
| 7 | OTP expiry; lockout after 5 wrong codes; rate limit; reset invalidates old session; no account enumeration |
| 8 | Pauses on amber/red; runs on green only; off by default; never breaks bill cover |
| 10 | Mocked Groq: valid accepted; invented number rejected → template fallback |
| 11 | Account deletion removes data; demo/admin refused; old sessions expire |
| 12 | Shock scenario delays transfers and cuts amounts; stress results saved with sensible fields |
| 14 | Role escalation, household isolation for every family endpoint, injection strings, bad amounts/dates; coverage reported |
| 15 / 16 / 18 | Overall MAE and coverage not worse than before, otherwise change not kept |
| 21 | Signed event updates a demo household; unsigned, bad-signature and replayed events rejected |

Also run `pip-audit` and `npm audit` (Task 14) and the load script (Task 13) once the app starts; record results in docs.

## Manual demo smoke checklist
- [ ] Cold start screen appears and recovers
- [ ] Reset household → Guided demo 1…5 in order
- [ ] Each step opens the right family screen
- [ ] Warning appears with readable reason (medical / Eid)
- [ ] Resolution: "Ask sender to send earlier" clears or lowers warning
- [ ] Insights and Admin show 60/80/100 with "Simulated, not measured"
- [ ] Admin shows threshold before/after table and chart
- [ ] EN ↔ বাংলা on every screen of the demo path; no layout break
- [ ] upay colours applied; text contrast readable
- [ ] Sign-up → OTP (demo code shown) → sign-in; forgot password works
- [ ] Micro-savings off by default; pauses under risk
- [ ] (If built) systemic shock button, monitoring panel, KPI card, 🔊/🎤 work in English and Bangla

## Evidence to keep
Screenshots of before/after table, 60/80/100 table, Bangla Home, and the final test run output for the pitch backup.
