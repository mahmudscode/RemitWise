"""Inflow forecaster: LightGBM quantile models + conformal calibration (doc 06-A).

Forecast is made at the moment a remittance arrives, for the NEXT remittance
(gap in days, amount). Output is a range (P10/P50/P90), never a single number.
"""
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from . import config
from .simulator import EID_DATES

QUANTILES = (0.1, 0.5, 0.9)
FEATURES = [
    "last_gap", "gap_mean3", "gap_mean_all", "gap_std_all", "gap_cv", "late_rate",
    "last_amt", "amt_mean3", "amt_mean_all", "amt_cv",
    "dom", "month", "days_to_eid", "eid_within_30", "n_events",
    "local_income_monthly", "size", "is_rural",
]
# Sender-regularity features added by the irregular-sender experiment (Task 15)
REGULARITY_FEATURES = ["gap_cv6", "max_gap6", "gap_trend6"]
ALL_FEATURES = FEATURES + REGULARITY_FEATURES
MODEL_PATH = config.ARTIFACTS / "forecaster.joblib"


def _days_to_eid(ts: pd.Timestamp) -> float:
    later = EID_DATES[EID_DATES >= ts]
    return float((later[0] - ts).days) if len(later) else 400.0


def row_features(hist: pd.DataFrame, hh: pd.Series) -> dict:
    """Features from the remittance history up to and including the current arrival.
    `hist` columns: date, amount (sorted)."""
    amounts = hist["amount"].to_numpy(dtype=float)
    dates = pd.to_datetime(hist["date"]).reset_index(drop=True)
    gaps = np.diff(dates.values).astype("timedelta64[D]").astype(float) if len(dates) > 1 else np.array([30.0])
    # Treat tiny top-up transfers separately: gaps use all events (model learns this noise).
    cur = dates.iloc[-1]
    med = np.median(gaps)
    g6 = gaps[-6:]
    trend = float(np.polyfit(np.arange(len(g6)), g6, 1)[0]) if len(g6) >= 3 else 0.0
    return dict(
        gap_cv6=float(g6.std() / g6.mean()) if len(g6) > 1 and g6.mean() > 0 else 0.0,
        max_gap6=float(g6.max()), gap_trend6=trend,
        last_gap=gaps[-1], gap_mean3=gaps[-3:].mean(), gap_mean_all=gaps.mean(),
        gap_std_all=gaps.std() if len(gaps) > 1 else 0.0,
        gap_cv=(gaps.std() / gaps.mean()) if len(gaps) > 1 else 0.0,
        late_rate=float((gaps > 1.3 * med).mean()),
        last_amt=amounts[-1], amt_mean3=amounts[-3:].mean(), amt_mean_all=amounts.mean(),
        amt_cv=(amounts.std() / amounts.mean()) if len(amounts) > 1 else 0.0,
        dom=cur.day, month=cur.month, days_to_eid=_days_to_eid(cur),
        eid_within_30=float(_days_to_eid(cur) <= 30), n_events=len(amounts),
        local_income_monthly=float(hh["local_income_monthly"]), size=float(hh["size"]),
        is_rural=float(hh["region"] == "rural"),
    )


def build_dataset(households: pd.DataFrame, remittances: pd.DataFrame, min_hist: int = 4) -> pd.DataFrame:
    """One row per (household, arrival k): features from events[:k+1], targets from event k+1."""
    hh_idx = households.set_index("household_id")
    rows = []
    for hid, ev in remittances.groupby("household_id"):
        ev = ev.sort_values("seq").reset_index(drop=True)
        for k in range(min_hist - 1, len(ev) - 1):
            f = row_features(ev.iloc[: k + 1], hh_idx.loc[hid])
            f.update(household_id=hid, seq=int(ev.loc[k, "seq"]), day=int(ev.loc[k, "day"]),
                     target_gap=float(ev.loc[k + 1, "day"] - ev.loc[k, "day"]),
                     target_amt=float(ev.loc[k + 1, "amount"]),
                     amount_now=float(ev.loc[k, "amount"]))
            rows.append(f)
    return pd.DataFrame(rows)


