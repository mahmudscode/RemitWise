"""End-to-end build: simulate -> store -> train -> forecast table -> evaluate -> data card.

Run:  python -m app.pipeline
"""
from __future__ import annotations

import json
import time

import pandas as pd

from . import bills as billslib, config, db, evaluation, forecast, sim, simulator


def run():
    t0 = time.time()
    print("1/6 generating synthetic data ...")
    h, r, l, bdefs, bsched = simulator.generate_dataset()
    bsched = billslib.annotate(bsched, bdefs)
    bmaps = evaluation._bills_maps(h, bdefs, bsched)
    ds = forecast.build_dataset(h, r)
    ds["split"] = ds["household_id"].map(h.set_index("household_id")["split"])
    tr, ca, te = (ds[ds.split == s] for s in ("train", "cal", "test"))
    print(f"   households={len(h)} remittances={len(r)} ledger_rows={len(l)} "
          f"train/cal/test rows={len(tr)}/{len(ca)}/{len(te)}")

    print("2/6 training forecaster (LightGBM quantile + conformal) ...")
    fc_base = forecast.Forecaster().fit(tr, ca)
    fc_feat = forecast.Forecaster(forecast.ALL_FEATURES).fit(tr, ca)
    fc_new = forecast.Forecaster(forecast.ALL_FEATURES, group_conformal=True).fit(tr, ca)
    exp = evaluation.irregular_experiment(te, h[h.split == "test"].reset_index(drop=True),
                                          {"baseline": fc_base, "regularity_features": fc_feat, "regularity_features_group_calibration": fc_new})
    fc = fc_new if exp["adopted"] else fc_base  # keep the change only if it does not hurt overall and helps irregular senders
    fc_temporal = forecast.Forecaster(forecast.FEATURES + forecast.LAG_FEATURES).fit(tr, ca)
    seq_exp = evaluation.sequence_experiment(tr, ca, te, h[h.split == "test"].reset_index(drop=True), fc, fc_temporal)
    for k in ("lightgbm_temporal", "mlp_sequence"):
        v = seq_exp["verdicts"][k]
        print(f"   sequence experiment {k}: gap MAE change {v['gap_mae_change']:+.2f} days, amount error change {v['amt_mape_change']:+.3f}, wins={v['wins']}")
    if seq_exp["adopted"]:
        fc = fc_temporal
    print(f"   irregular-sender experiment: {exp['reason']}")
    fc.save()
    P_ca = fc.predict(ca)
    P_all = fc.predict(ds)
    P_all["household_id"] = ds["household_id"].to_numpy()
    P_all["seq"] = ds["seq"].to_numpy()
    P_all["day"] = ds["day"].to_numpy()
    P_te = P_all.loc[te.index]

    print("3/6 storing data in database ...")
    db.init_db()
    db.write_frame(h, "households")
    db.write_frame(r, "remittances")
    db.write_frame(l, "ledger", index_cols=["household_id", "day"])
    db.write_frame(bdefs, "bill_defs", index_cols=["household_id"])
    db.write_frame(bsched, "bill_schedule", index_cols=["household_id", "due_day"])
    feat = ds[["household_id", "seq"] + forecast.STORED_FEATURES]
    db.write_frame(feat, "forecast_features", index_cols=["household_id", "seq"])
    db.write_frame(P_all, "forecasts", index_cols=["household_id", "seq"])

    print("4/6 forecast metrics (clean test households) ...")
    fm = evaluation.forecast_metrics(te, P_te, h[h.split == "test"].reset_index(drop=True))

    adaptive = evaluation.adaptive_experiment(ca, P_ca, te, P_te, h[h.split == "test"].reset_index(drop=True))
    print(f"   adaptive household correction: before MAE {adaptive['before']['gap_mae']:.2f} -> after {adaptive['after']['gap_mae']:.2f} days; {adaptive['reason']}")

    print("5/6 policy comparison (simulated year, with vs without) ...")
    cmp_ = evaluation.compare_policies(h, r, l, te, P_te, bmaps)

    print("6/6 warning quality ...")
    wm = evaluation.warning_metrics(h, r, l, ds, P_all, bmaps)
    b, a = wm["before"], wm["after"]
    print(f"   warning threshold before {b['threshold']}: precision {b['precision']} recall {b['recall']} f1 {b['f1']} lead {b['mean_lead_days']}d")
    mo = wm["model_only"]
    print(f"   model only  {mo['threshold']}: precision {mo['precision']} recall {mo['recall']} f1 {mo['f1']} lead {mo['mean_lead_days']}d")
    print(f"   warning threshold after  {a['threshold']}: precision {a['precision']} recall {a['recall']} f1 {a['f1']} lead {a['mean_lead_days']}d")
    print(f"   simple rule: precision {wm['threshold_only_rule']['precision']} recall {wm['threshold_only_rule']['recall']}")
    st_ = evaluation.stress_test(h, r, l, te, P_te, P_all, bmaps, wm["threshold"])
    print(f"   stress: warning recall normal {st_['warning']['normal']['recall']} vs shock {st_['warning']['shock']['recall']}; gap coverage {st_['forecast']['normal']['gap_coverage']} vs {st_['forecast']['shock']['gap_coverage']}")
    bm = evaluation.bill_metrics(h, bsched, bdefs)
    fs = evaluation.forecast_samples(te, P_te)

    report = dict(
        dataset=dict(households=len(h), remittances=len(r), ledger_rows=len(l), seed=config.SEED,
                     split_by="household", split_counts=h.split.value_counts().to_dict(),
                     start_date=config.START_DATE, days=config.N_DAYS),
        forecast=dict(fm, samples=fs), warning=wm, stress=st_, irregular_experiment=exp, sequence_experiment=seq_exp, adaptive=adaptive, kpi_base=evaluation.kpi_base(h, bdefs), bills=bm,
        compare=dict(summary=cmp_["summary"], by_class=cmp_["by_class"], n_households=cmp_["n_households"],
                     horizon_days=cmp_["horizon_days"], metrics=cmp_["metrics"]),
        conformal=fc.conf,
        generated_at=pd.Timestamp.now().isoformat(timespec="seconds"),
    )
    (config.ARTIFACTS / "evaluation.json").write_text(json.dumps(report, indent=2, default=float))
    (config.ARTIFACTS / "compare_per_household.json").write_text(json.dumps(cmp_["per_household"], default=float))
    write_data_card(h, r)
    print(f"done in {time.time() - t0:.0f}s -> {config.ARTIFACTS}")
    return report


