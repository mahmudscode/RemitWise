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
