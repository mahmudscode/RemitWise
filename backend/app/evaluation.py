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


def _checkpoints(h, r, l, ids, P_all, bmaps, n_mc=400, only_seqs=None):
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
            if seq is None or seq not in fc or (only_seqs is not None and seq not in only_seqs):
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


PRECISION_TARGET = 0.85


def _fbeta(m: dict, beta: float) -> float:
    p, r = m["precision"], m["recall"]
    return (1 + beta ** 2) * p * r / (beta ** 2 * p + r) if p + r else 0.0


def warning_metrics(h, r, l, ds_all, P_all_df, bmaps) -> dict:
    P_all = {}
    for hid, g in P_all_df.groupby("household_id"):
        P_all[hid] = {int(rw["seq"]): rw for rw in g.to_dict("records")}
    cal_ids = h[h.split == "cal"].household_id.tolist()[:60]
    test_ids = h[h.split == "test"].household_id.tolist()
    cal = _checkpoints(h, r, l, cal_ids, P_all, bmaps)
    test = _checkpoints(h, r, l, test_ids, P_all, bmaps)
    grid = [round(float(t), 2) for t in np.arange(0.15, 0.85, 0.05)]
    hyb = lambda df, t: (df.prob >= t) | df.naive_warn  # hybrid: warn when the model says so OR the simple rule fires
    cal_m = {t: _prf(cal, cal.prob >= t) for t in grid}  # selection uses calibration households only
    cal_h = {t: _prf(cal, hyb(cal, t)) for t in grid}
    # before: the F1-optimal threshold (Phase 1 behaviour)
    t_before = max(grid, key=lambda t: cal_m[t]["f1"])
    def pick(table):  # lowest threshold reaching the precision target on calibration; fallback = best F0.5
        ok = [t for t in grid if table[t]["precision"] >= PRECISION_TARGET]
        return (min(ok), True) if ok else (max(grid, key=lambda t: _fbeta(table[t], 0.5)), False)
    t_model, ok_m = pick(cal_m)
    t_after, ok_h = pick(cal_h)
    note_sel = lambda ok: "lowest threshold with precision >= %.2f on calibration" % PRECISION_TARGET if ok else "max F0.5 on calibration (target precision not reached)"
    keep = ("precision", "recall", "f1", "mean_lead_days")
    sweep = [dict(threshold=t, **{k: v for k, v in _prf(test, hyb(test, t)).items() if k in keep}) for t in grid]
    sweep_model_only = [dict(threshold=t, **{k: v for k, v in _prf(test, test.prob >= t).items() if k in keep}) for t in grid]
    before = dict(threshold=t_before, **_prf(test, test.prob >= t_before))
    model_only = dict(threshold=t_model, selection=note_sel(ok_m), **_prf(test, test.prob >= t_model))
    after = dict(threshold=t_after, selection=note_sel(ok_h) + " (hybrid: model OR simple rule)", mode="hybrid_or", **_prf(test, hyb(test, t_after)))
    return dict(threshold=t_after, mode="hybrid_or", before=before, after=after, model_only=model_only,
                sweep=sweep, sweep_model_only=sweep_model_only,
                model=after, threshold_only_rule=_prf(test, test.naive_warn),
                note="Thresholds chosen on calibration households; all numbers reported on clean test households. "
                     "The simple rule is 'current spendable money covers fewer days than the next transfer is expected to take'.")


SHOCK_START_SEQ = 6      # the corridor disruption starts at this transfer
SHOCK_DELAY_DAYS = 21    # each of the next three transfers arrives 21 days later than it otherwise would
SHOCK_AMOUNT_CUT = 0.30
SHOCK_LEN = 3


def shocked_events(r: pd.DataFrame) -> pd.DataFrame:
    """Same disruption the sandbox button applies: three transfers arrive later (cumulatively) and 30% smaller;
    every later transfer keeps its normal gap but is shifted by the accumulated delay."""
    r = r.copy()
    rank = (r["seq"] - SHOCK_START_SEQ + 1).clip(lower=0)
    r["day"] = r["day"] + SHOCK_DELAY_DAYS * rank.clip(upper=SHOCK_LEN)
    hit = (rank >= 1) & (rank <= SHOCK_LEN)
    r.loc[hit, "amount"] = r.loc[hit, "amount"] * (1 - SHOCK_AMOUNT_CUT)
    return r


