# Load test results

Script: `backend/scripts/load_test.py` (asyncio + httpx). Each simulated user signs in to a demo family account, then loops over four read endpoints: `home`, `shortfall`, `forecast`, `state`.

```bash
./run.sh api                                   # one terminal
cd backend && .venv/bin/python scripts/load_test.py --users 50 --seconds 60
```

## Environment (be honest about what this is)
- Laptop, AMD Ryzen 5 5625U (12 threads), Linux, Python 3.14. Client and server on the **same machine**, so they compete for CPU.
- `uvicorn` with a **single worker**, **SQLite** database, synthetic data, no network latency.
- PostgreSQL and a hosted deployment were **not** measured.

## Results (read endpoints, 0% errors in both runs)

| Concurrent users | Duration | Requests | Requests/s | p50 | p95 | p99 | Max | Error rate |
|---|---|---|---|---|---|---|---|---|
| 10 | 20 s | 3,957 | 198 | 50 ms | 73 ms | 84 ms | 173 ms | 0% |
| 50 | 60 s | 11,130 | 185 | 257 ms | 372 ms | 475 ms | 8.8 s* | 0% |

\* The 8.8 s maximum is a single outlier at the start of the run; p99 is 475 ms.

## Reading
- Throughput saturates at roughly 190 requests/s on one worker: adding users only adds queueing delay (latency grows about 5x from 10 to 50 users, throughput does not). The shortfall endpoint runs a 1,000-path Monte-Carlo simulation, which is the main CPU cost.
- No request failed under 50 concurrent users.
- This is a smoke-level capacity check, not a production benchmark. Scaling would use several workers, PostgreSQL, caching of the shortfall result per day, and a real load generator against a deployed environment.

## Resilience checks (automated tests)
- Database locked or unavailable: the API answers **503** with a retry hint instead of crashing.
- Unexpected server error: a clean **500** without internal details.
- Missing forecaster model file at start-up: the app still starts; only the "why" drivers are empty.


---

# Round 2: PostgreSQL, 4 workers, many households, write traffic and webhook volume

Same machine as above (AMD Ryzen 5 5625U, 12 threads; the load generator shares the CPU with the server and with PostgreSQL, so real hosting would do better). **PostgreSQL 18.6** (local, user-space install), `uvicorn --workers 4`, a fresh database, 300 registered family accounts on 300 different households.

```bash
cd backend && python -m app.bootstrap && uvicorn app.main:app --port 8100 --workers 4      # WEBHOOK_SECRET=loadsecret
python scripts/load_test.py --url http://127.0.0.1:8100 --users 100 --seconds 30            # read-only
python scripts/load_test.py --url http://127.0.0.1:8100 --register 300 --users 300 --seconds 60 --mix   # 80% reads / 20% writes
python scripts/load_test.py --url http://127.0.0.1:8100 --webhooks 4000 --concurrency 100 --secret loadsecret
```

| Scenario | Requests | Requests/s | p50 | p95 | p99 | Errors |
|---|---|---|---|---|---|---|
| Read-only, 100 users | 5,005 | 162 | 425 ms | 1.8 s | 2.9 s | 0 |
| Mixed 80/20 reads and writes, 300 users on 300 households | 7,702 (1,515 writes) | 125 | 812 ms | 7.9 s | 31 s | 93 (1.2%): clean 503 "busy" answers and client time-outs, no server crashes |
| 4,000 signed webhook events (2,000 unique, each sent twice), 100 concurrent | 4,000 | 79 | 828 ms | 3.9 s | 6.3 s | 0 |

**Correctness under concurrency (the important result).** The webhook run sends every event id twice at the same time. The server reported exactly 2,000 duplicates, and the household's money (spendable + buffer - debt) fell by exactly the sum of the 2,000 unique events (25,230 expected, 25,230 actual): no lost update and no event applied twice. The database ended with 606 goals for 300 + 3 households (2 each): no duplicate first-visit set-up.

## What the first runs found and fixed (why this was worth doing)
1. **Connection-pool deadlock.** Requests waiting for a household lock each held a database connection, leaving none for the request that held the lock. Throughput fell to 9 requests/s with 74% errors. Fix: locks live in their own small pool and are polled without blocking a connection; exhaustion becomes back-pressure.
2. **Lost updates between workers.** Household state is read, changed and saved as a whole. Fix: writes to one household are serialised across workers with PostgreSQL advisory locks (a middleware), and sign-up is serialised so two families never claim the same household.
3. **First-visit race.** Two simultaneous first requests for a household both tried to create it (key clash, duplicate goals). Fix: a lock around creation and an idempotent save.
4. **Start-up race.** Four workers starting together collided while seeding. Fix: a start-up lock.
5. **Webhook idempotency race.** Claim the event id with a primary-key insert first.
6. **Overload now answers 503** with `Retry-After` instead of 500.

## Reading and limits
- Throughput is bounded by CPU (the shortfall simulation is the heavy endpoint) and the load generator competes for the same cores. Latency tails (p99 31 s in the mixed run) show the server saturating at 300 users on this laptop; the 1.2% errors are overload back-pressure, not failures of correctness.
- This is a **local, single-machine** test with synthetic data. It is not a test of a hosted production environment, of PostgreSQL at production scale, or of real upay traffic. Scaling out needs more workers or instances behind a load balancer, a managed PostgreSQL, caching of the daily shortfall result, and a real load generator against a deployed environment.
- In-memory rate limits are per process (so per worker); a shared store such as Redis would be needed for strict limits across workers.
