"""RemitWise API (doc 09 / 21). Real accounts: bearer-token sessions, salted password hashes.

Roles: family (one household), sender (linked household), admin = platform operator (aggregates + demo households only).
Consent is enforced here on the server; sender responses are filtered before serialisation.
"""
from __future__ import annotations

import json
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from pydantic import BaseModel, Field

from . import allocator, auth, config, db, explain
from .db import Consent, Decision, DemoState, Goal as GoalRow, SenderLink, SessionLocal, SummaryCache
from .live import Engine

ENGINE: Engine | None = None
SCOPES = ("goal_progress", "savings_total", "bills_status", "spending_categories")
DEFAULT_SCOPE = "goal_progress"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ENGINE
    with db.locked("startup"):  # several workers start at once: do the one-time set-up one at a time
        db.init_db()
        ENGINE = Engine()
        ENGINE.thr = _threshold()
        for hid in ENGINE.demo_ids:
            _ensure_link(hid)
        auth.seed_demo_accounts(ENGINE)
        auth.purge_expired()
        with SessionLocal() as s:  # households claimed by registered families need their consent rows
            for (hid,) in s.query(db.User.household_id).filter(db.User.role == "family", db.User.household_id.isnot(None)).all():
                _ensure_link(hid)
    yield


app = FastAPI(title="RemitWise API", version="1.0", lifespan=lifespan)


@app.exception_handler(OperationalError)
async def _db_unavailable(request: Request, exc: OperationalError):
    """Database locked or unreachable: a clean, retryable error instead of a crash."""
    return JSONResponse(status_code=503, content=dict(detail="The database is busy or unavailable. Please try again in a moment."), headers={"Retry-After": "2"})


@app.exception_handler(TimeoutError)
async def _busy(request: Request, exc: TimeoutError):
    """Could not get a household lock or a database connection in time: overload, so say "try again", not "crashed"."""
    return JSONResponse(status_code=503, content=dict(detail="The service is busy. Please try again in a moment."), headers={"Retry-After": "2"})


@app.exception_handler(PoolTimeout)
async def _pool_busy(request: Request, exc: PoolTimeout):
    return JSONResponse(status_code=503, content=dict(detail="The service is busy. Please try again in a moment."), headers={"Retry-After": "2"})


@app.exception_handler(Exception)
async def _unexpected(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content=dict(detail="Something went wrong on our side. Please try again."))
# Extra allowed origins (e.g. your Vercel URL) via ALLOWED_ORIGINS="https://a.vercel.app,https://b.com"
_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"] + [
    o.strip().rstrip("/") for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
import re as _re

_LOCK_PATHS = (_re.compile(r"^/api/households/([^/]+)/"), _re.compile(r"^/api/sender/S-([^/]+)/"))


def _lock_name(method: str, path: str) -> str | None:
    """Writes to one household are serialised across workers; sign-up is serialised so two families never get the same household."""
    if method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    if path == "/api/auth/register":
        return "register"
    for rx in _LOCK_PATHS:
        m = rx.match(path)
        if m:
            return "hh:" + m.group(1)
    return None


class WriteLockMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        name = _lock_name(scope["method"], scope["path"]) if scope["type"] == "http" else None
        if name is None:
            return await self.app(scope, receive, send)
        import asyncio
        import time
        end = time.monotonic() + 25.0
        handle = None
        while handle is None:  # poll instead of blocking a worker thread and a database connection on the lock
            handle = await run_in_threadpool(db.try_acquire_lock, name)
            if handle is None:
                if time.monotonic() > end:
                    return await JSONResponse(status_code=503, content=dict(detail="This household is busy. Please try again in a moment."),
                                              headers={"Retry-After": "1"})(scope, receive, send)
                await asyncio.sleep(0.02)
        try:
            await self.app(scope, receive, send)
        finally:
            await run_in_threadpool(db.release_lock, handle)


app.add_middleware(WriteLockMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=_ORIGINS, allow_methods=["*"], allow_headers=["*"])


# ---------------- auth ----------------
class Who(BaseModel):
    role: str
    user: str  # family: household id; sender: "S-<household>"; admin: ""
    uid: int = 0


def who(authorization: str | None = Header(None)) -> Who:
    user = auth.user_from_token(auth.bearer(authorization))
    if user is None:
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    if user.role == "family":
        return Who(role="family", user=user.household_id or "", uid=user.id)
    if user.role == "sender":
        return Who(role="sender", user=f"S-{user.household_id}", uid=user.id)
    return Who(role="admin", user="", uid=user.id)


def family_or_admin(hid: str, w: Who = Depends(who)) -> Who:
    """A family user for their own household; an admin only for the seeded demo households."""
    if w.role == "family" and w.user == hid:
        return w
    if w.role == "admin" and hid in _eng().demo_ids:
        return w
    raise HTTPException(403, "not allowed for this household")


def admin_only(w: Who = Depends(who)) -> Who:
    if w.role != "admin":
        raise HTTPException(403, "admin only")
    return w


def _demo_only(hid: str):
    if hid not in _eng().demo_ids:
        raise HTTPException(403, "demo households only")


def _eng() -> Engine:
    assert ENGINE is not None
    return ENGINE


