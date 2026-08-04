"""Organisation management: recruiter invitations, team members, org summary.

All manager-only endpoints go through `permissions.require_manager` (org Manager,
UI "Admin" — distinct from the platform-admin allowlist). Everything is scoped to
the caller's own org; a manager can never see or touch another org's members or
invites. The one public endpoint (`GET /invites/{token}`) returns only the
invitee's own email and the org name, and only for a genuinely valid token.
"""

import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from database import users, organizations, invitations, job_assignments, candidates
from admin_identity import HR_ROLE
from models import InviteCreate, MemberStatusUpdate
import permissions
import invites
import email_service

router = APIRouter(prefix="/orgs", tags=["orgs"])
public_router = APIRouter(prefix="/invites", tags=["invites"])

# Statuses that consume a seat: a pending invite is a reserved seat so a manager
# can't over-invite past the limit and only discover it at accept time.
SEAT_STATUSES = ("invited", "active")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _app_url() -> str:
    """Base URL for invite links. Without it an invite link can't be built, so
    the endpoints that need it fail loudly rather than emailing a broken link."""
    return os.environ.get("APP_URL", "").strip().rstrip("/")


def _accept_url(raw_token: str) -> str:
    return f"{_app_url()}/accept-invite?token={raw_token}"


def _public_invite(inv: dict) -> dict:
    """Manager-facing invite view. Never exposes token_hash."""
    return {
        "id": inv["id"],
        "email": inv["email"],
        "status": inv["status"],
        "invited_by": inv.get("invited_by"),
        "created_at": inv.get("created_at"),
        "expires_at": inv.get("expires_at"),
        "resent_count": inv.get("resent_count", 0),
        "last_sent_at": inv.get("last_sent_at"),
    }


async def _seats_used(org_id: str) -> int:
    return await users.count_documents({"org_id": org_id, "status": {"$in": list(SEAT_STATUSES)}})


async def _under_invite_rate_limit(org_id: str) -> bool:
    cutoff = invites.one_hour_ago_iso(_now())
    recent = await invitations.count_documents({"org_id": org_id, "last_sent_at": {"$gte": cutoff}})
    return invites.within_rate_limit(recent, invites.INVITES_PER_HOUR)


# ---------------------------------------------------------------------------
# Invitations (manager)
# ---------------------------------------------------------------------------

@router.post("/invites")
async def create_invite(body: InviteCreate, user: dict = Depends(permissions.require_manager)):
    org_id = user["org_id"]
    email = body.email.lower().strip()

    if not _app_url():
        # Honest server-config error, like the Firebase-not-configured case —
        # never email a link to a host we don't know.
        raise HTTPException(
            status_code=503,
            detail="Invite links aren't configured on the server yet. Set APP_URL on the backend.",
        )

    # An email already attached to a real account can't be re-invited.
    existing = await users.find_one({"email": email}, {"_id": 0})
    if existing:
        if existing.get("org_id") == org_id and existing.get("status") == "invited":
            raise HTTPException(status_code=409, detail="This person has already been invited. Use Resend if they didn't get it.")
        if existing.get("org_id") == org_id:
            raise HTTPException(status_code=409, detail="This person is already on your team.")
        raise HTTPException(status_code=409, detail="That email is already registered and can't be invited.")

    if await _seats_used(org_id) >= (await organizations.find_one({"id": org_id}, {"_id": 0}) or {}).get("seat_limit", 25):
        raise HTTPException(status_code=409, detail="You've reached your team's seat limit. Suspend or remove a member first.")

    if not await _under_invite_rate_limit(org_id):
        raise HTTPException(status_code=429, detail="Too many invitations sent in the last hour. Please try again shortly.")

    now = _now()
    now_iso = now.isoformat()
    raw_token, token_hash = invites.generate_token()
    invite_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    name = (body.name or "").strip() or email.split("@")[0]

    # The placeholder member row reserves a seat and holds the recruiter's org
    # identity until they accept. No credentials until then.
    member = {
        "id": user_id,
        "name": name,
        "email": email,
        "password_hash": None,
        "firebase_uid": None,
        "role": HR_ROLE,               # platform role stays hr; org role is what matters
        "is_active": 1,
        "org_id": org_id,
        "org_role": "recruiter",
        "status": "invited",
        "invited_by": user["id"],
        "activated_at": None,
        "last_login_at": None,
        "created_at": now_iso,
    }
    try:
        await users.insert_one(member)
    except Exception as exc:
        # Unique-email race: someone registered/was invited between our check and now.
        raise HTTPException(status_code=409, detail="That email is already registered and can't be invited.") from exc

    invitation = {
        "id": invite_id,
        "org_id": org_id,
        "email": email,
        "token_hash": token_hash,
        "invited_by": user["id"],
        "status": "pending",
        "expires_at": invites.expiry_from(now),
        "accepted_at": None,
        "resent_count": 0,
        "last_sent_at": now_iso,
        "created_at": now_iso,
    }
    try:
        await invitations.insert_one(invitation)
    except Exception as exc:
        # Compensate: don't leave a seat-consuming placeholder with no invite.
        await users.delete_one({"id": user_id})
        raise HTTPException(status_code=409, detail="An invite is already pending for this email.") from exc

    subject, mail_body = email_service.build_invite_email(
        (await organizations.find_one({"id": org_id}, {"_id": 0}) or {}).get("name") or "your team",
        user.get("name"),
        _accept_url(raw_token),
    )
    email_sent = await email_service.send_email(email, subject, mail_body)

    return {
        "invite": _public_invite(invitation),
        # Returned once, so the manager can copy the link when SMTP is unconfigured.
        "accept_url": _accept_url(raw_token),
        "email_sent": email_sent,
    }


