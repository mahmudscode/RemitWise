"""Shortfall early warning: Monte-Carlo projection + rule-trace drivers (doc 06-C)."""
from __future__ import annotations

import numpy as np

CAP_H = 140


def sample_gap(rng: np.random.Generator, p10: float, p50: float, p90: float, n: int) -> np.ndarray:
    """Sample days-to-arrival by inverse-CDF through the forecast quantiles."""
    lo0 = max(p10 - (p50 - p10), 0.5)
    hi1 = p90 + (p90 - p50)
    return np.interp(rng.random(n), [0, 0.1, 0.5, 0.9, 1.0], [lo0, p10, p50, p90, hi1])


def simulate_shortfall(balance: float, daily_mean: float, daily_cv: float,
                       rem: dict, reserve: float = 0.0, n: int = 1000, seed: int = 7) -> dict:
    """Probability that spendable money (+ emergency reserve) runs out before the next transfer.

    rem: dict(rem_p10, rem_p50, rem_p90) days until next arrival.
    Returns probability, run-out day quantiles (days from now) among shortfall paths.
    """
    rng = np.random.default_rng(seed)
    gaps = sample_gap(rng, rem["rem_p10"], rem["rem_p50"], rem["rem_p90"], n)
    H = int(min(CAP_H, np.ceil(gaps.max()) + 2))
    cv = max(daily_cv, 0.05)
    spend = rng.gamma(1.0 / cv**2, daily_mean * cv**2, size=(n, H))
    cum = np.cumsum(spend, axis=1)
    avail = balance + reserve
    over = cum > avail
    runout = np.where(over.any(axis=1), over.argmax(axis=1) + 1, H + 1).astype(float)
    short = runout < gaps  # money gone before the transfer arrives
    prob = float(short.mean())
    out = dict(prob=prob)
    if short.any():
        out.update(runout_p10=float(np.quantile(runout[short], 0.1)),
                   runout_p50=float(np.quantile(runout[short], 0.5)),
                   runout_p90=float(np.quantile(runout[short], 0.9)),
                   expected_gap_days=float(np.mean(gaps[short] - runout[short])))
    return out


def severity(prob: float, thr: float) -> str:
    if prob >= max(thr + 0.2, 0.6):
        return "red"
    if prob >= thr:
        return "amber"
    return "green"


def drivers(recent_mean: float, usual_mean: float, balance: float, rem_p50: float,
            days_since: float, gap_p50_at_arrival: float, recent_shock: float) -> list[dict]:
    """Rule trace: why risk is elevated. Each item has a magnitude 0..1 for ranking."""
    items = []
    if usual_mean > 0:
        ratio = recent_mean / usual_mean
        if ratio > 1.15:
            items.append(dict(factor="spending_pace", magnitude=min(1.0, (ratio - 1) / 0.6),
                              ratio=round(ratio, 2),
                              detail=f"Spending in the last week is {round((ratio - 1) * 100)}% above usual."))
    if days_since > gap_p50_at_arrival:
        late = days_since - gap_p50_at_arrival
        items.append(dict(factor="late_transfer", magnitude=min(1.0, late / 15.0), days_late=round(late, 1),
                          detail=f"The next transfer is about {round(late)} days later than usual."))
    cover = balance / usual_mean if usual_mean > 0 else 99
    if cover < rem_p50:
        items.append(dict(factor="low_cover", magnitude=min(1.0, (rem_p50 - cover) / max(rem_p50, 1)),
                          cover_days=round(cover, 1),
                          detail=f"Current money covers about {round(cover)} days, but the next transfer is expected in about {round(rem_p50)} days."))
    if recent_shock > 0:
        items.append(dict(factor="large_expense", magnitude=0.5, amount=round(recent_shock),
                          detail="A large one-off expense happened recently."))
    return sorted(items, key=lambda d: -d["magnitude"])[:3]
