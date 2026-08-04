"""Route-level tests for Phase 10a: recruiter invitations, accept-invite, member
suspension, org summary, and the get_current_user suspension gate.

Offline. Stubs the modules that need native deps (jwt, bcrypt, motor/database,
firebase_auth) but imports the REAL auth / permissions / routes_orgs / routes_auth
so the actual enforcement runs. Collection references are rebound to shared fakes
regardless of import order (stub-merge pattern), so reverse-order runs stay green.
"""

import asyncio
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

def _matches(doc, query):
    for k, v in query.items():
        if isinstance(v, dict):
            if "$in" in v and doc.get(k) not in v["$in"]:
                return False
            if "$gte" in v and not (doc.get(k) is not None and doc.get(k) >= v["$gte"]):
                return False
            if not ("$in" in v or "$gte" in v) and doc.get(k) != v:
                return False
        elif doc.get(k) != v:
            return False
    return True


class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *a, **k):
        return self

    async def to_list(self, _n=None):
        return [dict(d) for d in self._docs]

    def __aiter__(self):
        async def gen():
            for d in self._docs:
                yield dict(d)
        return gen()


class FakeColl:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    async def find_one(self, query, projection=None):
        for d in self.docs:
            if _matches(d, query):
                return dict(d)
        return None

    def find(self, query, projection=None):
        return _Cursor([d for d in self.docs if _matches(d, query)])

    async def count_documents(self, query):
        return sum(1 for d in self.docs if _matches(d, query))

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    async def update_one(self, query, update):
        for d in self.docs:
            if _matches(d, query):
                d.update(update.get("$set", {}))
                return

    async def delete_one(self, query):
        for i, d in enumerate(self.docs):
            if _matches(d, query):
                del self.docs[i]
                return


def _merge_stub(name, **attrs):
    module = sys.modules.get(name) or types.ModuleType(name)
    for key, value in attrs.items():
        if not hasattr(module, key):
            setattr(module, key, value)
    sys.modules[name] = module
    return module


class _HTTPException(Exception):
    def __init__(self, status_code=None, detail=None):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class _APIRouter:
    def __init__(self, **kwargs):
        pass

    def _decorator(self, *a, **k):
        return lambda fn: fn

    get = post = put = patch = delete = _decorator


# Firebase stub whose behaviour tests drive through the token string.
class _FirebaseAuthError(Exception):
    pass


_FB = {"configured": True}


def _fb_is_configured():
    return _FB["configured"]


def _fb_verify(tok):
    if not tok or tok.startswith("bad"):
        raise _FirebaseAuthError("Could not verify your sign-in. Please try again.")
    # token format: "ok:<email>:<verified 0|1>"
    _, email, verified = tok.split(":")
    return {"uid": "fb-" + email, "email": email.lower(), "email_verified": verified == "1", "name": None}


# jwt / bcrypt stubs (auth.py imports them at module load).
class _ExpiredSignatureError(Exception):
    pass


def _jwt_encode(payload, secret, algorithm=None):
    return "jwt-" + str(payload.get("userId"))


def _jwt_decode(token, secret, algorithms=None):
    # In tests the bearer token IS the user id, so get_current_user resolves it.
    return {"userId": token}


ORG_A = {"id": "org-A", "name": "Alpha Agency", "plan": "free_beta", "seat_limit": 3, "status": "active"}
MANAGER = {"id": "mgr", "org_id": "org-A", "org_role": "manager", "status": "active",
           "name": "Mona", "email": "mona@alpha.com", "role": "hr", "is_active": 1}


@pytest.fixture(scope="module")
def world():
    os.environ.setdefault("JWT_SECRET", "test-secret")
    os.environ["APP_URL"] = "https://app.test"

    _merge_stub("fastapi", HTTPException=_HTTPException, Depends=lambda dep=None: None,
                APIRouter=_APIRouter, Request=object, status=types.SimpleNamespace())
    _merge_stub("fastapi.security", HTTPBearer=lambda **k: None, HTTPAuthorizationCredentials=object)
    _merge_stub("jwt", encode=_jwt_encode, decode=_jwt_decode,
                ExpiredSignatureError=_ExpiredSignatureError, InvalidTokenError=Exception)
    _merge_stub("bcrypt",
                hashpw=lambda pw, salt: pw + b"-h", gensalt=lambda: b"s",
                checkpw=lambda pw, h: h == pw + b"-h")

    colls = {name: FakeColl() for name in (
        "users", "jobs", "candidates", "stage_transitions", "login_activity",
        "feedback", "organizations", "invitations", "job_assignments",
        "job_jd_overrides", "activity_events",
    )}
    _merge_stub("database", ensure_indexes=lambda: None, UPLOAD_DIR=Path("."), **colls)

    _merge_stub("firebase_auth", is_configured=_fb_is_configured, verify_id_token=_fb_verify,
                FirebaseAuthError=_FirebaseAuthError)

    for mdl in ("SignupRequest", "LoginRequest", "FirebaseAuthRequest", "AcceptInviteRequest",
                "InviteCreate", "MemberStatusUpdate"):
        _merge_stub("models", **{mdl: object})

    # Force the REAL auth module against our jwt/bcrypt/database stubs.
    sys.modules.pop("auth", None)
    import auth
    import permissions
    import invites
    import routes_orgs
    import routes_auth

    for module in (auth, permissions, routes_orgs, routes_auth):
        for name, coll in colls.items():
            if hasattr(module, name):
                setattr(module, name, coll)

    return types.SimpleNamespace(
        auth=auth, orgs=routes_orgs, auth_routes=routes_auth, invites=invites,
        colls=colls, exc=sys.modules["fastapi"].HTTPException,
    )


