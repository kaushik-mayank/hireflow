"""Route-level tests for the approved-email onboarding flow (Cycle 2).

No emailed invitations in this release: an admin stores approved recruiter emails
(single or bulk); each recruiter sets their own password on first Firebase
sign-in, which activates them with a sticky recruiter role. Brand-new,
unapproved emails become their own manager (public manager sign-up).

Offline. Stubs the modules that need native deps (jwt, bcrypt, motor/database,
firebase_auth) but imports the REAL auth / permissions / routes_orgs / routes_auth
so the actual enforcement runs. Collection references are rebound to shared fakes
regardless of import order (stub-merge pattern), so reverse-order runs stay green.
"""

import asyncio
import os
import sys
import types
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


class _ExpiredSignatureError(Exception):
    pass


def _jwt_encode(payload, secret, algorithm=None):
    return "jwt-" + str(payload.get("userId"))


def _jwt_decode(token, secret, algorithms=None):
    return {"userId": token}


ORG_A = {"id": "org-A", "name": "Alpha Agency", "plan": "free_beta", "seat_limit": 3, "status": "active"}
MANAGER = {"id": "mgr", "org_id": "org-A", "org_role": "manager", "status": "active",
           "name": "Mona", "email": "mona@alpha.com", "role": "hr", "is_active": 1}


@pytest.fixture(scope="module")
def world():
    os.environ.setdefault("JWT_SECRET", "test-secret")

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

    for mdl in ("SignupRequest", "LoginRequest", "FirebaseAuthRequest",
                "MemberCreate", "BulkMemberCreate", "MemberStatusUpdate"):
        _merge_stub("models", **{mdl: object})

    sys.modules.pop("auth", None)
    import auth
    import permissions
    import routes_orgs
    import routes_auth

    for module in (auth, permissions, routes_orgs, routes_auth):
        for name, coll in colls.items():
            if hasattr(module, name):
                setattr(module, name, coll)

    return types.SimpleNamespace(
        auth=auth, orgs=routes_orgs, auth_routes=routes_auth,
        colls=colls, exc=sys.modules["fastapi"].HTTPException,
    )


def run(coro):
    return asyncio.run(coro)


def _seed(world, *, users=(), organizations=(ORG_A,)):
    world.colls["users"].docs = [dict(u) for u in users]
    world.colls["organizations"].docs = [dict(o) for o in organizations]
    world.colls["login_activity"].docs = []


def _ns(**kw):
    return types.SimpleNamespace(**kw)


def _approved(email="rue@alpha.com", uid="u-rue"):
    return {"id": uid, "name": "Rue", "email": email, "org_id": "org-A",
            "org_role": "recruiter", "status": "approved", "role": "hr", "is_active": 1,
            "firebase_uid": None, "password_hash": None}


# ===========================================================================
# add_member (single)
# ===========================================================================

def test_add_member_happy_path(world):
    _seed(world, users=[MANAGER])
    out = run(world.orgs.add_member(_ns(email="Rue@Alpha.com", name="Rue"), MANAGER))
    assert out["email"] == "rue@alpha.com"
    assert out["org_role"] == "recruiter"
    assert out["status"] == "approved"
    row = next(u for u in world.colls["users"].docs if u["email"] == "rue@alpha.com")
    assert row["password_hash"] is None and row["firebase_uid"] is None  # they set it later


def test_add_member_rejects_existing_teammate(world):
    _seed(world, users=[MANAGER, {**_approved(), "status": "active"}])
    with pytest.raises(world.exc) as e:
        run(world.orgs.add_member(_ns(email="rue@alpha.com", name=None), MANAGER))
    assert e.value.status_code == 409


def test_add_member_rejects_duplicate_approval(world):
    _seed(world, users=[MANAGER, _approved()])
    with pytest.raises(world.exc) as e:
        run(world.orgs.add_member(_ns(email="rue@alpha.com", name=None), MANAGER))
    assert e.value.status_code == 409
    assert "approved" in e.value.detail.lower()


def test_add_member_seat_limit(world):
    members = [MANAGER, {**_approved("a@alpha.com", "a")}, {**_approved("b@alpha.com", "b")}]
    _seed(world, users=members)  # seat_limit 3, already full
    with pytest.raises(world.exc) as e:
        run(world.orgs.add_member(_ns(email="c@alpha.com", name=None), MANAGER))
    assert e.value.status_code == 409
    assert "seat" in e.value.detail.lower()


# ===========================================================================
# add_members_bulk
# ===========================================================================

def test_bulk_add_parses_and_skips(world):
    _seed(world, users=[MANAGER])
    text = "one@alpha.com, two@alpha.com\nnot-an-email  three@alpha.com; two@alpha.com"
    out = run(world.orgs.add_members_bulk(_ns(text=text), MANAGER))
    added = {a["email"] for a in out["added"]}
    skipped = {s["email"]: s["reason"] for s in out["skipped"]}
    # 3 unique valid emails, but seat_limit 3 with manager already using one -> 2 seats.
    assert added == {"one@alpha.com", "two@alpha.com"}
    assert skipped.get("not-an-email") == "not a valid email"
    assert skipped.get("three@alpha.com") == "seat limit reached"
    assert out["seat_limit"] == 3 and out["seats_used"] == 3


def test_bulk_add_reports_existing(world):
    _seed(world, users=[MANAGER, {**_approved("dupe@alpha.com", "d")}])
    out = run(world.orgs.add_members_bulk(_ns(text="dupe@alpha.com new@alpha.com"), MANAGER))
    assert {a["email"] for a in out["added"]} == {"new@alpha.com"}
    assert any(s["email"] == "dupe@alpha.com" for s in out["skipped"])


# ===========================================================================
# list / remove members
# ===========================================================================

