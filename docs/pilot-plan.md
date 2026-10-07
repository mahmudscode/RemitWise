# Pilot plan: measuring the real effect with upay

The numbers in the app are **simulated**. This is how a controlled pilot would replace the assumptions with measurements.

## Question
Do families who use RemitWise keep more money in the wallet, pay more bills digitally and on time, save more and stay longer than similar families who do not?

## Design: randomized, controlled
- **Population:** upay wallet households that receive remittances at least monthly, opted in with explicit consent. Governed, anonymised data only; no sender surveillance.
- **Randomization:** eligible households are randomly assigned **treatment** (RemitWise on) or **control** (business as usual), stratified by sender regularity (regular / semi / irregular) and rural / urban.
- **Duration:** 6 months (at least 5 remittance cycles each), plus a 3-month follow-up for retention.
- **Sample size (rough, to be confirmed with a statistician):** to detect a 5 percentage-point rise in money kept in the wallet after 24 h (standard deviation about 0.25, 80% power, 5% significance) you need roughly 400 households per arm; plan **500 per arm** (1,000 total) to allow for drop-out and subgroup analysis.

## KPIs (same names as the Admin "Business KPIs" card)
| KPI | Measured as | Source |
|---|---|---|
| Wallet retention | Share of each remittance still in the wallet after 24 h and 7 days | Wallet balances |
| Transaction frequency | Digital bill payments and other wallet transactions per household per month | Transactions |
| Savings behaviour | Share of income moved to savings; micro-savings opt-in and pause rates | Wallet and app events |
| Bill reliability | Bills paid on time, late fees paid | Biller confirmations |
| Customer retention | Active at 3 months after the pilot ends | Wallet activity |
| Incremental revenue | Fees on extra payments plus value of held balances, per household, treatment minus control | Finance, with real fees and float values |
| Forecast quality | Timing error, range coverage, warning precision/recall on live data | Model monitoring |

## Success thresholds (agreed before the pilot starts)
- Wallet retention up by at least 5 percentage points against control.
- On-time bills up by at least 3 percentage points; late fees down.
- No group (irregular senders, rural households) worse off than control; forecast coverage at least 70% in every group.
- Warning precision at least 0.85 on live data, with false alarms reported to families as "AI estimate".
- Opt-out and complaint rate below 5%.

## Safeguards
- Consent for families and senders; senders see only what the family shares.
- Human decisions: auto-pay only under family mandates; the AI explains, it does not decide.
- Stop rule: pause the pilot if on-time payment in treatment falls below control, or complaints exceed the limit.
- Fairness and drift monitoring reviewed weekly (see Admin → Monitoring).

## Not claimed today
No effect size, revenue or retention figure in the app is measured. Compliance is an assumption; the pilot measures it.