class Forecaster:
    """`features` selects the inputs; `group_conformal` calibrates the range separately for senders who look
    regular / semi-regular / irregular IN THEIR HISTORY (from gap_cv: never the hidden simulation label)."""

    def __init__(self, features: list[str] | None = None, group_conformal: bool = False):
        self.features = list(features or FEATURES)
        self.group_conformal = group_conformal
        self.models: dict[str, dict[float, LGBMRegressor]] = {}
        self.conf: dict[str, float] = {}  # conformal widening per target
        self.conf_group: dict[str, list[float]] = {}
        self.cv_edges: list[float] = []

    def _fit_quantiles(self, X, y):
        out = {}
        for q in QUANTILES:
            m = LGBMRegressor(objective="quantile", alpha=q, n_estimators=250, learning_rate=0.04,
                              num_leaves=12, min_child_samples=25, subsample=0.8, subsample_freq=1,
                              colsample_bytree=0.9, random_state=config.SEED, verbose=-1)
            m.fit(X, y)
            out[q] = m
        return out

    def _raw(self, tgt, X):
        P = np.column_stack([self.models[tgt][q].predict(X) for q in QUANTILES])
        return np.sort(P, axis=1)

    def _group(self, X) -> np.ndarray:
        return np.digitize(X["gap_cv"].to_numpy(float), self.cv_edges)

    def fit(self, train: pd.DataFrame, cal: pd.DataFrame):
        Xt, Xc = train[self.features], cal[self.features]
        self.models["gap"] = self._fit_quantiles(Xt, train["target_gap"])
        self.models["amt"] = self._fit_quantiles(Xt, np.log(train["target_amt"]))
        self.cv_edges = [float(x) for x in np.quantile(train["gap_cv"], [1 / 3, 2 / 3])]
        grp = self._group(cal)
        # conformalized quantile regression (CQR) on the calibration households
        for tgt, y in (("gap", cal["target_gap"].to_numpy()), ("amt", np.log(cal["target_amt"].to_numpy()))):
            P = self._raw(tgt, Xc)
            score = np.maximum(P[:, 0] - y, y - P[:, 2])
            def widen(sc):
                level = min(1.0, np.ceil((len(sc) + 1) * config.INTERVAL_COVERAGE) / len(sc))
                return float(np.quantile(sc, level))
            self.conf[tgt] = widen(score)
            self.conf_group[tgt] = [widen(score[grp == g]) if (grp == g).sum() >= 40 else self.conf[tgt] for g in range(3)]
        return self

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        feats = getattr(self, "features", FEATURES)
        Xf = X[feats]
        G = self._raw("gap", Xf)
        A = self._raw("amt", Xf)
        if getattr(self, "group_conformal", False):
            grp = self._group(X)
            cg = np.array(self.conf_group["gap"])[grp]
            ca = np.array(self.conf_group["amt"])[grp]
        else:
            cg, ca = self.conf["gap"], self.conf["amt"]
        G = np.column_stack([np.maximum(G[:, 0] - cg, 1.0), G[:, 1], G[:, 2] + cg])
        A = np.exp(np.column_stack([A[:, 0] - ca, A[:, 1], A[:, 2] + ca]))
        return pd.DataFrame(dict(gap_p10=G[:, 0], gap_p50=G[:, 1], gap_p90=G[:, 2],
                                 amt_p10=A[:, 0], amt_p50=A[:, 1], amt_p90=A[:, 2]), index=X.index)

    def drivers(self, X: pd.DataFrame, top: int = 3) -> list[dict]:
        """Local feature contributions (LightGBM SHAP-style) for the median gap model; one row."""
        feats = getattr(self, "features", FEATURES)
        m = self.models["gap"][0.5]
        contrib = m.predict(X[feats], pred_contrib=True)[0][:-1]
        order = np.argsort(-np.abs(contrib))[:top]
        return [dict(feature=feats[i], value=float(X[feats].iloc[0, i]),
                     effect_days=float(contrib[i])) for i in order]

    def save(self, path=MODEL_PATH):
        joblib.dump(self, path)

    @staticmethod
    def load(path=MODEL_PATH) -> "Forecaster":
        return joblib.load(path)


def naive_forecast(X: pd.DataFrame) -> pd.DataFrame:
    """Baseline: 'same as last time'."""
    return pd.DataFrame(dict(gap=X["last_gap"].to_numpy(), amt=X["last_amt"].to_numpy()), index=X.index)


def remaining_forecast(fc: dict, days_since: float) -> dict:
    """Condition an at-arrival forecast on days already elapsed (documented heuristic).

    When the transfer is overdue (past the median), the interval is widened rather than
    pretending the original forecast still holds.
    """
    p10, p50, p90 = fc["gap_p10"], fc["gap_p50"], fc["gap_p90"]
    d = float(days_since)
    if d <= p50:
        r10, r50, r90 = max(p10 - d, 1.0), max(p50 - d, 1.0), max(p90 - d, 2.0)
        overdue = False
    else:
        base = max(p90 - d, 1.0)
        r10, r50, r90 = 1.0, base + 1.0, base + 0.5 * (p90 - p10) + 3.0
        overdue = True
    r10, r50, r90 = sorted([r10, r50, r90])
    return dict(rem_p10=r10, rem_p50=r50, rem_p90=r90, overdue=overdue)
