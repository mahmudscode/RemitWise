"""Send one signed test event to the transaction webhook.

    WEBHOOK_SECRET=devsecret python scripts/send_test_webhook.py --household H0123 --type remittance_received --amount 25000
    python scripts/send_test_webhook.py --secret devsecret --household H0123 --type bill_paid --amount 800 --bill-name Electricity

The server must be started with the same WEBHOOK_SECRET. Use --unsigned or --bad-signature to see a rejection.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import time
import uuid

import httpx


def sign(secret: str, timestamp: int, body: bytes) -> str:
    return hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--secret", default=os.getenv("WEBHOOK_SECRET", ""))
    ap.add_argument("--household", required=True)
    ap.add_argument("--type", default="remittance_received", choices=["remittance_received", "cash_out", "bill_paid"])
    ap.add_argument("--amount", type=float, required=True)
    ap.add_argument("--bill-name")
    ap.add_argument("--event-id", default=None, help="reuse an id to see idempotency")
    ap.add_argument("--unsigned", action="store_true")
    ap.add_argument("--bad-signature", action="store_true")
    a = ap.parse_args()
    event = dict(event_id=a.event_id or f"evt-{uuid.uuid4().hex[:12]}", type=a.type, household_id=a.household, amount=a.amount,
                 currency="BDT", bill_name=a.bill_name, occurred_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    body = json.dumps({k: v for k, v in event.items() if v is not None}).encode()
    ts = int(time.time())
    headers = {"Content-Type": "application/json"}
    if not a.unsigned:
        headers["X-RW-Timestamp"] = str(ts)
        headers["X-RW-Signature"] = ("0" * 64) if a.bad_signature else sign(a.secret, ts, body)
    r = httpx.post(f"{a.url}/api/webhooks/transactions", content=body, headers=headers, timeout=15)
    print(r.status_code, r.text)


if __name__ == "__main__":
    main()
