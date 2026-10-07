"""Send one real test email with the SMTP settings from backend/.env, to check that security codes will arrive.

    python scripts/test_email.py you@example.com
"""
from __future__ import annotations

import sys

from app import config, mailer


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python scripts/test_email.py you@example.com")
    if not mailer.configured():
        sys.exit("SMTP_HOST is not set. Add the SMTP_* settings to backend/.env first (see .env.example).")
    print(f"Sending through {config.SMTP_HOST}:{config.SMTP_PORT} as {config.SMTP_USER or '(no login)'} ...")
    try:
        mailer.send_code(sys.argv[1], "123456", "verify_email")
    except mailer.MailError as e:
        sys.exit(f"Sending failed: {e}\nFor Gmail use smtp.gmail.com, port 587, and a 16-character App Password (not your normal password).")
    print("Sent. Check the inbox (and spam). The code in this test email is 123456.")


if __name__ == "__main__":
    main()
