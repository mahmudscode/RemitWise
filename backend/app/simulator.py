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
        base = monthly_needs / 30.0
        essential = base * WEEKDAY_FACTOR[dates.dayofweek] * rng.lognormal(0, 0.15, n_days)
        shock = np.zeros(n_days)
        # festival spending: ~+100% essentials in the +/-5 day window around Eid
        for eid in EID_DATES:
            d0 = (eid - pd.Timestamp(config.START_DATE)).days
            for d in range(d0 - 5, d0 + 6):
                if 0 <= d < n_days:
                    shock[d] += base * 1.0
        # school fees (Jan / Jul, day 5)
        if school:
            for d in range(n_days):
                if dates[d].month in (1, 7) and dates[d].day == 5:
                    shock[d] += monthly_needs * 0.3
        # large one-off (medical / wedding / repair), ~35% chance per year
        for yr in range(int(np.ceil(n_days / 365))):
            if rng.random() < 0.35:
                d = int(yr * 365 + rng.integers(0, 365))
                if d < n_days:
                    shock[d] += monthly_needs * rng.uniform(0.5, 1.5)
        local_income = np.full(n_days, local_monthly / 30.0)

        led_frames.append(pd.DataFrame(dict(household_id=hid, day=days, date=dates,
                                            essential=essential.round(1), shock=shock.round(1),
                                            local_income=local_income.round(1))))
        hh_rows.append(dict(household_id=hid, region=region, size=size, sender_origin=sender_origin,
                            regularity_class=cls, small_sender=bool(small_sender),
                            typical_amount=round(typical, 0), gap_mean=round(gap_mean, 1),
                            local_income_monthly=round(local_monthly, 0),
                            monthly_needs=round(monthly_needs, 0), leak_rate=round(leak_rate, 3),
                            cashout_frac=round(cashout_frac, 3), school_children=bool(school),
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
    return households, remittances, ledger


if __name__ == "__main__":
    h, r, l = generate()
    print(h.regularity_class.value_counts().to_dict(), len(r), len(l))
