# 04 — README and Pitch Updates

## Task 22 — README section (do last)
Add **"Final-day updates (based on Phase 1 feedback)"** containing:
- Table: judge comment → what was built → where to see it (screen / button).
- Warning threshold before/after numbers (from `evaluation.json`, copied after the final build).
- Stress-test (Task 12) and load-test (Task 13) results, coverage and security-check summary (Task 14), if done.
- 60/80/100% compliance table with "simulated, not measured" wording.
- PostgreSQL run command (and whether it was executed).
- Out-of-scope list (see doc 07).

**Commit:** `Document final-day updates in README`

## Pitch changes
| Slot | Change |
|---|---|
| Opening | Frame: "You told us X; we built Y" for the top three comments |
| Problem | Use Eid surge and medical emergency as the human examples |
| Demo | Run the Guided demo 1→5; switch to বাংলা mid-demo |
| AI/ML | Show before/after threshold chart; state recall cost openly |
| Impact | Show 60/80/100% table; say "simulated, not measured" out loud |
| Differentiator | Landing comparison: budgeting app vs RemitWise |
| Responsible AI | Retention policy, account deletion, monitoring panel, security checks (if built) |
| Scalability | Webhook adapter and load-test numbers (if built) |
| Close | "These are our next phase, a controlled pilot with governed upay data." |

## Q&A prep
- **Why did recall drop?** Trade chosen to cut false alarms; sweep chart shows the whole curve; lead days quantified.
- **Is the money impact real?** No. Simulated; compliance assumed; pilot would measure it.
- **Is the security code real?** It is emailed when SMTP is configured; in demo mode it is shown on screen. Tested with a fake mail server, not a real provider.
- **Does micro-savings invest?** No. Saves only; off by default; pauses when bills at risk.
- **Postgres?** State exactly what was and was not run.
- **Colours?** Palette follows upay brand; logo image not copied.
