"""Recruiter-invitation tokens and state — the pure, side-effect-free core.

Kept separate from the routes so the security-sensitive bits (token generation,
hashing, expiry/validity, rate-limit thresholds) are unit-testable offline with
no FastAPI, Mongo or SMTP in the picture.

Security notes:
- The raw token is a 32-byte URL-safe secret. It is emailed to the recruiter and
  returned to the manager exactly once (copy-link fallback). Only its **sha256**
  is ever stored, so a database read never yields a usable invite link.
- Validity is derived, never trusted from a single field: an invite is usable
  only when status=="pending" AND it has not expired. Anything else resolves to a
  neutral reason the caller maps to a friendly, non-leaking message.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

# Invite lifetime and abuse limits. Deliberately conservative; a manager who
# hits them is almost certainly scripting or fat-fingering, not onboarding.
INVITE_TTL_DAYS = 7
INVITES_PER_HOUR = 20          # new/resent invites per org per rolling hour
ACCEPT_ATTEMPTS_PER_HOUR = 10  # accept calls per single token per rolling hour

# Reasons an invite link is not usable. "valid" is the only success value.
VALID = "valid"
EXPIRED = "expired"
REVOKED = "revoked"
ACCEPTED = "accepted"
UNKNOWN = "unknown"


def generate_token() -> tuple[str, str]:
    """Return (raw_token, token_hash). Store only the hash; email the raw."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256((raw or "").encode("utf-8")).hexdigest()


def expiry_from(now: datetime) -> str:
    return (now + timedelta(days=INVITE_TTL_DAYS)).isoformat()


def _parse(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:  # older/naive rows are treated as UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def invite_reason(invitation: dict | None, now: datetime) -> str:
    """Resolve an invitation to exactly one reason. Order matters: an accepted or
    revoked invite reports that even if also expired, so the message is accurate."""
    if not invitation:
        return UNKNOWN
    status = invitation.get("status")
    if status == "accepted":
        return ACCEPTED
    if status == "revoked":
        return REVOKED
    if status != "pending":
        return UNKNOWN
    expires = _parse(invitation.get("expires_at"))
    if expires and expires < now:
        return EXPIRED
    return VALID


def is_valid(invitation: dict | None, now: datetime) -> bool:
    return invite_reason(invitation, now) == VALID


def within_rate_limit(count_in_last_hour: int, limit: int) -> bool:
    """True when another action is still allowed. Callers supply the count; this
    keeps the threshold decision in one testable place."""
    return count_in_last_hour < limit


def one_hour_ago_iso(now: datetime) -> str:
    return (now - timedelta(hours=1)).isoformat()
