# 21 — Accounts, Login and Data Persistence

Replaces the earlier demo "role in a header" with real accounts.

## User types
| Type | Registers with | Sees |
|---|---|---|
| **Family** | name, email, password (8+ chars), optional sender city | Their own household only: Home, Payments, Plan, Goals, Insights. Gets a unique **invite code** (shown under Goals → Sharing). |
| **Sender abroad** | name, email, password, the family's **invite code** | Only the sender view, and only what the family has chosen to share. Cannot open any family endpoint. |
| **Admin** (platform operator) | **Provisioned, never self-registered** (see Settings) | The admin console: platform overview, user management, model performance, simulation sandbox, audit. Aggregates and masked emails only. **Never** a registered family's finances. |

Each new family account is given its own synthetic household (held-out test split first), so every family has separate data and state.

## How sign-in works
- Passwords are stored as **salted scrypt** hashes. Plain passwords are never stored or logged.
- A login returns a random 256-bit **session token**. The server stores only its **SHA-256 hash**; sessions last 30 days and can be ended with Log out.
- The browser keeps the token in `localStorage`, so a **refresh or a new browser session stays signed in**. A server that is only briefly unreachable does not sign anyone out.
- Failed sign-ins are rate limited (8 per 5 minutes per email and client). The error message is the same whether the email exists or not.
- Role is decided on the **server from the token**. The old `X-Role` header no longer grants anything.

## What persists
Accounts, sessions, goals, plan decisions, consent choices, bills and mandates, and each household's simulated state are stored in the database (`DATABASE_URL`). They survive refreshes, new sessions and server restarts. A test restarts the app on the same database and checks the account, session, goals and balances are unchanged.
**On free hosting with SQLite** (Render without a database) the file lives inside the container and resets on every redeploy. Set `DATABASE_URL` to a PostgreSQL database to keep accounts permanently.

## Demo accounts (hackathon convenience)
When `SEED_DEMO_ACCOUNTS=true` (default) the family **Rahima** and sender **Rahim** accounts are offered as buttons on the sign-in page, and an admin account `admin@demo.remitwise` is created. All use the password in `DEMO_PASSWORD` (default `demo1234`) and synthetic data. **The admin account is not shown on the sign-in page**: give its credentials to reviewers in your submission notes; they sign in through the normal form and the app opens the admin console.
For anything beyond a demo: set `SEED_DEMO_ACCOUNTS=false`, provision a real admin with `ADMIN_EMAIL` / `ADMIN_PASSWORD`, and change `DEMO_PASSWORD`.

## Settings
| Variable | Meaning |
|---|---|
| `SEED_DEMO_ACCOUNTS` | `true` / `false`. Create the demo family and sender accounts and the demo admin. |
| `DEMO_PASSWORD` | Password for the demo accounts. |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Create (if missing) a real administrator account on startup. |

## Privacy rules enforced on the server
- A family can only read and change its own household; a sender only its linked household's consent-filtered view.
- An admin can only act on the seeded demo households. Registered families' data, and their audit trail, are invisible to admins; the overview shows aggregates and the user list masks emails.
- Consent still gates everything a sender sees (doc 10).

## Known limits (be honest with judges)
- No email verification or password reset yet (a registered user who forgets a password cannot recover the account).
- Sessions are bearer tokens in `localStorage`; a hardened product would use short-lived tokens with refresh and HTTP-only cookies.
- Rate limiting is per server process.
- One consent record is shared by all senders linked to a household.

## Why an admin console (and not a "judge login")
A real fintech product needs an operator view. The hackathon guideline's architecture lists **monitoring and model dashboards**; the Responsible-AI section asks for **fairness checks and human oversight**. The admin console is where those live:
- **Overview:** accounts, households, how many plans families follow, bills paid on time, late fees avoided, unusual bills caught, system and model status.
- **Users:** search, see role and status, **disable or enable** an account (signs it out everywhere). Emails are masked.
- **Model performance:** measured forecast and warning quality on held-out test households, fairness by group, with-versus-without comparison, Responsible-AI checks.
- **Simulation sandbox:** trigger a remittance, delay a transfer, inject an unusual bill or a new EMI on synthetic households, to see how the product reacts without risking a real family.
- **Audit & data:** event log for demo households and the data card of assumptions.
Everything it shows is either aggregate or synthetic, which keeps the privacy promise to families.
