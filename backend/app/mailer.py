"""Security codes by email.

If SMTP_HOST is set the code is really emailed (any SMTP server: Gmail app password, SendGrid, Mailgun, your own).
If not, nothing is sent and the API runs in demo mode (OTP_DEMO_MODE) where the code is shown on screen instead.
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from . import config


class MailError(Exception):
    pass


def configured() -> bool:
    return bool(config.SMTP_HOST)


def build(to: str, code: str, purpose: str, minutes: int) -> EmailMessage:
    what = "reset your password" if purpose == "reset" else "verify your email address"
    m = EmailMessage()
    m["Subject"] = "Your RemitWise security code"
    m["From"] = config.SMTP_FROM or config.SMTP_USER or "no-reply@remitwise.local"
    m["To"] = to
    m.set_content(
        f"Your RemitWise security code is {code}\n\n"
        f"Use it to {what}. It works for {minutes} minutes and allows 5 tries.\n"
        f"If you did not ask for this code, you can ignore this email. Nobody can use it without your account.\n\n"
        f"RemitWise is a hackathon prototype running on synthetic data. We will never ask for your PIN or password by email.\n")
    return m


def send_code(to: str, code: str, purpose: str) -> bool:
    """Returns True if an email was sent, False if email is not configured. Raises MailError if sending fails."""
    if not configured():
        return False
    msg = build(to, code, purpose, config.OTP_TTL_SECONDS // 60)
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as s:
            if config.SMTP_STARTTLS:
                s.starttls()
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            s.send_message(msg)
    except (OSError, smtplib.SMTPException) as e:
        raise MailError(str(e)) from e
    return True
