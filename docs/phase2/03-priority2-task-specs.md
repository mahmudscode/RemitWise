# 03 — Priority 2 Task Specs (Tasks 7–10)

Only start after Priority 1 is committed and the demo path is verified.

---
## Task 7 — Email security code and password reset (changed from phone to email)
**Behaviour**
- The code goes to the account's email address, not a phone number (the phone version was replaced). Existing databases are upgraded without data loss.
- OTP request: 6-digit code, stored hashed, 5-minute expiry, max 5 attempts, rate-limited. Demo mode (default) shows the code on screen; with SMTP configured and `OTP_DEMO_MODE=false` it is only emailed.
- Verify marks the email address verified.
- Password reset by email: request (OTP) then confirm (code + new password); confirm invalidates all existing sessions.
- UI: "Verify your email" step after sign-up; "Forgot password?" on sign-in.

**Security notes:** never store plain codes; constant-time compare; generic responses that do not reveal whether an account exists; lockout after attempts exhausted.
**Tests:** expiry, wrong-code lockout, reset invalidates old token, rate limit.
**Commit:** `Add simulated phone OTP verification and password reset`

---
## Task 8 — Consent-based micro-savings
**Principle:** save first. Later change: an optional, separately consented, clearly **simulated** low-risk yield pot (synthetic money, illustrative rate, not advice, not a real product).

**Behaviour**
- Family setting, **off by default**, requires explicit opt-in.
- At day end, move a small amount (round spending up to next ৳10, or 1% of safe-to-spend surplus) into the emergency fund or a chosen goal.
- Runs only when shortfall risk is green and bills are covered; pauses on amber/red with message "Paused to protect your bills".
- "Micro-saved this month: ৳X" on Goals and in AI-summary facts.

**Tests:** pauses on amber and red; resumes on green; never runs when off; never dips below bill cover.
**Commit:** `Add consent-based micro-savings that pause when bills are at risk`

---
## Task 9 — "Not a budgeting app" message
**Behaviour**
- Home, under Next remittance: one line — "Budget apps track what you spent. RemitWise predicts when money will arrive and plans around that uncertainty."
- Sign-in/landing: 3-row comparison, Budgeting app vs RemitWise:
  - fixed salary vs irregular income
  - past spending vs future arrival
  - one number vs calibrated range

**Commit:** `Explain forecasting-first difference from budgeting apps`

---
## Task 10 — LLM path and PostgreSQL credibility
**Behaviour**
- Test with mocked Groq HTTP call: valid output accepted; output containing an invented number rejected and replaced by the template.
- PostgreSQL: add compose service or CI note to run the suite with the database URL set. Run once if Docker is available; otherwise document the exact command in the README and say it was not run.

**Honesty rule:** do not claim PostgreSQL was tested unless it actually ran.
**Commit:** `Test LLM path with mocked Groq and document PostgreSQL test run`