def run(coro):
    return asyncio.run(coro)


def _seed(world, *, users=(), invitations=(), organizations=(ORG_A,)):
    world.colls["users"].docs = [dict(u) for u in users]
    world.colls["invitations"].docs = [dict(i) for i in invitations]
    world.colls["organizations"].docs = [dict(o) for o in organizations]
    world.colls["login_activity"].docs = []


def _ns(**kw):
    return types.SimpleNamespace(**kw)


def _pending_invite(email="rue@alpha.com", token="rawtok", days=7, status="pending"):
    from datetime import datetime as _dt, timezone as _tz
    import invites as _inv
    exp = (_dt.now(_tz.utc) + timedelta(days=days)).isoformat()
    return {
        "id": "inv-1", "org_id": "org-A", "email": email,
        "token_hash": _inv.hash_token(token), "invited_by": "mgr",
        "status": status, "expires_at": exp, "accepted_at": None,
        "resent_count": 0, "last_sent_at": _dt.now(_tz.utc).isoformat(),
        "created_at": _dt.now(_tz.utc).isoformat(),
    }


def _invited_member(email="rue@alpha.com"):
    return {"id": "u-rue", "name": "Rue", "email": email, "org_id": "org-A",
            "org_role": "recruiter", "status": "invited", "role": "hr", "is_active": 1}


# ===========================================================================
# create_invite
# ===========================================================================

def test_create_invite_happy_path(world):
    _seed(world, users=[MANAGER])
    out = run(world.orgs.create_invite(_ns(email="Rue@Alpha.com", name="Rue"), MANAGER))
    assert out["invite"]["email"] == "rue@alpha.com"
    assert out["invite"]["status"] == "pending"
    assert out["accept_url"].startswith("https://app.test/accept-invite?token=")
    assert out["email_sent"] is False  # SMTP not configured offline
    # A placeholder member row and an invitation row now exist.
    assert any(u["email"] == "rue@alpha.com" and u["status"] == "invited" for u in world.colls["users"].docs)
    assert len(world.colls["invitations"].docs) == 1
    # The stored invitation never holds the raw token.
    assert "rawtok" not in str(world.colls["invitations"].docs[0])


def test_create_invite_rejects_existing_teammate(world):
    _seed(world, users=[MANAGER, {**_invited_member(), "status": "active", "email": "rue@alpha.com"}])
    with pytest.raises(world.exc) as e:
        run(world.orgs.create_invite(_ns(email="rue@alpha.com", name=None), MANAGER))
    assert e.value.status_code == 409


def test_create_invite_seat_limit(world):
    # seat_limit is 3: manager + 2 invited fills it.
    members = [MANAGER,
               {**_invited_member("a@alpha.com"), "id": "a"},
               {**_invited_member("b@alpha.com"), "id": "b"}]
    _seed(world, users=members)
    with pytest.raises(world.exc) as e:
        run(world.orgs.create_invite(_ns(email="c@alpha.com", name=None), MANAGER))
    assert e.value.status_code == 409
    assert "seat" in e.value.detail.lower()


def test_create_invite_requires_app_url(world):
    _seed(world, users=[MANAGER])
    os.environ["APP_URL"] = ""
    try:
        with pytest.raises(world.exc) as e:
            run(world.orgs.create_invite(_ns(email="x@alpha.com", name=None), MANAGER))
        assert e.value.status_code == 503
    finally:
        os.environ["APP_URL"] = "https://app.test"


# ===========================================================================
# list / resend / revoke
# ===========================================================================

