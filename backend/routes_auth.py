import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Request

from database import users, login_activity
from auth import hash_password, verify_password, create_token, get_current_user
from admin_identity import effective_role, HR_ROLE
from models import SignupRequest, LoginRequest, FirebaseAuthRequest
import firebase_auth

router = APIRouter(prefix="/auth", tags=["auth"])


def _public_user(u: dict) -> dict:
    return {
        "id": u["id"],
        "name": u["name"],
        "email": u["email"],
        # Derived from the server-side allowlist on every response, never read
        # from the stored field.
        "role": effective_role(u),
        "company": u.get("company"),
    }


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
    user = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "email": body.email.lower(),
        "password_hash": hash_password(body.password),
        "company": body.company,
        "role": HR_ROLE,
        "is_active": 1,
        "last_login_at": now,
        "created_at": now,
    }
    await users.insert_one(user)
    token = create_token(user)
    return {"token": token, "user": _public_user(user)}


@router.post("/login")
async def login(body: LoginRequest, request: Request):
    user = await users.find_one({"email": body.email.lower()}, {"_id": 0})
    if not user or not user.get("password_hash") or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("is_active", 1):
        raise HTTPException(status_code=403, detail="Your account has been deactivated")

    await _record_login(user, request)
    return {"token": create_token(user), "user": _public_user(user)}


@router.post("/firebase")
async def firebase_exchange(body: FirebaseAuthRequest, request: Request):
    """Exchange a verified Firebase ID token for this app's own JWT.

    Firebase owns credentials, email verification and password resets. Session
    handling downstream is unchanged: the caller receives the same JWT the
    password flow issues, so every existing route and guard keeps working.

    Accounts created here are always `hr`. Admin comes only from the allowlist.
    """
    try:
        claims = firebase_auth.verify_id_token(body.id_token)
    except firebase_auth.FirebaseAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    now = datetime.now(timezone.utc).isoformat()
    user = await users.find_one({"email": claims["email"]}, {"_id": 0})

    if user:
        if not user.get("is_active", 1):
            raise HTTPException(status_code=403, detail="Your account has been deactivated")
        # Link the Firebase UID on first federated sign-in of an existing
        # account, so the allowlist can match on UID as well as email.
        if user.get("firebase_uid") != claims["uid"]:
            await users.update_one(
                {"id": user["id"]}, {"$set": {"firebase_uid": claims["uid"]}}
            )
            user["firebase_uid"] = claims["uid"]
    else:
        user = {
            "id": str(uuid.uuid4()),
            "name": body.name or claims.get("name") or claims["email"].split("@")[0],
            "email": claims["email"],
            "password_hash": None,
            "company": body.company,
            "role": HR_ROLE,
            "firebase_uid": claims["uid"],
            "email_verified": claims["email_verified"],
            "is_active": 1,
            "last_login_at": now,
            "created_at": now,
        }
        await users.insert_one(user)
        user.pop("_id", None)

    await _record_login(user, request)
    return {"token": create_token(user), "user": _public_user(user)}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"user": _public_user(user)}