def _check(hid: str):
    e = _eng()
    if hid not in e.h.index:
        raise HTTPException(404, "unknown household")
    e.ensure(hid)


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
def households(w: Who = Depends(who)):
    e = _eng()
    if w.role == "admin":
        return [e.profile(h) for h in e.demo_ids]
    hid = w.user if w.role == "family" else w.user[2:]
    return [e.profile(hid)] if hid in e.h.index else []


def _public_state(hid: str, st: dict) -> dict:
    e = _eng()
    goals = e.goals_list(hid, st)
    mean_ess, net, local = e.usual_needs(hid, st)
    return dict(
        household_id=hid, day=st["day"], date=_date(st["day"]), spendable=round(st["spendable"]),
        buffer=round(st["buffer"]), vault=round(st["vault"]), bills_monthly=round(e.bills_monthly(hid, st)), goals_total=round(sum(st["goals"].values())),
        debt=round(st["debt"]), bills_due=st["bills_due"], bills_on_time=st["bills_on_time"],
        late_fees=round(st["late_fees"]), fees_avoided=round(st["fees_avoided"]),
        anomalies_caught=st["anomalies_caught"], overbilling_avoided=round(st["overbilling_avoided"]),
        shortfall_days=st["shortfall_days"], pending=st["pending"], adherent=st["adherent"],
        goals=[dict(id=g.id, name=g.name, target=round(g.target), current=round(g.current),
                    pct=round(100 * min(g.current / g.target, 1.0), 1) if g.target else 0,
                    days_left=round(g.days_left), priority=g.priority, shared=_goal_shared(g.id),
                    pace=e.goal_pace(hid, st, g)) for g in goals],
        history=st["history"][-60:], log=st["log"][-12:], daily_needs=round(mean_ess), monthly_needs=round(mean_ess * 30),
        retained_share=round(st["retained_amt"] / st["total_amt"], 3) if st["total_amt"] else None,
        sender_intent=st.get("sender_intent"),
    )


def _goal_shared(gid: str) -> bool:
    with SessionLocal() as s:
        g = s.get(GoalRow, int(gid))
        return bool(g.shared) if g is not None and g.shared is not None else True


def _date(day: int) -> str:
    import pandas as pd
    return (pd.Timestamp(config.START_DATE) + pd.Timedelta(days=int(day))).strftime("%Y-%m-%d")


class MicroIn(BaseModel):
    enabled: bool
    mode: str | None = Field(None, max_length=12)
    target: str | None = Field(None, max_length=40)
    consent: bool = False
    yield_consent: bool = False


class YieldWithdraw(BaseModel):
    amount: float | None = Field(None, gt=0, le=10_000_000)  # empty = everything


