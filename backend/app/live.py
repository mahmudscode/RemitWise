"""Live demo engine: a stateful, deterministic replay of one household (doc 05 / 12 / 20).

The family can accept / edit / skip every plan; nothing executes automatically except bills the
family has switched on (auto-pay mandates). Unusual bills and bills over the family's limit always
wait for the family. Mirrors the policy rules of sim.py so the demo and the offline evaluation agree.
"""
from __future__ import annotations

import copy

import numpy as np
import pandas as pd

from . import allocator, bills as billslib, config, db, forecast, risk, sim
from .db import DemoState, Goal as GoalRow, SessionLocal

DEMO_START_SEQ = 3
GRACE_DAYS = {"due": 2, "needs_review": 5}  # days after the due date before an unresolved bill becomes overdue
BILLED_DAYS_BEFORE = 5  # a variable bill's real amount is known this many days before it is due
CATS = ("food", "transport", "education", "health", "other")


def _d(day: float) -> str:
    return (pd.Timestamp(config.START_DATE) + pd.Timedelta(days=int(round(day)))).strftime("%Y-%m-%d")


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
        self.bdefs = {k: v.reset_index(drop=True) for k, v in
                      db.read_sql(f"SELECT * FROM bill_defs WHERE household_id IN ({ids})").groupby("household_id")}
        self.bsched = {k: v.sort_values("due_day").reset_index(drop=True) for k, v in
                       db.read_sql(f"SELECT * FROM bill_schedule WHERE household_id IN ({ids})").groupby("household_id")}

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
        cfg = {r.bill_id: dict(autopay=True, monthly_limit=float(r.monthly_limit), confirm_over_limit=True, active=True)
               for r in self.bdefs[hid].itertuples()}
        return dict(day=start_day - 1, spendable=float(ess[start_day:start_day + 10].sum()), buffer=0.0, vault=0.0,
                    goals={}, debt=0.0, shortfall_days=0, last_arrival_day=int(ev.loc[ev.seq == k - 1, "day"].iloc[0]),
                    last_seq=k - 1, pending=None, adherent=False, overrides={}, extra_income=0.0,
                    need_mult=1.0, history=[], log=[], sender_intent=None, retained_amt=0.0, total_amt=0.0,
                    cycle_forecast=None, bill_cfg=cfg, mandates=[], bills={}, bill_override={}, paid_log=[],
                    bills_due=0, bills_on_time=0, late_fees=0.0, fees_avoided=0.0, overbilling_avoided=0.0,
                    anomalies_caught=0, contrib={}, sender_ask=False)

    def _upgrade(self, hid: str, st: dict) -> dict:
        fresh = self._fresh(hid)
        for k, v in fresh.items():
            st.setdefault(k, v)
        return st

    def get(self, hid: str) -> dict:
        with SessionLocal() as s:
            row = s.get(DemoState, hid)
            if row:
                return self._upgrade(hid, copy.deepcopy(row.state))
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
                s.add(GoalRow(household_id=hid, name="House repair", target=round(mn * 3.0, -2),
                              deadline_day=start + 360, priority=2))
                s.add(GoalRow(household_id=hid, name="Education fund", target=round(mn * 1.2, -2),
                              deadline_day=start + 150, priority=1))
                s.commit()

    def get_start_day(self, hid: str) -> int:
        ev = self.ev[hid]
        return int(ev.loc[ev.seq == self.start_seq(hid), "day"].iloc[0])

    # ---------- derived ----------
    def goals_list(self, hid: str, st: dict) -> list[allocator.Goal]:
        with SessionLocal() as s:
            rows = s.query(GoalRow).filter(GoalRow.household_id == hid).order_by(GoalRow.id).all()
        return [allocator.Goal(id=str(g.id), name=g.name, target=g.target,
                               current=float(st["goals"].get(str(g.id), 0.0)),
                               days_left=max(g.deadline_day - st["day"], 14.0), priority=g.priority) for g in rows]

    def usual_needs(self, hid: str, st: dict):
        ess = self.led[hid]["essential"].to_numpy()
        mean_ess = float(ess[max(0, st["day"] - 60): st["day"] + 1].mean()) * st["need_mult"]
        local_daily = (float(self.h.loc[hid, "local_income_monthly"]) + st["extra_income"]) / 30.0
        return mean_ess, max(mean_ess - local_daily, 0.0), local_daily

    def bills_monthly(self, hid: str, st: dict) -> float:
        tot = float(self.h.loc[hid, "bills_monthly"])
        return tot + sum(m["usual"] for m in st["mandates"])

    # ---------- bills ----------
    def _defs(self, hid: str, st: dict) -> dict:
        d = {r.bill_id: dict(bill_id=r.bill_id, name=r.name, kind=r.kind, usual=float(r.usual),
                             variable=bool(r.variable), due_dom=int(r.due_dom)) for r in self.bdefs[hid].itertuples()}
        for m in st["mandates"]:
            d[m["bill_id"]] = dict(m)
        return d

    def instances(self, hid: str, st: dict, d0: int, d1: int) -> list[dict]:
        """All bill instances due in [d0, d1], with status overlay. Amounts are 'billed' only close to the due date."""
        defs = self._defs(hid, st)
        raw = []
        sc = self.bsched[hid]
        for r in sc[(sc.due_day >= d0) & (sc.due_day <= d1)].itertuples():
            raw.append((r.bill_id, int(r.due_day), float(r.amount), float(r.expected)))
        for m in st["mandates"]:
            base = pd.Timestamp(config.START_DATE).replace(day=1)
            for k in range(0, 40):
                ts = (base + pd.DateOffset(months=k)).replace(day=min(m["due_dom"], 28))
                di = (ts - pd.Timestamp(config.START_DATE)).days
                if d0 <= di <= d1 and di >= m["start_day"]:
                    wiggle = 1.0 + ((di * 7919) % 7 - 3) / 100.0  # deterministic +/-3%
                    raw.append((m["bill_id"], di, round(m["usual"] * wiggle), m["usual"]))
        out = []
        for bid, due, amt, exp in raw:
            df = defs.get(bid)
            if df is None:
                continue
            key = f"{bid}:{due}"
            amt = float(st["bill_override"].get(key, amt))
            rec = st["bills"].get(key, {})
            billed = st["day"] >= due - BILLED_DAYS_BEFORE or key in st["bill_override"] or bool(rec)
            flagged = bool(billed and billslib.is_anomalous(amt, exp))
            out.append(dict(key=key, bill_id=bid, name=df["name"], kind=df["kind"], due_day=due, due_date=_d(due),
                            variable=df["variable"], expected=round(exp), amount=round(amt) if billed else None,
                            true_amount=amt, billed=billed, flagged=flagged, status=rec.get("status"),
                            paid_via=rec.get("via"), paid_day=rec.get("day")))
        out.sort(key=lambda x: (x["due_day"], x["name"]))
        return out

    def _cfg(self, st: dict, bid: str) -> dict:
        return st["bill_cfg"].setdefault(bid, dict(autopay=True, monthly_limit=1e9, confirm_over_limit=True, active=True))

    def _pay(self, st: dict, amount: float, use_vault: bool) -> tuple[bool, str]:
        """Pay from vault, then spendable, then emergency buffer. Returns (ok, source)."""
        avail = st["spendable"] + (st["vault"] if use_vault else 0.0)
        src = "vault" if use_vault and st["vault"] > 0 else "wallet"
        if avail < amount:
            extra = amount - avail
            if use_vault and st["buffer"] >= extra:
                st["buffer"] -= extra
                st["spendable"] += extra
                src = "buffer"
            else:
                return False, ""
        take = min(st["vault"], amount) if use_vault else 0.0
        st["vault"] -= take
        st["spendable"] -= amount - take
        return True, src

    def _process_bills(self, hid: str, st: dict, d: int, events: list):
        # 1) escalate unresolved bills from earlier days, then try to settle overdue ones
        for key, rec in list(st["bills"].items()):
            if rec.get("status") in GRACE_DAYS and d > rec["due_day"] + GRACE_DAYS[rec["status"]]:
                fee = billslib.late_fee(rec["amount"])
                rec.update(status="overdue", fee=fee)
                st["late_fees"] += fee
                st["bills_due"] += 1
                events.append(dict(day=d, type="bill_overdue", name=rec["name"], amount=round(rec["amount"])))
            if rec.get("status") == "overdue" and st["spendable"] >= rec["amount"] + rec.get("fee", 0.0):
                st["spendable"] -= rec["amount"] + rec.get("fee", 0.0)
                rec.update(status="paid", via="wallet", day=d, late=True)
                st["paid_log"].append(dict(day=d, name=rec["name"], kind=rec["kind"], amount=rec["amount"]))
                events.append(dict(day=d, type="bill_paid_late", name=rec["name"]))
        # 2) bills due today
        for inst in self.instances(hid, st, d, d):
            key = inst["key"]
            if key in st["bills"]:
                continue
            cfg = self._cfg(st, inst["bill_id"])
            if not cfg["active"]:
                continue
            amount = inst["true_amount"]
            base = dict(name=inst["name"], kind=inst["kind"], amount=amount, expected=inst["expected"], due_day=d)
            over_limit = cfg["confirm_over_limit"] and amount > cfg["monthly_limit"]
            if not cfg["autopay"]:
                st["bills"][key] = dict(base, status="due")
                events.append(dict(day=d, type="bill_due_manual", name=inst["name"]))
            elif inst["flagged"] or over_limit:
                st["bills"][key] = dict(base, status="needs_review", reason="unusual" if inst["flagged"] else "over_limit")
                events.append(dict(day=d, type="bill_needs_review", name=inst["name"], amount=round(amount)))
            else:
                before = st["spendable"]
                ok, src = self._pay(st, amount, True)
                st["bills_due"] += 1
                if ok:
                    st["bills_on_time"] += 1
                    if src == "vault" and before < amount:
                        st["fees_avoided"] += billslib.late_fee(amount)
                    st["bills"][key] = dict(base, status="paid", via=src, day=d)
                    st["paid_log"].append(dict(day=d, name=inst["name"], kind=inst["kind"], amount=amount))
                    events.append(dict(day=d, type="bill_paid", name=inst["name"], amount=round(amount)))
                else:
                    fee = billslib.late_fee(amount)
                    st["late_fees"] += fee
                    st["bills"][key] = dict(base, status="overdue", fee=fee)
                    events.append(dict(day=d, type="bill_overdue", name=inst["name"], amount=round(amount)))
        st["paid_log"] = st["paid_log"][-80:]

    def resolve_bill(self, hid: str, st: dict, key: str, action: str) -> dict:
        rec = st["bills"].get(key)
        if not rec or rec["status"] not in ("due", "needs_review", "overdue"):
            raise ValueError("this bill is not waiting for a decision")
        amount = rec["amount"]
        if action == "dispute":
            amount = rec["expected"]  # assumption: dispute resolved, corrected to the estimate
            st["anomalies_caught"] += 1
            st["overbilling_avoided"] += max(rec["amount"] - rec["expected"], 0.0)
        elif action not in ("approve", "pay_manually"):
            raise ValueError("unknown action")
        ok, src = self._pay(st, amount, True)
        if not ok:
            raise ValueError("not enough money available to pay this bill right now")
        was_overdue = rec["status"] == "overdue"
        fee = rec.get("fee", 0.0) if was_overdue else 0.0
        if fee and st["spendable"] >= fee:
            st["spendable"] -= fee
        if not was_overdue:
            st["bills_due"] += 1
            st["bills_on_time"] += 1
        rec.update(status="paid", via=src if action != "dispute" else "dispute", day=st["day"], amount=amount)
        st["paid_log"].append(dict(day=st["day"], name=rec["name"], kind=rec["kind"], amount=amount))
        return st

    def set_autopay(self, hid: str, st: dict, bill_id: str, on: bool) -> dict:
        if bill_id not in self._defs(hid, st):
            raise ValueError("unknown bill")
        self._cfg(st, bill_id)["autopay"] = bool(on)
        return st

    def add_mandate(self, hid: str, st: dict, name: str, kind: str, usual: float, due_dom: int,
                    monthly_limit: float, confirm_over_limit: bool, account: str) -> dict:
        bid = f"{hid}-m{len(st['mandates']) + 1}-{abs(hash(name)) % 1000}"
        st["mandates"].append(dict(bill_id=bid, name=name, kind=kind, usual=float(usual), variable=False,
                                   due_dom=int(due_dom), account=account[-4:].rjust(len(account), "*"),
                                   start_day=st["day"] + 1))
        st["bill_cfg"][bid] = dict(autopay=True, monthly_limit=float(monthly_limit),
                                   confirm_over_limit=bool(confirm_over_limit), active=True)
        return st

    def remove_mandate(self, hid: str, st: dict, bill_id: str) -> dict:
        self._cfg(st, bill_id)["active"] = False
        return st

    def bills_needed(self, hid: str, st: dict, horizon: float) -> float:
        tot = 0.0
        for i in self.instances(hid, st, st["day"], int(st["day"] + horizon)):
            if i["status"] in ("paid", "overdue", "needs_review", "due"):
                continue
            if not self._cfg(st, i["bill_id"])["active"] or not self._cfg(st, i["bill_id"])["autopay"]:
                continue
            tot += i["expected"] * (1.1 if i["variable"] else 1.0)
        return tot

    def bill_cards(self, hid: str, st: dict, days_ahead: int = 45, days_back: int = 35) -> list[dict]:
        """Bill list with display status: scheduled / paid / needs_review / at_risk / overdue."""
        items = self.instances(hid, st, st["day"] - days_back, st["day"] + days_ahead)
        funds = st["vault"] + st["spendable"]
        running = 0.0
        out = []
        for i in items:
            cfg = self._cfg(st, i["bill_id"])
            if not cfg["active"]:
                continue
            status = i["status"]
            manual = not cfg["autopay"]
            if status is None:
                if i["due_day"] < st["day"]:
                    continue
                running += i["expected"]
                status = "at_risk" if (running > funds and not manual) else "scheduled"
                if manual and running > funds:
                    status = "at_risk"
            elif status == "due":
                status = "needs_review"
            planned = _d(i["due_day"])
            out.append(dict(i, display_status=status, autopay=cfg["autopay"], monthly_limit=cfg["monthly_limit"],
                            confirm_over_limit=cfg["confirm_over_limit"], planned_date=planned,
                            note=self._bill_note(i)))
        return out

    def _bill_note(self, i: dict) -> str | None:
        if i["variable"] and i["billed"] and i["amount"] is not None and i["expected"]:
            r = i["true_amount"] / i["expected"]
            if r > billslib.ANOMALY_FACTOR:
                return f"{r:.1f}x your usual amount (estimate {round(i['expected']):,})"
        if i["variable"] and not i["billed"]:
            return "Estimate based on the same month last year"
        return None

    # ---------- forecasts / risk ----------
    def arrival_forecast(self, hid: str, seq: int):
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
        if intent:
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

    def _burn(self, hid: str, st: dict):
        mean_ess, net, local_daily = self.usual_needs(hid, st)
        hist = st["history"][-7:]
        recent = float(np.mean([x["spent"] for x in hist])) if hist else mean_ess
        # burn uses the MEDIAN of recent days so one large expense does not distort the whole projection
        typical = float(np.median([x.get("base", x["spent"]) for x in hist])) if hist else mean_ess
        daily_mean = max(typical, mean_ess) if hist else mean_ess
        return mean_ess, recent, max(daily_mean - local_daily, 1.0), local_daily

    def shortfall(self, hid: str, st: dict, thr: float) -> dict:
        f = self.current_forecast(hid, st)
        if f is None:
            return dict(available=False)
        mean_ess, recent, net_burn, local_daily = self._burn(hid, st)
        rem = dict(rem_p10=f["rem_p10"], rem_p50=f["rem_p50"], rem_p90=f["rem_p90"])
        res = risk.simulate_shortfall(st["spendable"], net_burn, 0.35, rem, reserve=st["buffer"], n=1000, seed=st["day"])
        led = self.led[hid]
        recent_shock = float(led["shock"].to_numpy()[max(0, st["day"] - 7): st["day"] + 1].sum())
        drv = risk.drivers(recent, mean_ess, st["spendable"] + st["buffer"], f["rem_p50"],
                           f["days_since_arrival"], f["gap_p50"], recent_shock)
        sev = risk.severity(res["prob"], thr)
        return dict(available=True, **res, severity=sev, threshold=thr, drivers=drv, suggestions=_suggest(sev, drv))

    def home(self, hid: str, st: dict, thr: float) -> dict:
        """Everything the Home screen needs, computed in code (no LLM)."""
        f = self.current_forecast(hid, st)
        cards = self.bill_cards(hid, st, 45, 0)
        upcoming = [c for c in cards if c["display_status"] in ("scheduled", "at_risk", "needs_review")][:3]
        out = dict(available=round(st["spendable"]), reserved_bills=round(st["vault"]),
                   savings=round(st["buffer"] + sum(st["goals"].values())), upcoming=upcoming, safe=None, alert=None)
        if f is None:
            return out
        horizon = f["rem_p50"] + 0.6 * (f["rem_p90"] - f["rem_p50"])
        uncovered = 0.0
        for c in cards:
            if c["due_day"] <= st["day"] + horizon and c["display_status"] in ("scheduled", "at_risk") and c["autopay"]:
                uncovered += c["expected"]
        uncovered = max(uncovered - st["vault"], 0.0)
        usable = max(st["spendable"] - uncovered, 0.0)
        days = max(horizon, 1.0)
        per_day = usable / days
        mean_ess, net, _ = self.usual_needs(hid, st)
        usual = max(net, 1.0)
        ratio = per_day / usual
        out["safe"] = dict(per_day=round(per_day), usual_per_day=round(usual), days=round(days),
                           status="green" if ratio >= 1.0 else ("amber" if ratio >= 0.7 else "red"),
                           bills_not_yet_covered=round(uncovered))
        sf = self.shortfall(hid, st, thr)
        if sf.get("available") and sf["severity"] != "green":
            gap = sf.get("expected_gap_days") or 0
            out["alert"] = dict(severity=sf["severity"], prob=round(sf["prob"], 3), days_short=max(round(gap), 1),
                                text=f"You may run short about {max(round(gap), 1)} days before your next transfer.")
        return out

    def projection(self, hid: str, st: dict, n: int = 500) -> dict | None:
        """Day-by-day projected balance until the next expected remittance, with an uncertainty band."""
        f = self.current_forecast(hid, st)
        if f is None:
            return None
        H = int(min(max(np.ceil(f["rem_p90"]) + 3, 7), 70))
        mean_ess, recent, net_burn, _ = self._burn(hid, st)
        cv = 0.35
        rng = np.random.default_rng(st["day"])
        spend = rng.gamma(1 / cv**2, net_burn * cv**2, size=(n, H))
        cum = np.cumsum(spend, axis=1)
        # bills: vault pays first; anything beyond the vault comes out of the wallet
        vault = st["vault"]
        deduct = np.zeros(H)
        marks = []
        for c in self.bill_cards(hid, st, H, 0):
            if c["display_status"] not in ("scheduled", "at_risk", "needs_review"):
                continue
            off = c["due_day"] - st["day"]
            if not 1 <= off <= H:
                continue
            amt = float(c["expected"])
            from_vault = min(vault, amt) if c["autopay"] else 0.0
            vault -= from_vault
            deduct[off - 1:] += amt - from_vault
            marks.append(dict(day=off, name=c["name"], amount=round(amt)))
        bal = st["spendable"] - cum - deduct[None, :]
        q = np.quantile(bal, [0.1, 0.5, 0.9], axis=0)
        return dict(days=list(range(1, H + 1)), dates=[_d(st["day"] + i) for i in range(1, H + 1)],
                    p10=[round(x) for x in q[0]], p50=[round(x) for x in q[1]], p90=[round(x) for x in q[2]],
                    bills=marks, next_p10=round(f["rem_p10"], 1), next_p50=round(f["rem_p50"], 1),
                    next_p90=round(f["rem_p90"], 1), starting_balance=round(st["spendable"]),
                    goes_negative=bool((q[1] < 0).any()))

    def options(self, hid: str, st: dict, thr: float) -> list[dict]:
        sf = self.shortfall(hid, st, thr)
        if not sf.get("available") or sf["severity"] == "green":
            return []
        f = self.current_forecast(hid, st)
        mean_ess, recent, net_burn, _ = self._burn(hid, st)
        days = max(f["rem_p50"], 1.0)
        sustainable = max(st["spendable"], 0.0) / days
        cut = max(net_burn - sustainable, 0.0)
        gap = (sf.get("expected_gap_days") or 3.0) * net_burn
        goals_total = sum(st["goals"].values())
        out = []
        if cut > 0:
            out.append(dict(id="reduce_spending", title=f"Spend about ৳{round(cut):,} less per day",
                            detail="This keeps your money lasting until the transfer arrives.", amount=round(cut),
                            actionable=False))
        if goals_total > 0:
            move = min(goals_total, gap)
            out.append(dict(id="move_from_goals", title=f"Move ৳{round(move):,} from goal savings",
                            detail="Your goals stay yours; you can top them up from the next transfer.",
                            amount=round(move), actionable=True))
        out.append(dict(id="ask_sender", title="Ask your sender for an earlier transfer",
                        detail="We will show your sender a gentle note. They decide.", amount=0, actionable=True))
        return out

    def apply_option(self, hid: str, st: dict, option: str, thr: float) -> dict:
        if option == "ask_sender":
            st["sender_ask"] = True
        elif option == "move_from_goals":
            opts = {o["id"]: o for o in self.options(hid, st, thr)}
            o = opts.get("move_from_goals")
            if not o:
                raise ValueError("no goal savings to move")
            need = o["amount"]
            tot = sum(st["goals"].values())
            for k in list(st["goals"]):
                st["goals"][k] -= st["goals"][k] / tot * need
            st["spendable"] += need
        else:
            raise ValueError("unknown option")
        return st

    def categories(self, hid: str, st: dict, days: int = 30) -> dict:
        led = self.led[hid]
        lo = max(0, st["day"] - days + 1)
        w = led[(led.day >= lo) & (led.day <= st["day"])]
        hh = self.h.loc[hid]
        tot = {c: float(w["essential"].sum()) * float(hh[f"cat_{c}"]) * st["need_mult"] for c in CATS}
        for r in w.itertuples():
            if r.shock > 0:
                tot[r.shock_cat if r.shock_cat in CATS else "other"] += float(r.shock)
        tot["bills"] = float(sum(p["amount"] for p in st["paid_log"] if p["day"] >= lo))
        return dict(days=days, items=[dict(category=k, amount=round(v)) for k, v in tot.items() if v > 0],
                    note="Categories are simulated shares of spending (an assumption).")

    # ---------- plan ----------
    def propose(self, hid: str, st: dict) -> list[dict]:
        p = st["pending"]
        if not p:
            return []
        f = self.arrival_forecast(hid, p["seq"])
        if f is None:
            return []
        mean_ess, net, _ = self.usual_needs(hid, st)
        rem = dict(rem_p10=f["gap_p10"], rem_p50=f["gap_p50"], rem_p90=f["gap_p90"])
        goals = self.goals_list(hid, st)
        out = []
        for style in allocator.STYLES:
            horizon = allocator.reserve_days_for(style, rem)
            plan = allocator.propose(p["got"], rem, net, st["spendable"], st["buffer"], mean_ess * 30,
                                     goals, style, config.BUFFER_TARGET_MONTHS, float(self.h.loc[hid, "gap_mean"]),
                                     bills_needed=self.bills_needed(hid, st, horizon), vault=st["vault"],
                                     bills_monthly=self.bills_monthly(hid, st))
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
            plan_obj = allocator.custom_plan(got, plan.get("needs", 0), plan.get("savings", 0),
                                             plan.get("goals", {}), plan.get("bills", 0))
            st["vault"] += plan_obj.bills
            st["spendable"] += plan_obj.needs
            st["buffer"] += plan_obj.savings
            for name, amt in plan_obj.goals.items():
                gid = goals.get(name)
                if gid:
                    st["goals"][gid] = st["goals"].get(gid, 0.0) + amt
                    st["contrib"].setdefault(gid, []).append(dict(day=st["day"], amount=round(amt)))
                else:
                    st["buffer"] += amt
            st["adherent"] = True
            mean_ess, _, _ = self.usual_needs(hid, st)
            first = min(plan_obj.needs, mean_ess * allocator.WALLET_RELEASE_DAYS)
            st["retained_amt"] += max(p["amount"] - first, 0.0)
        st["pending"] = None
        ev: list = []
        self._process_bills(hid, st, st["day"], ev)
        st["log"] = (st["log"] + ev)[-40:]
        return st

    def goal_pace(self, hid: str, st: dict, g: allocator.Goal) -> dict:
        """Months to reach a goal at the recent contribution pace (an estimate, not a promise)."""
        rows = st["contrib"].get(g.id, [])[-3:]
        remaining = max(g.target - g.current, 0.0)
        if remaining <= 0:
            return dict(months=0.0, text="Goal reached")
        if not rows:
            return dict(months=None, text="Accept a plan to see a pace estimate")
        per_transfer = float(np.mean([r["amount"] for r in rows]))
        f = self.current_forecast(hid, st)
        gap = f["gap_p50"] if f else float(self.h.loc[hid, "gap_mean"])
        per_month = per_transfer * 30.0 / max(gap, 7.0)
        if per_month <= 0:
            return dict(months=None, text="No contributions yet")
        months = remaining / per_month
        return dict(months=round(months, 1), text=f"At your current pace, about {round(months)} months")

    # ---------- time ----------
    def advance(self, hid: str, st: dict, days: int, to_arrival: bool = False) -> dict:
        led, ev = self.led[hid], self.ev[hid]
        ess, shock, inc = led["essential"].to_numpy(), led["shock"].to_numpy(), led["local_income"].to_numpy()
        leak = float(self.h.loc[hid, "leak_rate"])
        events = []
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
                st["sender_ask"] = False
                st["pending"] = dict(seq=seq, amount=amount, got=got, day=d, date=_d(d))
                st["adherent"] = False
                events.append(dict(day=d, type="arrival", amount=amount))
                break
            self._process_bills(hid, st, d, events)
            base_need = ess[d] * st["need_mult"]
            if not st["adherent"]:
                excess = max(st["spendable"] + inc[d] + st["extra_income"] / 30.0 - sim.CUSHION_DAYS * ess[d], 0.0)
                base_need += leak * sim.CREEP_FACTOR * excess
            need = base_need + shock[d] * st["need_mult"]
            a = sim.Account(spendable=st["spendable"], buffer=st["buffer"], goals=0.0, debt=st["debt"])
            income = inc[d] + st["extra_income"] / 30.0
            short = a.spend_day(need, income)
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
            st["history"].append(dict(day=d, date=_d(d), spent=float(need), base=float(base_need),
                                      balance=float(st["spendable"] + st["buffer"] + st["vault"]), short=bool(short)))
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
        elif kind == "high_bill":
            # make the next variable (electricity) bill unusually high: 2.4x its estimate
            cand = [i for i in self.instances(hid, st, st["day"] + 1, st["day"] + 60)
                    if i["variable"] and i["status"] is None]
            if not cand:
                raise ValueError("no upcoming variable bill to change")
            c = cand[0]
            st["bill_override"][c["key"]] = round(c["expected"] * 2.4)
            st["log"].append(dict(day=st["day"], type="high_bill_injected", name=c["name"]))
        elif kind == "new_emi":
            st = self.add_mandate(hid, st, "Phone EMI", "emi", round(float(self.h.loc[hid, "monthly_needs"]) * 0.06, -1),
                                  int((pd.Timestamp(_d(st["day"])).day + 9) % 27) + 1, 9_999_999, False, "01710000000")
        else:
            raise ValueError("unknown scenario")
        return st

    def sender_view(self, hid: str, st: dict) -> dict:
        """Coarse signals for the sender (no balances, no transactions)."""
        cards = [c for c in self.bill_cards(hid, st, 45, 0) if c["autopay"] or True]
        month_end = st["day"] + 30
        due = [c for c in cards if c["due_day"] <= month_end]
        risky = [c for c in due if c["display_status"] in ("at_risk", "needs_review", "overdue")]
        send_by = None
        for c in cards:
            if c["display_status"] == "at_risk":
                send_by = _d(c["due_day"] - 1)
                break
        return dict(bills_status="all_covered" if not risky else "at_risk", at_risk_count=len(risky),
                    send_by=send_by, asked=bool(st.get("sender_ask")))


def _suggest(sev: str, drivers: list[dict]) -> list[str]:
    if sev == "green":
        return []
    s = ["Delay non-essential spending for a few days.", "Consider using your emergency buffer only for essentials."]
    if any(d["factor"] == "late_transfer" for d in drivers):
        s.append("Ask your sender whether the transfer date has changed.")
    return s[:2] if sev == "amber" else s
