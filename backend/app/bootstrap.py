"""First-start data load for PostgreSQL deployments.

Loads the synthetic data (about a minute) only when the database has none, and only in one process even if several
containers start together. Restarts and redeploys leave existing data, accounts and household state untouched.

    python -m app.bootstrap
"""
from __future__ import annotations

from sqlalchemy import inspect, text

from . import db


def has_data() -> bool:
    if "households" not in inspect(db.engine).get_table_names():
        return False
    with db.engine.connect() as c:
        return c.execute(text("SELECT COUNT(*) FROM households")).scalar() > 0


def run() -> str:
    with db.locked("bootstrap"):
        if has_data():
            print("bootstrap: data already loaded, nothing to do")
            return "skipped"
        print("bootstrap: empty database, loading synthetic data ...")
        from . import pipeline
        pipeline.run()
        return "loaded"


if __name__ == "__main__":
    run()