@router.get("/invites")
async def list_invites(user: dict = Depends(permissions.require_manager)):
    docs = await invitations.find(
        {"org_id": user["org_id"], "status": "pending"}, {"_id": 0}
    ).sort("created_at", -1).to_list(1000)
    return [_public_invite(d) for d in docs]


@router.post("/invites/{invite_id}/resend")
async def resend_invite(invite_id: str, user: dict = Depends(permissions.require_manager)):
    if not _app_url():
        raise HTTPException(status_code=503, detail="Invite links aren't configured on the server yet. Set APP_URL on the backend.")

    inv = await invitations.find_one({"id": invite_id, "org_id": user["org_id"]}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invite not found")
    if inv["status"] != "pending":
        raise HTTPException(status_code=409, detail="This invite can no longer be resent.")

    if not await _under_invite_rate_limit(user["org_id"]):
        raise HTTPException(status_code=429, detail="Too many invitations sent in the last hour. Please try again shortly.")

    # Rotate the token on every resend: the previous link stops working, so a
    # forwarded or leaked old link can't be used after a resend.
    now = _now()
    raw_token, token_hash = invites.generate_token()
    updates = {
        "token_hash": token_hash,
        "expires_at": invites.expiry_from(now),
        "resent_count": inv.get("resent_count", 0) + 1,
        "last_sent_at": now.isoformat(),
    }
    await invitations.update_one({"id": invite_id}, {"$set": updates})
    inv.update(updates)

    subject, mail_body = email_service.build_invite_email(
        (await organizations.find_one({"id": user["org_id"]}, {"_id": 0}) or {}).get("name") or "your team",
        user.get("name"),
        _accept_url(raw_token),
    )
    email_sent = await email_service.send_email(inv["email"], subject, mail_body)
    return {"invite": _public_invite(inv), "accept_url": _accept_url(raw_token), "email_sent": email_sent}


@router.delete("/invites/{invite_id}")
async def revoke_invite(invite_id: str, user: dict = Depends(permissions.require_manager)):
    inv = await invitations.find_one({"id": invite_id, "org_id": user["org_id"]}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invite not found")
    if inv["status"] == "accepted":
        raise HTTPException(status_code=409, detail="This person has already joined — suspend them from the team instead.")
    if inv["status"] == "pending":
        await invitations.update_one(
            {"id": invite_id}, {"$set": {"status": "revoked", "revoked_at": _now().isoformat()}}
        )
        # Release the reserved seat: drop the never-activated placeholder member.
        await users.delete_one({"org_id": user["org_id"], "email": inv["email"], "status": "invited"})
    return {"success": True}


# ---------------------------------------------------------------------------
# Members (manager)
# ---------------------------------------------------------------------------

def _member_view(u: dict, jobs_assigned: int, candidates_sourced: int) -> dict:
    return {
        "id": u["id"],
        "name": u.get("name"),
        "email": u.get("email"),
        "org_role": u.get("org_role") or "manager",
        "status": u.get("status") or "active",
        "last_login_at": u.get("last_login_at"),
        "activated_at": u.get("activated_at"),
        "jobs_assigned": jobs_assigned,
        "candidates_sourced": candidates_sourced,
    }


@router.get("/members")
async def list_members(user: dict = Depends(permissions.require_manager)):
    members = await users.find(
        {"org_id": user["org_id"], "status": {"$in": ["invited", "active", "disabled"]}}, {"_id": 0}
    ).to_list(1000)

    # Counts in two grouped passes rather than per-member queries.
    assign_counts: dict = {}
    async for a in job_assignments.find(
        {"org_id": user["org_id"], "status": "active"}, {"_id": 0, "user_id": 1}
    ):
        assign_counts[a["user_id"]] = assign_counts.get(a["user_id"], 0) + 1
    sourced_counts: dict = {}
    async for c in candidates.find(
        {"org_id": user["org_id"]}, {"_id": 0, "sourced_by": 1}
    ):
        sourced_counts[c.get("sourced_by")] = sourced_counts.get(c.get("sourced_by"), 0) + 1

    return [
        _member_view(m, assign_counts.get(m["id"], 0), sourced_counts.get(m["id"], 0))
        for m in members
    ]


@router.patch("/members/{member_id}")
async def update_member(member_id: str, body: MemberStatusUpdate, user: dict = Depends(permissions.require_manager)):
    if body.status not in ("active", "disabled"):
        raise HTTPException(status_code=400, detail="Status must be 'active' or 'disabled'.")
    if member_id == user["id"]:
        raise HTTPException(status_code=400, detail="You can't change your own status.")

    target = await users.find_one({"id": member_id, "org_id": user["org_id"]}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    # An org must always keep at least one active manager.
    if body.status == "disabled" and target.get("org_role") == "manager":
        active_mgrs = await users.count_documents(
            {"org_id": user["org_id"], "org_role": "manager", "status": "active"}
        )
        if active_mgrs <= 1:
            raise HTTPException(status_code=409, detail="An organisation must have at least one active admin.")

    await users.update_one({"id": member_id}, {"$set": {"status": body.status}})
    target["status"] = body.status
    return _member_view(target, 0, 0)


# ---------------------------------------------------------------------------
# Org summary (any member)
# ---------------------------------------------------------------------------

@router.get("/me")
async def org_me(user: dict = Depends(permissions.require_org_member)):
    org = await organizations.find_one({"id": user["org_id"]}, {"_id": 0})
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    seats_used = await _seats_used(user["org_id"])
    return {
        "org": {
            "id": org["id"],
            "name": org.get("name"),
            "plan": org.get("plan"),
            "seat_limit": org.get("seat_limit", 25),
            "seats_used": seats_used,
        },
        "role": user.get("org_role") or "manager",
        "status": user.get("status") or "active",
    }


# ---------------------------------------------------------------------------
# Public: validate an invite token (no auth)
# ---------------------------------------------------------------------------

@public_router.get("/{token}")
async def validate_invite(token: str):
    inv = await invitations.find_one({"token_hash": invites.hash_token(token)}, {"_id": 0})
    reason = invites.invite_reason(inv, _now())
    if reason != invites.VALID:
        # Neutral: reveal nothing about another org's invite beyond "not usable".
        return {"valid": False, "reason": reason}
    org = await organizations.find_one({"id": inv["org_id"]}, {"_id": 0})
    return {
        "valid": True,
        "reason": reason,
        "email": inv["email"],
        "org_name": (org or {}).get("name"),
    }
