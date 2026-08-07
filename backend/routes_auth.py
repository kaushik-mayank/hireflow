import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Request

from database import users, login_activity, organizations
from auth import hash_password, verify_password, create_token, get_current_user
from admin_identity import effective_role, HR_ROLE
from models import SignupRequest, LoginRequest, FirebaseAuthRequest, OnboardingCheck
import firebase_auth

router = APIRouter(prefix="/auth", tags=["auth"])

ORG_SETUP_FAILED = "We couldn't finish setting up your account. Please try again."


def _public_user(u: dict) -> dict:
    return {
        "id": u["id"],
        "name": u["name"],
        "email": u["email"],
        # Platform role, derived from the allowlist on every response — gates
        # /admin/* only. Never read from the stored field.
        "role": effective_role(u),
        "company": u.get("company"),
        # Org identity for the frontend (Cycle 2). A legacy user with no org is
        # treated as their own manager so the manager UI still works for them.
        "org_id": u.get("org_id"),
        "org_role": u.get("org_role") or "manager",
        "status": u.get("status") or "active",
    }


def _org_name_for(name: str | None, company: str | None) -> str:
    company = (company or "").strip()
    if company:
        return company
    return f"{(name or 'My').strip()}'s Team"


async def _create_org(owner_user_id: str, name: str | None, company: str | None) -> str:
    """Create an organisation owned by this user. Raises 500 on failure so the
    caller can compensate (never leave a half-created account)."""
    now = datetime.now(timezone.utc).isoformat()
    org = {
        "id": f"org-{uuid.uuid4()}",
        "name": _org_name_for(name, company),
        "owner_user_id": owner_user_id,
        "plan": "free_beta",
        "seat_limit": 25,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    try:
        await organizations.insert_one(org)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=ORG_SETUP_FAILED) from exc
    return org["id"]


async def _record_login(user: dict, request: Request | None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    await users.update_one({"id": user["id"]}, {"$set": {"last_login_at": now}})
    await login_activity.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "ip_address": request.client.host if request and request.client else None,
        "user_agent": request.headers.get("user-agent") if request else None,
        "action": "login",
        "created_at": now,
    })


@router.post("/signup")
async def signup(body: SignupRequest):
    """Legacy password signup.

    Always creates an `hr` account. There is no way to request any other role —
    the request model no longer carries one, and the value below is a constant.
    """
    existing = await users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    now = datetime.now(timezone.utc).isoformat()
    user_id = str(uuid.uuid4())
    org_id = await _create_org(user_id, body.name, body.company)
    user = {
        "id": user_id,
        "name": body.name,
        "email": body.email.lower(),
        "password_hash": hash_password(body.password),
        "company": body.company,
        "role": HR_ROLE,
        "is_active": 1,
        "org_id": org_id,
        "org_role": "manager",
        "status": "active",
        "invited_by": None,
        "activated_at": now,
        "last_login_at": now,
        "created_at": now,
    }
    try:
        await users.insert_one(user)
    except Exception as exc:
        await organizations.delete_one({"id": org_id})
        raise HTTPException(status_code=500, detail=ORG_SETUP_FAILED) from exc
    token = create_token(user)
    return {"token": token, "user": _public_user(user)}


@router.post("/login")
async def login(body: LoginRequest, request: Request):
    user = await users.find_one({"email": body.email.lower()}, {"_id": 0})
    if not user or not user.get("password_hash") or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("is_active", 1) or user.get("status") == "disabled":
        raise HTTPException(status_code=403, detail="Your account has been deactivated")

    # Self-heal an org-less legacy/demo account so org-scoped routes work for it.
    if not user.get("org_id"):
        org_id = await _create_org(user["id"], user.get("name"), user.get("company"))
        await users.update_one({"id": user["id"]}, {"$set": {
            "org_id": org_id, "org_role": "manager", "status": "active",
        }})
        user.update({"org_id": org_id, "org_role": "manager", "status": "active"})

    await _record_login(user, request)
    return {"token": create_token(user), "user": _public_user(user)}


# Whether a Firebase user must have a verified email before a session is
# issued. Defaults on — during live testing you want real, confirmed emails.
# Set REQUIRE_EMAIL_VERIFICATION=false only if you deliberately want to skip it.
REQUIRE_EMAIL_VERIFICATION = os.environ.get(
    "REQUIRE_EMAIL_VERIFICATION", "true"
).strip().lower() not in ("0", "false", "no", "off")


