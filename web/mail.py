"""Outgoing mail: password reset links and email confirmation.

Plain SMTP, so any provider works (Yandex 360, Gmail with an app password,
Brevo, Resend, Mailgun, …). Configured by env:

    SMTP_HOST, SMTP_PORT (587: STARTTLS, 465: TLS), SMTP_USER, SMTP_PASSWORD,
    SMTP_FROM ("Petzy <no-reply@example.com>"), APP_BASE_URL (links in letters)

MAIL_OUTBOX=memory keeps letters in OUTBOX instead of sending them: the
local runner (scripts/dev_local.py) and tests read them from there.
"""

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid

logger = logging.getLogger(__name__)

# Letters "sent" with MAIL_OUTBOX=memory, newest last. Never used in production.
OUTBOX: list[dict] = []
_OUTBOX_LIMIT = 50


def _outbox_mode() -> bool:
    return os.getenv("MAIL_OUTBOX", "").strip().lower() == "memory"


def mail_configured() -> bool:
    return _outbox_mode() or bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM"))


def app_url(path: str) -> str:
    base = os.getenv("APP_BASE_URL", "https://petzy.duckdns.org").rstrip("/")
    return f"{base}{path}"


def send_mail(to: str, subject: str, text: str) -> None:
    """Send one plain-text letter. Raises on failure; the caller decides what
    the user is told (a password reset request always gets the same answer)."""
    if _outbox_mode():
        OUTBOX.append({"to": to, "subject": subject, "text": text})
        del OUTBOX[:-_OUTBOX_LIMIT]
        logger.info(f"Mail kept in the outbox: to={to}, subject={subject!r}")
        return

    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = to
    message["Subject"] = subject
    message["Message-ID"] = make_msgid(domain=os.environ["SMTP_FROM"].rsplit("@", 1)[-1].strip("> "))
    message.set_content(text)

    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=10) as smtp:
            if user:
                smtp.login(user, password or "")
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls(context=context)
            if user:
                smtp.login(user, password or "")
            smtp.send_message(message)
    logger.info(f"Mail sent: subject={subject!r}")
