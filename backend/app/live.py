"""Live demo engine: a stateful, deterministic replay of one household (doc 05 / 12).

The family can accept / edit / skip every plan; nothing executes automatically.
Mirrors the policy rules of sim.py so the demo and the offline evaluation agree.
"""
from __future__ import annotations

import copy

import numpy as np
import pandas as pd

from . import allocator, config, db, forecast, risk, sim
from .db import DemoState, Goal as GoalRow, SessionLocal

DEMO_START_SEQ = 3


class Engine:
    def __init__(self):
        self.h = db.read_sql("SELECT * FROM households").set_index("household_id")
        self.ev = {k: v.sort_values("seq").reset_index(drop=True)
                   for k, v in db.read_sql("SELECT * FROM remittances").groupby("household_id")}
        self.led = {}  # filled for the demo households only (keeps memory small on free hosts)
        fc = db.read_sql("SELECT * FROM forecasts")
        self.fc = {k: {int(r["seq"]): r for r in v.to_dict("records")} for k, v in fc.groupby("household_id")}
        ff = db.read_sql("SELECT * FROM forecast_features")
        self.ff = {k: {int(r["seq"]): r for r in v.to_dict("records")} for k, v in ff.groupby("household_id")}
        self.model = forecast.Forecaster.load()
        self._start = {}
        self.demo_ids = self._pick_demo()
        ids = ",".join(f"'{i}'" for i in self.demo_ids)
        led = db.read_sql(f"SELECT * FROM ledger WHERE household_id IN ({ids})")
        self.led = {k: v.sort_values("day").reset_index(drop=True) for k, v in led.groupby("household_id")}

    def start_seq(self, hid: str) -> int:
        """First arrival (seq >= 3) that is a normal-sized transfer, so the demo starts on a main remittance."""
        if hid not in self._start:
            ev, typ = self.ev[hid], float(self.h.loc[hid, "typical_amount"])
            ok = ev[(ev.seq >= DEMO_START_SEQ) & (ev.amount >= 0.6 * typ)]
            ok = ok[ok.seq.isin(self.fc.get(hid, {}).keys())]
            self._start[hid] = int(ok.seq.iloc[0]) if len(ok) else DEMO_START_SEQ
        return self._start[hid]

    def _pick_demo(self):
        t = self.h[self.h.split == "test"]
        out = {}
        for cls, name in (("semi", "Rahima"), ("regular", "Salma"), ("irregular", "Nasrin")):
            sub = t[t.regularity_class == cls]
            # prefer a household with local income so the story is richer, and enough events
            sub = sub[sub.index.map(lambda i: len(self.ev[i]) >= 18)]
            if len(sub):
                ratio = sub.monthly_needs / (sub.typical_amount * 30 / sub.gap_mean + sub.local_income_monthly)
                out[ratio.idxmin()] = name
        return out

    # ---------- state ----------
    def _fresh(self, hid: str) -> dict:
        ev = self.ev[hid]
        k = self.start_seq(hid)
        start_day = int(ev.loc[ev.seq == k, "day"].iloc[0])
        ess = self.led[hid]["essential"].to_numpy()
        return dict(day=start_day - 1, spendable=float(ess[start_day:start_day + 10].sum()), buffer=0.0,
                    goals={}, debt=0.0, shortfall_days=0, last_arrival_day=int(ev.loc[ev.seq == k - 1, "day"].iloc[0]),
                    last_seq=k - 1, pending=None, adherent=False, overrides={}, extra_income=0.0,
                    need_mult=1.0, history=[], log=[], sender_intent=None, retained_amt=0.0, total_amt=0.0,
                    cycle_forecast=None)

    def get(self, hid: str) -> dict:
        with SessionLocal() as s:
            row = s.get(DemoState, hid)
            if row:
                return copy.deepcopy(row.state)
        st = self._fresh(hid)
        self.save(hid, st)
        self._seed_goals(hid)
        return st

    def save(self, hid: str, st: dict):
        with SessionLocal() as s:
            row = s.get(DemoState, hid)
            if row:
                row.state = st
                row.updated_at = db.now()
            else:
                s.add(DemoState(household_id=hid, state=st))
            s.commit()

    def reset(self, hid: str) -> dict:
        with SessionLocal() as s:
            s.query(GoalRow).filter(GoalRow.household_id == hid).delete()
            s.query(DemoState).filter(DemoState.household_id == hid).delete()
            s.commit()
        return self.get(hid)

    def _seed_goals(self, hid: str):
        start = self.get_start_day(hid)
        mn = float(self.h.loc[hid, "monthly_needs"])
        with SessionLocal() as s:
            if s.query(GoalRow).filter(GoalRow.household_id == hid).count() == 0:
                s.add(GoalRow(household_id=hid, name="School fees", target=round(mn * 1.2, -2),
                              deadline_day=start + 150, priority=1))
                s.add(GoalRow(household_id=hid, name="Home repair", target=round(mn * 3.0, -2),
                              deadline_day=start + 360, priority=2))
                s.commit()

    def get_start_day(self, hid: str) -> int:
        ev = self.ev[hid]
        return int(ev.loc[ev.seq == self.start_seq(hid), "day"].iloc[0])

    # ---------- derived ----------
    def goals_list(self, hid: str, st: dict) -> list[allocator.Goal]:
        with SessionLocal() as s:
            rows = s.query(GoalRow).filter(GoalRow.household_id == hid).order_by(GoalRow.id).all()
        out = []
        for g in rows:
            out.append(allocator.Goal(id=str(g.id), name=g.name, target=g.target,
                                      current=float(st["goals"].get(str(g.id), 0.0)),
                                      days_left=max(g.deadline_day - st["day"], 14.0), priority=g.priority))
        return out

    def usual_needs(self, hid: str, st: dict):
        ess = self.led[hid]["essential"].to_numpy()
        mean_ess = float(ess[max(0, st["day"] - 60): st["day"] + 1].mean()) * st["need_mult"]
        local_daily = (float(self.h.loc[hid, "local_income_monthly"]) + st["extra_income"]) / 30.0
        return mean_ess, max(mean_ess - local_daily, 0.0), local_daily

    def arrival_forecast(self, hid: str, seq: int):
        """At-arrival forecast for the transfer after `seq` (None if history too short)."""
        r = self.fc.get(hid, {}).get(seq)
        if r is None:
            return None
        return {k: float(r[k]) for k in ("gap_p10", "gap_p50", "gap_p90", "amt_p10", "amt_p50", "amt_p90")}

    def current_forecast(self, hid: str, st: dict) -> dict | None:
        f = st.get("cycle_forecast") or self.arrival_forecast(hid, st["last_seq"])
        if f is None:
            return None
        f = dict(f)
        since = st["day"] - st["last_arrival_day"]
        rem = forecast.remaining_forecast(f, since)
        intent = st.get("sender_intent")
        if intent:  # sender-declared intent narrows the range (documented heuristic)
            gap = max(intent["day"] - st["day"], 1.0)
            mid = 0.5 * (rem["rem_p50"] + gap)
            half = 0.75 * 0.5 * (rem["rem_p90"] - rem["rem_p10"])
            rem = dict(rem_p10=max(mid - half, 1.0), rem_p50=mid, rem_p90=mid + half, overdue=rem["overdue"])
            f["amt_p50"] = 0.5 * (f["amt_p50"] + intent["amount"])
        out = dict(f)
        out.update(rem)
        out["days_since_arrival"] = since
        out["next_date_p10"] = _d(st["day"] + rem["rem_p10"])
        out["next_date_p50"] = _d(st["day"] + rem["rem_p50"])
        out["next_date_p90"] = _d(st["day"] + rem["rem_p90"])
        out["naive"] = dict(gap=float(self.ff[hid][st["last_seq"]]["last_gap"]),
                            amt=float(self.ff[hid][st["last_seq"]]["last_amt"])) if st["last_seq"] in self.ff.get(hid, {}) else None
        return out

    def shortfall(self, hid: str, st: dict, thr: float) -> dict:
        f = self.current_forecast(hid, st)
        if f is None:
            return dict(available=False)
        mean_ess, net, local_daily = self.usual_needs(hid, st)
        hist = st["history"][-7:]
        recent = float(np.mean([x["spent"] for x in hist])) if hist else mean_ess
        daily_mean = max(recent, mean_ess) if hist else mean_ess
        rem = dict(rem_p10=f["rem_p10"], rem_p50=f["rem_p50"], rem_p90=f["rem_p90"])
        # local income arrives daily, so projected net burn is spend minus income
        net_burn = max(daily_mean - local_daily, 1.0)
        res = risk.simulate_shortfall(st["spendable"], net_burn, 0.35, rem, reserve=st["buffer"], n=1000, seed=st["day"])
        led = self.led[hid]
        recent_shock = float(led["shock"].to_numpy()[max(0, st["day"] - 7): st["day"] + 1].sum())
        drv = risk.drivers(recent, mean_ess, st["spendable"] + st["buffer"], f["rem_p50"],
                           f["days_since_arrival"], f["gap_p50"], recent_shock)
        sev = risk.severity(res["prob"], thr)
        out = dict(available=True, **res, severity=sev, threshold=thr, drivers=drv,
                   suggestions=_suggest(sev, drv))
        return out

    # ---------- plan ----------
    def propose(self, hid: str, st: dict) -> list[dict]:
        p = st["pending"]
        if not p:
            return []
        f = self.arrival_forecast(hid, p["seq"])
        if f is None:
            return []
        if st.get("sender_intent"):
            pass
        mean_ess, net, _ = self.usual_needs(hid, st)
        rem = dict(rem_p10=f["gap_p10"], rem_p50=f["gap_p50"], rem_p90=f["gap_p90"])
        goals = self.goals_list(hid, st)
        out = []
        for style in allocator.STYLES:
            plan = allocator.propose(p["got"], rem, net, st["spendable"], st["buffer"], mean_ess * 30,
                                     goals, style, config.BUFFER_TARGET_MONTHS, float(self.h.loc[hid, "gap_mean"]))
            d = plan.to_dict()
            d["shortfall_prob"] = self.plan_risk(hid, st, plan.needs, rem)
            out.append(d)
        return out

    def plan_risk(self, hid: str, st: dict, needs: float, rem: dict) -> float:
        mean_ess, net, local_daily = self.usual_needs(hid, st)
        res = risk.simulate_shortfall(st["spendable"] + needs, max(net, 1.0), 0.35, rem,
                                      reserve=st["buffer"], n=800, seed=11)
        return round(res["prob"], 3)

    def decide(self, hid: str, st: dict, decision: str, plan: dict | None) -> dict:
        p = st["pending"]
        if not p:
            raise ValueError("no pending remittance")
        got = p["got"]
        if decision == "skip" or plan is None:
            st["spendable"] += got
            st["adherent"] = False
            st["retained_amt"] += p["amount"] * (1 - float(self.h.loc[hid, "cashout_frac"]))
        else:
            goals = {g.name: g.id for g in self.goals_list(hid, st)}
            plan_obj = allocator.custom_plan(got, plan["needs"], plan["savings"], plan.get("goals", {}))
            st["spendable"] += plan_obj.needs
            st["buffer"] += plan_obj.savings
            for name, amt in plan_obj.goals.items():
                gid = goals.get(name)
                if gid:
                    st["goals"][gid] = st["goals"].get(gid, 0.0) + amt
                else:
                    st["buffer"] += amt
            st["adherent"] = True
            mean_ess, _, _ = self.usual_needs(hid, st)
            first = min(plan_obj.needs, mean_ess * allocator.WALLET_RELEASE_DAYS)
            st["retained_amt"] += max(p["amount"] - first, 0.0)
        st["pending"] = None
        return st

    # ---------- time ----------
    def advance(self, hid: str, st: dict, days: int, to_arrival: bool = False) -> dict:
        led, ev = self.led[hid], self.ev[hid]
        ess, shock, inc = led["essential"].to_numpy(), led["shock"].to_numpy(), led["local_income"].to_numpy()
        leak = float(self.h.loc[hid, "leak_rate"])
        events = []
        # unresolved pending arrival is treated as "skipped" (family did not decide)
        if st["pending"]:
            st = self.decide(hid, st, "skip", None)
            events.append(dict(day=st["day"], type="auto_skip"))
        arrivals = {}
        for r in ev.itertuples():
            d = st["overrides"].get(str(r.seq), int(r.day))
            arrivals[d] = (int(r.seq), float(r.amount))
        steps = 0
        max_steps = 120 if to_arrival else days
        while steps < max_steps and st["day"] + 1 < len(led):
            st["day"] += 1
            d = st["day"]
            steps += 1
            if d in arrivals and arrivals[d][0] >= self.start_seq(hid):
                seq, amount = arrivals[d]
                a = sim.Account(spendable=st["spendable"], buffer=st["buffer"], goals=sum(st["goals"].values()),
                                debt=st["debt"])
                got = a.receive(amount)
                st["debt"] = a.debt
                st["spendable"] = a.spendable
                st["last_arrival_day"], st["last_seq"] = d, seq
                st["total_amt"] += amount
                st["cycle_forecast"] = self.arrival_forecast(hid, seq)
                st["sender_intent"] = None
                st["pending"] = dict(seq=seq, amount=amount, got=got, day=d, date=_d(d))
                st["adherent"] = False
                events.append(dict(day=d, type="arrival", amount=amount))
                # still apply today's spending after the family decides; stop here so the UI can show the plan
                st["day"] = d
                break
            need = (ess[d] + shock[d]) * st["need_mult"]
            if not st["adherent"]:
                excess = max(st["spendable"] + inc[d] + st["extra_income"] / 30.0 - sim.CUSHION_DAYS * ess[d], 0.0)
                need += leak * sim.CREEP_FACTOR * excess
            a = sim.Account(spendable=st["spendable"], buffer=st["buffer"], goals=0.0, debt=st["debt"])
            income = inc[d] + st["extra_income"] / 30.0
            short = a.spend_day(need, income)
            # goal raid only when buffer exhausted: draw proportionally
            if short and sum(st["goals"].values()) > 0:
                deficit = a.debt - st["debt"]
                tot = sum(st["goals"].values())
                raid = min(tot, deficit)
                if raid > 0:
                    for k in list(st["goals"]):
                        st["goals"][k] -= st["goals"][k] / tot * raid
                    a.debt -= raid
                    a.deficit_total -= raid
                    short = a.debt - st["debt"] > 0.5
                    events.append(dict(day=d, type="goal_used", amount=round(raid)))
            st["spendable"], st["buffer"], st["debt"] = a.spendable, a.buffer, a.debt
            if short:
                st["shortfall_days"] += 1
                events.append(dict(day=d, type="shortfall"))
            st["history"].append(dict(day=d, date=_d(d), spent=float(need), balance=float(st["spendable"] + st["buffer"]),
                                      short=bool(short)))
        st["history"] = st["history"][-120:]
        st["log"] = (st["log"] + events)[-40:]
        return st

    def scenario(self, hid: str, st: dict, kind: str, value: float) -> dict:
        if kind == "delay":
            seq = st["last_seq"] + 1
            ev = self.ev[hid]
            cur = st["overrides"].get(str(seq), int(ev.loc[ev.seq == seq, "day"].iloc[0]))
            st["overrides"][str(seq)] = int(cur + value)
        elif kind == "expense":
            a = sim.Account(spendable=st["spendable"], buffer=st["buffer"], debt=st["debt"])
            a.spend_day(value, 0.0)
            st["spendable"], st["buffer"], st["debt"] = a.spendable, a.buffer, a.debt
            st["log"].append(dict(day=st["day"], type="large_expense", amount=value))
        elif kind == "second_income":
            st["extra_income"] += value
        elif kind == "family_member":
            st["need_mult"] *= 1.0 + value
        else:
            raise ValueError("unknown scenario")
        return st


def _d(day: float) -> str:
    return (pd.Timestamp(config.START_DATE) + pd.Timedelta(days=int(round(day)))).strftime("%Y-%m-%d")


def _suggest(sev: str, drivers: list[dict]) -> list[str]:
    if sev == "green":
        return []
    s = ["Delay non-essential spending for a few days.", "Consider using your emergency buffer only for essentials."]
    if any(d["factor"] == "late_transfer" for d in drivers):
        s.append("Ask your sender whether the transfer date has changed.")
    return s[:2] if sev == "amber" else s
