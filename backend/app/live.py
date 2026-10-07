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
EID_FACTOR = 1.4   # daily needs during the Eid surge scenario (assumption: about +40%)
EID_DAYS = 10
MEDICAL_DEFAULT = 8000.0
MICRO_MODES = {"roundup": "Round spending up to the next ৳10", "percent": "1% of safe-to-spend surplus"}
MICRO_DAILY_CAP = 100.0   # ৳ per day, a deliberately small amount
CATS = ("food", "transport", "education", "health", "other")


def _d(day: float) -> str:
    return (pd.Timestamp(config.START_DATE) + pd.Timedelta(days=int(round(day)))).strftime("%Y-%m-%d")


class Engine:
    thr = config.WARN_THRESHOLD_DEFAULT  # warning threshold; main.py sets the tuned value from evaluation.json

    def __init__(self):
        self.h = db.read_sql("SELECT * FROM households").set_index("household_id")
        self.ev = {k: v.sort_values("seq").reset_index(drop=True)
                   for k, v in db.read_sql("SELECT * FROM remittances").groupby("household_id")}
        self.led = {}  # filled for the demo households only (keeps memory small on free hosts)
        fc = db.read_sql("SELECT * FROM forecasts")
        self.fc = {k: {int(r["seq"]): r for r in v.to_dict("records")} for k, v in fc.groupby("household_id")}
        ff = db.read_sql("SELECT * FROM forecast_features")
        self.ff = {k: {int(r["seq"]): r for r in v.to_dict("records")} for k, v in ff.groupby("household_id")}
        try:
            self.model = forecast.Forecaster.load()
        except Exception:  # a missing model file must not take the whole API down: only 'why' drivers go missing
            self.model = None
        self._start = {}
        self._senders = ["Rahim", "Karim", "Jamal"]
        self.demo_ids = self._pick_demo()
        self.bdefs, self.bsched, self._bhist, self._loaded = {}, {}, {}, set()

    def ensure(self, hid: str):
        """Load one household's ledger and bills on first use (any registered family, not just the demos)."""
        if hid in self._loaded:
            return
        led = db.read_sql("SELECT * FROM ledger WHERE household_id = :h", h=hid)
        self.led[hid] = led.sort_values("day").reset_index(drop=True)
        self.bdefs[hid] = db.read_sql("SELECT * FROM bill_defs WHERE household_id = :h", h=hid).reset_index(drop=True)
        sc = db.read_sql("SELECT * FROM bill_schedule WHERE household_id = :h", h=hid).sort_values("due_day").reset_index(drop=True)
        self.bsched[hid] = sc
        for bid, g in sc.groupby("bill_id"):
            g = g.sort_values("due_day")
            self._bhist[bid] = (g.due_day.to_numpy(), g.amount.to_numpy(), g.anomaly.to_numpy().astype(bool))
        self._loaded.add(hid)

    def default_sender_name(self, hid: str) -> str:
        ids = list(self.demo_ids)
        return self._senders[ids.index(hid) % 3] if hid in ids else "your sender"

    def sender_name(self, hid: str) -> str:
        """The first registered sender's first name, else a default."""
        with SessionLocal() as s:
            u = s.query(db.User).filter(db.User.household_id == hid, db.User.role == "sender").order_by(db.User.id).first()
            if u:
                return u.name.split()[0]
        return self.default_sender_name(hid)

    def profile(self, hid: str) -> dict:
        """Display profile for a household: family name, sender name and city."""
        cities = {"gulf": "Dubai", "malaysia": "Kuala Lumpur", "other": "abroad"}
        with SessionLocal() as s:
            fam = s.query(db.User).filter(db.User.household_id == hid, db.User.role == "family").order_by(db.User.id).first()
        row = self.h.loc[hid]
        name = fam.name.split()[0] if fam else self.demo_ids.get(hid, "Family")
        city = (fam.sender_city if fam and fam.sender_city else cities.get(row["sender_origin"], "abroad"))
        return dict(household_id=hid, name=name, regularity_class=row["regularity_class"], region=row["region"],
                    size=int(row["size"]), sender_id=f"S-{hid}", sender_name=self.sender_name(hid), sender_city=city,
                    is_demo=hid in self.demo_ids)

    def eligible(self, taken: set) -> list:
        """Unclaimed synthetic households a new family account can be given (test split first, enough history)."""
        out = []
        for hid in self.h[self.h.split == "test"].index:
            if hid in self.demo_ids or hid in taken:
                continue
            if len(self.ev.get(hid, [])) >= 18 and len(self.fc.get(hid, {})) >= 8:
                out.append(hid)
        return out

    def usual_range(self, bid: str, due: int):
        """Min and max of the last 6 normal (non-anomalous) amounts of this bill before `due`."""
        h = self._bhist.get(bid)
        if h is None:
            return None, None
        days, amts, anom = h
        sel = amts[(days < due) & ~anom][-6:]
        if len(sel) < 2:
            return None, None
        return round(float(sel.min()), -1), round(float(sel.max()), -1)

    def start_seq(self, hid: str) -> int:
        """First arrival (seq >= 3) that is a normal-sized transfer, so the demo starts on a main remittance."""
        if hid not in self._start:
            ev, typ = self.ev[hid], float(self.h.loc[hid, "typical_amount"])
            # start on a normal transfer whose PREVIOUS arrival already has a forecast, so a new household
            # sees "next remittance", "safe to spend" and the projection from the very first screen
            have = self.fc.get(hid, {}).keys()
            ok = ev[(ev.seq >= DEMO_START_SEQ + 1) & (ev.amount >= 0.6 * typ)]
            ok = ok[ok.seq.isin(have) & (ok.seq - 1).isin(have)]
            self._start[hid] = int(ok.seq.iloc[0]) if len(ok) else DEMO_START_SEQ
        return self._start[hid]

    def _pick_demo(self):
        t = self.h[self.h.split == "test"]
        t = t[t.index <= f"H{300:03d}"]  # demo households stay fixed: only the original block can be chosen
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
                    need_mult=1.0, eid_until=-1, amt_mult={}, micro_on=False, micro_mode="roundup", micro_target="emergency",
                    micro_total=0.0, micro_log=[], micro_paused=None, micro_consent_day=None, history=[], log=[], sender_intent=None, retained_amt=0.0, total_amt=0.0,
                    cycle_forecast=None, bill_cfg=cfg, mandates=[], bills={}, bill_override={}, paid_log=[],
                    bills_due=0, bills_on_time=0, late_fees=0.0, fees_avoided=0.0, overbilling_avoided=0.0,
                    anomalies_caught=0, contrib={}, sender_ask=False)

    def _upgrade(self, hid: str, st: dict) -> dict:
        fresh = self._fresh(hid)
        for k, v in fresh.items():
            st.setdefault(k, v)
        return st

    def get(self, hid: str) -> dict:
        self.ensure(hid)
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

    @staticmethod
    def eid_factor(st: dict, day: int) -> float:
        """Temporary Eid spending surge: applies to every day up to and including st['eid_until']."""
        return EID_FACTOR if day <= st.get("eid_until", -1) else 1.0

    def usual_needs(self, hid: str, st: dict):
        ess = self.led[hid]["essential"].to_numpy()
        mean_ess = float(ess[max(0, st["day"] - 60): st["day"] + 1].mean()) * st["need_mult"] * self.eid_factor(st, st["day"] + 1)
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
            lo, hi = self.usual_range(bid, due)
            out.append(dict(key=key, bill_id=bid, name=df["name"], kind=df["kind"], due_day=due, due_date=_d(due),
                            usual_low=lo, usual_high=hi,
                            variable=df["variable"], expected=round(exp), amount=round(amt) if billed else None,
                            true_amount=amt, billed=billed, flagged=flagged, status=rec.get("status"),
                            paid_via=rec.get("via"), paid_day=rec.get("day"),
                            paid_date=_d(rec["day"]) if rec.get("day") is not None else None))
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
        drv = self._scenario_drivers(st) + drv
        drv = sorted(drv, key=lambda d: -d["magnitude"])[:3]
        sev = risk.severity(res["prob"], thr)
        return dict(available=True, **res, severity=sev, threshold=thr, drivers=drv, suggestions=_suggest(sev, drv))

    @staticmethod
    def _scenario_drivers(st: dict) -> list[dict]:
        """Readable reasons for the real-life scenarios (Eid surge, medical expense)."""
        out = []
        if st["day"] < st.get("eid_until", -1):
            out.append(dict(factor="eid_surge", magnitude=0.6, until=_d(st["eid_until"]),
                            detail=f"Eid spending: daily needs are about {round((EID_FACTOR - 1) * 100)}% higher until {_d(st['eid_until'])}."))
        for e in reversed(st["log"]):
            if e["type"] == "medical_emergency" and st["day"] - e["day"] <= 14:
                out.append(dict(factor="medical_emergency", magnitude=0.7, amount=e["amount"],
                                detail=f"Unexpected medical expense of ৳{e['amount']:,} recently."))
                break
        return out

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
        send_by = None
        for c in self.bill_cards(hid, st, 45, 0):
            if c["display_status"] == "at_risk":
                send_by = _d(c["due_day"] - 1)
                break
        who = self.sender_name(hid)
        title = f"Ask {who} to send by {pd.Timestamp(send_by).strftime('%-d %b')}" if send_by else f"Ask {who} for an earlier transfer"
        out.append(dict(id="ask_sender", title=title, detail=f"We will show {who} a gentle note. They decide.",
                        amount=0, actionable=True, send_by=send_by, asked=bool(st.get("sender_ask"))))
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
        """Pace of a goal: months to reach it at the recent contribution pace (an estimate, not a promise)."""
        rows = st["contrib"].get(g.id, [])[-3:]
        remaining = max(g.target - g.current, 0.0)
        months_left = max(g.days_left / 30.0, 0.5)
        required = remaining / months_left
        target_date = _d(st["day"] + g.days_left)
        base = dict(required_per_month=round(required), target_date=target_date)
        if remaining <= 0:
            return dict(base, months=0.0, per_month=0, on_track=True, catch_up=0, text="Goal reached")
        if not rows:
            return dict(base, months=None, per_month=None, on_track=None, catch_up=None,
                        text="Accept a plan to see a pace estimate")
        per_transfer = float(np.mean([r["amount"] for r in rows]))
        f = self.current_forecast(hid, st)
        gap = f["gap_p50"] if f else float(self.h.loc[hid, "gap_mean"])
        per_month = per_transfer * 30.0 / max(gap, 7.0)
        if per_month <= 0:
            return dict(base, months=None, per_month=0, on_track=None, catch_up=None, text="No contributions yet")
        months = remaining / per_month
        on_track = per_month >= 0.95 * required
        catch_up = 0 if on_track else round(required - per_month, -1)
        return dict(base, months=round(months, 1), per_month=round(per_month), on_track=bool(on_track),
                    catch_up=catch_up, text=f"At your current pace, about {round(months)} months")

    def add_money(self, hid: str, st: dict, gid: str, amount: float) -> dict:
        goals = {g.id: g for g in self.goals_list(hid, st)}
        if gid not in goals:
            raise ValueError("unknown goal")
        if amount <= 0 or amount > st["spendable"]:
            raise ValueError("not enough spendable money for that amount")
        st["spendable"] -= amount
        st["goals"][gid] = st["goals"].get(gid, 0.0) + amount
        st["contrib"].setdefault(gid, []).append(dict(day=st["day"], amount=round(amount)))
        return st

    def bill_history(self, hid: str, st: dict) -> dict | None:
        """Last 6 billed amounts of the main variable bill and the estimate for the next one."""
        defs = self.bdefs[hid]
        var = defs[defs["variable"].astype(bool)]
        if var.empty:
            return None
        bid = var.iloc[0].bill_id
        name = var.iloc[0]["name"]
        sc = self.bsched[hid]
        sc = sc[sc.bill_id == bid]
        past = sc[sc.due_day <= st["day"]].tail(6)
        nxt = sc[sc.due_day > st["day"]].head(1)
        pts = [dict(label=pd.Timestamp(_d(r.due_day)).strftime("%b"), amount=round(float(r.amount)), estimate=False)
               for r in past.itertuples()]
        if len(nxt):
            r = nxt.iloc[0]
            pts.append(dict(label=pd.Timestamp(_d(int(r.due_day))).strftime("%b"), amount=round(float(r.expected)), estimate=True))
        return dict(name=name, points=pts)

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
                amount = amount * st["amt_mult"].get(str(seq), 1.0)  # systemic-shock scenario cuts some transfers
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
            base_need = ess[d] * st["need_mult"] * self.eid_factor(st, d)
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
            if st.get("micro_on"):
                self._micro_save(hid, st, d, float(need), bool(short), events)
        st["history"] = st["history"][-120:]
        st["log"] = (st["log"] + events)[-40:]
        return st

    def scenario(self, hid: str, st: dict, kind: str, value: float) -> dict:
        if kind == "delay":
            seq = st["last_seq"] + 1
            ev = self.ev[hid]
            cur = st["overrides"].get(str(seq), int(ev.loc[ev.seq == seq, "day"].iloc[0]))
            st["overrides"][str(seq)] = int(cur + value)
        elif kind in ("expense", "medical"):
            if kind == "medical" and value <= 0:
                value = MEDICAL_DEFAULT
            a = sim.Account(spendable=st["spendable"], buffer=st["buffer"], debt=st["debt"])
            a.spend_day(value, 0.0)
            st["spendable"], st["buffer"], st["debt"] = a.spendable, a.buffer, a.debt
            st["log"].append(dict(day=st["day"], type="medical_emergency" if kind == "medical" else "large_expense",
                                  amount=round(value)))
        elif kind == "systemic_shock":
            # remittance-corridor disruption: the next 3 transfers arrive 21 days later each and 30% smaller
            if st.get("shock_seq") == st["last_seq"]:
                raise ValueError("a systemic shock is already active for the next transfers")
            ev = self.ev[hid]
            for r in ev[ev.seq > st["last_seq"]].itertuples():
                rank = int(r.seq - st["last_seq"])
                cur = st["overrides"].get(str(r.seq), int(r.day))
                st["overrides"][str(r.seq)] = int(cur + 21 * min(rank, 3))
                if rank <= 3:
                    st["amt_mult"][str(r.seq)] = 0.7
            st["shock_seq"] = st["last_seq"]
            st["log"].append(dict(day=st["day"], type="systemic_shock"))
        elif kind == "eid_surge":
            st["eid_until"] = int(st["day"] + EID_DAYS)
            st["log"].append(dict(day=st["day"], type="eid_surge", until=_d(st["eid_until"])))
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

    # ---------- micro-savings: save, never invest ----------
    def _micro_pause_reason(self, hid: str, st: dict, short_today: bool) -> str | None:
        """Why micro-savings must not move money right now (None = all clear)."""
        if short_today:
            return "risk"
        sf = self.shortfall(hid, st, self.thr)
        if not sf.get("available"):
            return "history"
        if sf["severity"] != "green":
            return "risk"
        if any(c["display_status"] in ("at_risk", "overdue") for c in self.bill_cards(hid, st, 12, 0)):
            return "bills"
        return None

    def _micro_amount(self, hid: str, st: dict, need: float) -> float:
        mean_ess, _, _ = self.usual_needs(hid, st)
        if st["micro_mode"] == "percent":
            amt = 0.01 * max(st["spendable"] - 3.0 * mean_ess, 0.0)
        else:
            amt = (-need) % 10.0  # round the day's spending up to the next ৳10
        room = st["spendable"] - 2.0 * mean_ess  # daily cash for the next two days is never touched
        return float(max(min(amt, MICRO_DAILY_CAP, room), 0.0))

    def _micro_save(self, hid: str, st: dict, d: int, need: float, short_today: bool, events: list):
        reason = self._micro_pause_reason(hid, st, short_today)
        if reason:
            if st.get("micro_paused") != reason:
                st["micro_paused"] = reason
                events.append(dict(day=d, type="micro_paused", reason=reason))
            return
        if st.get("micro_paused"):
            st["micro_paused"] = None
            events.append(dict(day=d, type="micro_resumed"))
        amt = round(self._micro_amount(hid, st, need), 2)
        if amt < 0.5:
            return
        goals = {g.id: g for g in self.goals_list(hid, st)}
        tgt = st["micro_target"]
        if tgt in goals and goals[tgt].current < goals[tgt].target:
            st["goals"][tgt] = st["goals"].get(tgt, 0.0) + amt
        else:
            st["buffer"] += amt
        st["spendable"] -= amt
        st["micro_total"] += amt
        st["micro_log"] = (st["micro_log"] + [dict(day=d, amount=amt)])[-400:]

    def micro_month_total(self, st: dict) -> float:
        month = _d(st["day"])[:7]
        return round(sum(x["amount"] for x in st["micro_log"] if _d(x["day"])[:7] == month), 2)

    def micro_view(self, hid: str, st: dict) -> dict:
        goals = self.goals_list(hid, st)
        names = {"emergency": "Emergency fund", **{g.id: g.name for g in goals}}
        paused = st.get("micro_paused") if st.get("micro_on") else None
        return dict(enabled=bool(st["micro_on"]), mode=st["micro_mode"], target=st["micro_target"], target_name=names.get(st["micro_target"], "Emergency fund"),
                    month_total=self.micro_month_total(st), total=round(st["micro_total"], 2), paused=paused,
                    paused_text="Paused to protect your bills" if paused else None, consent_day=st.get("micro_consent_day"),
                    modes=[dict(id=k, label=v) for k, v in MICRO_MODES.items()],
                    targets=[dict(id="emergency", name="Emergency fund")] + [dict(id=g.id, name=g.name) for g in goals])

    def set_micro(self, hid: str, st: dict, enabled: bool, mode: str | None, target: str | None, consent: bool) -> dict:
        if mode is not None:
            if mode not in MICRO_MODES:
                raise ValueError("unknown micro-savings mode")
            st["micro_mode"] = mode
        if target is not None:
            if target != "emergency" and target not in {g.id for g in self.goals_list(hid, st)}:
                raise ValueError("unknown micro-savings target")
            st["micro_target"] = target
        if enabled and not st["micro_on"]:
            if not consent:
                raise ValueError("Micro-savings needs your consent. Confirm that you agree to switch it on.")
            st["micro_on"], st["micro_consent_day"], st["micro_paused"] = True, _d(st["day"]), None
            st["log"].append(dict(day=st["day"], type="micro_on"))
        elif not enabled and st["micro_on"]:
            st["micro_on"], st["micro_paused"] = False, None
            st["log"].append(dict(day=st["day"], type="micro_off"))
        return st

    # ---------- guided demo (admin sandbox) ----------
    def _accept_pending(self, hid: str, st: dict) -> dict:
        if st["pending"]:
            st = self.decide(hid, st, "accept", self.propose(hid, st)[1])
        return st

    def guided_step(self, hid: str, st: dict, step: int, thr: float) -> tuple[dict, dict]:
        """One step of the judge path: remittance -> allocation -> unusual bill -> warning -> resolution.
        Each step works from a freshly reset household and tells the UI which family screen to open."""
        if step == 1:
            if not st["pending"]:
                st = self.advance(hid, st, 1, to_arrival=True)
            if not st["pending"]:
                raise ValueError("no remittance could be triggered")
            return st, dict(open="home", message="Remittance arrived. Review the suggested split.")
        if step == 2:
            if not st["pending"]:
                raise ValueError("Run step 1 first: no remittance is waiting for a decision.")
            st = self._accept_pending(hid, st)
            return st, dict(open="home", message="Allocation accepted: bills reserved, needs and goals funded.")
        if step == 3:
            st = self._accept_pending(hid, st)
            st = self.scenario(hid, st, "high_bill", 0)
            for _ in range(75):
                if any(c["display_status"] == "needs_review" for c in self.bill_cards(hid, st, 10, 6)):
                    return st, dict(open="payments", message="An unusually high bill is waiting for the family to review.")
                st = self._accept_pending(hid, st)
                st = self.advance(hid, st, 1)
            raise ValueError("the unusual bill did not appear in time")
        if step == 4:
            st = self._accept_pending(hid, st)
            st = self.scenario(hid, st, "delay", 14)
            st = self.scenario(hid, st, "medical", 0)
            for extra in ("eid_surge", "medical", "medical"):  # escalate until a warning shows
                sf = self.shortfall(hid, st, thr)
                if sf.get("available") and sf["severity"] != "green":
                    break
                st = self.scenario(hid, st, extra, 0)
            sf = self.shortfall(hid, st, thr)
            if not sf.get("available") or sf["severity"] == "green":
                raise ValueError("no warning could be produced for this household")
            return st, dict(open="home", message="Warning: the delayed transfer and a medical expense put the next days at risk.",
                            severity=sf["severity"])
        if step == 5:
            if not any(o["id"] == "ask_sender" for o in self.options(hid, st, thr)):
                raise ValueError("Run step 4 first: there is no warning to resolve.")
            st = self.apply_option(hid, st, "ask_sender", thr)
            return st, dict(open="plan", message="The family asked the sender to send earlier. It is the sender's decision.")
        raise ValueError("unknown step")

    def sender_view(self, hid: str, st: dict) -> dict:
        """Coarse signals for the sender (no balances, no transactions)."""
        cards = self.bill_cards(hid, st, 45, 35)
        month_end = st["day"] + 30
        due = [c for c in cards if c["due_day"] <= month_end and c["due_day"] >= st["day"] - 30]
        risky = [c for c in due if c["display_status"] in ("at_risk", "overdue")]
        review = [c for c in due if c["display_status"] == "needs_review"]
        paid = [c for c in due if c["display_status"] == "paid"]
        upcoming = [c for c in due if c["display_status"] in ("scheduled", "at_risk", "needs_review", "overdue")]
        send_by = None
        for c in cards:
            if c["display_status"] == "at_risk":
                send_by = _d(c["due_day"] - 1)
                break
        f = self.current_forecast(hid, st)
        mean_ess, net, _ = self.usual_needs(hid, st)
        bills30 = sum(c["expected"] for c in cards if st["day"] <= c["due_day"] <= month_end
                      and c["display_status"] in ("scheduled", "at_risk"))
        typical = f["amt_p50"] if f else float(self.h.loc[hid, "typical_amount"])
        need = bills30 + net * 30.0 - (st["spendable"] + st["vault"])
        suggested = float(np.clip(max(need, 0.0), 0.8 * typical, 1.5 * typical))
        suggested = round(suggested / 500.0) * 500.0
        shortfall_date = None
        if risky:
            shortfall_date = _d(min(c["due_day"] for c in risky))
        return dict(bills_status="all_covered" if not risky else "at_risk", at_risk_count=len(risky), review_count=len(review),
                    paid_count=len(paid), total_count=len(due), vault_scheduled=len([c for c in upcoming if c["status"] is None]),
                    send_by=send_by, suggested_amount=int(suggested), shortfall_date=shortfall_date,
                    next_expected=f["next_date_p50"] if f else None, asked=bool(st.get("sender_ask")))


def _suggest(sev: str, drivers: list[dict]) -> list[str]:
    if sev == "green":
        return []
    s = ["Delay non-essential spending for a few days.", "Consider using your emergency buffer only for essentials."]
    if any(d["factor"] == "late_transfer" for d in drivers):
        s.append("Ask your sender whether the transfer date has changed.")
    return s[:2] if sev == "amber" else s
