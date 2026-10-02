"""Central configuration. Secrets only via environment variables."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")

ARTIFACTS = ROOT / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)

# PostgreSQL in production/demo (see .env.example); SQLite only as a local fallback.
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ARTIFACTS / 'remitwise.db'}")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Synthetic data (doc 07)
SEED = 42
N_HOUSEHOLDS = 300
START_DATE = "2024-01-01"
N_DAYS = 900
SPLIT = {"train": 0.6, "cal": 0.2, "test": 0.2}  # by household

# Product parameters (documented assumptions, doc 06 / 11)
INTERVAL_COVERAGE = 0.8
BUFFER_TARGET_MONTHS = 1.0
WARN_THRESHOLD_DEFAULT = 0.4

# Accounts (see docs/21-auth-and-accounts.md)
SESSION_DAYS = 30
SEED_DEMO_ACCOUNTS = os.getenv("SEED_DEMO_ACCOUNTS", "true").lower() in ("1", "true", "yes")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "demo1234")
# Admins are provisioned, never self-registered. Set both to create/ensure an admin on startup.
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
