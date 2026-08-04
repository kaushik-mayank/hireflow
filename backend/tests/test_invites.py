"""Unit tests for the invitation token/state core (invites.py).

Pure functions only — no FastAPI, Mongo or SMTP. These guard the security-
sensitive bits: tokens are unpredictable and stored only as a hash, and an
invite's usability is derived correctly from its status and expiry.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import invites  # noqa: E402

NOW = datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc)


def _inv(status="pending", expires_delta_days=7):
    exp = (NOW + timedelta(days=expires_delta_days)).isoformat() if expires_delta_days is not None else None
    return {"status": status, "expires_at": exp}


# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------

def test_generate_token_is_unique_and_hashed():
    raw1, h1 = invites.generate_token()
    raw2, h2 = invites.generate_token()
    assert raw1 != raw2                      # unpredictable
    assert h1 != h2
    assert len(raw1) >= 32                    # 32 bytes url-safe -> long string
    # The stored hash is reproducible from the raw token and is not the token.
    assert invites.hash_token(raw1) == h1
    assert h1 != raw1
    assert len(h1) == 64                      # sha256 hex


def test_hash_token_is_deterministic():
    assert invites.hash_token("abc") == invites.hash_token("abc")
    assert invites.hash_token("abc") != invites.hash_token("abd")


def test_expiry_is_ttl_days_ahead():
    exp = invites.expiry_from(NOW)
    assert datetime.fromisoformat(exp) == NOW + timedelta(days=invites.INVITE_TTL_DAYS)


# --------------------------------------------------------------------------
# Validity / reason
# --------------------------------------------------------------------------

def test_none_invite_is_unknown():
    assert invites.invite_reason(None, NOW) == invites.UNKNOWN
    assert invites.is_valid(None, NOW) is False


def test_pending_unexpired_is_valid():
    assert invites.invite_reason(_inv("pending", 7), NOW) == invites.VALID
    assert invites.is_valid(_inv("pending", 7), NOW) is True


def test_pending_expired_is_expired():
    assert invites.invite_reason(_inv("pending", -1), NOW) == invites.EXPIRED
    assert invites.is_valid(_inv("pending", -1), NOW) is False


def test_accepted_is_accepted_even_if_expired():
    # Precedence: an accepted invite reports "accepted", not "expired".
    assert invites.invite_reason(_inv("accepted", -5), NOW) == invites.ACCEPTED


def test_revoked_is_revoked():
    assert invites.invite_reason(_inv("revoked", 7), NOW) == invites.REVOKED


def test_unknown_status_is_unknown():
    assert invites.invite_reason(_inv("something-else", 7), NOW) == invites.UNKNOWN


def test_missing_expiry_is_treated_as_valid_when_pending():
    # A pending invite with no expiry set never blocks on expiry.
    assert invites.invite_reason(_inv("pending", None), NOW) == invites.VALID


# --------------------------------------------------------------------------
# Rate-limit predicate
# --------------------------------------------------------------------------

def test_within_rate_limit_boundary():
    assert invites.within_rate_limit(0, 3) is True
    assert invites.within_rate_limit(2, 3) is True
    assert invites.within_rate_limit(3, 3) is False   # at the limit, blocked
    assert invites.within_rate_limit(4, 3) is False


def test_one_hour_ago_iso_is_before_now():
    cutoff = invites.one_hour_ago_iso(NOW)
    assert datetime.fromisoformat(cutoff) == NOW - timedelta(hours=1)
