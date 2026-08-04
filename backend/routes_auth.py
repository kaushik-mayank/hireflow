import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Request

from database import users, login_activity, organizations, invitations
from auth import hash_password, verify_password, create_token, get_current_user
from admin_identity import effective_role, HR_ROLE
from models import SignupRequest, LoginRequest, FirebaseAuthRequest, AcceptInviteRequest
import firebase_auth
import invites

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
        # Self-heal: an existing user with no org (e.g. migration not yet run)
        # becomes the manager of a freshly created org. Invited recruiters never
        # reach this endpoint's create path — they use /auth/accept-invite.
        if not user.get("org_id"):
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

    # Gate the session on a verified email. The record above is already saved.
    if REQUIRE_EMAIL_VERIFICATION and not claims["email_verified"]:
        return {"verified": False}

    await _record_login(user, request)
    return {"verified": True, "token": create_token(user), "user": _public_user(user)}


async def _accept_rate_limited(inv: dict, now: datetime) -> bool:
    """Per-token throttle on accept attempts, so a leaked/guessed token can't be
    hammered. A rolling one-hour window stored on the invitation doc."""
    window_start = inv.get("accept_window_start")
    attempts = inv.get("accept_attempts", 0)
    cutoff = invites.one_hour_ago_iso(now)
    if not window_start or window_start < cutoff:
        window_start, attempts = now.isoformat(), 0
    if not invites.within_rate_limit(attempts, invites.ACCEPT_ATTEMPTS_PER_HOUR):
        return True
    await invitations.update_one(
        {"id": inv["id"]},
        {"$set": {"accept_window_start": window_start, "accept_attempts": attempts + 1}},
    )
    return False


# Friendly, non-leaking messages for a token that can't be accepted.
_ACCEPT_MESSAGE = {
    invites.ACCEPTED: (409, "You've already set up your account — please sign in."),
    invites.EXPIRED: (410, "This invitation has expired. Ask your admin to resend it."),
    invites.REVOKED: (400, "This invitation link is no longer valid."),
    invites.UNKNOWN: (400, "This invitation link is no longer valid."),
}


@router.post("/accept-invite")
async def accept_invite(body: AcceptInviteRequest, request: Request):
    """Complete a recruiter's onboarding from an emailed invite.

    Email verification is deliberately NOT required on this path: holding the
    emailed token already proves the recruiter controls that mailbox. That bypass
    lives here and only here — it is never a global flag, so the manager sign-up
    path keeps requiring a verified email.
    """
    now = datetime.now(timezone.utc)
    inv = await invitations.find_one({"token_hash": invites.hash_token(body.token)}, {"_id": 0})

    reason = invites.invite_reason(inv, now)
    if reason != invites.VALID:
        code, message = _ACCEPT_MESSAGE.get(reason, (400, "This invitation link is no longer valid."))
        raise HTTPException(status_code=code, detail=message)

    if await _accept_rate_limited(inv, now):
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait a little and try again.")

    if not firebase_auth.is_configured():
        raise HTTPException(status_code=503, detail="Sign-in isn't configured on the server.")
    try:
        claims = firebase_auth.verify_id_token(body.firebase_id_token)
    except firebase_auth.FirebaseAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    # The token must belong to the exact address the invite was issued to.
    if claims["email"] != inv["email"]:
        raise HTTPException(status_code=400, detail="This invitation was issued for a different email address.")

    now_iso = now.isoformat()
    member = await users.find_one({"email": inv["email"]}, {"_id": 0})
    activation = {
        "firebase_uid": claims["uid"],
        "email_verified": claims["email_verified"],
        "status": "active",
        "activated_at": now_iso,
    }
    if member:
        await users.update_one({"id": member["id"]}, {"$set": activation})
        member.update(activation)
    else:
        # Placeholder missing (e.g. cleaned up) — recreate the recruiter row.
        member = {
            "id": str(uuid.uuid4()),
            "name": claims.get("name") or inv["email"].split("@")[0],
            "email": inv["email"],
            "password_hash": None,
            "role": HR_ROLE,
            "org_id": inv["org_id"],
            "org_role": "recruiter",
            "invited_by": inv.get("invited_by"),
            "is_active": 1,
            "last_login_at": None,
            "created_at": now_iso,
            **activation,
        }
        await users.insert_one(member)
        member.pop("_id", None)

    await invitations.update_one(
        {"id": inv["id"]}, {"$set": {"status": "accepted", "accepted_at": now_iso}}
    )

    await _record_login(member, request)
    return {"token": create_token(member), "user": _public_user(member)}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"user": _public_user(user)}
