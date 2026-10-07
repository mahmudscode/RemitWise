"""Database layer. PostgreSQL via DATABASE_URL; SQLite fallback for local runs."""
from __future__ import annotations

import datetime as dt

import pandas as pd
from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, Integer, String, Text, create_engine,
                        text)
from sqlalchemy.orm import declarative_base, sessionmaker

from . import config

_kw = {"future": True}
IS_SQLITE = config.DATABASE_URL.startswith("sqlite")
if IS_SQLITE:
    _kw["connect_args"] = {"check_same_thread": False}
else:  # production-style pool: reuse connections, detect dead ones, bounded per worker (see docs/production-deployment.md)
    _kw.update(pool_size=config.DB_POOL_SIZE, max_overflow=config.DB_MAX_OVERFLOW, pool_pre_ping=True,
               pool_recycle=1800, pool_timeout=config.DB_POOL_TIMEOUT)
engine = create_engine(config.DATABASE_URL, **_kw)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()


# ---- cross-worker locks ----
# Household state is read, changed and saved as a whole, so two requests for the same household must not interleave
# (lost updates) and two sign-ups must not claim the same free household. PostgreSQL advisory locks work across all
# workers and containers; SQLite (single machine) falls back to in-process locks.
import threading
import zlib

_LOCAL: dict[str, threading.Lock] = {}
_LOCAL_GUARD = threading.Lock()


def _key(name: str) -> int:
    return zlib.crc32(name.encode())


# Locks use their own small connection pool so waiting for a lock can never starve the main pool (that deadlocked under load).
_lock_engine = None


def _lock_pool():
    global _lock_engine
    if _lock_engine is None:
        _lock_engine = create_engine(config.DATABASE_URL, future=True, pool_size=config.DB_LOCK_POOL, max_overflow=0,
                                     pool_pre_ping=True, pool_timeout=0.2)
    return _lock_engine


def try_acquire_lock(name: str):
    """Non-blocking: returns a handle, or None if somebody else holds the lock (callers poll; nothing sits blocked on a connection)."""
    if IS_SQLITE:
        with _LOCAL_GUARD:
            lock = _LOCAL.setdefault(name, threading.Lock())
        return ("local", lock) if lock.acquire(blocking=False) else None
    from sqlalchemy.exc import TimeoutError as PoolTimeout
    try:
        conn = _lock_pool().connect().execution_options(isolation_level="AUTOCOMMIT")
    except PoolTimeout:  # every lock connection of this worker is in use: back-pressure, the caller polls again
        return None
    try:
        got = conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": _key(name)}).scalar()
    except Exception:
        conn.close()
        raise
    if not got:
        conn.close()
        return None
    return ("pg", conn, name)


def acquire_lock(name: str, timeout: float = 30.0):
    """Blocking wrapper around try_acquire_lock (used by synchronous code such as start-up)."""
    import time
    end = time.monotonic() + timeout
    while True:
        h = try_acquire_lock(name)
        if h:
            return h
        if time.monotonic() > end:
            raise TimeoutError(f"could not get lock {name}")
        time.sleep(0.02)


def release_lock(handle) -> None:
    if handle[0] == "local":
        handle[1].release()
        return
    _, conn, name = handle
    try:
        conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _key(name)})
    finally:
        conn.close()


from contextlib import contextmanager


@contextmanager
def locked(name: str):
    h = acquire_lock(name)
    try:
        yield
    finally:
        release_lock(h)


def now():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class Goal(Base):
    __tablename__ = "goals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(String(16), index=True)
    name = Column(String(60))
    target = Column(Float)
    deadline_day = Column(Integer)  # simulated day index
    priority = Column(Integer, default=2)
    shared = Column(Boolean, default=True)  # per-goal "share progress with sender"
    created_at = Column(DateTime, default=now)


class SenderLink(Base):
    __tablename__ = "sender_links"
    household_id = Column(String(16), primary_key=True)
    sender_id = Column(String(24), primary_key=True)
    sender_accepted = Column(Boolean, default=False)


class Consent(Base):
    """scope in {goal_progress, savings_total, spending_categories}; state in {granted, revoked, requested}."""
    __tablename__ = "consents"
    household_id = Column(String(16), primary_key=True)
    sender_id = Column(String(24), primary_key=True)
    scope = Column(String(32), primary_key=True)
    state = Column(String(12), default="revoked")
    updated_at = Column(DateTime, default=now)