@router.post("/firebase")
async def firebase_exchange(body: FirebaseAuthRequest, request: Request):
    """Exchange a verified Firebase ID token for this app's own JWT.

    Firebase owns credentials, email verification and password resets. Session
    handling downstream is unchanged: the caller receives the same JWT the
    password flow issues, so every existing route and guard keeps working.

    The account record (including the name and company entered at signup) is
    created/updated whenever a valid token arrives, so nothing is lost — but a
    SESSION is only issued once the email is verified. Until then this returns
    {"verified": false} and no token, which is how the frontend knows to show
    the "check your email" screen. This closes the reported gap where creating
    a password granted immediate dashboard access.

    Accounts created here are always `hr`. Admin comes only from the allowlist.
    """
    # Distinguish a server misconfiguration from a bad token: a 503 with a clear
    # message is far easier to diagnose than a generic 401, and it can't be
    # mistaken for "session expired". This is the case that fires when the
    # backend is missing FIREBASE_PROJECT_ID (the plain var, not REACT_APP_*).
    if not firebase_auth.is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Firebase sign-in isn't configured on the server. Set FIREBASE_PROJECT_ID "
                "(no REACT_APP_ prefix) on the backend to your Firebase project id."
            ),
        )
    try:
        claims = firebase_auth.verify_id_token(body.id_token)
    except firebase_auth.FirebaseAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    now = datetime.now(timezone.utc).isoformat()
    user = await users.find_one({"email": claims["email"]}, {"_id": 0})

    # An approved recruiter (added by their admin, awaiting first sign-in) is
    # activated here rather than through a public signup. Because the admin
    # already vouched for the email, activation does NOT wait on email
    # verification — that gate applies only to public manager sign-ups below.
    approved_recruiter = bool(user) and user.get("status") in ("approved", "invited")

    if user:
        if not user.get("is_active", 1) or user.get("status") == "disabled":
            raise HTTPException(status_code=403, detail="Your account has been deactivated")
        updates = {"email_verified": claims["email_verified"]}
        # Link the Firebase UID on first federated sign-in of an existing account.
        if user.get("firebase_uid") != claims["uid"]:
            updates["firebase_uid"] = claims["uid"]
        # Backfill name/company from signup if this record was missing them.
        if body.name and not user.get("name"):
            updates["name"] = body.name
        if body.company and not user.get("company"):
            updates["company"] = body.company
        if approved_recruiter:
            # First sign-in of an approved recruiter: activate, keep their org and
            # recruiter role exactly as the admin set them (role stays sticky).
            updates.update({"status": "active", "activated_at": now})
        elif not user.get("org_id"):
            # Self-heal: a legacy user with no org (e.g. migration not yet run)
            # becomes the manager of a freshly created org.
            org_id = await _create_org(user["id"], user.get("name"), body.company or user.get("company"))
            updates.update({"org_id": org_id, "org_role": "manager", "status": "active"})
        await users.update_one({"id": user["id"]}, {"$set": updates})
        user.update(updates)
    else:
        user_id = str(uuid.uuid4())
        name = body.name or claims.get("name") or claims["email"].split("@")[0]
        # Manager sign-up: create the org first, then the user; if the user
        # insert fails, delete the orphan org so we never half-create an account.
        org_id = await _create_org(user_id, name, body.company)
        user = {
            "id": user_id,
            "name": name,
            "email": claims["email"],
            "password_hash": None,
            "company": body.company,
            "role": HR_ROLE,
            "firebase_uid": claims["uid"],
            "email_verified": claims["email_verified"],
            "is_active": 1,
            "org_id": org_id,
            "org_role": "manager",
            "status": "active",
            "invited_by": None,
            "activated_at": now,
            "last_login_at": now,
            "created_at": now,
        }
        try:
            await users.insert_one(user)
        except Exception as exc:
            await organizations.delete_one({"id": org_id})
            raise HTTPException(status_code=500, detail=ORG_SETUP_FAILED) from exc
        user.pop("_id", None)

    # Gate the session on a verified email — but ONLY for public manager
    # sign-ups. A recruiter (whether being activated now or signing in later)
    # never hits this: their admin vouched for the address and they verify it as
    # part of first-time setup, so their later password logins must not be
    # bounced back to a "verify your email" screen.
    is_recruiter = bool(user) and user.get("org_role") == "recruiter"
    if (REQUIRE_EMAIL_VERIFICATION and not claims["email_verified"]
            and not approved_recruiter and not is_recruiter):
        return {"verified": False}

    await _record_login(user, request)
    return {"verified": True, "token": create_token(user), "user": _public_user(user)}


@router.post("/onboarding-status")
async def onboarding_status(body: OnboardingCheck):
    """Tell the login page how to greet this email (public, no auth):

    - `needs_setup` — an admin approved them but they have no credentials yet, so
      show a "create your password" screen.
    - `registered`  — they already have credentials, so ask for their password.
    - `not_approved` — no account; ask them to check with their admin or, if
      they're starting an organisation, to sign up.

    Returns only a coarse status (no name, no org), and the behaviour is
    deliberate: the whole point of admin-approved onboarding is to tell an
    approved teammate to set a password and an unknown email that it isn't set up.
    """
    email = body.email.lower().strip()
    user = await users.find_one({"email": email}, {"_id": 0})
    if not user:
        return {"status": "not_approved"}
    if user.get("status") == "disabled":
        # Don't offer setup/sign-in to a suspended account; keep it neutral.
        return {"status": "not_approved"}
    if user.get("firebase_uid") or user.get("password_hash"):
        return {"status": "registered"}
    return {"status": "needs_setup"}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"user": _public_user(user)}
