"""Outbound email over SMTP.

Chosen over SendGrid/SES/Resend SDKs because it needs **zero new
dependencies** — `smtplib` and `email` are stdlib — and works unchanged with
Gmail app passwords, Resend, Brevo, Mailgun or any other SMTP relay. Swapping
provider is an env-var change, not a code change.

Deliverability note: the `From` address must be one the SMTP account is
authorised to send as, otherwise SPF/DKIM fail and the message is filed as
spam or rejected. So a submitter's address is NEVER used as `From` — it goes
in `Reply-To`, which means hitting reply in the inbox still answers the user.

Configuration (all backend-only):
    SMTP_HOST         e.g. smtp.gmail.com
    SMTP_PORT         587 for STARTTLS (default), 465 for implicit SSL
    SMTP_USER         username for the relay
    SMTP_PASSWORD     password / app password / API key
    SMTP_FROM         authorised sender address; defaults to SMTP_USER
    SMTP_FROM_NAME    display name; defaults to "HireFlow"
    SMTP_USE_SSL      "true" to use implicit SSL instead of STARTTLS
    FEEDBACK_TO       where feedback lands; defaults to connecting800@gmail.com

If SMTP is not configured, send_email() returns False rather than raising.
Callers persist the message to the database first, so nothing is ever lost to
a mail outage or a missing setting.
"""

import asyncio
import logging
import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587") or 587)
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "").strip() or SMTP_USER
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "HireFlow").strip()
SMTP_USE_SSL = os.environ.get("SMTP_USE_SSL", "").strip().lower() in ("1", "true", "yes")

FEEDBACK_TO = os.environ.get("FEEDBACK_TO", "connecting800@gmail.com").strip()

_TIMEOUT = 20


def is_configured() -> bool:
    return bool(SMTP_HOST and SMTP_FROM)


def _build(to: str, subject: str, body: str, reply_to: str | None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((SMTP_FROM_NAME, SMTP_FROM))
    msg["To"] = to
    msg["Subject"] = subject
    # Explicit Date and Message-ID: absent headers are a common spam signal.
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=SMTP_FROM.split("@")[-1] or None)
    msg["Auto-Submitted"] = "auto-generated"
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)
    return msg


def _send_blocking(msg: EmailMessage) -> None:
    if SMTP_USE_SSL:
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=_TIMEOUT)
    else:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=_TIMEOUT)
    try:
        server.ehlo()
        if not SMTP_USE_SSL:
            server.starttls()
            server.ehlo()
        if SMTP_USER:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            server.close()


async def send_email(to: str, subject: str, body: str, reply_to: str | None = None) -> bool:
    """Send one plain-text email. Returns False instead of raising on failure.

    smtplib is blocking, so the call is pushed to a worker thread to avoid
    stalling the event loop.
    """
    if not is_configured():
        logger.warning("SMTP is not configured — skipping email to %s (subject: %s)", to, subject)
        return False
    try:
        msg = _build(to, subject, body, reply_to)
        await asyncio.to_thread(_send_blocking, msg)
        logger.info("Sent email to %s (subject: %s)", to, subject)
        return True
    except Exception as exc:
        # Never propagate: the caller has already persisted the message.
        logger.error("Failed to send email to %s: %s", to, exc)
        return False
