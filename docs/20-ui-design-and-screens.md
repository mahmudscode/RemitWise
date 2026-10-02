# 20 — UI Design and Functionality (as built)

Mobile-first web app (React + Vite) that looks like a wallet app on a phone and runs in any browser. Three views: **Family app** (main product), **Sender view**, **Demo & insights** panel (for judges).

## Design rules
- White cards on a light background, one brand colour (green). Status colours used consistently: green = covered / on time, amber = needs attention, red = shortfall / overdue.
- Every AI prediction carries an **"AI estimate"** badge with a **"Why?"** link (forecast, projection). Rule-based or statistical numbers carry **"Estimate"**, **"Rule trace"** or **"Simulated"** instead, so predictions, assumptions and generated text stay visibly separate.
- Large numbers, short sentences, simple icons. English and Bangla toggle (Bangla needs native review).
- The family always decides; nothing moves money unless the family set it up (auto-pay) or pressed a button.

## Family app (bottom navigation: Home, Payments, Plan, Goals, Insights)
| Screen | What it shows / does |
|---|---|
| **Home** | Available balance and "reserved for bills and EMI"; next-remittance range with confidence bar and AI badge; **safe-to-spend per day** meter (green/amber/red); alert banner only when needed; next 3 payments with covered / not covered; plain-language month summary. |
| **Remittance arrived** (pop-up) | "৳X received from <sender> (<city>)"; stacked bar split into **Bills and EMI / Daily needs / Emergency fund / Goals**; three plan styles; sliders to adjust with live shortfall risk; **Accept plan / Adjust / Skip for now**. |
| **Payments** | Month calendar with coloured dots; flagged-bill card (**Approve / Dispute / Pay manually / Why?**); auto-pay cards with amount (estimate for variable bills), due date, planned payment date, status (Scheduled / Paid / Needs review / At risk / Overdue) and an auto-pay toggle; **Add new** mandate (biller, account number, monthly limit, confirm-over-limit). |
| **Plan** | Cash-flow chart: projected balance until the next expected remittance with an uncertainty band, bill/EMI markers, red where it goes below zero; spending-by-category donut; shortfall **options** (spend less per day / move money from goals / ask sender) the family chooses. |
| **Goals** | Progress bars, target and date, **pace estimate**, **share-with-sender toggle per goal**, new-goal form with a **suggested realistic monthly amount** from the forecast. |
| **Insights** | Monthly summary, forecast "why" bars (feature contributions), warning "why" bars (rule trace), late fees avoided, on-time rate, savings built, unusual bills caught. |

## Sender view
Shared goals only (those the family toggled on); **bills and EMIs this month: all covered / N at risk** and a **suggested "send by" date** (only if the family shares bills status); optional "planning a transfer" note to improve the family's forecast; consent status and requests. No transactions, no balances, no amounts.

## Demo & insights panel (judges)
- **Simulation controls:** Trigger remittance, Advance 7 days, Delay next transfer, Inject unusually high bill, Add new EMI, plus large expense, second income, new family member, reset.
- **Model performance (clean test set):** forecast vs actual chart (model range and "same as last time" side by side); key metrics (forecast error, warning precision / recall / lead time, bill-estimate error, unusual-bill flags); a simulated year **with vs without** RemitWise and vs a fixed 50/30/20 rule, at 60 / 80 / 100% compliance; **fairness** table; audit log; data card.
- The "honest reading" sentence under the comparison table is generated from the numbers, so it cannot drift from the data.

## Where this differs from the original brief
- Bills and EMIs are **simulated mandates**. No real accounts or money are involved.
- The bill estimate is a **seasonal-naive statistical rule** (same month last year), not a deep model, and is labelled "Estimate".
- Categories are simulated shares of spending, and are labelled "Simulated".
- "SHAP" bars use LightGBM's built-in feature contributions for the forecast, and a rule trace for warnings.
- Auto-pay obeys the Responsible-AI rules in doc 10: it only pays what the family switched on; **unusual bills and bills over the family's limit always wait for approval**.
