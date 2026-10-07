"""Model-drift and fairness monitoring (Admin → Monitoring).

Looks at the most recent window of the simulated timeline, only for households the model was NOT trained on,
and compares what the model predicted at each arrival with what actually happened next. In production the same
code would run on live data and alert the model owner.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from . import db

WINDOW_DAYS = 180        # "recent" = arrivals in the last 180 days of the timeline
PERIOD_DAYS = 30         # rolling error is reported per 30-day period
MIN_COVERAGE = 0.70      # red flag below this
ERR_RATIO = 1.5          # red flag when a group's error is this many times the median of the other groups
PSI_WARN, PSI_ALERT = 0.10, 0.25
DRIFT_FEATURES = ["last_gap", "gap_mean_all", "gap_cv", "last_amt", "amt_mean_all", "late_rate"]
_CACHE: dict = {}


def psi(ref: np.ndarray, cur: np.ndarray, bins: int = 10) -> float:
    """Population stability index of `cur` against `ref` (quantile bins of ref). <0.1 stable, >0.25 shifted."""
    ref, cur = ref[np.isfinite(ref)], cur[np.isfinite(cur)]
    if len(ref) < 20 or len(cur) < 20:
        return float("nan")
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    p = np.histogram(ref, edges)[0] / len(ref)
    q = np.histogram(cur, edges)[0] / len(cur)
    p, q = np.clip(p, 1e-4, None), np.clip(q, 1e-4, None)
    return float(np.sum((q - p) * np.log(q / p)))


def _frame() -> pd.DataFrame:
    """One row per (household, arrival) with the prediction made then and the outcome that followed."""
    f = db.read_sql("SELECT household_id, seq, day, gap_p10, gap_p50, gap_p90, amt_p10, amt_p50, amt_p90 FROM forecasts")
    r = db.read_sql("SELECT household_id, seq, day AS next_day, amount AS next_amt FROM remittances")
    r["seq"] = r["seq"] - 1
    h = db.read_sql("SELECT household_id, regularity_class, region, split FROM households")
    m = f.merge(r, on=["household_id", "seq"]).merge(h, on="household_id")
    m["gap"] = m["next_day"] - m["day"]
    m["gap_err"] = (m["gap_p50"] - m["gap"]).abs()
    m["gap_in"] = (m["gap"] >= m["gap_p10"]) & (m["gap"] <= m["gap_p90"])
    m["amt_in"] = (m["next_amt"] >= m["amt_p10"]) & (m["next_amt"] <= m["amt_p90"])
    m["amt_err"] = (m["amt_p50"] - m["next_amt"]).abs() / m["next_amt"]
    return m


def _block(d: pd.DataFrame) -> dict:
    return dict(n=int(len(d)), gap_mae=round(float(d.gap_err.mean()), 2), gap_coverage=round(float(d.gap_in.mean()), 3),
                amt_mape=round(float(d.amt_err.mean()), 3), amt_coverage=round(float(d.amt_in.mean()), 3))


def compute(warning_rate: dict | None = None) -> dict:
    m = _frame()
    live = m[m.split != "train"]
    end = int(live.next_day.max())
    recent = live[live.next_day > end - WINDOW_DAYS]
    overall = _block(recent)

    rolling = []
    for k in range(6):  # last six 30-day periods, oldest first
        hi = end - PERIOD_DAYS * (5 - k)
        w = live[(live.next_day > hi - PERIOD_DAYS) & (live.next_day <= hi)]
        if len(w) >= 10:
            rolling.append(dict(period=f"days {hi - PERIOD_DAYS + 1}–{hi}", **_block(w)))

    groups = []
    for name, col in (("Sender regularity", "regularity_class"), ("Region", "region")):
        blocks = {g: _block(d) for g, d in recent.groupby(col) if len(d) >= 10}
        for g, b in blocks.items():
            others = [x["gap_mae"] for k, x in blocks.items() if k != g]
            flags = []
            if b["gap_coverage"] < MIN_COVERAGE:
                flags.append(f"range coverage {int(b['gap_coverage'] * 100)}% is below {int(MIN_COVERAGE * 100)}%")
            if others and b["gap_mae"] > ERR_RATIO * float(np.median(others)):
                flags.append(f"timing error {b['gap_mae']} days is more than {ERR_RATIO}x the other groups")
            groups.append(dict(dimension=name, group=g, flags=flags, **b))

    feats = db.read_sql("SELECT f.*, h.split, p.day FROM forecast_features f JOIN households h ON h.household_id = f.household_id "
                        "JOIN forecasts p ON p.household_id = f.household_id AND p.seq = f.seq")
    ref = feats[feats.split == "train"]
    cur = feats[(feats.split != "train") & (feats.day > feats.day.max() - WINDOW_DAYS)]
    drift = []
    for c in DRIFT_FEATURES:
        v = psi(ref[c].to_numpy(float), cur[c].to_numpy(float))
        shift = float((cur[c].mean() - ref[c].mean()) / (ref[c].std() or 1.0))
        status = "alert" if v > PSI_ALERT else "watch" if v > PSI_WARN else "stable"
        drift.append(dict(feature=c, psi=None if np.isnan(v) else round(v, 3), mean_shift_sd=round(shift, 2), status=status))

    alerts = [f"{g['dimension']} · {g['group']}: " + "; ".join(g["flags"]) for g in groups if g["flags"]]
    if overall["gap_coverage"] < MIN_COVERAGE:
        alerts.insert(0, f"Overall timing range coverage {int(overall['gap_coverage'] * 100)}% is below {int(MIN_COVERAGE * 100)}%")
    alerts += [f"Input drift: {d['feature']} (PSI {d['psi']})" for d in drift if d["status"] == "alert"]
    return dict(window=dict(days=WINDOW_DAYS, households=int(recent.household_id.nunique()), cycles=overall["n"],
                            note="Households the model was not trained on, most recent 180 days of the simulated timeline."),
                overall=overall, rolling=rolling, groups=groups, drift=drift, warning_rate=warning_rate, alerts=alerts,
                thresholds=dict(min_coverage=MIN_COVERAGE, error_ratio=ERR_RATIO, psi_watch=PSI_WARN, psi_alert=PSI_ALERT),
                note="In production this runs on real data and alerts the model owner.")


def cached(warning_rate_fn, ttl: int = 60) -> dict:
    now = time.time()
    if "v" not in _CACHE or now - _CACHE["t"] > ttl:
        _CACHE.update(v=compute(warning_rate_fn()), t=now)
    return _CACHE["v"]
