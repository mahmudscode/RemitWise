"""Policy replay: same household history under different behaviours (doc 07 / 11).

ASSUMPTIONS (documented in the data card):
- Baseline family cashes out `cashout_frac` of each transfer soon after arrival and, while not
  following a plan, spends down money in hand above a 5-day cushion at `creep` per day
  ("cash-in-hand effect", creep = leak_rate x 0.08, i.e. ~1-3% of the excess per day), then runs
  short late in the cycle.
- Following a plan removes the cash-in-hand effect; needs money is held in the wallet and released
  weekly, savings/goals are parked and not spent down.
- Bills & EMIs: without a plan the family pays a bill on its due date only if cash is in hand,
  otherwise it is paid late with a late fee (3%, min 100). With a plan, the bill vault is funded
  from each transfer and bills are paid automatically on time. Unusually high bills are flagged
  and reviewed by the family (assumed to be corrected before the due date); without a plan the
  inflated bill is paid as billed.
- Compliance = probability the family follows the plan in a given cycle. Behaviour change is an
  ASSUMPTION, not evidence of a real-world effect; results are shown across compliance levels.
- Shortfall day = a day essentials could not be paid from spendable money or the emergency buffer.
  Shortfalls are covered by informal credit repaid at 1.05x on the next arrival.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import allocator, bills as billslib, config

CUSHION_DAYS = 5
CREEP_FACTOR = 0.08
CREDIT_PREMIUM = 1.05


@dataclass
class Account:
    spendable: float = 0.0
    buffer: float = 0.0  # emergency buffer (can cover shortfalls)
    goals: float = 0.0  # goal money (family may use it for emergencies as a last resort)
    vault: float = 0.0  # bill & EMI vault: earmarked for bills only
    debt: float = 0.0
    shortfall_days: int = 0
    deficit_total: float = 0.0
    borrow_cost: float = 0.0
    goal_raid: float = 0.0
    overdue: list = field(default_factory=list)  # [(amount, fee)]
    bills_due: int = 0
    bills_on_time: int = 0
    late_fees: float = 0.0
    fees_avoided: float = 0.0
    overbilling_avoided: float = 0.0
    overbilling_paid: float = 0.0
    anomalies_caught: int = 0

    def spend_day(self, need: float, income: float) -> bool:
        """Pay `need` after adding `income`. Returns True if it was a shortfall day."""
        self.spendable += income
        if self.spendable >= need:
            self.spendable -= need
            return False
        deficit = need - self.spendable
        self.spendable = 0.0
        draw = min(self.buffer, deficit)
        self.buffer -= draw
        deficit -= draw
        if deficit > 0 and self.goals > 0:
            raid = min(self.goals, deficit)
            self.goals -= raid
            self.goal_raid += raid
            deficit -= raid
        if deficit > 0.5:
            self.debt += deficit
            self.deficit_total += deficit
            self.shortfall_days += 1
            return True
        return False

    def receive(self, amount: float) -> float:
        """Repay informal credit first (with premium); return amount left for the family."""
        if self.debt > 0:
            owed = self.debt * CREDIT_PREMIUM
            pay = min(owed, amount)
            self.borrow_cost += pay - min(self.debt, pay / CREDIT_PREMIUM)
            self.debt = max(owed - pay, 0.0) / CREDIT_PREMIUM
            amount -= pay
        return amount

    def apply_plan(self, plan: allocator.Plan, received: float):
        scale = received / plan.amount if plan.amount > 0 else 1.0
        self.vault += plan.bills * scale
        self.spendable += plan.needs * scale
        self.buffer += plan.savings * scale
        self.goals += plan.goals_total() * scale

    def pay_bill(self, amount: float, use_vault: bool) -> bool:
        """Pay a bill now: vault first (if allowed), then spendable. True if fully paid."""
        avail = self.spendable + (self.vault if use_vault else 0.0)
        if avail < amount:
            if not use_vault:
                return False
            # a family following a plan may use its emergency buffer, then goal money, for a bill
            extra = amount - avail
            use_buf = min(self.buffer, extra)
            use_goal = min(self.goals, extra - use_buf)
            if use_buf + use_goal < extra - 1e-6:
                return False
            self.buffer -= use_buf
            self.goals -= use_goal
            self.goal_raid += use_goal
            self.spendable += use_buf + use_goal
            avail = self.spendable + self.vault
        take = min(self.vault, amount) if use_vault else 0.0
        self.vault -= take
        self.spendable -= amount - take
        return True


def est_daily_needs(ess: np.ndarray, day: int, local_daily: float):
    lo = max(0, day - 60)
    window = ess[lo:day + 1]
    mean_ess = float(window.mean()) if len(window) else float(ess[:7].mean())
    return mean_ess, max(mean_ess - local_daily, 0.0)


def bills_needed(bills_by_day: dict, day: int, horizon: float) -> float:
    """Sum of expected bill amounts due in [day, day+horizon] (estimates only; no peeking at true amounts)."""
    tot = 0.0
    for d in range(day, int(day + horizon) + 1):
        for b in bills_by_day.get(d, []):
            tot += b["expected"] * (1.1 if b["variable"] else 1.0)
    return tot


def run_policy(hh: pd.Series, ev: pd.DataFrame, led: pd.DataFrame, fc_by_seq: dict,
               policy: str, compliance: float = 1.0, seed: int = 0, record: bool = False,
               style: str = "balanced", start_seq: int = 3, horizon_days: int = 365,
               bills_by_day: dict | None = None) -> dict:
    """policy in {'baseline', 'fixed_rule', 'remitwise'}.

    All policies start at the same point (arrival `start_seq`, when the forecaster first has
    enough history) with the same starting state, and are measured over `horizon_days`
    ("a simulated year"). This keeps the comparison fair.
    """
    bills_by_day = bills_by_day or {}
    rng = np.random.default_rng(seed)
    start_day = int(ev.loc[ev["seq"] == start_seq, "day"].iloc[0])
    end_day = min(start_day + horizon_days, len(led))
    n_days = end_day - start_day
    ess = led["essential"].to_numpy()
    shock = led["shock"].to_numpy()
    inc = led["local_income"].to_numpy()
    arrivals = {int(r.day): (int(r.seq), float(r.amount)) for r in ev.itertuples()}
    leak, cash_frac = float(hh["leak_rate"]), float(hh["cashout_frac"])
    local_daily = float(hh["local_income_monthly"]) / 30.0
    bills_monthly = float(hh.get("bills_monthly", 0.0))

    acc = Account(spendable=float(ess[start_day:start_day + 10].sum()))
    last_arrival, adherent = -999, False
    retained_amt = total_amt = 0.0
    total_income = 0.0
    series = []
    cycle_id = -1
    goal = allocator.Goal("g", "Family goal", target=3 * float(hh["monthly_needs"]), current=0.0,
                          days_left=365.0, priority=1)

    for d in range(start_day, end_day):
        if d in arrivals:
            seq, amount = arrivals[d]
            total_income += amount
            total_amt += amount
            got = acc.receive(amount)
            cycle_id += 1
            fc = fc_by_seq.get(seq)
            follows = policy != "baseline" and rng.random() < compliance
            adherent = False
            if policy == "remitwise" and follows and fc is not None:
                mean_ess, net = est_daily_needs(ess, d, local_daily)
                rem = dict(rem_p10=fc["gap_p10"], rem_p50=fc["gap_p50"], rem_p90=fc["gap_p90"])
                goal.current = acc.goals
                goal.days_left = max(end_day - d, 30.0)
                horizon = allocator.reserve_days_for(style, rem)
                plan = allocator.propose(got, rem, net, acc.spendable, acc.buffer, mean_ess * 30,
                                         [goal], style, config.BUFFER_TARGET_MONTHS, float(hh["gap_mean"]),
                                         bills_needed=bills_needed(bills_by_day, d, horizon),
                                         vault=acc.vault, bills_monthly=bills_monthly)
                acc.apply_plan(plan, got)
                adherent = True
                first_release = min(plan.needs, mean_ess * allocator.WALLET_RELEASE_DAYS)
                retained_amt += max(amount - first_release, 0.0)
            elif policy == "fixed_rule" and follows:
                acc.buffer += 0.2 * got
                acc.spendable += 0.8 * got
                adherent = True
                retained_amt += 0.2 * amount + 0.8 * amount * (1 - cash_frac)
            else:
                acc.spendable += got
                retained_amt += amount * (1 - cash_frac)
            last_arrival = d

        # ---- bills due today ----
        for b in bills_by_day.get(d, []):
            amt = float(b["amount"])
            if b["flagged"]:
                if policy == "remitwise" and adherent:
                    acc.anomalies_caught += 1
                    acc.overbilling_avoided += amt - b["expected"]
                    amt = float(b["expected"])  # reviewed and corrected before the due date (assumption)
                else:
                    acc.overbilling_paid += amt - b["expected"]
            acc.bills_due += 1
            vault_ok = policy == "remitwise" and adherent
            spend_before = acc.spendable
            if acc.pay_bill(amt, vault_ok):
                acc.bills_on_time += 1
                if vault_ok and spend_before < amt:
                    acc.fees_avoided += billslib.late_fee(amt)
            else:
                fee = billslib.late_fee(amt)
                acc.overdue.append((amt, fee))
                acc.late_fees += fee
        # settle overdue bills as soon as cash allows
        if acc.overdue:
            rest = []
            for amt, fee in acc.overdue:
                if acc.spendable >= amt + fee:
                    acc.spendable -= amt + fee
                else:
                    rest.append((amt, fee))
            acc.overdue = rest

        need = ess[d] + shock[d]
        if not adherent:
            excess = max(acc.spendable + inc[d] - CUSHION_DAYS * ess[d], 0.0)
            need += leak * CREEP_FACTOR * excess
        total_income += inc[d]
        short = acc.spend_day(need, inc[d])
        if record:
            series.append(dict(day=d, spendable=acc.spendable + acc.buffer, short=short, spent=need,
                               cycle=cycle_id, since=d - last_arrival, essential=ess[d],
                               shock=shock[d]))
    net_saved = acc.buffer + acc.goals + acc.spendable + acc.vault - acc.debt
    yr = 365.0 / n_days
    out = dict(
        shortfall_days_per_year=acc.shortfall_days * yr,
        borrow_cost_per_year=acc.borrow_cost * yr,
        savings_rate=float(net_saved / total_income) if total_income else 0.0,
        emergency_months=float(acc.buffer / max(float(hh["monthly_needs"]), 1.0)),
        saved_amount=float(acc.buffer + acc.goals),
        goal_raid=float(acc.goal_raid),
        retained_share=float(retained_amt / total_amt) if total_amt else 0.0,
        on_time_rate=float(acc.bills_on_time / acc.bills_due) if acc.bills_due else 1.0,
        late_fees_per_year=acc.late_fees * yr,
        overbilling_avoided_per_year=acc.overbilling_avoided * yr,
        overbilling_paid_per_year=acc.overbilling_paid * yr,
    )
    if record:
        out["series"] = pd.DataFrame(series)
    return out


def bills_by_day_map(sched: pd.DataFrame, defs: pd.DataFrame) -> dict:
    """{day: [bill dicts]} for one household (sched already annotated with expected / flagged)."""
    var = defs.set_index("bill_id")["variable"].to_dict()
    out: dict[int, list] = {}
    for r in sched.itertuples():
        out.setdefault(int(r.due_day), []).append(
            dict(bill_id=r.bill_id, amount=float(r.amount), expected=float(r.expected),
                 flagged=bool(r.flagged), variable=bool(var[r.bill_id])))
    return out
