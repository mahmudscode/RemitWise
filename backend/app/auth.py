"""Accounts: password hashing, sessions, rate limiting, demo-account seeding (docs/21).

- Passwords: salted scrypt (stdlib). Never stored or logged in plain text.
- Sessions: random 256-bit token returned once; only its SHA-256 is stored, so a database leak
  does not leak usable tokens.
- Login attempts are rate limited per email + client.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import os
import re
import secrets
import time
from collections import defaultdict, deque

from fastapi import HTTPException

from . import config, db
from .db import AuthSession, OtpCode, SessionLocal, User

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no look-alikes
_DUMMY = None


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, dk = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(calc.hex(), dk)
    except Exception:
        return False


def _dummy_hash() -> str:
    global _DUMMY
    if _DUMMY is None:
        _DUMMY = hash_password("not-a-real-password")
    return _DUMMY


def normalize_email(email: str) -> str:
    e = (email or "").strip().lower()
    if len(e) > 120 or not EMAIL_RE.match(e):
        raise HTTPException(422, "Enter a valid email address.")
    return e


def check_password_policy(password: str, email: str):
    if len(password) < 8:
        raise HTTPException(422, "Use a password of at least 8 characters.")
    if len(password) > 128:
        raise HTTPException(422, "That password is too long (max 128 characters).")
    if password.lower() == email.lower():
        raise HTTPException(422, "Your password should not be your email.")


def invite_code() -> str:
    return "RW-" + "".join(secrets.choice(_ALPHABET) for _ in range(6))


# ---- rate limiting (in memory, per process) ----
_FAILS: dict[str, deque] = defaultdict(deque)
MAX_FAILS, WINDOW = 8, 300


def _key(email: str, client: str) -> str:
    return f"{email}|{client}"


def check_rate(email: str, client: str, what: str = "sign-in"):
    q = _FAILS[_key(email, client)]
    now = time.time()
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= MAX_FAILS:
        raise HTTPException(429, f"Too many {what} attempts. Please wait a few minutes and try again.")


def record_fail(email: str, client: str):
    _FAILS[_key(email, client)].append(time.time())


def clear_fails(email: str, client: str):
    _FAILS.pop(_key(email, client), None)


# ---- sessions ----
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with SessionLocal() as s:
        s.query(AuthSession).filter(AuthSession.expires_at < db.now()).delete()
        s.add(AuthSession(token_hash=_hash_token(token), user_id=user_id,
                          expires_at=db.now() + dt.timedelta(days=config.SESSION_DAYS)))
        s.commit()
    return token


def delete_session(token: str):
    with SessionLocal() as s:
        s.query(AuthSession).filter(AuthSession.token_hash == _hash_token(token)).delete()
        s.commit()


def user_from_token(token: str) -> User | None:
    with SessionLocal() as s:
        sess = s.get(AuthSession, _hash_token(token))
        if not sess or sess.expires_at < db.now():
            return None
        u = s.get(User, sess.user_id)
        return u if u is not None and u.is_active is not False else None


def bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Please sign in.")
    return authorization[7:].strip()


def authenticate(email: str, password: str, client: str) -> User:
    email = (email or "").strip().lower()
    check_rate(email, client)
    with SessionLocal() as s:
        user = s.query(User).filter(User.email == email).first()
    ok = verify_password(password, user.password_hash if user else _dummy_hash())  # same cost either way
    if not user or not ok:
        record_fail(email, client)
        raise HTTPException(401, "Incorrect email or password.")
    clear_fails(email, client)
    if user.is_active is False:
        raise HTTPException(403, "This account has been disabled. Please contact the administrator.")
    return user


def public_user(u: User) -> dict:
    out = dict(id=u.id, name=u.name, email=u.email, role=u.role, household_id=u.household_id,
               sender_city=u.sender_city, is_demo=bool(u.is_demo),
               email_verified=bool(u.email_verified or u.is_demo))
    if u.role == "family":
        out["invite_code"] = u.invite_code
    return out


def mask_email(email: str) -> str:
    local, _, dom = email.partition("@")
    return f"{local[:1]}***@{dom}"


def seed_demo_accounts(engine) -> None:
    """Demo family and sender accounts for the synthetic households, plus an admin (public password by design)."""
    with SessionLocal() as s:
        legacy = s.query(User).filter(User.email == "judge@demo.remitwise").first()  # renamed: there is no "judge" account type
        if legacy:
            s.query(AuthSession).filter(AuthSession.user_id == legacy.id).delete()
            s.delete(legacy)
        def add(email, name, role, pw, hid=None, city=None, code=None, demo=True):
            if s.query(User).filter(User.email == email).first():
                return
            s.add(User(email=email, name=name, password_hash=hash_password(pw), role=role,
                       household_id=hid, sender_city=city, invite_code=code, is_demo=demo, is_active=True))
        if config.SEED_DEMO_ACCOUNTS:
            for hid, name in engine.demo_ids.items():
                add(f"{name.lower()}@demo.remitwise", name, "family", config.DEMO_PASSWORD, hid, code=invite_code())
                sn = engine.default_sender_name(hid)
                add(f"{sn.lower()}@demo.remitwise", sn, "sender", config.DEMO_PASSWORD, hid)
            add("admin@demo.remitwise", "Admin", "admin", config.DEMO_PASSWORD)
        if config.ADMIN_EMAIL and config.ADMIN_PASSWORD:  # a real, provisioned admin
            add(config.ADMIN_EMAIL, "Administrator", "admin", config.ADMIN_PASSWORD, demo=False)
        s.commit()


# ---- one-time security codes (emailed) and password reset ----
_OTP_REQS: dict[str, deque] = defaultdict(deque)


def _otp_hash(code: str, salt: str) -> str:
    return hmac.new(bytes.fromhex(salt), code.encode(), hashlib.sha256).hexdigest()


def limit_otp_requests(key: str):
    _check_otp_rate(key)


def _check_otp_rate(key: str):
    q = _OTP_REQS[key]
    now = time.time()
    while q and now - q[0] > config.OTP_WINDOW_SECONDS:
        q.popleft()
    if len(q) >= config.OTP_MAX_REQUESTS:
        raise HTTPException(429, "Too many code requests. Please wait a few minutes and try again.")
    q.append(now)


def issue_otp(user_id: int, purpose: str) -> str:
    """Create a 6-digit code (hashed at rest, 5-minute expiry, limited attempts); older codes stop working."""
    _check_otp_rate(f"{purpose}:{user_id}")
    code = f"{secrets.randbelow(10**6):06d}"
    salt = secrets.token_hex(8)
    with SessionLocal() as s:
        s.query(OtpCode).filter(OtpCode.user_id == user_id, OtpCode.purpose == purpose, OtpCode.used.is_(False)).update({"used": True})
        s.add(OtpCode(user_id=user_id, purpose=purpose, code_hash=f"{salt}${_otp_hash(code, salt)}",
                      expires_at=db.now() + dt.timedelta(seconds=config.OTP_TTL_SECONDS), attempts=0, used=False))
        s.commit()
    return code


def check_otp(user_id: int, purpose: str, code: str) -> None:
    """Raises unless `code` is the live code. Wrong guesses are counted; after the limit the code is dead."""
    code = (code or "").strip()
    with SessionLocal() as s:
        row = (s.query(OtpCode).filter(OtpCode.user_id == user_id, OtpCode.purpose == purpose, OtpCode.used.is_(False))
               .order_by(OtpCode.id.desc()).first())
        if row is None or row.expires_at < db.now():
            raise HTTPException(400, "That code is invalid or has expired. Request a new one.")
        if row.attempts >= config.OTP_MAX_ATTEMPTS:
            raise HTTPException(429, "Too many wrong codes. Request a new code.")
        row.attempts += 1
        salt, digest = row.code_hash.split("$")
        ok = code.isdigit() and hmac.compare_digest(_otp_hash(code, salt), digest)
        if ok:
            row.used = True
        s.commit()
    if not ok:
        raise HTTPException(400, "That code is invalid or has expired. Request a new one.")


def find_for_reset(email: str) -> User | None:
    """Look an account up by email. Demo and admin accounts cannot be reset this way."""
    e = (email or "").strip().lower()
    if not EMAIL_RE.match(e):
        return None
    with SessionLocal() as s:
        u = s.query(User).filter(User.email == e).first()
    if u is None or u.is_demo or u.role == "admin" or u.is_active is False:
        return None
    return u


def set_password(user_id: int, new_password: str) -> None:
    """New password; every existing session of the user is invalidated."""
    with SessionLocal() as s:
        u = s.get(User, user_id)
        u.password_hash = hash_password(new_password)
        s.query(AuthSession).filter(AuthSession.user_id == user_id).delete()
        s.commit()


AUDIT_RETENTION_DAYS = 365


def purge_expired() -> dict:
    """Retention (docs/data-retention.md): drop expired sessions, used/expired one-time codes, audit rows older than 12 months."""
    from .db import Audit
    cutoff = db.now() - dt.timedelta(days=AUDIT_RETENTION_DAYS)
    with SessionLocal() as s:
        n_sess = s.query(AuthSession).filter(AuthSession.expires_at < db.now()).delete()
        n_otp = s.query(OtpCode).filter((OtpCode.expires_at < db.now()) | (OtpCode.used.is_(True))).delete()
        n_aud = s.query(Audit).filter(Audit.ts < cutoff).delete()
        s.commit()
    return dict(sessions=n_sess, codes=n_otp, audit=n_aud)
