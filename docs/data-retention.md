# Data-retention policy

RemitWise is a hackathon prototype running on **synthetic data**. This policy describes how a real deployment would treat data, and the parts that are already implemented.

| Data | Why it is kept | How long | Who can see it |
|---|---|---|---|
| Account (name, email, password hash) | Sign-in and recovery | Until the person deletes the account | The person; admins see masked emails only |
| Sessions (hash of the login token) | Stay signed in | 30 days, then deleted (also on every start-up) | Nobody (only a hash is stored) |
| One-time codes (hash) | Email verification and password reset | 5 minutes; used or expired codes are deleted | Nobody |
| Household data (plans, goals, consents, decisions, simulated state) | The service itself | Until the family deletes its account; purged with it | The family; senders see only what the family shares |
| Audit log | Accountability (who did what) | 12 months, then deleted | Admins (demo and system events only) |
| Demo households and demo accounts | Judging and demos | Reset on request | Public by design |

## Deleting your data
- **Family or sender:** Goals → Your data → *Delete my account* (type DELETE). The account, its sessions and codes are removed. If it is the last family account of a household, the household's goals, consents, decisions and state are removed too.
- **Admin accounts and demo accounts** cannot be deleted through this route.
- Deleted accounts are removed immediately in this prototype. A production deployment would purge backups within 30 days.

## What is not collected
No real bank, wallet or identity data, no precise location, no spending details for senders. Admins see aggregates, not a family's finances.

## Implemented in code
`DELETE /api/me` (self-deletion), `auth.purge_expired()` (sessions, codes, audit rows older than 12 months, run at start-up), and tests in `backend/tests/test_core.py`.
