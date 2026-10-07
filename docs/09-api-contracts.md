# 09 — API Contracts (described, no code)

All responses include: `model_version`, `data_version`, `generated_at`, and where relevant `reasons[]` and `assumptions[]`. Predictions, assumptions and generated text are returned in separate fields.

## Household & data
| Endpoint | Purpose | Key inputs | Key outputs |
|---|---|---|---|
| List households | Demo picker | filters | id, archetype, regularity class |
| Get household timeline | History + events | household id, date range | remittances, spending, balance series |
| Advance simulated time  | Demo control | household id, target date / event trigger | updated state |

## Forecast
| Endpoint | Purpose | Inputs | Outputs |
|---|---|---|---|
| Get remittance forecast | Next arrival + amount | household id, as-of date, optional sender intent | P10/P50/P90 date, P10/P50/P90 amount, confidence label, baseline comparison |

## Allocation
| Endpoint | Purpose | Inputs | Outputs |
|---|---|---|---|
| Propose plan | Split an arrived remittance | household id, amount, date | 3 plan options (conservative/balanced/goal-focused): needs, savings, goals breakdown, shortfall probability under each, reasons |
| Record decision | Family accepts/edits/rejects | plan id, decision, edits | stored decision, updated balances |

## Risk
| Endpoint | Purpose | Inputs | Outputs |
|---|---|---|---|
| Get shortfall status | Early warning | household id, as-of date | shortfall probability, run-out date range, top drivers, suggested actions, severity |

## Goals
| Endpoint | Purpose | Inputs | Outputs |
|---|---|---|---|
| Create/update goal | Manage goals | name, target, deadline, priority | goal with feasibility check |
| Get goal progress (family) | Full view | household id | progress, contributions, on-track status |
| Get goal progress (sender) | Consent-filtered | sender id, household id | progress only; fields limited by consent scope |

## Consent
| Endpoint | Purpose | Inputs | Outputs |
|---|---|---|---|
| Get consent state | Show scope | household id, sender id | scopes, timestamps |
| Update consent | Family grants/revokes | scope, state | new state; audit entry |
| Request more visibility | Sender asks | requested scope | pending request for the family |

## Explanation
| Endpoint | Purpose | Inputs | Outputs |
|---|---|---|---|
| Get summary | Plain-language text | household id, type (plan/warning/progress), language | text, `source_facts` used, validation status, fallback flag |

## Simulation & metrics
| Endpoint | Purpose | Inputs | Outputs |
|---|---|---|---|
| Run with/without comparison | Side-by-side year | household or cohort, compliance assumption | shortfall days, savings rate, buffer months, wallet retention for both policies |
| Get evaluation report | Metrics for judges | split (test) | forecast errors vs baseline, coverage, warning precision/recall, fairness cuts |

## Contract rules
- Stable field names; versioned.
- Sender-facing responses must pass through consent filter before serialization.
- No endpoint auto-executes money movement.
- Errors never leak other households' data.

## Transaction webhook (MFS adapter)
Replaces simulated transaction events with real wallet events. **Disabled until `WEBHOOK_SECRET` is set** on the server. This is an adapter with signed test events; it is not a live upay feed.

`POST /api/webhooks/transactions`

| Header | Meaning |
|---|---|
| `X-RW-Timestamp` | Unix seconds when the request was signed. Rejected if more than 5 minutes from server time |
| `X-RW-Signature` | Hex `HMAC-SHA256(WEBHOOK_SECRET, "<timestamp>." + <raw request body>)` |

Body (JSON):
```json
{
  "event_id": "evt-9f2c1a77b3d0",
  "type": "remittance_received",
  "household_id": "H0123",
  "amount": 25000,
  "currency": "BDT",
  "bill_name": "Electricity",
  "occurred_at": "2026-03-02T09:15:00",
  "reference": "upay-txn-0001"
}
```
- `type`: `remittance_received` | `cash_out` | `bill_paid`. `bill_name` is required for `bill_paid` and must match an open bill.
- `event_id` (8–64 chars) is the **idempotency key**: a repeated id returns `200 {"duplicate": true}` and is not applied twice.
- `amount` > 0 and ≤ 10,000,000, `currency` must be `BDT`.

Mapping to internal events (same as the simulator produces, so forecasts, plans and warnings update):

| Webhook type | Internal effect |
|---|---|
| `remittance_received` | Arrival of the next transfer: credits the wallet, refreshes the forecast and opens the split plan for the family |
| `cash_out` | Spends from the wallet (logged as `cash_out`) |
| `bill_paid` | Marks the matching open bill paid on time, from the vault first |

| Status | When |
|---|---|
| 200 | Applied (`duplicate: false`) or already applied (`duplicate: true`) |
| 400 | Payload is not valid JSON or fails validation |
| 401 | Missing, stale or wrong signature (the same generic message for all) |
| 409 | Valid event that cannot be applied (no matching open bill, no forecast for the next transfer) |
| 503 | Webhooks not enabled (no secret configured) |

Try it: `WEBHOOK_SECRET=devsecret ./run.sh api`, then `WEBHOOK_SECRET=devsecret backend/.venv/bin/python backend/scripts/send_test_webhook.py --household <id> --type remittance_received --amount 25000` (add `--unsigned` or `--bad-signature` to see a rejection, or reuse `--event-id` to see idempotency).
