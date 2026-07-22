"""Regression tests for the admin allowlist.

This guards the privilege-escalation fix: before it, anyone could POST
role="admin" to /api/auth/signup and become a platform administrator. Admin is
now decided solely by admin_identity, so these tests are the ones that must
never go red.

Deliberately stdlib + pytest only — no database, no FastAPI, no network.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import admin_identity  # noqa: E402


@pytest.fixture
def allowlist(tmp_path, monkeypatch):
    """Point admin_identity at a temp credentials file and clean env vars."""
    creds = tmp_path / "admin.credentials.json"
    monkeypatch.setattr(admin_identity, "CREDENTIALS_PATH", creds)
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    monkeypatch.delenv("ADMIN_FIREBASE_UIDS", raising=False)

    def configure(emails=None, uids=None, raw=None):
        if raw is not None:
            creds.write_text(raw, encoding="utf-8")
        else:
            creds.write_text(json.dumps({
                "admin_emails": emails or [],
                "admin_firebase_uids": uids or [],
            }), encoding="utf-8")
        admin_identity.reload_allowlist()

    yield configure
    admin_identity.reload_allowlist()


# --------------------------------------------------------------------------
# The bug this exists to prevent
# --------------------------------------------------------------------------

def test_stored_admin_role_does_not_grant_admin(allowlist):
    """A user row claiming role='admin' must be ignored entirely."""
    allowlist(emails=["owner@company.com"])
    escalated = {"email": "attacker@evil.com", "role": "admin"}
    assert admin_identity.is_admin_identity(escalated) is False
    assert admin_identity.effective_role(escalated) == "hr"


def test_role_field_is_ignored_even_for_allowlisted_user(allowlist):
    """Allowlist membership decides the role, not the stored field."""
    allowlist(emails=["owner@company.com"])
    assert admin_identity.effective_role({"email": "owner@company.com", "role": "hr"}) == "admin"


# --------------------------------------------------------------------------
# Matching behaviour
# --------------------------------------------------------------------------

@pytest.mark.parametrize("email", [
    "owner@company.com",
    "OWNER@Company.COM",
    "  owner@company.com  ",
])
def test_email_match_is_case_and_whitespace_insensitive(allowlist, email):
    allowlist(emails=["owner@company.com"])
    assert admin_identity.is_admin_identity({"email": email}) is True


@pytest.mark.parametrize("email", [
    "xowner@company.com",           # prefix
    "owner@company.com.evil.com",   # suffix
    "owner@company.co",             # truncated
    "someone@else.com",
    "",
    None,
])
def test_non_matching_emails_are_rejected(allowlist, email):
    allowlist(emails=["owner@company.com"])
    assert admin_identity.is_admin_identity({"email": email}) is False


def test_firebase_uid_match_is_case_sensitive(allowlist):
    allowlist(uids=["uid-abc-123"])
    assert admin_identity.is_admin_identity({"firebase_uid": "uid-abc-123"}) is True
    assert admin_identity.is_admin_identity({"firebase_uid": "UID-ABC-123"}) is False


@pytest.mark.parametrize("user", [None, {}, {"email": None}, {"firebase_uid": ""}])
def test_missing_or_empty_identity_is_never_admin(allowlist, user):
    allowlist(emails=["owner@company.com"])
    assert admin_identity.is_admin_identity(user) is False


# --------------------------------------------------------------------------
# Failure modes must fail closed
# --------------------------------------------------------------------------

def test_no_configuration_means_nobody_is_admin(allowlist, tmp_path, monkeypatch):
    monkeypatch.setattr(admin_identity, "CREDENTIALS_PATH", tmp_path / "missing.json")
    admin_identity.reload_allowlist()
    assert admin_identity.admin_is_configured() is False
    assert admin_identity.is_admin_identity({"email": "owner@company.com"}) is False


def test_malformed_credentials_file_is_ignored_not_fatal(allowlist):
    allowlist(raw="{ not valid json")
    assert admin_identity.admin_is_configured() is False
    assert admin_identity.is_admin_identity({"email": "owner@company.com"}) is False


def test_non_object_credentials_file_is_ignored(allowlist):
    allowlist(raw='["owner@company.com"]')
    assert admin_identity.admin_is_configured() is False


@pytest.mark.parametrize("placeholder,key,field", [
    ("you@your-company.com", "admin_emails", "email"),
    ("replace-with-your-firebase-uid", "admin_firebase_uids", "firebase_uid"),
])
def test_unedited_example_placeholders_never_grant_admin(allowlist, placeholder, key, field):
    """Copying the example file without editing it must not create an admin."""
    allowlist(**{"emails" if key == "admin_emails" else "uids": [placeholder]})
    assert admin_identity.is_admin_identity({field: placeholder}) is False
    assert admin_identity.admin_is_configured() is False


# --------------------------------------------------------------------------
# Hosted deploys rely on the env-var fallback
# --------------------------------------------------------------------------

def test_env_vars_grant_admin_when_file_is_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(admin_identity, "CREDENTIALS_PATH", tmp_path / "missing.json")
    monkeypatch.setenv("ADMIN_EMAILS", "Owner@Company.com , second@co.uk")
    monkeypatch.setenv("ADMIN_FIREBASE_UIDS", "uid-abc-123")
    admin_identity.reload_allowlist()

    assert admin_identity.is_admin_identity({"email": "owner@company.com"}) is True
    assert admin_identity.is_admin_identity({"email": "second@co.uk"}) is True
    assert admin_identity.is_admin_identity({"firebase_uid": "uid-abc-123"}) is True
    assert admin_identity.is_admin_identity({"email": "nobody@co.uk"}) is False


def test_file_and_env_sources_are_merged(allowlist, monkeypatch):
    allowlist(emails=["from-file@company.com"])
    monkeypatch.setenv("ADMIN_EMAILS", "from-env@company.com")
    admin_identity.reload_allowlist()

    assert admin_identity.is_admin_identity({"email": "from-file@company.com"}) is True
    assert admin_identity.is_admin_identity({"email": "from-env@company.com"}) is True
