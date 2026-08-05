"""Organisation management: approved recruiters (the team) and org summary.

Onboarding model for this release (no emailed invitations):
- An admin ("Manager") stores approved recruiter emails — typed one at a time or
  pasted/bulk-uploaded. Storing an email does NOT send anything; it simply puts
  the email on the org's allow-list with status "approved".
- Only an approved email may join the org. The recruiter sets their own password
  the first time they sign in (Firebase), which activates them (see
  routes_auth.firebase_exchange). Their org role is fixed at approval time, so an
  approved user always signs in as a recruiter and an admin always as an admin.

All endpoints here are manager-only (`permissions.require_manager`) and scoped to
the caller's own org — a manager can never see or touch another org's members.

The emailed-token invite flow (invites.py, the `invitations` collection) is left
in the codebase but unused, reserved for a future plan-purchase cycle.
"""

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from database import users, organizations, job_assignments, candidates
from admin_identity import HR_ROLE
from models import MemberCreate, BulkMemberCreate, MemberStatusUpdate, MemberRemove
import permissions

router = APIRouter(prefix="/orgs", tags=["orgs"])

# Statuses that occupy a seat: an approved-but-not-yet-activated email still
# reserves a seat so an admin can't approve past the limit and only find out
# when people try to sign in. ("invited" is the legacy value, still counted.)
PENDING_STATUSES = ("approved", "invited")
SEAT_STATUSES = ("approved", "invited", "active")
MEMBER_STATUSES = ("approved", "invited", "active", "disabled")

# Deliberately forgiving email shape: we validate format, not deliverability,
# because there is no confirmation email to bounce.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_emails(text: str) -> list[str]:
    """Split a pasted/typed/CSV blob into de-duplicated, lowercased emails,
    preserving first-seen order. Invalid-looking entries are kept so the caller
    can report them back as skipped rather than silently dropping them."""
    parts = re.split(r"[,;\s]+", text or "")
    seen, out = set(), []
    for raw in parts:
        email = raw.strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)
        out.append(email)
    return out


def _member_view(u: dict, jobs_assigned: int = 0, candidates_sourced: int = 0) -> dict:
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


async def _seats(org_id: str) -> tuple[int, int]:
    """(seats_used, seat_limit) for the org."""
    used = await users.count_documents({"org_id": org_id, "status": {"$in": list(SEAT_STATUSES)}})
    org = await organizations.find_one({"id": org_id}, {"_id": 0}) or {}
    return used, org.get("seat_limit", 25)


def _new_member_doc(org_id: str, approver_id: str, email: str, name: str | None) -> dict:
    now_iso = _now().isoformat()
    return {
        "id": str(uuid.uuid4()),
        "name": (name or "").strip() or email.split("@")[0],
        "email": email,
        "password_hash": None,   # the recruiter sets this themselves on first sign-in
        "firebase_uid": None,
        "role": HR_ROLE,         # platform role stays hr; org_role is what matters
        "is_active": 1,
        "org_id": org_id,
        "org_role": "recruiter",
        "status": "approved",
        "invited_by": approver_id,
        "approved_by": approver_id,
        "activated_at": None,
        "last_login_at": None,
        "created_at": now_iso,
    }


async def _addability(email: str, org_id: str) -> str | None:
    """None if the email can be approved, else a human reason it can't."""
    existing = await users.find_one({"email": email}, {"_id": 0})
    if not existing:
        return None
    if existing.get("org_id") == org_id and existing.get("status") in PENDING_STATUSES:
        return "already approved"
    if existing.get("org_id") == org_id:
        return "already on the team"
    return "already registered elsewhere"


# ---------------------------------------------------------------------------
# Approve recruiter emails (manager)
# ---------------------------------------------------------------------------

@router.post("/members")
async def add_member(body: MemberCreate, user: dict = Depends(permissions.require_manager)):
    org_id = user["org_id"]
    email = body.email.lower().strip()

    reason = await _addability(email, org_id)
    if reason == "already approved":
        raise HTTPException(status_code=409, detail="This email has already been approved.")
    if reason == "already on the team":
        raise HTTPException(status_code=409, detail="This person is already on your team.")
    if reason:
        raise HTTPException(status_code=409, detail="That email is already registered and can't be added.")

    used, limit = await _seats(org_id)
    if used >= limit:
        raise HTTPException(status_code=409, detail="You've reached your team's seat limit. Remove a member first.")

    member = _new_member_doc(org_id, user["id"], email, body.name)
    try:
        await users.insert_one(member)
    except Exception as exc:  # unique-email race
        raise HTTPException(status_code=409, detail="That email is already registered and can't be added.") from exc
    return _member_view(member)


@router.post("/members/bulk")
async def add_members_bulk(body: BulkMemberCreate, user: dict = Depends(permissions.require_manager)):
    """Approve many emails at once. Adds up to the remaining seats and reports
    every skipped entry with a reason, so nothing fails silently."""
    org_id = user["org_id"]
    used, limit = await _seats(org_id)
    remaining = max(limit - used, 0)

    added, skipped = [], []
    for email in _parse_emails(body.text):
        if not _EMAIL_RE.match(email):
            skipped.append({"email": email, "reason": "not a valid email"})
            continue
        reason = await _addability(email, org_id)
        if reason:
            skipped.append({"email": email, "reason": reason})
            continue
        if remaining <= 0:
            skipped.append({"email": email, "reason": "seat limit reached"})
            continue
        member = _new_member_doc(org_id, user["id"], email, None)
        try:
            await users.insert_one(member)
        except Exception:
            skipped.append({"email": email, "reason": "already registered elsewhere"})
            continue
        added.append(_member_view(member))
        remaining -= 1

    return {
        "added": added,
        "skipped": skipped,
        "seats_used": used + len(added),
        "seat_limit": limit,
    }