def test_list_invites_returns_pending_only(world):
    _seed(world, users=[MANAGER],
          invitations=[_pending_invite(), {**_pending_invite("old@alpha.com", "t2"), "id": "inv-2", "status": "revoked"}])
    rows = run(world.orgs.list_invites(MANAGER))
    assert {r["id"] for r in rows} == {"inv-1"}


def test_resend_rotates_token(world):
    inv = _pending_invite(token="oldtok")
    _seed(world, users=[MANAGER, _invited_member()], invitations=[inv])
    old_hash = world.colls["invitations"].docs[0]["token_hash"]
    out = run(world.orgs.resend_invite("inv-1", MANAGER))
    new_hash = world.colls["invitations"].docs[0]["token_hash"]
    assert new_hash != old_hash                      # old link no longer works
    assert out["invite"]["resent_count"] == 1
    assert out["accept_url"].startswith("https://app.test/accept-invite?token=")


def test_revoke_marks_revoked_and_frees_seat(world):
    _seed(world, users=[MANAGER, _invited_member()], invitations=[_pending_invite()])
    out = run(world.orgs.revoke_invite("inv-1", MANAGER))
    assert out["success"] is True
    assert world.colls["invitations"].docs[0]["status"] == "revoked"
    # placeholder member removed → seat freed
    assert not any(u["email"] == "rue@alpha.com" for u in world.colls["users"].docs)


def test_revoke_accepted_invite_is_409(world):
    _seed(world, users=[MANAGER], invitations=[{**_pending_invite(), "status": "accepted"}])
    with pytest.raises(world.exc) as e:
        run(world.orgs.revoke_invite("inv-1", MANAGER))
    assert e.value.status_code == 409


def test_manager_cannot_touch_another_orgs_invite(world):
    _seed(world, users=[MANAGER], invitations=[{**_pending_invite(), "org_id": "org-B"}])
    with pytest.raises(world.exc) as e:
        run(world.orgs.revoke_invite("inv-1", MANAGER))
    assert e.value.status_code == 404  # scoped by org_id → not found


# ===========================================================================
# validate_invite (public)
# ===========================================================================

def test_validate_valid_token(world):
    _seed(world, users=[MANAGER], invitations=[_pending_invite()])
    out = run(world.orgs.validate_invite("rawtok"))
    assert out["valid"] is True
    assert out["email"] == "rue@alpha.com"
    assert out["org_name"] == "Alpha Agency"


def test_validate_expired_token_is_neutral(world):
    _seed(world, users=[MANAGER], invitations=[_pending_invite(days=-1)])
    out = run(world.orgs.validate_invite("rawtok"))
    assert out["valid"] is False
    assert out["reason"] == "expired"
    assert "email" not in out  # no PII leaked for an unusable token


def test_validate_unknown_token(world):
    _seed(world, users=[MANAGER], invitations=[])
    out = run(world.orgs.validate_invite("nope"))
    assert out == {"valid": False, "reason": "unknown"}


# ===========================================================================
# accept_invite
# ===========================================================================

def test_accept_invite_happy_path(world):
    _FB["configured"] = True
    _seed(world, users=[MANAGER, _invited_member()], invitations=[_pending_invite()])
    out = run(world.auth_routes.accept_invite(
        _ns(token="rawtok", firebase_id_token="ok:rue@alpha.com:1"),
        _ns(client=None, headers={}),
    ))
    assert out["token"] == "jwt-u-rue"
    assert out["user"]["status"] == "active"
    member = next(u for u in world.colls["users"].docs if u["id"] == "u-rue")
    assert member["status"] == "active" and member["firebase_uid"] == "fb-rue@alpha.com"
    assert world.colls["invitations"].docs[0]["status"] == "accepted"


def test_accept_invite_wrong_email(world):
    _FB["configured"] = True
    _seed(world, users=[MANAGER, _invited_member()], invitations=[_pending_invite()])
    with pytest.raises(world.exc) as e:
        run(world.auth_routes.accept_invite(
            _ns(token="rawtok", firebase_id_token="ok:someone@else.com:1"),
            _ns(client=None, headers={}),
        ))
    assert e.value.status_code == 400
    assert world.colls["invitations"].docs[0]["status"] == "pending"  # not consumed


def test_accept_invite_expired_is_410(world):
    _seed(world, users=[MANAGER, _invited_member()], invitations=[_pending_invite(days=-1)])
    with pytest.raises(world.exc) as e:
        run(world.auth_routes.accept_invite(
            _ns(token="rawtok", firebase_id_token="ok:rue@alpha.com:1"),
            _ns(client=None, headers={}),
        ))
    assert e.value.status_code == 410