def test_list_members_includes_approved_and_active(world):
    _seed(world, users=[MANAGER, _approved()])
    rows = run(world.orgs.list_members(MANAGER))
    assert {r["email"] for r in rows} == {"mona@alpha.com", "rue@alpha.com"}


def test_remove_approved_member_frees_seat(world):
    _seed(world, users=[MANAGER, _approved()])
    out = run(world.orgs.remove_member("u-rue", MANAGER))
    assert out["success"] is True
    assert not any(u["id"] == "u-rue" for u in world.colls["users"].docs)


def test_remove_active_member_is_409(world):
    _seed(world, users=[MANAGER, {**_approved(), "status": "active"}])
    with pytest.raises(world.exc) as e:
        run(world.orgs.remove_member("u-rue", MANAGER))
    assert e.value.status_code == 409


def test_remove_cross_org_is_404(world):
    _seed(world, users=[MANAGER, {**_approved(), "org_id": "org-B"}])
    with pytest.raises(world.exc) as e:
        run(world.orgs.remove_member("u-rue", MANAGER))
    assert e.value.status_code == 404


# ===========================================================================
# members: suspend / reactivate
# ===========================================================================

def test_suspend_member(world):
    rec = {"id": "u-rec", "org_id": "org-A", "org_role": "recruiter", "status": "active",
           "name": "Rex", "email": "rex@alpha.com"}
    _seed(world, users=[MANAGER, rec])
    out = run(world.orgs.update_member("u-rec", _ns(status="disabled"), MANAGER))
    assert out["status"] == "disabled"


def test_manager_cannot_suspend_self(world):
    _seed(world, users=[MANAGER])
    with pytest.raises(world.exc) as e:
        run(world.orgs.update_member("mgr", _ns(status="disabled"), MANAGER))
    assert e.value.status_code == 400


def test_cannot_suspend_last_active_manager(world):
    other_mgr = {"id": "mgr2", "org_id": "org-A", "org_role": "manager", "status": "disabled",
                 "name": "Moe", "email": "moe@alpha.com"}
    _seed(world, users=[MANAGER, other_mgr])
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
    _seed(world, users=[MANAGER, _approved()])
    out = run(world.orgs.org_me(MANAGER))
    assert out["org"]["seat_limit"] == 3
    assert out["org"]["seats_used"] == 2  # manager + one approved
    assert out["role"] == "manager"


# ===========================================================================
# firebase_exchange: approved-recruiter activation vs public manager sign-up
# ===========================================================================

def test_approved_recruiter_activates_on_first_signin(world):
    _FB["configured"] = True
    _seed(world, users=[MANAGER, _approved()])
    # email_verified is False (":0"), but an approved recruiter is activated anyway.
    out = run(world.auth_routes.firebase_exchange(
        _ns(id_token="ok:rue@alpha.com:0", name=None, company=None),
        _ns(client=None, headers={}),
    ))
    assert out["verified"] is True
    assert out["user"]["org_role"] == "recruiter"   # role stays sticky
    assert out["user"]["org_id"] == "org-A"          # joins the admin's org, no new org
    row = next(u for u in world.colls["users"].docs if u["email"] == "rue@alpha.com")
    assert row["status"] == "active" and row["firebase_uid"] == "fb-rue@alpha.com"


def test_new_unapproved_email_becomes_manager(world):
    _FB["configured"] = True
    _seed(world, users=[MANAGER])
    out = run(world.auth_routes.firebase_exchange(
        _ns(id_token="ok:founder@beta.com:1", name="Fay", company="Beta Co"),
        _ns(client=None, headers={}),
    ))
    assert out["verified"] is True
    assert out["user"]["org_role"] == "manager"      # public sign-up -> admin
    new_user = next(u for u in world.colls["users"].docs if u["email"] == "founder@beta.com")
    assert new_user["org_id"] and new_user["org_id"] != "org-A"  # got their own org


def test_new_manager_unverified_email_gets_no_session(world):
    _FB["configured"] = True
    _seed(world, users=[MANAGER])
    out = run(world.auth_routes.firebase_exchange(
        _ns(id_token="ok:unverified@beta.com:0", name=None, company=None),
        _ns(client=None, headers={}),
    ))
    # A public manager sign-up still needs a verified email — no token issued.
    assert out == {"verified": False}


def test_suspended_user_cannot_exchange(world):
    _FB["configured"] = True
    _seed(world, users=[MANAGER, {**_approved(), "status": "disabled"}])
    with pytest.raises(world.exc) as e:
        run(world.auth_routes.firebase_exchange(
            _ns(id_token="ok:rue@alpha.com:1", name=None, company=None),
            _ns(client=None, headers={}),
        ))
    assert e.value.status_code == 403


# ===========================================================================
# get_current_user suspension gate (real auth.py)
# ===========================================================================

def test_get_current_user_blocks_suspended(world):
    world.colls["users"].docs = [{"id": "susp", "status": "disabled", "is_active": 1, "org_id": "org-A"}]
    with pytest.raises(world.exc) as e:
        run(world.auth.get_current_user(_ns(credentials="susp")))
    assert e.value.status_code == 401
    assert "suspend" in e.value.detail.lower()


def test_get_current_user_allows_active(world):
    world.colls["users"].docs = [{"id": "ok", "status": "active", "is_active": 1, "org_id": "org-A", "name": "OK"}]
    user = run(world.auth.get_current_user(_ns(credentials="ok")))
    assert user["id"] == "ok"


def test_get_current_user_blocks_platform_deactivated(world):
    world.colls["users"].docs = [{"id": "d", "status": "active", "is_active": 0, "org_id": "org-A"}]
    with pytest.raises(world.exc) as e:
        run(world.auth.get_current_user(_ns(credentials="d")))
    assert e.value.status_code == 403
