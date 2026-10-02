"""Database layer. PostgreSQL via DATABASE_URL; SQLite fallback for local runs."""
from __future__ import annotations

import datetime as dt

import pandas as pd
from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, Integer, String, Text, create_engine,
                        text)
from sqlalchemy.orm import declarative_base, sessionmaker

from . import config

_kw = {"future": True}
if config.DATABASE_URL.startswith("sqlite"):
    _kw["connect_args"] = {"check_same_thread": False}
engine = create_engine(config.DATABASE_URL, **_kw)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()


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


class SummaryCache(Base):
    __tablename__ = "summary_cache"
    key = Column(String(120), primary_key=True)
    text = Column(Text)
    created_at = Column(DateTime, default=now)


def init_db():
    Base.metadata.create_all(engine)


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