def stress_test(h, r, l, te, P_te, P_all_df, bmaps, threshold: float) -> dict:
    """Robustness to a systemic shock (remittance-corridor disruption). The model was never trained on shocks."""
    seqs = list(range(SHOCK_START_SEQ, SHOCK_START_SEQ + SHOCK_LEN))
    win = te[te.seq.isin(seqs)]
    P = P_te.loc[win.index]
    def cov(gap_add, amt_mult):
        g = win.target_gap + gap_add
        a = win.target_amt * amt_mult
        return dict(n=int(len(win)),
                    gap_mae=round(float(np.abs(P.gap_p50 - g).mean()), 2),
                    gap_coverage=round(float(((g >= P.gap_p10) & (g <= P.gap_p90)).mean()), 3),
                    amt_coverage=round(float(((a >= P.amt_p10) & (a <= P.amt_p90)).mean()), 3))
    P_all = {}
    for hid, g in P_all_df.groupby("household_id"):
        P_all[hid] = {int(rw["seq"]): rw for rw in g.to_dict("records")}
    test_ids = h[h.split == "test"].household_id.tolist()
    window = {k - 1 for k in seqs}  # cycles that start at the arrival before each affected transfer
    r_test = r[r.household_id.isin(test_ids)]
    out = {}
    for name, ev in (("normal", r_test), ("shock", shocked_events(r_test))):
        ck = _checkpoints(h, ev, l, test_ids, P_all, bmaps, only_seqs=window)
        out[name] = _prf(ck, (ck.prob >= threshold) | ck.naive_warn)  # same hybrid warning as the live app
    return dict(
        description=f"Three consecutive transfers (from transfer {SHOCK_START_SEQ}) arrive {SHOCK_DELAY_DAYS} days later each and {int(SHOCK_AMOUNT_CUT * 100)}% smaller.",
        threshold=threshold, forecast=dict(normal=cov(0, 1.0), shock=cov(SHOCK_DELAY_DAYS, 1 - SHOCK_AMOUNT_CUT)),
        warning=out,
        note="The forecaster was not trained on shocks. Protection comes from the rule that widens the range when a transfer is overdue, and from warnings that read the live balance.")


def kpi_base(h, bdefs) -> dict:
    """Volumes the business-KPI view multiplies by (test households): bills and remittance per household per month."""
    t = h[h.split == "test"]
    n_bills = bdefs[bdefs.household_id.isin(t.household_id)].groupby("household_id").size().reindex(t.household_id).fillna(0)
    monthly_remit = t["typical_amount"] * 30.0 / t["gap_mean"]
    return dict(households=int(len(t)), bills_per_household_month=round(float(n_bills.mean()), 2),
                monthly_remittance=round(float(monthly_remit.mean())), source="synthetic test households")


def irregular_experiment(te: pd.DataFrame, h_test: pd.DataFrame, variants: dict) -> dict:
    """Compare forecaster variants on the clean test households, overall and per sender-regularity group.
    The new variant is adopted only if it does not make overall error or coverage worse AND helps irregular senders."""
    res = {}
    for name, fc in variants.items():
        m = forecast_metrics(te, fc.predict(te), h_test)
        res[name] = dict(overall=m["overall"], by_regularity=m["by_group"]["regularity"])
    base, new = res["baseline"], res["regularity_features_group_calibration"]
    nominal = config.INTERVAL_COVERAGE
    off = lambda x: abs(x - nominal)
    ob, on = base["overall"], new["overall"]
    ib, i_n = base["by_regularity"]["irregular"], new["by_regularity"]["irregular"]
    checks = dict(
        overall_gap_mae_not_worse=bool(on["gap_mae_model"] <= ob["gap_mae_model"] + 1e-9),
        overall_gap_coverage_not_worse=bool(off(on["gap_coverage"]) <= off(ob["gap_coverage"]) + 0.01),
        overall_amount_error_not_worse=bool(on["amt_mape_model"] <= ob["amt_mape_model"] + 0.01),
        overall_amount_coverage_not_worse=bool(off(on["amt_coverage"]) <= off(ob["amt_coverage"]) + 0.01),
        irregular_improves_materially=bool(i_n["gap_mae_model"] <= ib["gap_mae_model"] - 0.25 or off(i_n["gap_coverage"]) <= off(ib["gap_coverage"]) - 0.02),  # a rounding-error gain does not count
    )
    adopted = all(checks.values())
    res.update(adopted=adopted, checks=checks,
               description="Adds sender-regularity features (gap variation over the last 6 transfers, longest recent gap, gap trend) and "
                           "calibrates the range separately for senders who look regular / semi-regular / irregular in their own history.",
               reason=("Adopted: overall error and coverage are no worse and irregular senders improve materially (0.25 days of error or 2 points of coverage)." if adopted else
                       "Not adopted: " + ", ".join(k.replace("_", " ") for k, v in checks.items() if not v) + " failed. The original forecaster is kept."))
    return res


