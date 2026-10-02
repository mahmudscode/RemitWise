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
