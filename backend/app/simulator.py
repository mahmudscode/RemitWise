"""Synthetic remittance-household generator (doc 07). Seeded, reproducible.

Every parameter below is a documented ASSUMPTION, not real-world evidence.
No real PII is used or needed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

# Approximate Eid dates inside the simulated window (assumption for festival effects).
EID_DATES = pd.to_datetime(
    ["2024-04-10", "2024-06-17", "2025-03-31", "2025-06-07", "2026-03-20", "2026-05-27"]
)

CLASS_PARAMS = {
    # gap_sd: sd of days between transfers; sigma: amount log-sd; delay_p: chance a cycle is delayed
    "regular": dict(gap_mean=(28, 32), gap_sd=2.5, sigma=0.08, delay_p=0.05, topup_p=0.0),
    "semi": dict(gap_mean=(26, 34), gap_sd=7.0, sigma=0.20, delay_p=0.12, topup_p=0.25),
    "irregular": dict(gap_mean=(22, 50), gap_sd=14.0, sigma=0.45, delay_p=0.22, topup_p=0.15),
}
CLASS_PROBS = {"regular": 0.40, "semi": 0.35, "irregular": 0.25}
WEEKDAY_FACTOR = np.array([1.15, 1.0, 0.95, 0.9, 0.9, 1.0, 1.1])  # mean ~1.0
# Seasonal multiplier for variable bills (electricity): hot months cost more (assumption).
SEASON_VAR = {1: 0.8, 2: 0.8, 3: 0.95, 4: 1.35, 5: 1.5, 6: 1.6, 7: 1.6, 8: 1.5, 9: 1.2, 10: 1.0, 11: 0.9, 12: 0.85}


def _day_to_ts(day: int) -> pd.Timestamp:
    return pd.Timestamp(config.START_DATE) + pd.Timedelta(days=int(day))


def _next_eid_after(ts: pd.Timestamp):
    later = EID_DATES[EID_DATES >= ts]
    return later[0] if len(later) else None


def generate(seed: int = config.SEED, n: int = config.N_HOUSEHOLDS, n_days: int = config.N_DAYS):
    """Return (households, remittances, ledger) DataFrames."""
    rng = np.random.default_rng(seed)
    classes = rng.choice(list(CLASS_PROBS), size=n, p=list(CLASS_PROBS.values()))
    hh_rows, ev_rows, led_frames = [], [], []
    bill_def_rows, bill_sched_rows = [], []

    for i in range(n):
        hid = f"H{i + 1:03d}"
        cls = str(classes[i])
        p = CLASS_PARAMS[cls]
        size = int(rng.integers(3, 8))
        region = str(rng.choice(["urban", "rural"], p=[0.35, 0.65]))
        sender_origin = str(rng.choice(["gulf", "malaysia", "other"], p=[0.6, 0.2, 0.2]))
        gap_mean = float(rng.uniform(*p["gap_mean"]))
        typical = float(np.clip(rng.lognormal(np.log(28000), 0.4), 8000, 90000))
        small_sender = cls == "irregular" and rng.random() < 0.4  # fairness cohort: small + irregular
        if small_sender:
            typical *= 0.5
        local_monthly = 0.0 if rng.random() < 0.5 else float(rng.uniform(3000, 12000))
        income_month = typical * 30.0 / gap_mean + local_monthly
        monthly_needs = float(income_month * rng.uniform(0.55, 0.78))
        leak_rate = float(rng.uniform(0.10, 0.35))  # cash-in-hand discretionary spend (baseline only)
        cashout_frac = float(rng.uniform(0.75, 1.0))  # baseline: share cashed out soon after arrival
        school = rng.random() < 0.6

        # ---- bills / EMIs (carved out of monthly_needs, so total needs are unchanged) ----
        bdefs = []
        def _add(name, kind, share, variable, dom):
            usual = float(np.round(monthly_needs * share, -1))
            bdefs.append(dict(household_id=hid, bill_id=f"{hid}-{name.lower().replace(' ', '-')}", name=name,
                              kind=kind, usual=usual, variable=variable, due_dom=int(dom),
                              autopay=True, monthly_limit=float(np.round(usual * 2.2, -1))))
        _add("Electricity", "utility", rng.uniform(0.05, 0.08), True, rng.integers(8, 13))
        _add("Gas", "utility", rng.uniform(0.02, 0.035), False, 15)
        if rng.random() < 0.6:
            _add("Internet", "utility", rng.uniform(0.02, 0.035), False, 5)
        if rng.random() < 0.4:
            _add("Motorcycle EMI", "emi", rng.uniform(0.10, 0.18), False, rng.integers(10, 21))
        if school:
            _add("School fees", "school", rng.uniform(0.06, 0.10), False, 5)
        bills_monthly = float(sum(b["usual"] for b in bdefs))
        cat = rng.dirichlet(np.array([5.0, 1.2, 1.4 if school else 0.4, 0.8, 1.2]))

        sched = []
        base_m = pd.Timestamp(config.START_DATE).replace(day=1)
        for m in range(int(np.ceil(n_days / 30)) + 2):
            for b in bdefs:
                ts = (base_m + pd.DateOffset(months=m)).replace(day=min(b["due_dom"], 28))
                di = (ts - pd.Timestamp(config.START_DATE)).days
                if not 0 <= di < n_days:
                    continue
                if b["variable"]:
                    amt = b["usual"] * SEASON_VAR[ts.month] * rng.lognormal(0, 0.08)
                else:
                    amt = b["usual"] * rng.normal(1.0, 0.02)
                anomaly = bool(b["variable"] and rng.random() < 0.04)
                if anomaly:
                    amt *= rng.uniform(2.0, 3.2)
                sched.append(dict(household_id=hid, bill_id=b["bill_id"], due_day=int(di),
                                  amount=float(np.round(amt, 0)), anomaly=anomaly))
        bill_def_rows += bdefs
        bill_sched_rows += sched

        # ---- remittance events ----
        day, seq, prev_day = 0.0, 0, None
        first = float(rng.uniform(5, 25))
        events = []
        t = first
        while t < n_days:
            ts = _day_to_ts(t)
            amount = float(typical * rng.lognormal(0, p["sigma"]))
            delayed, festival = False, False
            eid = _next_eid_after(ts)
            if eid is not None and 0 <= (eid - ts).days <= 18 and rng.random() < 0.6:
                t_new = (eid - pd.Timestamp(config.START_DATE)).days - rng.uniform(3, 10)
                if prev_day is None or t_new > prev_day + 7:
                    t, festival = t_new, True
                    amount *= float(rng.uniform(1.2, 1.5))
            events.append(dict(day=int(round(t)), amount=round(amount, 0), delayed=delayed, festival=festival))
            prev_day = t
            gap = max(8.0, rng.normal(gap_mean, p["gap_sd"]))
            if rng.random() < p["delay_p"]:
                gap += float(rng.integers(5, 26))
                events[-1]["next_delayed"] = True
            t = t + gap
            # occasional small mid-cycle top-up
            if rng.random() < p["topup_p"]:
                tu = prev_day + rng.uniform(10, 15)
                if tu < t - 5 and tu < n_days:
                    events.append(dict(day=int(round(tu)), amount=round(typical * rng.uniform(0.15, 0.3), 0),
                                       delayed=False, festival=False))
                    prev_day = tu
        for k, e in enumerate(events):
            ev_rows.append(dict(household_id=hid, seq=k, day=e["day"], date=_day_to_ts(e["day"]),
                                amount=e["amount"], festival=e["festival"]))
        # delayed flag: a transfer is "late" when its preceding gap is much longer than usual
        # (computed downstream from gaps; kept implicit to avoid leaking labels)

        # ---- daily ledger ----
        days = np.arange(n_days)
        dates = pd.to_datetime(config.START_DATE) + pd.to_timedelta(days, unit="D")
        base = (monthly_needs - bills_monthly) / 30.0
        essential = base * WEEKDAY_FACTOR[dates.dayofweek] * rng.lognormal(0, 0.15, n_days)
        shock = np.zeros(n_days)
        shock_cat = np.full(n_days, "", dtype=object)
        # festival spending: ~+100% essentials in the +/-5 day window around Eid
        for eid in EID_DATES:
            d0 = (eid - pd.Timestamp(config.START_DATE)).days
            for d in range(d0 - 5, d0 + 6):
                if 0 <= d < n_days:
                    shock[d] += base * 1.0
                    shock_cat[d] = "other"
        # large one-off (medical / wedding / repair), ~35% chance per year
        for yr in range(int(np.ceil(n_days / 365))):
            if rng.random() < 0.35:
                d = int(yr * 365 + rng.integers(0, 365))
                if d < n_days:
                    shock[d] += monthly_needs * rng.uniform(0.5, 1.5)
                    shock_cat[d] = "health"
        local_income = np.full(n_days, local_monthly / 30.0)

        led_frames.append(pd.DataFrame(dict(household_id=hid, day=days, date=dates,
                                            essential=essential.round(1), shock=shock.round(1), shock_cat=shock_cat,
                                            local_income=local_income.round(1))))
        hh_rows.append(dict(household_id=hid, region=region, size=size, sender_origin=sender_origin,
                            regularity_class=cls, small_sender=bool(small_sender),
                            typical_amount=round(typical, 0), gap_mean=round(gap_mean, 1),
                            local_income_monthly=round(local_monthly, 0),
                            monthly_needs=round(monthly_needs, 0), leak_rate=round(leak_rate, 3),
                            cashout_frac=round(cashout_frac, 3), school_children=bool(school),
                            bills_monthly=round(bills_monthly, 0), cat_food=round(float(cat[0]), 3),
                            cat_transport=round(float(cat[1]), 3), cat_education=round(float(cat[2]), 3),
                            cat_health=round(float(cat[3]), 3), cat_other=round(float(cat[4]), 3),
                            sender_id=f"S-{hid}"))

    households = pd.DataFrame(hh_rows)
    # split by household (doc 07): train / calibration / clean test
    ids = households["household_id"].to_numpy()
    perm = rng.permutation(len(ids))
    n_tr = int(config.SPLIT["train"] * len(ids))
    n_ca = int(config.SPLIT["cal"] * len(ids))
    split = np.empty(len(ids), dtype=object)
    split[perm[:n_tr]] = "train"
    split[perm[n_tr:n_tr + n_ca]] = "cal"
    split[perm[n_tr + n_ca:]] = "test"
    households["split"] = split
    remittances = pd.DataFrame(ev_rows)
    ledger = pd.concat(led_frames, ignore_index=True)
    bill_defs = pd.DataFrame(bill_def_rows)
    bill_sched = pd.DataFrame(bill_sched_rows)
    return households, remittances, ledger, bill_defs, bill_sched


if __name__ == "__main__":
    h, r, l, bd, bs = generate()
    print(h.regularity_class.value_counts().to_dict(), len(r), len(l), len(bd), len(bs))
