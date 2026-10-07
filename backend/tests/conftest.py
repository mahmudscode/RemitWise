"""Run tests against a throwaway copy of the database so the demo data is never modified."""
import os

import shutil
import tempfile
from pathlib import Path

ART = Path(__file__).resolve().parents[1] / "artifacts"
src = ART / "remitwise.db"
if src.exists() and not os.getenv("DATABASE_URL"):
    tmp = Path(tempfile.mkdtemp()) / "test.db"
    shutil.copy(src, tmp)
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp}"

# The tests read codes from the API reply (demo mode) or from a fake mail server; production keeps demo mode off.
os.environ.setdefault("OTP_DEMO_MODE", "true")
