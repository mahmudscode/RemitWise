"""Offline evaluation on the clean test households (doc 11). Measured vs assumed is kept separate."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import bills as billslib, config, forecast, risk, sim

COMPLIANCE_LEVELS = (0.6, 0.8, 1.0)


def _cuts(h: pd.DataFrame) -> dict[str, pd.Series]:
    amt_bin = pd.qcut(h["typical_amount"], 3, labels=["small", "medium", "large"])
    return {"regularity": h["regularity_class"], "transfer_size": amt_bin.astype(str),
            "region": h["region"]}


def forecast_metrics(te: pd.DataFrame, P: pd.DataFrame, h: pd.DataFrame) -> dict:
    N = forecast.naive_forecast(te)
    def block(mask):
        m = te[mask]; p = P[mask]; n = N[mask]
        if len(m) == 0:
            return None
        return dict(
            n=int(len(m)),
            gap_mae_model=float(np.abs(p.gap_p50 - m.target_gap).mean()),
            gap_mae_naive=float(np.abs(n.gap - m.target_gap).mean()),
            amt_mape_model=float((np.abs(p.amt_p50 - m.target_amt) / m.target_amt).mean()),
            amt_mape_naive=float((np.abs(n.amt - m.target_amt) / m.target_amt).mean()),
            gap_coverage=float(((m.target_gap >= p.gap_p10) & (m.target_gap <= p.gap_p90)).mean()),
            amt_coverage=float(((m.target_amt >= p.amt_p10) & (m.target_amt <= p.amt_p90)).mean()),
        )
    allm = np.ones(len(te), dtype=bool)
    out = dict(overall=block(allm), nominal_coverage=config.INTERVAL_COVERAGE, by_group={})
    hh = h.set_index("household_id")
    for name, ser in _cuts(h).items():
        mapping = ser.set_axis(h["household_id"])
        grp = te["household_id"].map(mapping).to_numpy()
        out["by_group"][name] = {g: block(grp == g) for g in sorted(set(grp)) if g == g}
    return out


def _fc_dict(P: pd.DataFrame, ids: pd.Series, seqs: pd.Series, hid: str) -> dict:
    sel = (ids.to_numpy() == hid)
    return {int(s): r for s, r in zip(seqs[sel], P[sel].to_dict("records"))}


def _bills_maps(h, bdefs, bsched):
    out = {}
    for hid, g in bsched.groupby("household_id"):
        out[hid] = sim.bills_by_day_map(g, bdefs[bdefs.household_id == hid])
    return out


def compare_policies(h, r, l, te, P, bmaps) -> dict:
    tests = h[h.split == "test"]
    led_by = {k: v.reset_index(drop=True) for k, v in l.groupby("household_id")}
    ev_by = {k: v for k, v in r.groupby("household_id")}
    fcs = {hid: _fc_dict(P, te["household_id"], te["seq"], hid) for hid in tests.household_id}
    rows = []
    for _, row in tests.iterrows():
        hid = row["household_id"]
        bm = bmaps.get(hid, {})
        base = sim.run_policy(row, ev_by[hid], led_by[hid], fcs[hid], "baseline", seed=11, bills_by_day=bm)
        rows.append(dict(household_id=hid, cls=row["regularity_class"], policy="baseline", compliance=1.0, **base))
        for c in COMPLIANCE_LEVELS:
            fx = sim.run_policy(row, ev_by[hid], led_by[hid], fcs[hid], "fixed_rule", c, seed=11, bills_by_day=bm)
            rw = sim.run_policy(row, ev_by[hid], led_by[hid], fcs[hid], "remitwise", c, seed=11, bills_by_day=bm)
            rows.append(dict(household_id=hid, cls=row["regularity_class"], policy="fixed_rule", compliance=c, **fx))
            rows.append(dict(household_id=hid, cls=row["regularity_class"], policy="remitwise", compliance=c, **rw))
    df = pd.DataFrame(rows)
    metrics = ["shortfall_days_per_year", "savings_rate", "emergency_months", "retained_share",
               "borrow_cost_per_year", "saved_amount", "goal_raid", "on_time_rate", "late_fees_per_year",
               "overbilling_avoided_per_year", "overbilling_paid_per_year"]
    agg = df.groupby(["policy", "compliance"])[metrics].mean().round(4).reset_index()
    by_cls = df.groupby(["cls", "policy", "compliance"])[metrics].mean().round(4).reset_index()
    return dict(summary=agg.to_dict("records"), by_class=by_cls.to_dict("records"),
                per_household=df.round(4).to_dict("records"), n_households=int(len(tests)),
                horizon_days=365, metrics=metrics)


def _checkpoints(h, r, l, ids, P_all, bmaps, n_mc=400):
    """Build warning checkpoints (features + truth) for given households."""
    led_by = {k: v.reset_index(drop=True) for k, v in l.groupby("household_id")}
    ev_by = {k: v for k, v in r.groupby("household_id")}
    hh_by = h.set_index("household_id")
    out = []
    for hid in ids:
        row = hh_by.loc[hid].copy(); row["household_id"] = hid
        fc = P_all.get(hid, {})
        o = sim.run_policy(row, ev_by[hid], led_by[hid], fc, "baseline", seed=3, record=True,
                           horizon_days=700, bills_by_day=bmaps.get(hid, {}))
        s = o["series"]
        arr = ev_by[hid].set_index("seq")["day"].to_dict()
        seq_of_day = {v: k for k, v in arr.items()}
        ess = led_by[hid]["essential"].to_numpy()
        for cyc, grp in s.groupby("cycle"):
            if cyc < 0:
                continue
            day0 = int(grp["day"].iloc[0] - grp["since"].iloc[0]) if False else int(grp["day"].iloc[0])
            seq = seq_of_day.get(day0)
            if seq is None or seq not in fc:
                continue
            f = fc[seq]
            grp = grp.reset_index(drop=True)
            if len(grp) < 8:
                continue
            for i in range(4, len(grp) - 3, 5):
                row_i = grp.iloc[i]
                d = int(row_i["day"])
                since = int(row_i["since"])
                rec_days = grp.iloc[max(0, i - 6): i + 1]
                recent = float(rec_days["spent"].median())  # median: one-off expenses must not distort burn
                usual = float(ess[max(0, d - 60): d + 1].mean())
                local_daily = float(row["local_income_monthly"]) / 30.0
                dm = max(max(recent, usual) - local_daily, 1.0)  # net burn: local income arrives daily
                rem = forecast.remaining_forecast(f, since)
                res = risk.simulate_shortfall(float(row_i["spendable"]), dm, 0.35, rem, n=n_mc, seed=d)
                cover = float(row_i["spendable"]) / max(usual - local_daily, 1.0)
                truth = bool(grp.iloc[i + 1:]["short"].any())
                lead = None
                if truth:
                    lead = int(grp.iloc[i + 1:][grp.iloc[i + 1:]["short"]]["day"].iloc[0] - d)
                out.append(dict(household_id=hid, prob=res["prob"], naive_warn=cover < rem["rem_p50"],
                                truth=truth, lead=lead))
    return pd.DataFrame(out)


def _prf(df, warn):
    tp = int((warn & df.truth).sum()); fp = int((warn & ~df.truth).sum()); fn = int((~warn & df.truth).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * rec / (p + rec) if p + rec else 0.0
    leads = df.loc[warn & df.truth, "lead"].dropna()
    return dict(precision=round(p, 4), recall=round(rec, 4), f1=round(f1, 4),
                mean_lead_days=round(float(leads.mean()), 2) if len(leads) else None,
                n=int(len(df)), base_rate=round(float(df.truth.mean()), 4))


def warning_metrics(h, r, l, ds_all, P_all_df, bmaps) -> dict:
    P_all = {}
    for hid, g in P_all_df.groupby("household_id"):
        P_all[hid] = {int(rw["seq"]): rw for rw in g.to_dict("records")}
    cal_ids = h[h.split == "cal"].household_id.tolist()[:60]
    test_ids = h[h.split == "test"].household_id.tolist()
    cal = _checkpoints(h, r, l, cal_ids, P_all, bmaps)
    grid = np.arange(0.15, 0.85, 0.05)
    best = max(grid, key=lambda t: _prf(cal, cal.prob >= t)["f1"])  # tuned on calibration households only
    test = _checkpoints(h, r, l, test_ids, P_all, bmaps)
    return dict(threshold=round(float(best), 2),
                model=_prf(test, test.prob >= best),
                threshold_only_rule=_prf(test, test.naive_warn),
                note="Tuned on calibration households; reported on clean test households.")


def forecast_samples(te: pd.DataFrame, P: pd.DataFrame, n: int = 60) -> list[dict]:
    """Forecast vs actual on the clean test set, model and naive side by side (for the judge chart)."""
    N = forecast.naive_forecast(te)
    idx = te.sample(n=min(n, len(te)), random_state=config.SEED).index
    rows = []
    for i in idx:
        rows.append(dict(household_id=te.loc[i, "household_id"], actual_gap=float(te.loc[i, "target_gap"]),
                         model_p10=float(P.loc[i, "gap_p10"]), model_p50=float(P.loc[i, "gap_p50"]),
                         model_p90=float(P.loc[i, "gap_p90"]), naive=float(N.loc[i, "gap"]),
                         actual_amt=float(te.loc[i, "target_amt"]), model_amt=float(P.loc[i, "amt_p50"]),
                         naive_amt=float(N.loc[i, "amt"])))
    rows.sort(key=lambda r: r["actual_gap"])
    return rows


def bill_metrics(h, bsched, bdefs) -> dict:
    """Bill estimate vs 'same as last month' and anomaly flagging, on the clean test households."""
    test_ids = set(h[h.split == "test"].household_id)
    s = bsched[bsched.household_id.isin(test_ids)].copy()
    var = bdefs.set_index("bill_id")["variable"].to_dict()
    s["variable"] = s["bill_id"].map(var)
    v = s[s.variable & ~s.anomaly].sort_values(["bill_id", "due_day"]).copy()
    v["last"] = v.groupby("bill_id")["amount"].shift(1)
    v = v.dropna(subset=["last"])
    v = v[v.due_day > 400]  # after a year of history so seasonal memory exists
    tp = int((s.flagged & s.anomaly).sum()); fp = int((s.flagged & ~s.anomaly).sum()); fn = int((~s.flagged & s.anomaly).sum())
    return dict(
        n_estimates=int(len(v)),
        estimate_mape_model=float((abs(v.expected - v.amount) / v.amount).mean()),
        estimate_mape_naive=float((abs(v["last"] - v.amount) / v.amount).mean()),
        anomaly_precision=float(tp / (tp + fp)) if tp + fp else None,
        anomaly_recall=float(tp / (tp + fn)) if tp + fn else None,
        anomalies=int(s.anomaly.sum()))
