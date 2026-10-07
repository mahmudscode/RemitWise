"""Simple load test: N concurrent simulated users hit the read endpoints for D seconds.

    python scripts/load_test.py --url http://127.0.0.1:8000 --users 50 --seconds 60

Signs in the demo family accounts (needs SEED_DEMO_ACCOUNTS=true), then each user loops over
home / shortfall / forecast / state. Reports requests per second, p50/p95/p99 latency and the error rate.
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx

ENDPOINTS = ["/households/{hid}/home", "/households/{hid}/shortfall", "/households/{hid}/forecast", "/households/{hid}/state"]


async def login(client: httpx.AsyncClient, email: str, password: str) -> tuple[str, str]:
    r = await client.post("/api/auth/login", json=dict(email=email, password=password))
    r.raise_for_status()
    d = r.json()
    return d["token"], d["user"]["household_id"]


async def user_loop(client, token, hid, stop, lat, errs):
    headers = {"Authorization": f"Bearer {token}"}
    i = 0
    while time.perf_counter() < stop:
        path = "/api" + ENDPOINTS[i % len(ENDPOINTS)].format(hid=hid)
        i += 1
        t0 = time.perf_counter()
        try:
            r = await client.get(path, headers=headers)
            ok = r.status_code < 400
        except httpx.HTTPError:
            ok = False
        lat.append((time.perf_counter() - t0) * 1000)
        if not ok:
            errs.append(1)


async def main(url: str, users: int, seconds: int, password: str, emails: list[str]):
    limits = httpx.Limits(max_connections=users + 5)
    async with httpx.AsyncClient(base_url=url, timeout=30, limits=limits) as client:
        sessions = [await login(client, emails[i % len(emails)], password) for i in range(min(users, len(emails) * 4))]
        lat: list[float] = []
        errs: list[int] = []
        t0 = time.perf_counter()
        stop = t0 + seconds
        await asyncio.gather(*[user_loop(client, *sessions[i % len(sessions)], stop, lat, errs) for i in range(users)])
        wall = time.perf_counter() - t0
    lat.sort()
    q = lambda p: lat[min(int(len(lat) * p), len(lat) - 1)]
    res = dict(users=users, seconds=round(wall, 1), requests=len(lat), rps=round(len(lat) / wall, 1),
               p50_ms=round(statistics.median(lat), 1), p95_ms=round(q(0.95), 1), p99_ms=round(q(0.99), 1),
               max_ms=round(lat[-1], 1), error_rate=round(len(errs) / max(len(lat), 1), 4))
    print(res)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--users", type=int, default=50)
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--password", default="demo1234")
    ap.add_argument("--emails", nargs="+", default=["rahima@demo.remitwise", "salma@demo.remitwise", "nasrin@demo.remitwise"])
    a = ap.parse_args()
    asyncio.run(main(a.url, a.users, a.seconds, a.password, a.emails))
