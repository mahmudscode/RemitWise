# 12 — Demo Script

Length: adapt to organizer limit (see open questions). Plan A ≈ 5 minutes. Always lead with the working product, not slides.

## Setup (before going on)
- Pre-generated dataset and models loaded; demo household "Rahima" selected; sender "Karim" open on a second screen/window.
- LLM fallback cache ready; offline mode tested.

## Flow 
1. **Hook (20s):** "Rahima's husband sends money from abroad. It arrives late, in different amounts, and is gone in a week." Show the *without* timeline: shortfall red zone.
2. **Forecast (40s):** Home screen shows next transfer as a *range* (date and amount), compared with naive guess. One line on how much better it is on the test set.
3. **Remittance arrives (60s):** Trigger arrival. Show 3 plan options, reasons in plain language; family adjusts a slider; shortfall risk updates; accept.
4. **Early warning (45s):** Advance time; spending spike appears; warning with run-out range and drivers; suggested action.
5. **Delayed transfer (30s):** Toggle delay; interval widens; plan buffers more. *(Final-day flexibility.)*
6. **Shared goal on both screens (45s):** Show progress bar on family and sender screens; show consent toggles; sender sees progress only, not transactions. Revoke consent → sender view changes.
7. **Side-by-side year (45s):** With vs without: shortfall days, savings, buffer, wallet retention. Mention compliance sensitivity.
8. **Responsible AI + path (30s):** Family decides, consent, fairness cut, synthetic data, post-hackathon validation.

## Judge Q&A prep
- *"Isn't this a budgeting app?"* → irregular-income forecast with uncertainty + optimizer reacting to it + side-by-side proof.
- *"Where does AI matter vs a rule?"* → show naive baseline and fixed-rule comparisons.
- *"Is the behavior change real?"* → it is an assumption; we show sensitivity and propose controlled validation.
- *"What if the LLM lies?"* → numbers validated against computed facts; template fallback.
- *"Privacy of the sender view?"* → server-side consent filter; progress only.
- *"What would you need from upay?"* → anonymized/aggregated inflow timing/amount data; see doc 16.

## Final-day flexibility moves (rehearse)
Add a goal; add second income; trigger delay; add family member. Each should take under 30 seconds.

## Fallbacks
- LLM down → template summaries.
- Network down → fully local run.
- Live bug → pre-recorded 2-minute backup video.

## Final build: judge path (5 minutes, rehearsed)
Open the app a minute early so the free server is awake (the app shows "Waking up the server…" otherwise).
1. Sign in as admin → Simulation sandbox → **Reset household**.
2. Use the **Guided demo** (steps 1 to 5, also on the floating bar over the family app):
   1. *Remittance arrives*: split pop-up. Say the AI suggests, the family decides.
   2. *Accept allocation*: bills reserved first, goals funded.
   3. *Unusual bill*: Payments shows a 2.4x electricity bill held for review.
   4. *Warning*: a delayed transfer plus a medical emergency. Open the banner, point at the reasons and 🔊 read aloud.
   5. *Resolution*: Plan screen, ask the sender to send earlier.
3. Switch to **বাংলা** mid-demo: the same screens, Bangla text and Bangla read-aloud (needs a Bangla voice on the device).
4. Admin → Model performance: warning before/after/hybrid table, **60/80/100% table with "Simulated, not measured"**, stress test, "The model serving the app".
5. Say out loud: the OTP is simulated, micro-savings is off by default and saves only, the business KPIs are a simulated estimate.
Extra scenarios to show in under 30 seconds each: Eid expense surge, Medical emergency, Systemic shock.
Fallbacks: Waking screen has a retry; the Guided demo can be restarted with Reset household.
