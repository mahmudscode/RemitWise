# 20 — UI Design and Functionality (as built)

> **Visual source of truth:** the Figma file "RemitWise UI" exported to [DESINE/](DESINE/) (7 mobile frames at 390×844, 8 desktop frames at 1440×900). The app follows it: blue brand (`#0e6e9c`), navy header on sender and judge views, purple AI badges, status colours green / amber / red, and a **responsive layout**: left sidebar on desktop, bottom navigation on mobile (breakpoint 960 px). The earlier "phone frame" layout was replaced.

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

## Admin console (platform operators)
- **Tabs:** Overview, Users, Model performance, Simulation sandbox, Audit & data. See doc 21 for why.
- **Simulation controls:** Trigger remittance, Advance 7 days, Delay next transfer, Inject unusually high bill, Add new EMI, plus large expense, second income, new family member, reset.
- **Model performance (clean test set):** forecast vs actual chart (model range and "same as last time" side by side); key metrics (forecast error, warning precision / recall / lead time, bill-estimate error, unusual-bill flags); a simulated year **with vs without** RemitWise and vs a fixed 50/30/20 rule, at 60 / 80 / 100% compliance; **fairness** table; audit log; data card.
- The "honest reading" sentence under the comparison table is generated from the numbers, so it cannot drift from the data.

## Where this differs from the original brief
- Bills and EMIs are **simulated mandates**. No real accounts or money are involved.
- The bill estimate is a **seasonal-naive statistical rule** (same month last year), not a deep model, and is labelled "Estimate".
- Categories are simulated shares of spending, and are labelled "Simulated".
- "SHAP" bars use LightGBM's built-in feature contributions for the forecast, and a rule trace for warnings.
- Auto-pay obeys the Responsible-AI rules in doc 10: it only pays what the family switched on; **unusual bills and bills over the family's limit always wait for approval**.

## Design-to-build notes (what was matched, what was changed on purpose)
- **Matched:** all 7 mobile and 8 desktop frames, including the remittance-arrived pop-up (centred on desktop, bottom sheet on mobile), the needs-review card with usual range, the vault card with Paid / Scheduled / At risk, the amber options card with **Apply choice**, per-goal share toggles with **Add money**, the electricity history chart with a dashed purple estimate bar, the forecast-vs-actual chart, the fairness bars and the Responsible-AI checks.
- **Real numbers replace the mock-up's.** The Judges frame says "Illustrative values · replace with your real test results" (e.g. 2.1 days, precision 0.84, 99% vs 81%). The app shows measured values from the held-out synthetic test households instead.
- **Honest comparison added.** The design has no with/without table; the app adds one (vs no plan and vs a fixed 50/30/20 rule) because that is the main evidence for judges.
- **"Send money" became "Plan this transfer"** on the sender view. No money moves in this demo; the action shares the sender's planned transfer with the family's forecast.
- **"Pays 8 Jun"** (two days before due) became "pays on due date", which is what the engine does.
- **"SHAP explanations"** are labelled "Feature explanations" (LightGBM's built-in contributions).
- **Not built:** the "Edit budget" button on the desktop Plan frame.
- **Added beyond the design:** a collapsed **Demo clock** (trigger remittance, +1 / +7 days, demo panel, language toggle), the family-side **Sharing with sender** card (grant or revoke, answer requests), and **Pause all** / **Download report** which the design shows as buttons.
- Deep links work: `#/home`, `#/payments`, `#/plan`, `#/goals`, `#/insights`, `#/sender`, `#/judge`.
