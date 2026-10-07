"""Central configuration. Secrets only via environment variables."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")

ARTIFACTS = Path(os.getenv("RW_ARTIFACTS_DIR") or ROOT / "artifacts")  # override to keep a PostgreSQL test run out of the repo
ARTIFACTS.mkdir(exist_ok=True)

# PostgreSQL in production/demo (see .env.example); SQLite only as a local fallback.
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ARTIFACTS / 'remitwise.db'}")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Synthetic data (doc 07)
SEED = 42
N_HOUSEHOLDS = 500
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

# Simulated phone OTP (no SMS gateway). In demo mode the code is returned in the API response and shown on screen.
OTP_DEMO_MODE = os.getenv("OTP_DEMO_MODE", "true").lower() in ("1", "true", "yes")  # on: the code is shown on screen (and emailed too if SMTP is set). Set false in production so it is only emailed
OTP_TTL_SECONDS = 300
OTP_MAX_ATTEMPTS = 5
OTP_MAX_REQUESTS = 3        # code requests per window, per account and purpose
OTP_WINDOW_SECONDS = 600

# Signed transaction webhooks (docs/09-api-contracts.md). The endpoint is disabled until a shared secret is set.
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
WEBHOOK_TOLERANCE_SECONDS = 300

# Team decision: ship the Priority 3 experiments in the live model even where the offline rule ("adopt only if it wins")
# says no. The measured effect is still reported honestly in Admin. Set any of these to false to fall back to the baseline.
_flag = lambda name: os.getenv(name, "true").lower() in ("1", "true", "yes")
FORCE_IRREGULAR_MODEL = _flag("FORCE_IRREGULAR_MODEL")   # regularity features + group-wise calibration
FORCE_TEMPORAL_FEATURES = _flag("FORCE_TEMPORAL_FEATURES")  # lag / rolling features
FORCE_ADAPTIVE = _flag("FORCE_ADAPTIVE")                 # per-household online correction in the live app

# SIMULATED low-risk yield pot for micro-savings (docs/10-responsible-ai.md). Not a real product: an illustrative annual rate on synthetic money.
SIM_YIELD_RATE = float(os.getenv("SIM_YIELD_RATE", "0.05"))

# Database pool, per worker process (PostgreSQL). Keep workers x (pool + overflow) below the server's max_connections.
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "15"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
DB_LOCK_POOL = int(os.getenv("DB_LOCK_POOL", "10"))  # concurrent household writes per worker
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))

# Security codes are emailed when SMTP_HOST is set (any SMTP server). Without it, OTP_DEMO_MODE shows the code on screen instead.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "true").lower() in ("1", "true", "yes")