def test_accept_invite_already_accepted_is_409(world):
    _seed(world, users=[MANAGER], invitations=[{**_pending_invite(), "status": "accepted"}])
    with pytest.raises(world.exc) as e:
        run(world.auth_routes.accept_invite(
            _ns(token="rawtok", firebase_id_token="ok:rue@alpha.com:1"),
            _ns(client=None, headers={}),
        ))
    assert e.value.status_code == 409


def test_accept_invite_firebase_not_configured_is_503(world):
    _seed(world, users=[MANAGER, _invited_member()], invitations=[_pending_invite()])
    _FB["configured"] = False
    try:
        with pytest.raises(world.exc) as e:
            run(world.auth_routes.accept_invite(
                _ns(token="rawtok", firebase_id_token="ok:rue@alpha.com:1"),
                _ns(client=None, headers={}),
            ))
        assert e.value.status_code == 503
    finally:
        _FB["configured"] = True


def test_accept_invite_bad_firebase_token_is_401(world):
    _FB["configured"] = True
    _seed(world, users=[MANAGER, _invited_member()], invitations=[_pending_invite()])
    with pytest.raises(world.exc) as e:
        run(world.auth_routes.accept_invite(
            _ns(token="rawtok", firebase_id_token="bad-token"),
            _ns(client=None, headers={}),
        ))
    assert e.value.status_code == 401


# ===========================================================================
# members: suspend / reactivate
# ===========================================================================

def test_suspend_member(world):
    rec = {"id": "u-rec", "org_id": "org-A", "org_role": "recruiter", "status": "active",
           "name": "Rex", "email": "rex@alpha.com"}
    _seed(world, users=[MANAGER, rec])
    out = run(world.orgs.update_member("u-rec", _ns(status="disabled"), MANAGER))
    assert out["status"] == "disabled"
    assert next(u for u in world.colls["users"].docs if u["id"] == "u-rec")["status"] == "disabled"


def test_manager_cannot_suspend_self(world):
    _seed(world, users=[MANAGER])
    with pytest.raises(world.exc) as e:
        run(world.orgs.update_member("mgr", _ns(status="disabled"), MANAGER))
    assert e.value.status_code == 400


def test_cannot_suspend_last_active_manager(world):
    other_mgr = {"id": "mgr2", "org_id": "org-A", "org_role": "manager", "status": "active",
                 "name": "Moe", "email": "moe@alpha.com"}
    _seed(world, users=[MANAGER, other_mgr])
    # Suspending the only OTHER manager while there are 2 managers is fine…
    run(world.orgs.update_member("mgr2", _ns(status="disabled"), MANAGER))
    # …now only MANAGER is active; suspending them (via mgr2 reactivated? no) —
    # simulate a single active manager and try to suspend it through a peer path.
    _seed(world, users=[MANAGER, {**other_mgr, "status": "disabled"}])
    with pytest.raises(world.exc) as e:
        run(world.orgs.update_member("mgr", _ns(status="disabled"), other_mgr))
    assert e.value.status_code == 409


def test_update_member_cross_org_is_404(world):
    _seed(world, users=[MANAGER, {"id": "x", "org_id": "org-B", "org_role": "recruiter", "status": "active"}])
    with pytest.raises(world.exc) as e:
        run(world.orgs.update_member("x", _ns(status="disabled"), MANAGER))
    assert e.value.status_code == 404


# ===========================================================================
# org_me
# ===========================================================================

def test_org_me_reports_seats(world):
    _seed(world, users=[MANAGER, _invited_member()])
    out = run(world.orgs.org_me(MANAGER))
    assert out["org"]["name"] == "Alpha Agency"
    assert out["org"]["seat_limit"] == 3
    assert out["org"]["seats_used"] == 2  # manager + one invited
    assert out["role"] == "manager"


# ===========================================================================
# get_current_user suspension gate (real auth.py)
# ===========================================================================

def test_get_current_user_blocks_suspended(world):
    world.colls["users"].docs = [
        {"id": "susp", "status": "disabled", "is_active": 1, "org_id": "org-A"},
    ]
    with pytest.raises(world.exc) as e:
        run(world.auth.get_current_user(_ns(credentials="susp")))
    assert e.value.status_code == 401
    assert "suspend" in e.value.detail.lower()


def test_get_current_user_allows_active(world):
    world.colls["users"].docs = [
        {"id": "ok", "status": "active", "is_active": 1, "org_id": "org-A", "name": "OK"},
    ]
    user = run(world.auth.get_current_user(_ns(credentials="ok")))
    assert user["id"] == "ok"


def test_get_current_user_blocks_platform_deactivated(world):
    world.colls["users"].docs = [{"id": "d", "status": "active", "is_active": 0, "org_id": "org-A"}]
    with pytest.raises(world.exc) as e:
        run(world.auth.get_current_user(_ns(credentials="d")))
    assert e.value.status_code == 403
