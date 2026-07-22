import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Request

from database import users, login_activity
from auth import hash_password, verify_password, create_token, get_current_user
from models import SignupRequest, LoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])


def _public_user(u: dict) -> dict:
    return {
        "id": u["id"],
        "name": u["name"],
        "email": u["email"],
        "role": u["role"],
        "company": u.get("company"),
    }


@router.post("/signup")
async def signup(body: SignupRequest):
    existing = await users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    role = body.role if body.role in ("hr", "admin") else "hr"
    now = datetime.now(timezone.utc).isoformat()
    user = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "email": body.email.lower(),
        "password_hash": hash_password(body.password),
        "company": body.company,
        "role": role,
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
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("is_active", 1):
        raise HTTPException(status_code=403, detail="Your account has been deactivated")

    now = datetime.now(timezone.utc).isoformat()
    await users.update_one({"id": user["id"]}, {"$set": {"last_login_at": now}})
    await login_activity.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "action": "login",
        "created_at": now,
    })
    token = create_token(user)
    return {"token": token, "user": _public_user(user)}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"user": _public_user(user)}
