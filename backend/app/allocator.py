"""Smart budget allocator: deterministic rules + greedy goal optimizer (doc 06-B).

Business rules live here, separate from the ML forecaster. Nothing here is auto-executed:
the family always accepts / edits / rejects.
"""
from __future__ import annotations

from dataclasses import dataclass, field

STYLES = {
    # protect_q: how far toward the pessimistic (P90) arrival date we reserve needs for
    # extra_days: safety days; topup: share of surplus sent to emergency buffer first
    "conservative": dict(protect_q=1.0, extra_days=3, topup=0.40, label="Conservative"),
    "balanced": dict(protect_q=0.6, extra_days=2, topup=0.25, label="Balanced"),
    "goal_focused": dict(protect_q=0.3, extra_days=1, topup=0.10, label="Goal-focused"),
}
WALLET_RELEASE_DAYS = 7  # needs money is held in wallet and released weekly (family can always withdraw)


@dataclass
class Goal:
    id: str
    name: str
    target: float
    current: float
    days_left: float  # days to deadline
    priority: int = 2  # 1 high .. 3 low


@dataclass
class Plan:
    style: str
    label: str
    amount: float
    needs: float
    savings: float
    goals: dict = field(default_factory=dict)
    reserve_days: float = 0.0
    reasons: list = field(default_factory=list)

    def goals_total(self) -> float:
        return float(sum(self.goals.values()))

    def to_dict(self) -> dict:
        return dict(style=self.style, label=self.label, amount=round(self.amount),
                    needs=round(self.needs), savings=round(self.savings),
                    goals={k: round(v) for k, v in self.goals.items()},
                    goals_total=round(self.goals_total()), reserve_days=round(self.reserve_days, 1),
                    reasons=self.reasons)


def reserve_days_for(style: str, rem: dict) -> float:
    s = STYLES[style]
    gap = rem["rem_p50"] + s["protect_q"] * (rem["rem_p90"] - rem["rem_p50"])
    return gap + s["extra_days"]


def propose(amount: float, rem: dict, daily_needs: float, spendable: float, buffer: float,
            monthly_needs: float, goals: list[Goal], style: str = "balanced",
            buffer_target_months: float = 1.0, typical_gap: float = 30.0) -> Plan:
    """Split an arrived remittance into needs / savings (emergency buffer) / goals.

    daily_needs is the NET daily deficit to cover from the remittance (essentials minus local income).
    """
    s = STYLES[style]
    days = reserve_days_for(style, rem)
    margin = 1.05  # 5% margin on essentials for noise
    needs_target = daily_needs * days * margin
    needs = float(min(max(needs_target - spendable, 0.0), amount))
    surplus = amount - needs
    reasons = [
        f"Next transfer is expected in {round(rem['rem_p50'])} days (could be as late as {round(rem['rem_p90'])}). "
        f"We reserve money for about {round(days)} days of essentials.",
    ]
    if spendable > 0 and needs < needs_target:
        reasons.append("Money you already have in hand is counted before adding more to needs.")

    target_buffer = buffer_target_months * monthly_needs
    topup_room = max(target_buffer - buffer, 0.0)
    savings = float(min(topup_room, s["topup"] * surplus))
    surplus -= savings
    if savings > 0:
        reasons.append(f"Part of the surplus builds your emergency buffer toward {buffer_target_months:g} month of needs.")

    # goals: greedy by priority then urgency; required per cycle = remaining / cycles left
    alloc: dict[str, float] = {}
    order = sorted(goals, key=lambda g: (g.priority, g.days_left))
    for g in order:
        if surplus <= 0:
            break
        remaining = max(g.target - g.current, 0.0)
        if remaining <= 0:
            continue
        cycles_left = max(g.days_left / max(typical_gap, 7.0), 1.0)
        need_now = remaining / cycles_left
        give = float(min(need_now, remaining, surplus))
        if give > 0:
            alloc[g.name] = give
            surplus -= give
    # leftover surplus: second pass fills goals toward target by priority, else returns to buffer/needs
    for g in order:
        if surplus <= 0:
            break
        remaining = max(g.target - g.current - alloc.get(g.name, 0.0), 0.0)
        give = float(min(remaining, surplus))
        if give > 0:
            alloc[g.name] = alloc.get(g.name, 0.0) + give
            surplus -= give
    if alloc:
        reasons.append("Goals are funded by priority and how close the deadline is.")
    if surplus > 1:
        savings += surplus  # nothing left to fund: keep as extra savings (still the family's money)
        reasons.append("Extra money not needed for goals is kept as savings.")
    return Plan(style=style, label=s["label"], amount=amount, needs=needs, savings=savings,
                goals=alloc, reserve_days=days, reasons=reasons)


def custom_plan(amount: float, needs: float, savings: float, goals: dict) -> Plan:
    """Family-edited split. Normalised so it never exceeds the amount."""
    needs = max(needs, 0.0)
    savings = max(savings, 0.0)
    g = {k: max(float(v), 0.0) for k, v in goals.items()}
    total = needs + savings + sum(g.values())
    if total > amount and total > 0:
        k = amount / total
        needs, savings = needs * k, savings * k
        g = {a: b * k for a, b in g.items()}
    elif total < amount:
        needs += amount - total  # unallocated money stays spendable
    return Plan(style="custom", label="Your edit", amount=amount, needs=needs, savings=savings, goals=g,
                reasons=["Edited by the family."])