def _adapted(rows: pd.DataFrame, P: pd.DataFrame, alpha: float, shrink: float) -> pd.DataFrame:
    """Apply the online correction row by row, using only transfers that had already happened."""
    out = P.copy()
    for hid, g in rows.groupby("household_id"):
        g = g.sort_values("seq")
        idx = list(g.index)
        err_pred, err_act = [], []
        for j, i in enumerate(idx):
            b = forecast.adaptive_bias(err_pred, err_act, alpha, shrink)
            for c in ("gap_p10", "gap_p50", "gap_p90"):
                out.loc[i, c] = max(P.loc[i, c] + b, 1.0)
            err_pred.append(float(P.loc[i, "gap_p50"]))
            err_act.append(float(g.loc[i, "target_gap"]))
    return out


def adaptive_experiment(ca, P_ca, te, P_te, h_test) -> dict:
    """Does a per-household online bias correction help? Parameters are picked on calibration households only."""
    grid = [(a, k) for a in (0.3, 0.5, 0.7) for k in (1.0, 2.0, 4.0)]
    cal_mae = {g: float(np.abs(_adapted(ca, P_ca, *g).gap_p50 - ca.target_gap).mean()) for g in grid}
    alpha, shrink = min(grid, key=cal_mae.get)
    after = _adapted(te, P_te, alpha, shrink)
    before_m = forecast_metrics(te, P_te, h_test)
    after_m = forecast_metrics(te, after, h_test)
    ob, oa = before_m["overall"], after_m["overall"]
    off = lambda x: abs(x - config.INTERVAL_COVERAGE)
    helps = bool(oa["gap_mae_model"] <= ob["gap_mae_model"] - 0.05 and off(oa["gap_coverage"]) <= off(ob["gap_coverage"]) + 0.01)
    pick = lambda m: {k: dict(gap_mae=v["gap_mae_model"], gap_coverage=v["gap_coverage"]) for k, v in m["by_group"]["regularity"].items()}
    return dict(adopted=helps, alpha=alpha, shrink=shrink, cap=10.0,
                before=dict(gap_mae=ob["gap_mae_model"], gap_coverage=ob["gap_coverage"], by_regularity=pick(before_m)),
                after=dict(gap_mae=oa["gap_mae_model"], gap_coverage=oa["gap_coverage"], by_regularity=pick(after_m)),
                reason=("Adopted: lower timing error and coverage no worse." if helps else "Not adopted: no meaningful gain (needs 0.05 days lower error with coverage no worse)."),
                description="Each household's recent forecast errors (how much later or earlier its transfers came than predicted) nudge its next forecast: an exponentially weighted correction, shrunk while history is short, capped at 10 days. Parameters chosen on calibration households.")


