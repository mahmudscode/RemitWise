# Security checks (basic, not a penetration test)

What was run and what it found. This is a hackathon prototype: these are automated self-checks, not an independent security audit or penetration test.

## Automated tests (`./run.sh test`, 103 tests)
| Check | How |
|---|---|
| No endpoint answers without a valid token | Every non-public route is called with no token and with a garbage token; the answer must be 401 (or 422 for an empty body), never 2xx |
| Role escalation | Every route that depends on the admin check is called with a family token and a sender token; all must return 403 |
| Household isolation | Every household route is called by another family and by a sender; every sender route by the wrong family or sender; all must return 403 |
| Prompt injection | Injection strings in goal names, auto-pay biller names, sign-up name and city are sanitised and never reach state, bills or summaries |
| Input validation | Negative, zero, huge and malformed amounts, days and due dates are rejected with 422; balances stay unchanged |
| Brute force | Sign-in is rate limited per account and client (429); OTP requests, attempts and password-reset requests are limited too |
| One-time codes | Hashed at rest, 5-minute expiry, 5 attempts, no account discovery on reset |
| Resilience | Database locked gives a clean 503, unexpected error a clean 500 without internals, a missing model file does not stop the app |

The route checks introspect the real FastAPI routes, so a new endpoint without the right dependency fails the test.

## Finding fixed during this check
- **Admin scenario endpoint accepted negative values**: `kind=expense` with a negative value would have added money to a demo household. The request model now bounds `value` to 0 to 10,000,000. (Admin-only and demo households only, but it is the kind of bug the validation tests exist to catch.)

## Dependency audit
| Tool | Scope | Result |
|---|---|---|
| `pip-audit -r backend/requirements.txt` | Pinned Python dependencies | No known vulnerabilities found |
| `npm audit` (in `frontend/`) | Frontend dependencies | 0 vulnerabilities |

Run on the date of the last commit; vulnerability databases change, so re-run before any real deployment.

## Test coverage (`pytest --cov=app`)
Overall **73%** of statements. The API and engine are higher: `auth.py` 94%, `risk.py` 95%, `allocator.py` 98%, `live.py` 89%, `main.py` 85%. The offline modules that generate data, train and evaluate (`simulator.py`, `sim.py`, `forecast.py`, `evaluation.py`, `pipeline.py`) are exercised by running `./run.sh build`, not by unit tests, which pulls the total down.

```bash
pip install pytest-cov pip-audit
cd backend && python -m pytest -q --cov=app --cov-report=term
pip-audit -r requirements.txt
```

## Known gaps (stated plainly)
- Tokens live in `localStorage` (readable by any script on the page); a production system would use httpOnly cookies and a CSP.
- Rate limiting is in memory per process; it resets on restart and is not shared between workers.
- No independent penetration test, no load-bearing security review, no WAF.
- Demo accounts have a public password by design; disable them (`SEED_DEMO_ACCOUNTS=false`) on a real deployment.