class Decision(Base):
    __tablename__ = "decisions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(String(16), index=True)
    day = Column(Integer)
    decision = Column(String(12))  # accepted / edited / skipped
    plan = Column(JSON)
    created_at = Column(DateTime, default=now)


class Audit(Base):
    __tablename__ = "audit"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, default=now)
    actor = Column(String(40))
    action = Column(String(60))
    household_id = Column(String(16), index=True)
    detail = Column(JSON)


class DemoState(Base):
    __tablename__ = "demo_state"
    household_id = Column(String(16), primary_key=True)
    state = Column(JSON)
    updated_at = Column(DateTime, default=now)


class User(Base):
    """role in {family, sender, admin}. family and sender belong to a household; admin (platform operator) does not."""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(120), unique=True, index=True)
    name = Column(String(60))
    password_hash = Column(String(200))
    role = Column(String(10))
    household_id = Column(String(16), index=True, nullable=True)
    sender_city = Column(String(40), nullable=True)
    invite_code = Column(String(16), nullable=True, index=True)  # family only: lets a sender link to this household
    is_demo = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)  # admins can disable an account
    phone = Column(String(20), nullable=True, index=True)  # +8801XXXXXXXXX; optional
    phone_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)


class AuthSession(Base):
    """Server-side login sessions. Only a SHA-256 hash of the token is stored."""
    __tablename__ = "auth_sessions"
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, index=True)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=now)


class OtpCode(Base):
    """One-time codes for phone verification and password reset. Only a salted hash of the code is stored."""
    __tablename__ = "otp_codes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True)
    purpose = Column(String(16))  # verify_phone | reset
    code_hash = Column(String(140))
    expires_at = Column(DateTime)
    attempts = Column(Integer, default=0)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)


class WebhookEvent(Base):
    """Idempotency record: an event id is applied at most once."""
    __tablename__ = "webhook_events"
    event_id = Column(String(64), primary_key=True)
    type = Column(String(24))
    household_id = Column(String(16), index=True)
    received_at = Column(DateTime, default=now)


class SummaryCache(Base):
    __tablename__ = "summary_cache"
    key = Column(String(120), primary_key=True)
    text = Column(Text)
    created_at = Column(DateTime, default=now)


def init_db():
    Base.metadata.create_all(engine)
    # light migration for databases created before goals.shared existed
    from sqlalchemy import inspect
    cols = {c["name"] for c in inspect(engine).get_columns("goals")}
    ucols = {c["name"] for c in inspect(engine).get_columns("users")}
    if "is_active" not in ucols:
        d2 = "1" if engine.dialect.name == "sqlite" else "TRUE"
        with engine.begin() as c:
            c.execute(text(f"ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT {d2}"))
    for col, ddl in (("phone", "VARCHAR(20)"), ("phone_verified", "BOOLEAN DEFAULT " + ("0" if engine.dialect.name == "sqlite" else "FALSE"))):
        if col not in ucols:  # migration-safe: add the column only if an older database lacks it
            with engine.begin() as c:
                c.execute(text(f"ALTER TABLE users ADD COLUMN {col} {ddl}"))
    if "shared" not in cols:
        default = "1" if engine.dialect.name == "sqlite" else "TRUE"
        with engine.begin() as c:
            c.execute(text(f"ALTER TABLE goals ADD COLUMN shared BOOLEAN DEFAULT {default}"))


def write_frame(df: pd.DataFrame, name: str, index_cols: list[str] | None = None):
    df.to_sql(name, engine, if_exists="replace", index=False, chunksize=20000)
    if index_cols:
        cols = ", ".join(index_cols)
        with engine.begin() as c:
            c.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{name} ON {name} ({cols})"))


def read_sql(q: str, **params) -> pd.DataFrame:
    with engine.connect() as c:
        return pd.read_sql(text(q), c, params=params)


def audit(actor: str, action: str, household_id: str | None = None, detail: dict | None = None):
    with SessionLocal() as s:
        s.add(Audit(actor=actor, action=action, household_id=household_id, detail=detail or {}))
        s.commit()