def sequence_experiment(tr, ca, te, h_test, fc_base, fc_temporal) -> dict:
    """Does a temporal model beat the current LightGBM? Variants share the same households and metrics.
    1) LightGBM + lag/rolling features (same quantile + conformal recipe)   2) small neural net over the last 6 gaps and 3 amounts."""
    from sklearn.neural_network import MLPRegressor
    from sklearn.preprocessing import StandardScaler
    lag_cols = [f"lag_gap_{i}" for i in range(1, forecast.N_LAGS + 1)] + [f"lag_logamt_{i}" for i in range(1, 4)]
    scaler = StandardScaler().fit(tr[lag_cols])
    def fit(y):
        m = MLPRegressor(hidden_layer_sizes=(32, 16), activation="relu", early_stopping=True, validation_fraction=0.15, n_iter_no_change=15,
                         max_iter=400, alpha=1e-3, random_state=config.SEED)
        return m.fit(scaler.transform(tr[lag_cols]), y)
    m_gap, m_amt = fit(tr.target_gap.to_numpy()), fit(np.log(tr.target_amt.to_numpy()))
    def predict(d):
        X = scaler.transform(d[lag_cols])
        return np.maximum(m_gap.predict(X), 1.0), np.exp(m_amt.predict(X))
    gc, ac = predict(ca)
    q = config.INTERVAL_COVERAGE  # split-conformal symmetric intervals from calibration residuals
    qg = float(np.quantile(np.abs(ca.target_gap.to_numpy() - gc), q))
    qa = float(np.quantile(np.abs(np.log(ca.target_amt.to_numpy()) - np.log(ac)), q))
    gt, at = predict(te)
    P_mlp = pd.DataFrame(dict(gap_p10=np.maximum(gt - qg, 1.0), gap_p50=gt, gap_p90=gt + qg,
                              amt_p10=at * np.exp(-qa), amt_p50=at, amt_p90=at * np.exp(qa)), index=te.index)
    out = {}
    for name, P in (("baseline", fc_base.predict(te)), ("lightgbm_temporal", fc_temporal.predict(te)), ("mlp_sequence", P_mlp)):
        m = forecast_metrics(te, P, h_test)
        out[name] = dict(overall=m["overall"], by_regularity=m["by_group"]["regularity"])
    off = lambda x: abs(x - config.INTERVAL_COVERAGE)
    b = out["baseline"]["overall"]
    verdicts = {}
    for name in ("lightgbm_temporal", "mlp_sequence"):
        o = out[name]["overall"]
        wins = bool(o["gap_mae_model"] <= b["gap_mae_model"] - 0.15 and o["amt_mape_model"] <= b["amt_mape_model"] + 0.01
                    and off(o["gap_coverage"]) <= off(b["gap_coverage"]) + 0.01 and off(o["amt_coverage"]) <= off(b["amt_coverage"]) + 0.01)
        verdicts[name] = dict(wins=wins, gap_mae_change=round(o["gap_mae_model"] - b["gap_mae_model"], 3),
                              amt_mape_change=round(o["amt_mape_model"] - b["amt_mape_model"], 4))
    winner = "lightgbm_temporal" if verdicts["lightgbm_temporal"]["wins"] else None  # only this variant can replace the live model
    out.update(verdicts=verdicts, winner=winner, adopted=winner is not None,
               description="Tried a temporal variant of LightGBM (last 6 gaps, last 3 amounts, fast and slow moving averages) and a small neural network over the last 6 gaps and 3 amounts. Same test households, same metrics. A variant replaces the current model only if timing error is at least 0.15 days lower with amount error and coverage no worse.",
               reason=("The temporal LightGBM won and is now the live model." if winner else
                       "Neither temporal variant beat the current model, so LightGBM with the original features stays. Short, noisy transfer histories give sequence models little extra signal."))
    return out


def live_model_summary(te, h_test, fc_base, fc_live, feats, use_irregular, use_temporal, exp, seq_exp) -> dict:
    """What the model that actually serves the app looks like, measured against the original baseline."""
    def block(fc):
        m = forecast_metrics(te, fc.predict(te), h_test)
        o = m["overall"]
        g = m["by_group"]["regularity"]
        return dict(gap_mae=o["gap_mae_model"], gap_coverage=o["gap_coverage"], amt_mape=o["amt_mape_model"], amt_coverage=o["amt_coverage"],
                    by_regularity={k: dict(gap_mae=v["gap_mae_model"], gap_coverage=v["gap_coverage"]) for k, v in g.items()})
    parts = ["LightGBM quantile model with conformal calibration"]
    if use_irregular:
        parts.append("sender-regularity features and group-wise calibration" + ("" if exp["adopted"] else " (enabled by team decision; the offline rule did not require it)"))
    if use_temporal:
        parts.append("lag and rolling features" + ("" if seq_exp["adopted"] else " (enabled by team decision; the offline rule did not require it)"))
    return dict(description="; ".join(parts), n_features=len(feats), group_calibration=bool(use_irregular), temporal_features=bool(use_temporal),
                baseline=block(fc_base), live=block(fc_live))


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