# ---------------------------------------------------------------------------
# Members (manager)
# ---------------------------------------------------------------------------

@router.get("/members")
async def list_members(user: dict = Depends(permissions.require_manager)):
    members = await users.find(
        {"org_id": user["org_id"], "status": {"$in": list(MEMBER_STATUSES)}}, {"_id": 0}
    ).to_list(1000)

    # Counts in two grouped passes rather than a query per member.
    assign_counts: dict = {}
    async for a in job_assignments.find(
        {"org_id": user["org_id"], "status": "active"}, {"_id": 0, "user_id": 1}
    ):
        assign_counts[a["user_id"]] = assign_counts.get(a["user_id"], 0) + 1
    sourced_counts: dict = {}
    async for c in candidates.find({"org_id": user["org_id"]}, {"_id": 0, "sourced_by": 1}):
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

    # An org must always keep at least one active admin.
    if body.status == "disabled" and target.get("org_role") == "manager":
        active_mgrs = await users.count_documents(
            {"org_id": user["org_id"], "org_role": "manager", "status": "active"}
        )
        if active_mgrs <= 1:
            raise HTTPException(status_code=409, detail="An organisation must have at least one active admin.")

    await users.update_one({"id": member_id}, {"$set": {"status": body.status}})
    target["status"] = body.status
    return _member_view(target)


@router.delete("/members/{member_id}")
async def remove_member(member_id: str, body: MemberRemove = MemberRemove(), user: dict = Depends(permissions.require_manager)):
    """Remove a member. A never-signed-in approval is simply deleted (frees the
    seat). An active member's work is **reassigned first** so nothing is orphaned:
    their active assignments move to `reassign_to` (or are revoked if null) and
    their sourced candidates are re-attributed; then the member is disabled."""
    org_id = user["org_id"]
    if member_id == user["id"]:
        raise HTTPException(status_code=400, detail="You can't remove yourself.")
    target = await users.find_one({"id": member_id, "org_id": org_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    # Never-activated approval: drop it, freeing the seat.
    if target.get("status") in PENDING_STATUSES:
        await users.delete_one({"id": member_id})
        return {"success": True, "removed": True}

    # An org must always keep at least one active admin.
    if target.get("org_role") == "manager":
        active_mgrs = await users.count_documents(
            {"org_id": org_id, "org_role": "manager", "status": "active"}
        )
        if active_mgrs <= 1:
            raise HTTPException(status_code=409, detail="An organisation must have at least one active admin.")

    reassign_to = body.reassign_to
    if reassign_to:
        dest = await users.find_one({"id": reassign_to, "org_id": org_id}, {"_id": 0})
        if not dest or dest.get("org_role") != "recruiter" or dest.get("status") != "active" or reassign_to == member_id:
            raise HTTPException(status_code=400, detail="Choose an active teammate to receive the reassigned work.")

    now = _now().isoformat()
    # Move (or revoke) each active assignment.
    async for a in job_assignments.find(
        {"org_id": org_id, "user_id": member_id, "status": "active"}, {"_id": 0}
    ):
        if reassign_to:
            existing = await job_assignments.find_one(
                {"job_id": a["job_id"], "user_id": reassign_to}, {"_id": 0}
            )
            if existing:
                await job_assignments.update_one(
                    {"id": existing["id"]}, {"$set": {"status": "active", "updated_at": now}}
                )
            else:
                await job_assignments.insert_one({
                    "id": str(uuid.uuid4()), "org_id": org_id, "job_id": a["job_id"],
                    "user_id": reassign_to, "assigned_by": user["id"], "status": "active",
                    "permissions": a.get("permissions", {}), "targets": a.get("targets", {}),
                    "deadline": a.get("deadline"), "note": a.get("note"),
                    "assigned_at": now, "updated_at": now,
                })
        await job_assignments.update_one({"id": a["id"]}, {"$set": {"status": "revoked", "updated_at": now}})

    # Re-attribute their sourced candidates so team reports stay coherent.
    if reassign_to:
        await candidates.update_many(
            {"org_id": org_id, "sourced_by": member_id}, {"$set": {"sourced_by": reassign_to}}
        )

    await users.update_one({"id": member_id}, {"$set": {"status": "disabled", "removed_at": now}})
    return {"success": True, "removed": True, "reassigned_to": reassign_to}


# ---------------------------------------------------------------------------
# Org summary (any member)
# ---------------------------------------------------------------------------

@router.get("/me")
async def org_me(user: dict = Depends(permissions.require_org_member)):
    org = await organizations.find_one({"id": user["org_id"]}, {"_id": 0})
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    seats_used, seat_limit = await _seats(user["org_id"])
    return {
        "org": {
            "id": org["id"],
            "name": org.get("name"),
            "plan": org.get("plan"),
            "seat_limit": seat_limit,
            "seats_used": seats_used,
        },
        "role": user.get("org_role") or "manager",
        "status": user.get("status") or "active",
    }
