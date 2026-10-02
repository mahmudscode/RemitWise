"""RemitWise API (doc 09). Demo auth only: roles come from headers, NOT real authentication.

Consent is enforced here on the server; sender responses are filtered before serialisation.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import allocator, config, db, explain
from .db import Consent, Decision, Goal as GoalRow, SenderLink, SessionLocal, SummaryCache
from .live import Engine

ENGINE: Engine | None = None
SCOPES = ("goal_progress", "savings_total", "spending_categories")
DEFAULT_SCOPE = "goal_progress"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ENGINE
    db.init_db()
    ENGINE = Engine()
    for hid in ENGINE.demo_ids:
        _ensure_link(hid)
    yield


app = FastAPI(title="RemitWise API", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


# ---------------- auth (demo) ----------------
class Who(BaseModel):
    role: str
    user: str


def who(x_role: str = Header("family"), x_user: str = Header("")) -> Who:
    if x_role not in ("family", "sender", "admin"):
        raise HTTPException(401, "unknown role")
    return Who(role=x_role, user=x_user)


def family_or_admin(hid: str, w: Who = Depends(who)) -> Who:
    if w.role == "admin" or (w.role == "family" and w.user == hid):
        return w
    raise HTTPException(403, "not allowed for this household")


def admin_only(w: Who = Depends(who)) -> Who:
    if w.role != "admin":
        raise HTTPException(403, "admin only")
    return w


def _eng() -> Engine:
    assert ENGINE is not None
    return ENGINE


def _check(hid: str):
    if hid not in _eng().h.index:
        raise HTTPException(404, "unknown household")


def _stamp(d: dict) -> dict:
    d["model_version"] = "lgbm-cqr-1"
    d["data_version"] = f"synthetic-seed{config.SEED}"
    return d


def _ensure_link(hid: str):
    sid = f"S-{hid}"
    with SessionLocal() as s:
        if not s.get(SenderLink, (hid, sid)):
            s.add(SenderLink(household_id=hid, sender_id=sid, sender_accepted=False))
        for sc in SCOPES:
            if not s.get(Consent, (hid, sid, sc)):
                s.add(Consent(household_id=hid, sender_id=sid, scope=sc, state="revoked"))
        s.commit()


# ---------------- read endpoints ----------------
@app.get("/")
def root():
    return dict(service="RemitWise API", docs="/docs", web_app="http://localhost:5173",
                note="This is the API. The app itself runs on the web port (npm run dev).")



@app.get("/api/health")
def health():
    return dict(ok=True, db=config.DATABASE_URL.split(":")[0], groq=bool(config.GROQ_API_KEY))


@app.get("/api/households")
def households():
    e = _eng()
    return [dict(household_id=h, name=n, regularity_class=e.h.loc[h, "regularity_class"],
                 region=e.h.loc[h, "region"], size=int(e.h.loc[h, "size"]), sender_id=f"S-{h}")
            for h, n in e.demo_ids.items()]


def _public_state(hid: str, st: dict) -> dict:
    e = _eng()
    goals = e.goals_list(hid, st)
    mean_ess, net, local = e.usual_needs(hid, st)
    return dict(
        household_id=hid, day=st["day"], date=_date(st["day"]), spendable=round(st["spendable"]),
        buffer=round(st["buffer"]), goals_total=round(sum(st["goals"].values())), debt=round(st["debt"]),
        shortfall_days=st["shortfall_days"], pending=st["pending"], adherent=st["adherent"],
        goals=[dict(id=g.id, name=g.name, target=round(g.target), current=round(g.current),
                    pct=round(100 * min(g.current / g.target, 1.0), 1) if g.target else 0,
                    days_left=round(g.days_left), priority=g.priority) for g in goals],
        history=st["history"][-60:], log=st["log"][-12:], daily_needs=round(mean_ess), monthly_needs=round(mean_ess * 30),
        retained_share=round(st["retained_amt"] / st["total_amt"], 3) if st["total_amt"] else None,
        sender_intent=st.get("sender_intent"),
    )


def _date(day: int) -> str:
    import pandas as pd
    return (pd.Timestamp(config.START_DATE) + pd.Timedelta(days=int(day))).strftime("%Y-%m-%d")


@app.get("/api/households/{hid}/state")
def get_state(hid: str, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    return _stamp(_public_state(hid, st))


@app.get("/api/households/{hid}/timeline")
def timeline(hid: str, start: int = 0, end: int = 900, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    led = e.led[hid]
    led = led[(led.day >= start) & (led.day < end)]
    ev = e.ev[hid]
    ev = ev[(ev.day >= start) & (ev.day < end)]
    return dict(ledger=led[["day", "essential", "shock", "local_income"]].to_dict("records"),
                remittances=ev[["seq", "day", "amount"]].to_dict("records"))


class Advance(BaseModel):
    days: int = Field(1, ge=1, le=120)
    to_arrival: bool = False


@app.post("/api/households/{hid}/advance")
def advance(hid: str, body: Advance, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    st = e.advance(hid, st, body.days, body.to_arrival)
    e.save(hid, st)
    db.audit(w.role, "advance", hid, dict(days=body.days, to_arrival=body.to_arrival, day=st["day"]))
    return _stamp(_public_state(hid, st))


class Scenario(BaseModel):
    kind: str
    value: float = 0.0


@app.post("/api/households/{hid}/scenario")
def scenario(hid: str, body: Scenario, w: Who = Depends(admin_only)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    try:
        st = e.scenario(hid, st, body.kind, body.value)
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    e.save(hid, st)
    db.audit(w.role, "scenario", hid, body.model_dump())
    return _stamp(_public_state(hid, st))


@app.post("/api/households/{hid}/reset")
def reset(hid: str, w: Who = Depends(admin_only)):
    _check(hid)
    e = _eng()
    st = e.reset(hid)
    db.audit(w.role, "reset", hid)
    return _stamp(_public_state(hid, st))


@app.get("/api/households/{hid}/forecast")
def get_forecast(hid: str, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    f = e.current_forecast(hid, st)
    if f is None:
        raise HTTPException(409, "not enough history yet")
    drivers = []
    try:
        import pandas as pd
        feat = e.ff[hid][st["last_seq"]]
        drivers = e.model.drivers(pd.DataFrame([feat]))
    except Exception:
        pass
    return _stamp(dict(forecast=f, confidence_label=_conf(f), drivers=drivers,
                       assumptions=["Forecast is a range, not a promise.",
                                    "Made at the last arrival; widened if the transfer is overdue."]))


def _conf(f: dict) -> str:
    width = f["rem_p90"] - f["rem_p10"]
    return "high" if width < 12 else ("medium" if width < 30 else "low")


@app.get("/api/households/{hid}/shortfall")
def get_shortfall(hid: str, threshold: float = Query(None), w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    thr = threshold if threshold is not None else _threshold()
    return _stamp(e.shortfall(hid, st, thr))


def _threshold() -> float:
    try:
        return float(json.loads((config.ARTIFACTS / "evaluation.json").read_text())["warning"]["threshold"])
    except Exception:
        return config.WARN_THRESHOLD_DEFAULT


@app.get("/api/households/{hid}/plan")
def get_plan(hid: str, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    if not st["pending"]:
        return _stamp(dict(pending=None, options=[]))
    f = e.arrival_forecast(hid, st["pending"]["seq"])
    return _stamp(dict(pending=st["pending"], options=e.propose(hid, st), forecast=f,
                       note="These are recommendations. The family decides."))


class PlanEval(BaseModel):
    needs: float
    savings: float = 0.0
    goals: dict[str, float] = {}


@app.post("/api/households/{hid}/plan/evaluate")
def plan_evaluate(hid: str, body: PlanEval, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    if not st["pending"]:
        raise HTTPException(409, "no pending remittance")
    f = e.arrival_forecast(hid, st["pending"]["seq"])
    rem = dict(rem_p10=f["gap_p10"], rem_p50=f["gap_p50"], rem_p90=f["gap_p90"])
    plan = allocator.custom_plan(st["pending"]["got"], body.needs, body.savings, body.goals)
    d = plan.to_dict()
    d["shortfall_prob"] = e.plan_risk(hid, st, plan.needs, rem)
    return _stamp(d)


class DecisionBody(BaseModel):
    decision: str = Field(pattern="^(accept|edit|skip)$")
    plan: dict | None = None


@app.post("/api/households/{hid}/plan/decision")
def plan_decision(hid: str, body: DecisionBody, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    if not st["pending"]:
        raise HTTPException(409, "no pending remittance")
    try:
        st = e.decide(hid, st, "skip" if body.decision == "skip" else body.decision, body.plan)
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    e.save(hid, st)
    with SessionLocal() as s:
        s.add(Decision(household_id=hid, day=st["day"], decision=body.decision, plan=body.plan or {}))
        s.commit()
    db.audit(w.role, f"decision:{body.decision}", hid, dict(plan=body.plan))
    return _stamp(_public_state(hid, st))


# ---------------- goals ----------------
class GoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    target: float = Field(gt=0, le=10_000_000)
    days: int = Field(180, ge=14, le=1500)
    priority: int = Field(2, ge=1, le=3)


@app.post("/api/households/{hid}/goals")
def add_goal(hid: str, body: GoalIn, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    name = explain.sanitize_text(body.name)
    with SessionLocal() as s:
        g = GoalRow(household_id=hid, name=name, target=body.target, deadline_day=st["day"] + body.days,
                    priority=body.priority)
        s.add(g)
        s.commit()
    db.audit(w.role, "goal_add", hid, dict(name=name, target=body.target))
    cycles = max(body.days / max(float(e.h.loc[hid, "gap_mean"]), 7.0), 1.0)
    per_cycle = body.target / cycles
    _, net, _ = e.usual_needs(hid, st)
    feasible = per_cycle <= 0.4 * float(e.h.loc[hid, "typical_amount"])
    return dict(ok=True, name=name, per_transfer_needed=round(per_cycle), feasible=feasible,
                note=None if feasible else "This goal needs a large share of each transfer; consider a longer deadline.")


@app.delete("/api/households/{hid}/goals/{gid}")
def del_goal(hid: str, gid: int, w: Who = Depends(family_or_admin)):
    _check(hid)
    with SessionLocal() as s:
        g = s.get(GoalRow, gid)
        if not g or g.household_id != hid:
            raise HTTPException(404, "goal not found")
        s.delete(g)
        s.commit()
    db.audit(w.role, "goal_delete", hid, dict(id=gid))
    return dict(ok=True)


# ---------------- consent ----------------
def _consent_view(hid: str, sid: str) -> dict:
    with SessionLocal() as s:
        link = s.get(SenderLink, (hid, sid))
        scopes = {c.scope: c.state for c in s.query(Consent).filter(Consent.household_id == hid, Consent.sender_id == sid)}
    return dict(sender_id=sid, sender_accepted=bool(link and link.sender_accepted), scopes=scopes,
                default_scope=DEFAULT_SCOPE)


@app.get("/api/households/{hid}/consent")
def get_consent(hid: str, w: Who = Depends(family_or_admin)):
    _check(hid)
    _ensure_link(hid)
    return _consent_view(hid, f"S-{hid}")


class ConsentUpdate(BaseModel):
    scope: str
    state: str = Field(pattern="^(granted|revoked)$")


@app.post("/api/households/{hid}/consent")
def set_consent(hid: str, body: ConsentUpdate, w: Who = Depends(family_or_admin)):
    _check(hid)
    if body.scope not in SCOPES:
        raise HTTPException(400, "unknown scope")
    sid = f"S-{hid}"
    with SessionLocal() as s:
        c = s.get(Consent, (hid, sid, body.scope))
        c.state = body.state
        c.updated_at = db.now()
        s.commit()
    db.audit(w.role, f"consent:{body.state}", hid, dict(scope=body.scope))
    return _consent_view(hid, sid)


# ---------------- sender ----------------
def sender_only(sid: str, w: Who = Depends(who)) -> Who:
    if w.role == "admin" or (w.role == "sender" and w.user == sid):
        return w
    raise HTTPException(403, "not allowed for this sender")


def _hid_of(sid: str) -> str:
    hid = sid[2:] if sid.startswith("S-") else ""
    if hid not in _eng().h.index:
        raise HTTPException(404, "unknown sender")
    return hid


@app.post("/api/sender/{sid}/accept")
def sender_accept(sid: str, w: Who = Depends(sender_only)):
    hid = _hid_of(sid)
    with SessionLocal() as s:
        link = s.get(SenderLink, (hid, sid))
        link.sender_accepted = True
        s.commit()
    db.audit(w.role, "sender_accept", hid)
    return _consent_view(hid, sid)


@app.get("/api/sender/{sid}/goals")
def sender_goals(sid: str, w: Who = Depends(sender_only)):
    """Consent-filtered. Returns goal progress ONLY (never transactions or balances)."""
    hid = _hid_of(sid)
    view = _consent_view(hid, sid)
    allowed = view["sender_accepted"] and view["scopes"].get("goal_progress") == "granted"
    out = dict(consent=view, goals=[], savings_total=None)
    if allowed:
        e = _eng()
        st = e.get(hid)
        out["goals"] = [dict(name=g.name, pct=round(100 * min(g.current / g.target, 1.0), 1) if g.target else 0,
                             on_track=_on_track(g)) for g in e.goals_list(hid, st)]
        if view["scopes"].get("savings_total") == "granted":
            out["savings_total"] = round(st["buffer"] + sum(st["goals"].values()))
    else:
        out["message"] = "The family has not shared goal progress with you yet."
    return out


def _on_track(g: allocator.Goal) -> bool:
    # linear pace: remaining must fit in remaining time at an assumed 1 contribution/month
    return g.current >= 0.0 and (g.target - g.current) / max(g.days_left / 30.0, 1.0) <= 0.5 * g.target


class Intent(BaseModel):
    in_days: int = Field(ge=1, le=90)
    amount: float = Field(gt=0, le=1_000_000)


@app.post("/api/sender/{sid}/intent")
def sender_intent(sid: str, body: Intent, w: Who = Depends(sender_only)):
    hid = _hid_of(sid)
    if not _consent_view(hid, sid)["sender_accepted"]:
        raise HTTPException(403, "accept the link first")
    e = _eng()
    st = e.get(hid)
    st["sender_intent"] = dict(day=st["day"] + body.in_days, amount=body.amount)
    e.save(hid, st)
    db.audit(w.role, "sender_intent", hid, body.model_dump())
    return dict(ok=True, note="The family's forecast now reflects your planned transfer (a heuristic, not a promise).")


class VisReq(BaseModel):
    scope: str


@app.post("/api/sender/{sid}/request")
def request_more(sid: str, body: VisReq, w: Who = Depends(sender_only)):
    hid = _hid_of(sid)
    if body.scope not in SCOPES:
        raise HTTPException(400, "unknown scope")
    with SessionLocal() as s:
        c = s.get(Consent, (hid, sid, body.scope))
        if c.state != "granted":
            c.state = "requested"
            c.updated_at = db.now()
        s.commit()
    db.audit(w.role, "visibility_request", hid, dict(scope=body.scope))
    return _consent_view(hid, sid)


# ---------------- explanation ----------------
@app.get("/api/households/{hid}/summary")
def summary(hid: str, type: str = Query("plan", pattern="^(plan|warning|progress)$"),
            lang: str = Query("en", pattern="^(en|bn)$"), w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    if type == "plan":
        opts = e.propose(hid, st)
        if not opts:
            return dict(text="No new remittance to plan right now.", source="template", label="generated explanation",
                        validated=True, source_facts={}, language=lang)
        f = e.arrival_forecast(hid, st["pending"]["seq"])
        facts = dict(plan=opts[1], rem_p50=f["gap_p50"], rem_p90=f["gap_p90"])
    elif type == "warning":
        sf = e.shortfall(hid, st, _threshold())
        if not sf.get("available"):
            raise HTTPException(409, "not enough history yet")
        facts = dict(shortfall={k: sf.get(k) for k in ("prob", "runout_p50", "severity")} | dict(drivers=sf["drivers"]))
    else:
        facts = dict(goals=[dict(name=g.name, pct=round(100 * min(g.current / g.target, 1.0), 1) if g.target else 0)
                            for g in e.goals_list(hid, st)])
    key = f"{hid}:{type}:{lang}:{st['day']}:{hash(json.dumps(facts, sort_keys=True, default=str)) & 0xffffff}"
    with SessionLocal() as s:
        c = s.get(SummaryCache, key)
        if c:
            return dict(text=c.text, source="cache", label="generated explanation", validated=True,
                        source_facts=facts, language=lang)
    res = explain.summarize(type, facts, lang)
    with SessionLocal() as s:
        s.merge(SummaryCache(key=key, text=res["text"]))
        s.commit()
    return _stamp(res)


# ---------------- evaluation / admin ----------------
@app.get("/api/evaluation")
def evaluation():
    p = config.ARTIFACTS / "evaluation.json"
    if not p.exists():
        raise HTTPException(404, "run `python -m app.pipeline` first")
    return json.loads(p.read_text())


@app.get("/api/compare")
def compare(household_id: str | None = None, compliance: float = 0.8):
    p = config.ARTIFACTS / "compare_per_household.json"
    if not p.exists():
        raise HTTPException(404, "run `python -m app.pipeline` first")
    rows = json.loads(p.read_text())
    if household_id:
        rows = [r for r in rows if r["household_id"] == household_id and
                (r["policy"] == "baseline" or abs(r["compliance"] - compliance) < 1e-9)]
    return rows


@app.get("/api/data-card")
def data_card():
    p = config.ARTIFACTS / "data_card.md"
    return dict(markdown=p.read_text() if p.exists() else "")


@app.get("/api/audit")
def audit_log(limit: int = 50, w: Who = Depends(admin_only)):
    with SessionLocal() as s:
        from .db import Audit
        rows = s.query(Audit).order_by(Audit.id.desc()).limit(limit).all()
    return [dict(ts=r.ts.isoformat(), actor=r.actor, action=r.action, household_id=r.household_id,
                 detail=r.detail) for r in rows]
