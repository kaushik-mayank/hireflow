"""Single source of truth for who is a platform administrator.

Admin status is NEVER derived from a client-settable field. It cannot be
requested at signup, cannot be set through the API, and is not trusted from the
`role` column in the database. It is decided only by matching the *authenticated*
identity against an allowlist held outside the public users collection.

Resolution order:

  1. ``backend/admin.credentials.json`` — git-ignored. Used for local
     development and any deploy where you can place a file on disk.
  2. ``ADMIN_EMAILS`` / ``ADMIN_FIREBASE_UIDS`` environment variables —
     comma-separated. Needed for hosted deploys (Render), where a git-ignored
     file does not exist because it was never pushed.

Both sources are read and merged. These are backend-only: nothing here is ever
sent to the browser, and no value is exposed through any API response.

**Fails closed.** If neither source yields a usable identity, nobody is an
admin and the admin panel is unreachable. That is the safe outcome — a
misconfiguration locks the owner out rather than letting anyone in.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

CREDENTIALS_PATH = Path(__file__).parent / "admin.credentials.json"

HR_ROLE = "hr"
ADMIN_ROLE = "admin"

# Values shipped in admin.credentials.example.json. If someone copies the
# example without editing it, we must not hand out admin to a well-known
# placeholder address.
_PLACEHOLDERS = {
    "you@your-company.com",
    "replace-with-your-firebase-uid",
    "",
}


def _clean(values, lower: bool) -> set:
    """Normalise a list of identity strings, dropping blanks and placeholders."""
    out = set()
    for v in values or []:
        if not isinstance(v, str):
            continue
        v = v.strip()
        if lower:
            v = v.lower()
        if v and v not in _PLACEHOLDERS:
            out.add(v)
    return out


def _from_file() -> tuple[set, set]:
    if not CREDENTIALS_PATH.exists():
        return set(), set()
    try:
        data = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.error("admin.credentials.json could not be read (%s) — ignoring it", exc)
        return set(), set()
    if not isinstance(data, dict):
        logger.error("admin.credentials.json must contain a JSON object — ignoring it")
        return set(), set()
    return (
        _clean(data.get("admin_emails"), lower=True),
        _clean(data.get("admin_firebase_uids"), lower=False),
    )


def _from_env() -> tuple[set, set]:
    return (
        _clean(os.environ.get("ADMIN_EMAILS", "").split(","), lower=True),
        _clean(os.environ.get("ADMIN_FIREBASE_UIDS", "").split(","), lower=False),
    )


class _AdminAllowlist:
    """Loaded once at import; call reload() if the file changes at runtime."""

    def __init__(self):
        self.emails: set = set()
        self.uids: set = set()
        self.reload()

    def reload(self) -> None:
        file_emails, file_uids = _from_file()
        env_emails, env_uids = _from_env()
        self.emails = file_emails | env_emails
        self.uids = file_uids | env_uids

        if not self.emails and not self.uids:
            logger.warning(
                "No admin identity configured. Create backend/admin.credentials.json "
                "(see admin.credentials.example.json) or set ADMIN_EMAILS. "
                "Until then the admin panel is unreachable by anyone."
            )
        else:
            logger.info(
                "Admin allowlist loaded: %d email(s), %d firebase uid(s)",
                len(self.emails), len(self.uids),
            )


_allowlist = _AdminAllowlist()


def reload_allowlist() -> None:
    _allowlist.reload()


def is_admin_identity(user: dict) -> bool:
    """True only if this authenticated user matches the configured admin.

    Deliberately ignores ``user["role"]`` — that field is descriptive, not
    authoritative, and was writable by the client before this was introduced.
    """
    if not user:
        return False
    email = (user.get("email") or "").strip().lower()
    uid = (user.get("firebase_uid") or "").strip()
    return bool((email and email in _allowlist.emails) or (uid and uid in _allowlist.uids))


def effective_role(user: dict) -> str:
    """The role to trust, derived fresh from the allowlist on every call."""
    return ADMIN_ROLE if is_admin_identity(user) else HR_ROLE


def admin_is_configured() -> bool:
    return bool(_allowlist.emails or _allowlist.uids)