@app.get("/api/households/{hid}/micro")
def get_micro(hid: str, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    return _stamp(e.micro_view(hid, e.get(hid)))


@app.post("/api/households/{hid}/micro")
def set_micro(hid: str, body: MicroIn, w: Who = Depends(family_or_admin)):
    """Consent-based micro-savings: off by default; the family must switch it on and can switch it off any time."""
    _check(hid)
    e = _eng()
    st = e.get(hid)
    try:
        st = e.set_micro(hid, st, body.enabled, body.mode, body.target, body.consent, body.yield_consent)
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    e.save(hid, st)
    db.audit(w.role, "micro_savings_on" if body.enabled else "micro_savings_off", hid, dict(mode=st["micro_mode"], target=st["micro_target"]))
    return _stamp(e.micro_view(hid, st))


@app.post("/api/households/{hid}/micro/yield/withdraw")
def withdraw_yield(hid: str, body: YieldWithdraw, w: Who = Depends(family_or_admin)):
    """Move money out of the SIMULATED yield pot back to the wallet. No lock-in, no fee."""
    _check(hid)
    e = _eng()
    st = e.get(hid)
    try:
        st = e.withdraw_yield(hid, st, body.amount)
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    e.save(hid, st)
    db.audit(w.role, "yield_withdrawn", hid, dict(amount=body.amount))
    return _stamp(e.micro_view(hid, st))


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
    kind: str = Field(max_length=30)
    value: float = Field(0.0, ge=0, le=10_000_000)  # a negative expense would create money


@app.post("/api/households/{hid}/scenario")
def scenario(hid: str, body: Scenario, w: Who = Depends(admin_only)):
    _check(hid)
    _demo_only(hid)
    e = _eng()
    st = e.get(hid)
    try:
        st = e.scenario(hid, st, body.kind, body.value)
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    e.save(hid, st)
    db.audit(w.role, "scenario", hid, body.model_dump())
    return _stamp(_public_state(hid, st))


class GuidedStep(BaseModel):
    step: int = Field(ge=1, le=5)


@app.post("/api/households/{hid}/demo/step")
def guided_step(hid: str, body: GuidedStep, w: Who = Depends(admin_only)):
    """Guided demo: runs one step of remittance -> allocation -> unusual bill -> warning -> resolution."""
    _check(hid)
    _demo_only(hid)
    e = _eng()
    st = e.get(hid)
    try:
        st, info = e.guided_step(hid, st, body.step, _threshold())
    except ValueError as ex:
        raise HTTPException(409, str(ex))
    e.save(hid, st)
    db.audit(w.role, "guided_demo_step", hid, dict(step=body.step))
    return _stamp(dict(info, step=body.step, state=_public_state(hid, st)))


@app.post("/api/households/{hid}/reset")
def reset(hid: str, w: Who = Depends(admin_only)):
    _check(hid)
    _demo_only(hid)
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
    bills: float = 0.0
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
    plan = allocator.custom_plan(st["pending"]["got"], body.needs, body.savings, body.goals, body.bills)
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
    if w.role == "sender" and w.user == sid:
        return w
    if w.role == "admin" and sid.startswith("S-") and sid[2:] in _eng().demo_ids:
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
    out = dict(consent=view, goals=[], savings_total=None, bills=None, today=_date(_eng().get(hid)["day"]))
    if view["sender_accepted"] and view["scopes"].get("bills_status") == "granted":
        sv = _eng().sender_view(hid, _eng().get(hid))
        out["bills"] = dict(status=sv["bills_status"], at_risk_count=sv["at_risk_count"], review_count=sv["review_count"], send_by=sv["send_by"],
                            paid_count=sv["paid_count"], total_count=sv["total_count"],
                            scheduled_from_vault=sv["vault_scheduled"], shortfall_date=sv["shortfall_date"],
                            suggested_amount=sv["suggested_amount"], next_expected=sv["next_expected"],
                            family_asked=sv["asked"])
    if view["sender_accepted"]:
        out["recent_transfers"] = _recent_transfers(hid, view["scopes"].get("bills_status") == "granted")
    if allowed:
        e = _eng()
        st = e.get(hid)
        out["goals"] = [dict(name=g.name, pct=round(100 * min(g.current / g.target, 1.0), 1) if g.target else 0,
                             on_track=_on_track(g)) for g in e.goals_list(hid, st) if _goal_shared(g.id)]
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
def summary(hid: str, type: str = Query("plan", pattern="^(plan|warning|progress|monthly)$"),
            lang: str = Query("en", pattern="^(en|bn)$"), w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    if type == "plan":
        opts = e.propose(hid, st)
        if not opts:
            return dict(text="এখন পরিকল্পনা করার মতো নতুন রেমিট্যান্স নেই।" if lang == "bn" else "No new remittance to plan right now.", source="template", label="generated explanation",
                        validated=True, source_facts={}, language=lang)
        f = e.arrival_forecast(hid, st["pending"]["seq"])
        facts = dict(plan=opts[1], rem_p50=f["gap_p50"], rem_p90=f["gap_p90"])
    elif type == "warning":
        sf = e.shortfall(hid, st, _threshold())
        if not sf.get("available"):
            raise HTTPException(409, "not enough history yet")
        facts = dict(shortfall={k: sf.get(k) for k in ("prob", "runout_p50", "severity")} | dict(drivers=sf["drivers"]))
    elif type == "monthly":
        facts = dict(month=_month_facts(e, hid, st))
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
        rows = s.query(Audit).order_by(Audit.id.desc()).limit(limit * 4).all()
    demo = _eng().demo_ids  # judges never see registered families' activity
    rows = [r for r in rows if r.household_id in demo or r.household_id is None][:limit]
    return [dict(ts=r.ts.isoformat(), actor=r.actor, action=r.action, household_id=r.household_id,
                 detail=r.detail if r.household_id in demo else None) for r in rows]


def _month_facts(e: Engine, hid: str, st: dict) -> dict:
    due = max(st["bills_due"], 0)
    pct = round(100 * st["bills_on_time"] / due) if due else 100
    unused = [x for x in e.goals_list(hid, st)]
    suggestion = "keep the bill vault funded first when a transfer arrives."
    if st["shortfall_days"] > 0:
        suggestion = "set a small daily spending limit in the week before the next transfer."
    out = dict(on_time_pct=pct, late_fees_avoided=round(st["fees_avoided"]),
               savings_built=round(st["buffer"] + sum(st["goals"].values()) + st["yield_balance"]),
               suggestion=suggestion)
    if st.get("micro_on") or st.get("micro_total"):
        out["micro_saved"] = round(e.micro_month_total(st))
    return out


# ---------------- Home / Plan / Payments / Goals / Insights (family app) ----------------
@app.get("/api/households/{hid}/home")
def home(hid: str, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    return _stamp(e.home(hid, st, _threshold()))


@app.get("/api/households/{hid}/bills")
def bills_list(hid: str, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    cards = e.bill_cards(hid, st, 45, 35)
    for c in cards:
        c.pop("true_amount", None)
    defs = [dict(bill_id=b["bill_id"], name=b["name"], kind=b["kind"], usual=round(b["usual"]),
                 variable=b["variable"], due_dom=b["due_dom"], **{k: v for k, v in e._cfg(st, b["bill_id"]).items()})
            for b in e._defs(hid, st).values() if e._cfg(st, b["bill_id"])["active"]]
    return _stamp(dict(items=cards, mandates=defs, today=_date(st["day"]), today_day=st["day"],
                       vault=round(st["vault"]), late_fees=round(st["late_fees"])))


class AutopayIn(BaseModel):
    on: bool


@app.post("/api/households/{hid}/bills/{bill_id}/autopay")
def bills_autopay(hid: str, bill_id: str, body: AutopayIn, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    try:
        st = e.set_autopay(hid, st, bill_id, body.on)
    except ValueError as ex:
        raise HTTPException(404, str(ex))
    e.save(hid, st)
    db.audit(w.role, "autopay", hid, dict(bill_id=bill_id, on=body.on))
    return dict(ok=True)


class MandateIn(BaseModel):
    biller: str = Field(min_length=2, max_length=40)
    kind: str = Field("utility", pattern="^(utility|emi|school|other)$")
    account_number: str = Field(min_length=4, max_length=24)
    usual_amount: float = Field(gt=0, le=1_000_000)
    due_day: int = Field(ge=1, le=28)
    monthly_limit: float = Field(gt=0, le=10_000_000)
    confirm_over_limit: bool = True


@app.post("/api/households/{hid}/bills/mandates")
def bills_add_mandate(hid: str, body: MandateIn, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    st = e.add_mandate(hid, st, explain.sanitize_text(body.biller), body.kind, body.usual_amount, body.due_day,
                       body.monthly_limit, body.confirm_over_limit, body.account_number)
    e.save(hid, st)
    db.audit(w.role, "mandate_add", hid, dict(biller=body.biller, limit=body.monthly_limit))
    return dict(ok=True)


@app.delete("/api/households/{hid}/bills/mandates/{bill_id}")
def bills_remove_mandate(hid: str, bill_id: str, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    st = e.remove_mandate(hid, st, bill_id)
    e.save(hid, st)
    db.audit(w.role, "mandate_cancel", hid, dict(bill_id=bill_id))
    return dict(ok=True)


class ResolveIn(BaseModel):
    action: str = Field(pattern="^(approve|dispute|pay_manually)$")


@app.post("/api/households/{hid}/bills/resolve")
def bills_resolve(hid: str, key: str, body: ResolveIn, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    try:
        st = e.resolve_bill(hid, st, key, body.action)
    except ValueError as ex:
        raise HTTPException(409, str(ex))
    e.save(hid, st)
    db.audit(w.role, f"bill:{body.action}", hid, dict(key=key))
    return _stamp(_public_state(hid, st))


@app.get("/api/households/{hid}/plan/projection")
def plan_projection(hid: str, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    p = e.projection(hid, st)
    if p is None:
        raise HTTPException(409, "not enough history yet")
    return _stamp(p)


@app.get("/api/households/{hid}/plan/categories")
def plan_categories(hid: str, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    return e.categories(hid, e.get(hid))


@app.get("/api/households/{hid}/plan/options")
def plan_options(hid: str, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    return _stamp(dict(options=e.options(hid, e.get(hid), _threshold())))


class OptionIn(BaseModel):
    option: str = Field(pattern="^(move_from_goals|ask_sender)$")


@app.post("/api/households/{hid}/plan/options/apply")
def plan_option_apply(hid: str, body: OptionIn, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    try:
        st = e.apply_option(hid, st, body.option, _threshold())
    except ValueError as ex:
        raise HTTPException(409, str(ex))
    e.save(hid, st)
    db.audit(w.role, f"option:{body.option}", hid)
    return _stamp(_public_state(hid, st))


class ShareIn(BaseModel):
    shared: bool


@app.post("/api/households/{hid}/goals/{gid}/share")
def goal_share(hid: str, gid: int, body: ShareIn, w: Who = Depends(family_or_admin)):
    _check(hid)
    with SessionLocal() as s:
        g = s.get(GoalRow, gid)
        if not g or g.household_id != hid:
            raise HTTPException(404, "goal not found")
        g.shared = body.shared
        s.commit()
    db.audit(w.role, "goal_share", hid, dict(id=gid, shared=body.shared))
    return dict(ok=True, shared=body.shared)


class SuggestIn(BaseModel):
    target: float = Field(gt=0, le=10_000_000)
    days: int = Field(180, ge=14, le=1500)


@app.post("/api/households/{hid}/goals/suggest")
def goal_suggest(hid: str, body: SuggestIn, w: Who = Depends(family_or_admin)):
    """A realistic monthly amount from the forecast: half of the expected monthly surplus."""
    _check(hid)
    e = _eng()
    st = e.get(hid)
    f = e.current_forecast(hid, st)
    mean_ess, net, local = e.usual_needs(hid, st)
    gap = f["gap_p50"] if f else float(e.h.loc[hid, "gap_mean"])
    amt = f["amt_p50"] if f else float(e.h.loc[hid, "typical_amount"])
    income_month = amt * 30.0 / max(gap, 7.0) + local * 30.0
    spend_month = mean_ess * 30.0 + e.bills_monthly(hid, st)
    surplus = max(income_month - spend_month, 0.0)
    suggested = round(0.5 * surplus, -1)
    wanted = body.target / max(body.days / 30.0, 1.0)
    months = body.target / suggested if suggested > 0 else None
    return _stamp(dict(suggested_monthly=suggested, needed_monthly=round(wanted),
                       months_at_suggested=round(months, 1) if months else None,
                       realistic=bool(suggested and wanted <= suggested * 1.1),
                       explanation="Half of your expected monthly surplus, so there is room for surprises."))


@app.get("/api/households/{hid}/insights")
def insights(hid: str, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    due = st["bills_due"]
    fc = None
    try:
        import pandas as pd
        feat = e.ff[hid][st["last_seq"]]
        fc = e.model.drivers(pd.DataFrame([feat]), top=5)
    except Exception:
        pass
    sf = e.shortfall(hid, st, _threshold())
    return _stamp(dict(
        on_time_rate=round(st["bills_on_time"] / due, 3) if due else None, bills_due=due,
        late_fees_paid=round(st["late_fees"]), late_fees_avoided=round(st["fees_avoided"]),
        anomalies_caught=st["anomalies_caught"], overbilling_avoided=round(st["overbilling_avoided"]),
        savings_built=round(st["buffer"] + sum(st["goals"].values())),
        forecast_drivers=fc or [], warning_drivers=sf.get("drivers", []) if sf.get("available") else []))


def _recent_transfers(hid: str, with_split: bool) -> list[dict]:
    """The sender's own recent transfers (date, amount). The split is shown only if the family shares bills status."""
    e = _eng()
    st = e.get(hid)
    ev = e.ev[hid]
    past = ev[ev.day <= st["day"]].tail(3).iloc[::-1]
    with SessionLocal() as s:
        decisions = {d.day: d.plan for d in s.query(Decision).filter(Decision.household_id == hid).all()}
    out = []
    for r in past.itertuples():
        item = dict(date=_date(r.day), amount=round(float(r.amount)))
        plan = decisions.get(int(r.day))
        if with_split and plan:
            item["split"] = dict(bills=round(plan.get("bills", 0)), needs=round(plan.get("needs", 0)),
                                 savings=round(plan.get("savings", 0) + sum((plan.get("goals") or {}).values())))
        out.append(item)
    return out


@app.get("/api/households/{hid}/bills/history")
def bills_history(hid: str, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    h = e.bill_history(hid, e.get(hid))
    if h is None:
        raise HTTPException(404, "no variable bills")
    return h


class AddMoneyIn(BaseModel):
    amount: float = Field(gt=0, le=10_000_000)


@app.post("/api/households/{hid}/goals/{gid}/add_money")
def goal_add_money(hid: str, gid: int, body: AddMoneyIn, w: Who = Depends(family_or_admin)):
    _check(hid)
    e = _eng()
    st = e.get(hid)
    try:
        st = e.add_money(hid, st, str(gid), body.amount)
    except ValueError as ex:
        raise HTTPException(409, str(ex))
    e.save(hid, st)
    db.audit(w.role, "goal_add_money", hid, dict(id=gid, amount=body.amount))
    return _stamp(_public_state(hid, st))


# ---------------- accounts ----------------
class RegisterIn(BaseModel):
    role: str = Field(pattern="^(family|sender)$")  # admins are provisioned, never self-registered
    name: str = Field(min_length=2, max_length=60)
    email: str = Field(max_length=120)
    password: str = Field(min_length=1, max_length=128)
    invite_code: str | None = Field(None, max_length=16)
    access_code: str | None = Field(None, max_length=64)
    sender_city: str | None = Field(None, max_length=40)


class LoginIn(BaseModel):
    email: str = Field(max_length=120)
    password: str = Field(max_length=128)


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@app.get("/api/auth/config")
def auth_config():
    """Public: what the sign-in page may offer. Demo family/sender accounts exist only when seeding is enabled.
    The admin account is never advertised here."""
    e = _eng()
    demos = []
    if config.SEED_DEMO_ACCOUNTS:
        first = next(iter(e.demo_ids.items()))
        sn = e.default_sender_name(first[0])
        demos = [dict(label=f"Family · {first[1]}", email=f"{first[1].lower()}@demo.remitwise", password=config.DEMO_PASSWORD),
                 dict(label=f"Sender · {sn}", email=f"{sn.lower()}@demo.remitwise", password=config.DEMO_PASSWORD)]
    return dict(demo_accounts=demos)


@app.post("/api/auth/register")
def register(body: RegisterIn, request: Request):
    e = _eng()
    email = auth.normalize_email(body.email)
    auth.check_password_policy(body.password, email)
    name = explain.sanitize_text(body.name, 60)
    if len(name) < 2:
        raise HTTPException(422, "Please enter your name.")
    with SessionLocal() as s:
        if s.query(db.User).filter(db.User.email == email).first():
            raise HTTPException(409, "An account with this email already exists. Try signing in.")
        hid, code, city = None, None, None
        if body.role == "family":
            taken = {h for (h,) in s.query(db.User.household_id).filter(db.User.household_id.isnot(None)).all()}
            pool = e.eligible(taken)
            if not pool:
                raise HTTPException(503, "No demo households are free right now.")
            hid, code = pool[0], auth.invite_code()
            city = explain.sanitize_text(body.sender_city, 40) if body.sender_city else None
        elif body.role == "sender":
            fam = s.query(db.User).filter(db.User.role == "family", db.User.invite_code == (body.invite_code or "").strip().upper()).first() if body.invite_code else None
            if not fam:
                raise HTTPException(400, "That invite code was not found. Ask your family for the code shown in their app.")
            hid = fam.household_id
        u = db.User(email=email, name=name, password_hash=auth.hash_password(body.password), role=body.role,
                    household_id=hid, sender_city=city, invite_code=code, is_demo=False)
        s.add(u)
        s.commit()
        s.refresh(u)
    if hid:
        _ensure_link(hid)
    token = auth.create_session(u.id)
    db.audit(body.role, "register", hid, dict(user_id=u.id))
    return dict(token=token, user=auth.public_user(u))


@app.post("/api/auth/login")
def login(body: LoginIn, request: Request):
    u = auth.authenticate(body.email, body.password, _client(request))
    token = auth.create_session(u.id)
    db.audit(u.role, "login", u.household_id, dict(user_id=u.id))
    return dict(token=token, user=auth.public_user(u))


@app.get("/api/auth/me")
def me(authorization: str | None = Header(None)):
    u = auth.user_from_token(auth.bearer(authorization))
    if u is None:
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    return dict(user=auth.public_user(u))


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(None)):
    auth.delete_session(auth.bearer(authorization))
    return dict(ok=True)


# ---------------- signed transaction webhooks (MFS core-banking adapter) ----------------
class TxEvent(BaseModel):
    event_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_\-.:]+$")
    type: str = Field(pattern="^(remittance_received|cash_out|bill_paid)$")
    household_id: str = Field(min_length=1, max_length=16)
    amount: float = Field(gt=0, le=10_000_000)
    currency: str = Field("BDT", pattern="^BDT$")
    bill_name: str | None = Field(None, max_length=60)
    occurred_at: str | None = Field(None, max_length=40)
    reference: str | None = Field(None, max_length=64)


def verify_webhook_signature(raw: bytes, timestamp: str | None, signature: str | None) -> None:
    """Signature = hex HMAC-SHA256(secret, f"{timestamp}.{raw body}"). Rejects stale timestamps (replays)."""
    import hashlib
    import hmac
    import time
    if not config.WEBHOOK_SECRET:
        raise HTTPException(503, "Webhooks are not enabled on this server.")
    try:
        ts = int(timestamp or "")
    except ValueError:
        raise HTTPException(401, "Invalid signature.")
    if abs(time.time() - ts) > config.WEBHOOK_TOLERANCE_SECONDS:
        raise HTTPException(401, "Invalid signature.")
    expected = hmac.new(config.WEBHOOK_SECRET.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(expected, signature.strip()):
        raise HTTPException(401, "Invalid signature.")


@app.post("/api/webhooks/transactions")
async def transaction_webhook(request: Request, x_rw_signature: str | None = Header(None), x_rw_timestamp: str | None = Header(None)):
    """Real MFS events (remittance received, cash-out, bill paid) in; the same internal events the simulator makes out."""
    raw = await request.body()
    verify_webhook_signature(raw, x_rw_timestamp, x_rw_signature)
    try:
        ev = TxEvent.model_validate_json(raw)
    except Exception:
        raise HTTPException(400, "Invalid event payload.")
    _check(ev.household_id)
    return await run_in_threadpool(_apply_webhook, ev)


def _apply_webhook(ev: "TxEvent") -> dict:
    from sqlalchemy.exc import IntegrityError
    e = _eng()
    with db.locked("hh:" + ev.household_id):  # same lock as every other write to this household
        with SessionLocal() as s:  # claim the event id first: the primary key makes "applied once" safe under concurrency
            s.add(db.WebhookEvent(event_id=ev.event_id, type=ev.type, household_id=ev.household_id))
            try:
                s.commit()
            except IntegrityError:
                return dict(ok=True, duplicate=True, event_id=ev.event_id)
        st = e.get(ev.household_id)
        try:
            st = e.apply_external(ev.household_id, st, ev.type, ev.amount, ev.bill_name)
        except ValueError as ex:
            with SessionLocal() as s:  # a rejected event may be retried after it is fixed
                s.query(db.WebhookEvent).filter(db.WebhookEvent.event_id == ev.event_id).delete()
                s.commit()
            raise HTTPException(409, str(ex))
        e.save(ev.household_id, st)
    db.audit("webhook", "tx_" + ev.type, ev.household_id, dict(event_id=ev.event_id, amount=ev.amount))
    return dict(ok=True, duplicate=False, event_id=ev.event_id, pending_plan=bool(st["pending"]))


# ---------------- email security codes and password reset ----------------
class CodeIn(BaseModel):
    code: str = Field(max_length=12)


class ResetRequestIn(BaseModel):
    email: str = Field(max_length=120)


class ResetConfirmIn(BaseModel):
    email: str = Field(max_length=120)
    code: str = Field(max_length=12)
    new_password: str = Field(min_length=1, max_length=128)


def _me(authorization: str | None) -> db.User:
    u = auth.user_from_token(auth.bearer(authorization))
    if u is None:
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    return u


def _deliver(email: str, code: str, purpose: str, strict: bool) -> dict:
    """Email the code if SMTP is configured; otherwise (demo mode) show it on screen. `strict`: report a failed send
    (account verification). The password-reset flow stays silent about failures so it cannot reveal which accounts exist."""
    from . import mailer
    emailed = False
    if mailer.configured():
        try:
            emailed = mailer.send_code(email, code, purpose)
        except mailer.MailError:
            if strict:
                raise HTTPException(502, "We could not send the email right now. Please try again in a moment.")
    elif not config.OTP_DEMO_MODE:
        raise HTTPException(503, "Email delivery is not configured on this server.")
    if not strict:
        emailed = mailer.configured()  # identical to the reply for unknown addresses, even if the send failed
    out = dict(sent=True, expires_in=config.OTP_TTL_SECONDS, to=auth.mask_email(email), emailed=emailed)
    if config.OTP_DEMO_MODE:
        out.update(demo_code=code, note="Demo mode: the code is shown here instead of being emailed." if not emailed else "Demo mode: the code is also shown here.")
    return out


@app.post("/api/auth/otp/request")
def otp_request(authorization: str | None = Header(None)):
    """Send a 6-digit security code to the signed-in account's email address."""
    u = _me(authorization)
    if u.is_demo or u.email_verified:
        raise HTTPException(400, "This email address is already verified.")
    code = auth.issue_otp(u.id, "verify_email")
    db.audit(u.role, "email_code_requested", u.household_id, dict(user_id=u.id))
    return _deliver(u.email, code, "verify_email", strict=True)


@app.post("/api/auth/otp/verify")
def otp_verify(body: CodeIn, authorization: str | None = Header(None)):
    u = _me(authorization)
    auth.check_otp(u.id, "verify_email", body.code)
    with SessionLocal() as s:
        row = s.get(db.User, u.id)
        row.email_verified = True
        s.commit()
        s.refresh(row)
    db.audit(u.role, "email_verified", u.household_id, dict(user_id=u.id))
    return dict(ok=True, user=auth.public_user(row))


@app.post("/api/auth/reset/request")
def reset_request(body: ResetRequestIn, request: Request):
    """Same answer whether or not the account exists, so this cannot be used to discover accounts."""
    ident = body.email.strip().lower()
    auth.check_rate("reset:" + ident, _client(request))
    auth.record_fail("reset:" + ident, _client(request))  # every request counts toward the sign-in style limit
    auth.limit_otp_requests("reset-req:" + ident)  # identical limit for real and unknown addresses
    u = auth.find_for_reset(ident)
    code = f"{secrets.randbelow(10**6):06d}"  # unknown addresses get a lookalike code that never works
    target = ident
    if u:
        try:
            code = auth.issue_otp(u.id, "reset")
        except HTTPException as ex:
            if ex.status_code != 429:
                raise
        db.audit(u.role, "reset_requested", u.household_id, dict(user_id=u.id))
    if u:
        out = _deliver(u.email, code, "reset", strict=False)
    else:
        out = _deliver_dummy(target, code)
    out["message"] = "If an account matches, a code has been sent to that email address."
    return out


def _deliver_dummy(email: str, code: str) -> dict:
    """What an unknown address gets: the same reply shape and timing class, and nothing is sent."""
    from . import mailer
    if not mailer.configured() and not config.OTP_DEMO_MODE:
        raise HTTPException(503, "Email delivery is not configured on this server.")
    out = dict(sent=True, expires_in=config.OTP_TTL_SECONDS, to=auth.mask_email(email) if "@" in email else "***", emailed=mailer.configured())
    if config.OTP_DEMO_MODE:
        out.update(demo_code=code, note="Demo mode: the code is shown here instead of being emailed.")
    return out


@app.post("/api/auth/reset/confirm")
def reset_confirm(body: ResetConfirmIn, request: Request):
    ident = body.email.strip().lower()
    key = "reset-confirm:" + ident
    auth.check_rate(key, _client(request))
    u = auth.find_for_reset(ident)
    if u is None:
        auth.record_fail(key, _client(request))
        raise HTTPException(400, "That code is invalid or has expired. Request a new one.")
    try:
        auth.check_otp(u.id, "reset", body.code)
    except HTTPException:
        auth.record_fail(key, _client(request))
        raise
    auth.check_password_policy(body.new_password, u.email)
    auth.set_password(u.id, body.new_password)
    with SessionLocal() as s:  # receiving the code proves the mailbox is theirs
        row = s.get(db.User, u.id)
        row.email_verified = True
        s.commit()
    auth.clear_fails(key, _client(request))
    db.audit(u.role, "password_reset", u.household_id, dict(user_id=u.id))
    return dict(ok=True, message="Password changed. Sign in with your new password.")


# ---------------- admin console (aggregates only) ----------------
@app.get("/api/admin/overview")
def admin_overview(w: Who = Depends(admin_only)):
    """Platform-level numbers. Individual families' finances are never exposed here."""
    import collections
    from .db import Audit, DemoState
    e = _eng()
    with SessionLocal() as s:
        users = s.query(db.User).all()
        decisions = [d for (d,) in s.query(Decision.decision).all()]
        actions = [a for (a,) in s.query(Audit.action).order_by(Audit.id.desc()).limit(2000).all()]
        rows = s.query(DemoState).all()
    real_hh = {u.household_id for u in users if u.role == "family" and not u.is_demo and u.household_id}
    scope = "registered families" if real_hh else "demo households"
    pool = real_hh or set(e.demo_ids)
    states = [r.state for r in rows if r.household_id in pool]
    week_ago = db.now() - __import__("datetime").timedelta(days=7)
    by_role = collections.Counter(u.role for u in users if not u.is_demo)
    dec = collections.Counter(decisions)
    tot_dec = sum(dec.values())
    agg = dict(bills_due=0, bills_on_time=0, late_fees=0.0, fees_avoided=0.0, anomalies_caught=0, shortfall_days=0)
    for st in states:
        for k in agg:
            agg[k] += st.get(k, 0) or 0
    ev = {}
    p = config.ARTIFACTS / "evaluation.json"
    if p.exists():
        ev = json.loads(p.read_text())
    return dict(
        accounts=dict(families=by_role.get("family", 0), senders=by_role.get("sender", 0), admins=by_role.get("admin", 0),
                      demo_accounts=sum(1 for u in users if u.is_demo), new_last_7_days=sum(1 for u in users if not u.is_demo and u.created_at and u.created_at >= week_ago),
                      disabled=sum(1 for u in users if u.is_active is False)),
        households=dict(total=int(len(e.h)), in_use=len({u.household_id for u in users if u.household_id}), demo=len(e.demo_ids),
                        free=len(e.eligible({u.household_id for u in users if u.household_id}))),
        plans=dict(accepted=dec.get("accept", 0), edited=dec.get("edit", 0), skipped=dec.get("skip", 0),
                   followed_rate=round((dec.get("accept", 0) + dec.get("edit", 0)) / tot_dec, 3) if tot_dec else None),
        bills=dict(scope=scope, paid_on_time_rate=round(agg["bills_on_time"] / agg["bills_due"], 3) if agg["bills_due"] else None, bills_due=agg["bills_due"],
                   late_fees_paid=round(agg["late_fees"]), late_fees_avoided=round(agg["fees_avoided"]),
                   unusual_bills_caught=agg["anomalies_caught"], shortfall_days=agg["shortfall_days"]),
        activity=[dict(action=a, count=c) for a, c in collections.Counter(actions).most_common(8)],
        system=dict(database=config.DATABASE_URL.split(":")[0], llm_configured=bool(config.GROQ_API_KEY), llm_model=config.GROQ_MODEL,
                    model="lightgbm quantile + conformal", data_seed=config.SEED, trained_at=ev.get("generated_at"),
                    households_trained_on=ev.get("dataset", {}).get("households")),
        privacy="Aggregates only. Admins cannot see a registered family's balances, bills or goals.")


def _warning_rate() -> dict:
    """Share of active (in-use) households whose warning is amber or red right now."""
    e = _eng()
    with SessionLocal() as s:
        ids = [h for (h,) in s.query(DemoState.household_id).all()]
    counts = dict(green=0, amber=0, red=0, unavailable=0)
    for hid in ids:
        if hid not in e.h.index:
            continue
        try:
            sf = e.shortfall(hid, e.get(hid), _threshold())
            counts[sf["severity"] if sf.get("available") else "unavailable"] += 1
        except Exception:
            counts["unavailable"] += 1
    n = sum(counts.values())
    return dict(households=n, **counts, rate=round((counts["amber"] + counts["red"]) / n, 3) if n else None)


@app.get("/api/admin/monitoring")
def admin_monitoring(w: Who = Depends(admin_only)):
    from . import monitoring
    return monitoring.cached(_warning_rate)


@app.get("/api/admin/users")
def admin_users(w: Who = Depends(admin_only)):
    with SessionLocal() as s:
        rows = s.query(db.User).order_by(db.User.id.desc()).all()
    return [dict(id=u.id, name=u.name, email=auth.mask_email(u.email), role=u.role, household_id=u.household_id if u.is_demo else None,
                 is_demo=bool(u.is_demo), is_active=u.is_active is not False, joined=u.created_at.date().isoformat() if u.created_at else None)
            for u in rows]


class StatusIn(BaseModel):
    active: bool


def _purge_user(uid: int) -> tuple[str, str | None]:
    """Delete an account, its sessions and codes, and (for the last family of a household) the household's data."""
    with SessionLocal() as s:
        u = s.get(db.User, uid)
        role, hid = u.role, u.household_id
        s.query(db.AuthSession).filter(db.AuthSession.user_id == uid).delete()
        s.query(db.OtpCode).filter(db.OtpCode.user_id == uid).delete()
        if role == "family" and hid and not s.query(db.User).filter(db.User.household_id == hid, db.User.id != uid, db.User.role == "family").count():
            for m in (db.Goal, db.Consent, db.SenderLink, db.Decision, db.DemoState):
                if hasattr(m, "household_id"):
                    s.query(m).filter(m.household_id == hid).delete()
        s.delete(u)
        s.commit()
    return role, hid


@app.delete("/api/admin/users/{uid}")
def admin_user_delete(uid: int, w: Who = Depends(admin_only)):
    if uid == w.uid:
        raise HTTPException(400, "You cannot delete your own account.")
    with SessionLocal() as s:
        u = s.get(db.User, uid)
        if u is None:
            raise HTTPException(404, "user not found")
        if u.is_demo:
            raise HTTPException(400, "Demo accounts cannot be deleted. Disable them instead.")
    role, _ = _purge_user(uid)
    db.audit("admin", "user_deleted", None, dict(user_id=uid, role=role))
    return dict(ok=True, id=uid)


class DeleteMeIn(BaseModel):
    confirm: str = Field(max_length=20)


@app.delete("/api/me")
def delete_me(body: DeleteMeIn, authorization: str | None = Header(None)):
    """Self-service deletion (docs/data-retention.md). Admins and demo accounts are excluded."""
    u = _me(authorization)
    if u.role == "admin" or u.is_demo:
        raise HTTPException(403, "Admin and demo accounts cannot be deleted here.")
    if body.confirm.strip().upper() != "DELETE":
        raise HTTPException(400, "Type DELETE to confirm.")
    role, _ = _purge_user(u.id)
    db.audit(role, "self_deleted", None, dict(user_id=u.id))
    return dict(ok=True)


@app.post("/api/admin/users/{uid}/status")
def admin_user_status(uid: int, body: StatusIn, w: Who = Depends(admin_only)):
    if uid == w.uid:
        raise HTTPException(400, "You cannot disable your own account.")
    with SessionLocal() as s:
        u = s.get(db.User, uid)
        if u is None:
            raise HTTPException(404, "user not found")
        u.is_active = body.active
        if not body.active:  # sign them out everywhere
            s.query(db.AuthSession).filter(db.AuthSession.user_id == uid).delete()
        s.commit()
    db.audit("admin", "user_enabled" if body.active else "user_disabled", None, dict(user_id=uid))
    return dict(ok=True, id=uid, is_active=body.active)
