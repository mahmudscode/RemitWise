"""Load and volume tests against a running API.

  read-only smoke (demo accounts):
      python scripts/load_test.py --users 50 --seconds 60
  realistic mix on many households (registers N family accounts first, 80% reads / 20% writes):
      python scripts/load_test.py --register 300 --users 300 --seconds 60 --mix
  high-volume signed webhooks with duplicates, checking that no update is lost or applied twice
  (the server needs WEBHOOK_SECRET set to the same value):
      python scripts/load_test.py --webhooks 3000 --concurrency 100 --secret devsecret

Reports requests per second, p50/p95/p99 latency, error rate and (webhooks) the exact consistency check.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import random
import statistics
import time
import uuid

import httpx

READS = ["/households/{hid}/home", "/households/{hid}/shortfall", "/households/{hid}/forecast", "/households/{hid}/state"]


async def login(client, email, password):
    r = await client.post("/api/auth/login", json=dict(email=email, password=password))
    r.raise_for_status()
    d = r.json()
    return d["token"], d["user"]["household_id"]


async def register_many(client, n, tag):
    sem = asyncio.Semaphore(8)  # password hashing is CPU-heavy; do not stampede the sign-up itself
    out = []

    async def one(i):
        async with sem:
            r = await client.post("/api/auth/register", json=dict(role="family", name=f"Load Tester {i}", email=f"load-{tag}-{i}@example.com", password="load-test-pass-1"))
            if r.status_code == 200:
                d = r.json()
                out.append((d["token"], d["user"]["household_id"]))
            elif r.status_code != 503:  # 503 = no free household left
                r.raise_for_status()
    await asyncio.gather(*[one(i) for i in range(n)])
    return out


async def user_loop(client, token, hid, stop, lat, errs, kinds, mix):
    headers = {"Authorization": f"Bearer {token}"}
    i = 0
    while time.perf_counter() < stop:
        write = mix and random.random() < 0.2
        if write:
            req = ("POST", f"/api/households/{hid}/advance", {"days": 1})
        else:
            req = ("GET", "/api" + READS[i % len(READS)].format(hid=hid), None)
        i += 1
        t0 = time.perf_counter()
        try:
            r = await client.request(req[0], req[1], json=req[2], headers=headers)
            ok = r.status_code < 400
            code = r.status_code
        except httpx.HTTPError:
            ok, code = False, 0
        lat.append((time.perf_counter() - t0) * 1000)
        kinds.append("write" if write else "read")
        if not ok:
            errs.append(code)


def summarize(label, lat, errs, wall, extra=None):
    lat = sorted(lat)
    q = lambda p: lat[min(int(len(lat) * p), len(lat) - 1)]
    res = dict(label=label, seconds=round(wall, 1), requests=len(lat), rps=round(len(lat) / wall, 1), p50_ms=round(statistics.median(lat), 1),
               p95_ms=round(q(0.95), 1), p99_ms=round(q(0.99), 1), max_ms=round(lat[-1], 1), errors=len(errs),
               error_rate=round(len(errs) / max(len(lat), 1), 4), error_codes=sorted(set(errs)))
    res.update(extra or {})
    print(res)
    return res


async def run_traffic(url, users, seconds, password, emails, register, mix):
    limits = httpx.Limits(max_connections=users + 20, max_keepalive_connections=users + 20)
    async with httpx.AsyncClient(base_url=url, timeout=60, limits=limits) as client:
        if register:
            sessions = await register_many(client, register, uuid.uuid4().hex[:6])
            print(f"registered {len(sessions)} families (households claimed)")
        else:
            sessions = [await login(client, emails[i % len(emails)], password) for i in range(min(users, len(emails) * 4))]
        lat, errs, kinds = [], [], []
        t0 = time.perf_counter()
        stop = t0 + seconds
        await asyncio.gather(*[user_loop(client, *sessions[i % len(sessions)], stop, lat, errs, kinds, mix) for i in range(users)])
        wall = time.perf_counter() - t0
    return summarize(f"{'mixed' if mix else 'read-only'} traffic, {users} users, {len(sessions)} households", lat, errs, wall,
                     dict(writes=kinds.count("write"), households=len(sessions)))


def sign(secret, ts, body):
    return hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()


async def run_webhooks(url, total, concurrency, secret, password):
    """Send signed cash_out events for one household (every id sent twice, concurrently) and check the books.
    The household's spendable + buffer - debt must fall by exactly the sum of the UNIQUE events: no lost update, no double apply."""
    async with httpx.AsyncClient(base_url=url, timeout=60, limits=httpx.Limits(max_connections=concurrency + 10)) as client:
        admin = (await client.post("/api/auth/login", json=dict(email="admin@demo.remitwise", password=password))).json()["token"]
        hid = (await client.get("/api/households", headers={"Authorization": f"Bearer {admin}"})).json()[0]["household_id"]
        H = {"Authorization": f"Bearer {admin}"}
        await client.post(f"/api/households/{hid}/reset", headers=H)
        net = lambda s: s["spendable"] + s["buffer"] - s["debt"]
        before = net((await client.get(f"/api/households/{hid}/state", headers=H)).json())
        uniq = total // 2
        events = [dict(event_id=f"vol-{uuid.uuid4().hex[:14]}", type="cash_out", household_id=hid, amount=random.choice([5, 10, 15, 20]), currency="BDT") for _ in range(uniq)]
        expected = sum(e["amount"] for e in events)
        sends = events + events  # every id twice
        random.shuffle(sends)
        sem = asyncio.Semaphore(concurrency)
        lat, errs, dup = [], [], 0

        async def send(ev):
            nonlocal dup
            body = json.dumps(ev).encode()
            ts = int(time.time())
            async with sem:
                t0 = time.perf_counter()
                try:
                    r = await client.post("/api/webhooks/transactions", content=body, headers={"X-RW-Timestamp": str(ts), "X-RW-Signature": sign(secret, ts, body), "Content-Type": "application/json"})
                    lat.append((time.perf_counter() - t0) * 1000)
                    if r.status_code != 200:
                        errs.append(r.status_code)
                    elif r.json().get("duplicate"):
                        dup += 1
                except httpx.HTTPError:
                    lat.append((time.perf_counter() - t0) * 1000)
                    errs.append(0)
        t0 = time.perf_counter()
        await asyncio.gather(*[send(e) for e in sends])
        wall = time.perf_counter() - t0
        after = net((await client.get(f"/api/households/{hid}/state", headers=H)).json())
    drop = round(before - after, 2)
    res = summarize(f"webhooks: {len(sends)} signed events ({uniq} unique, each sent twice), concurrency {concurrency}", lat, errs, wall,
                    dict(duplicates_reported=dup, expected_drop=expected, actual_drop=drop, consistent=bool(abs(drop - expected) < 0.01 and dup == uniq)))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--users", type=int, default=50)
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--password", default="demo1234")
    ap.add_argument("--emails", nargs="+", default=["rahima@demo.remitwise", "salma@demo.remitwise", "nasrin@demo.remitwise"])
    ap.add_argument("--register", type=int, default=0, help="register N family accounts and spread the users over them")
    ap.add_argument("--mix", action="store_true", help="80%% reads, 20%% writes")
    ap.add_argument("--webhooks", type=int, default=0, help="send N signed webhook events (half unique, each sent twice)")
    ap.add_argument("--concurrency", type=int, default=100)
    ap.add_argument("--secret", default="")
    a = ap.parse_args()
    if a.webhooks:
        asyncio.run(run_webhooks(a.url, a.webhooks, a.concurrency, a.secret, a.password))
    else:
        asyncio.run(run_traffic(a.url, a.users, a.seconds, a.password, a.emails, a.register, a.mix))
