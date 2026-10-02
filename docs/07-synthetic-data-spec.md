# 07 — Synthetic Data Specification

No real PII, no production data. Realistic but clearly synthetic; every assumption documented.

## Entities
| Entity | Key fields |
|---|---| 
| Household | id, region type (urban/rural), size, local income level, remittance regularity class, risk profile |
| Sender | id, destination-country archetype, typical amount, regularity, reliability |
| Remittance event | household id, date, amount, delayed flag, source sender |
| Local income | monthly/weekly amount, volatility |
| Recurring expense | category (rent, food, school, medicine, utilities, loan repayment), amount, due day |
| Spending transaction | date, category, amount, channel (wallet / cash-out) |
| Goal | household id, name, target, deadline, priority |
| Consent | household id, sender id, scope, state, timestamps |

## Scale
200–500 households × 24–36 months of daily records. Seeded for reproducibility.

## Remittance generation assumptions (document and label as assumptions)
- Gap between transfers: mixture of regular monthly (±few days), semi-regular, and highly irregular classes.
- Amounts: log-normal around household/sender typical value; some senders send smaller top-ups mid-month.
- Seasonality: larger/earlier transfers before Eid and other festivals.
- Delay events: random delays of 5–25 days for a fraction of cycles.
- Large one-off events: medical emergency, wedding, repair; may also trigger extra transfer requests.
- Sender reliability varies (some very irregular, small transfers → needed for fairness test).

## Spending behavior model
- Baseline "cash-out heavy" behavior: large withdrawal soon after arrival (the problem we show).
- Daily essential spending with weekly rhythm; week-1 heavy, tail lighter.
- Festival spikes, school-fee months, medical shocks.
- Borrowing/informal credit when balance reaches zero (recorded as shortfall event).

## Planted patterns (known ground truth for validation)
1. Festival spike months.
2. Delayed-transfer cycles.
3. Large one-off expense.
4. Chronic early cash-out households.
5. Households with very irregular/small transfers (fairness cohort).
6. A second income source for some households.

## Splits
- Train / validation / **clean test** split **by household** (and by time for forecasting); test never touched during tuning.

## "With vs without" simulation
Replay the same household history under two policies: (a) baseline behavior, (b) following RemitWise plan with a *documented compliance assumption* (e.g., family accepts the plan X% of the time, partial adherence). Report sensitivity to compliance.

## Documentation required
A data card listing every assumption, parameter ranges, seeds, and known limitations, including: simulated behavior change is an assumption, not evidence of real-world effect.

## Dataset as built
500 households (H001–H500) × ~30 months. **Block design:** H001–H300 are the original build and never change; H301–H500 are a second block generated with its own seed (`seed + 1000`) and split 60/20/20 on its own. Appending households therefore never alters existing households, the held-out test split, the demo households, or any registered family's world. Splits overall: 300 train, 100 calibration, 100 test. Demo households are chosen only from the original block so they stay fixed.