def write_data_card(h, r):
    txt = f"""# Data card — RemitWise synthetic data

*Generated by `python -m app.pipeline`. Synthetic and self-generated. No real PII. All parameters below are ASSUMPTIONS.*

- Seed: {config.SEED}; households: {len(h)}; remittance events: {len(r)}; window: {config.START_DATE} + {config.N_DAYS} days.
- Split **by household**: {h.split.value_counts().to_dict()}. The `test` households are never used for training, calibration, or threshold tuning.
- Regularity classes (not a model feature; used only for fairness cuts): {h.regularity_class.value_counts().to_dict()}.

## Assumptions
- Gap between transfers: regular 28-32 days (sd 2.5); semi 26-34 (sd 7); irregular 22-50 (sd 14). Delayed cycles add 5-25 days (p = 0.05 / 0.12 / 0.22).
- Amount: lognormal around a household typical value (median 28,000 BDT, clipped 8,000-90,000); log-sd 0.08 / 0.20 / 0.45. 40% of irregular senders send small transfers (x0.5): this is the fairness cohort.
- Festivals: transfers before Eid are earlier (p = 0.6) and 1.2-1.5x larger; spending spikes around Eid (+100% essentials for 11 days).
- Total needs = 55-78% of average income. Bills & EMIs are carved out of that total: electricity (variable, seasonal: x1.35-1.6 in Apr-Sep, x0.8 in winter), gas, internet (60% of households), motorcycle EMI (40%), school fees (households with children). Due days are fixed per household. ~4% of electricity bills are unusually high (x2.0-3.2): planted anomalies with ground truth.
- Remaining essentials: weekday rhythm, lognormal noise, split into categories by a per-household Dirichlet share. ~35%/year chance of a large one-off expense (0.5-1.5x monthly needs, categorised as health).
- Bill estimate = seasonal-naive / trailing-median rule (not a deep model). An anomaly is flagged when a bill exceeds 1.8x its estimate. Late fee = 3% of the bill (min 100).
- Baseline behaviour: 75-100% of each transfer is cashed out soon after arrival; money in hand above a 5-day cushion is spent down at ~1-3% per day ("cash-in-hand effect").
- Informal credit covers shortfalls and is repaid at 1.05x on the next arrival.
- Following a plan removes the cash-in-hand effect; needs money is held in the wallet and released weekly. Bills are paid on time from a vault funded at each transfer; without a plan they are paid on the due date only if cash is in hand, otherwise late with a fee. Flagged bills are assumed to be reviewed and corrected before the due date.

## Known limitations
- Behaviour change under RemitWise is an ASSUMPTION controlled by the compliance level; it is not evidence of a real-world effect.
- Real remittance patterns, exchange-rate shocks and family dynamics may differ.
"""
    (config.ARTIFACTS / "data_card.md").write_text(txt)


if __name__ == "__main__":
    run()
