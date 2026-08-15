"""Job assignments and personal JD overrides (Cycle 2, Phase 12).

A manager assigns a job to a recruiter with per-assignment permissions, targets
and a deadline; the recruiter then sees that job (Phase 9's `resolve_job_access`
already enforces "assigned recruiters only"). A recruiter granted `can_edit_jd`
may save a **personal** JD override that only they see — the shared job is never
modified.

Everything is org-scoped and goes through `permissions`: a manager can only
assign their own org's jobs to their own org's members, and cross-org access is a
404 (never confirm another org's data).
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from database import jobs, users, job_assignments, job_jd_overrides, activity_events
from auth import get_current_user
from models import AssignmentUpsert, BulkAssignmentUpsert, JDOverrideUpdate
import permissions

router = APIRouter(prefix="/jobs", tags=["assignments"])
mine_router = APIRouter(prefix="/assignments", tags=["assignments"])

ACTIVE_ASSIGNMENT_STATUSES = ("active", "paused")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _manager_job_or_404(job_id: str, org_id: str) -> dict:
    job = await jobs.find_one({"id": job_id, "org_id": org_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _targets_from(body: AssignmentUpsert) -> dict:
    return {
        "shortlist_target": body.shortlist_target,
        "sourced_target": body.sourced_target,
        "interview_target": body.interview_target,
    }


def _assignment_view(a: dict, member: dict | None) -> dict:
    return {
        "id": a["id"],
        "job_id": a["job_id"],
        "user_id": a["user_id"],
        "user_name": (member or {}).get("name"),
        "user_email": (member or {}).get("email"),
        "user_status": (member or {}).get("status"),
        "permissions": a.get("permissions", {}),
        "targets": a.get("targets", {}),
        "deadline": a.get("deadline"),
        "note": a.get("note"),
        "status": a.get("status"),
        "assigned_at": a.get("assigned_at"),
        "updated_at": a.get("updated_at"),
    }


# ---------------------------------------------------------------------------
# Assignments (manager)
# ---------------------------------------------------------------------------

async def _validate_assignee(user_id: str, org_id: str) -> dict:
    """The teammate must exist in the org, be a recruiter, and be active/approved.
    Returns the member doc or raises the right HTTP error."""
    member = await users.find_one({"id": user_id, "org_id": org_id}, {"_id": 0})
    if not member:
        raise HTTPException(status_code=404, detail="Teammate not found")
    if member.get("org_role") == permissions.MANAGER:
        raise HTTPException(status_code=400, detail="Admins already have access to every job.")
    if member.get("status") not in ("approved", "active"):
        raise HTTPException(status_code=400, detail="You can only assign jobs to active teammates.")
    return member


async def _write_assignment(org_id, job_id, actor_id, user_id, perms, targets, deadline, note, status):
    """Idempotent upsert of one (job, user) assignment + its activity event."""
    now = _now_iso()
    existing = await job_assignments.find_one({"job_id": job_id, "user_id": user_id}, {"_id": 0})
    if existing:
        updates = {
            "permissions": perms, "targets": targets, "deadline": deadline, "note": note,
            "status": status, "updated_at": now, "org_id": org_id,
        }
        await job_assignments.update_one({"id": existing["id"]}, {"$set": updates})
        assignment = {**existing, **updates}
    else:
        assignment = {
            "id": str(uuid.uuid4()), "org_id": org_id, "job_id": job_id, "user_id": user_id,
            "assigned_by": actor_id, "status": status, "permissions": perms, "targets": targets,
            "deadline": deadline, "note": note, "assigned_at": now, "updated_at": now,
        }
        await job_assignments.insert_one(dict(assignment))
    await activity_events.insert_one({
        "id": str(uuid.uuid4()), "org_id": org_id, "actor_id": actor_id,
        "job_id": job_id, "candidate_id": None, "type": "job_assigned",
        "meta": {"user_id": user_id}, "created_at": now,
    })
    return assignment


@router.post("/{job_id}/assignments")
async def upsert_assignment(job_id: str, body: AssignmentUpsert, user: dict = Depends(permissions.require_capability("assign_jobs"))):
    """Assign a job to a recruiter, or edit the existing assignment. Idempotent
    on (job, user) — sending it twice updates rather than duplicates."""
    org_id = user["org_id"]
    await _manager_job_or_404(job_id, org_id)
    member = await _validate_assignee(body.user_id, org_id)
    perms = {**permissions.DEFAULT_PERMISSIONS, **permissions.sanitize_permissions(body.permissions)}
    status = body.status if body.status in ACTIVE_ASSIGNMENT_STATUSES else "active"
    assignment = await _write_assignment(
        org_id, job_id, user["id"], body.user_id, perms, _targets_from(body),
        body.deadline, body.note, status,
    )
    return _assignment_view(assignment, member)


@router.post("/{job_id}/assignments/bulk")
async def bulk_upsert_assignments(job_id: str, body: BulkAssignmentUpsert, user: dict = Depends(permissions.require_capability("assign_jobs"))):
    """Assign one job to several recruiters with the same settings. Invalid or
    ineligible ids are skipped-with-reason rather than failing the whole batch."""
    org_id = user["org_id"]
    await _manager_job_or_404(job_id, org_id)
    perms = {**permissions.DEFAULT_PERMISSIONS, **permissions.sanitize_permissions(body.permissions)}
    status = body.status if body.status in ACTIVE_ASSIGNMENT_STATUSES else "active"
    targets = {
        "shortlist_target": body.shortlist_target,
        "sourced_target": body.sourced_target,
        "interview_target": body.interview_target,
    }
    assigned, skipped = [], []
    for uid in dict.fromkeys(body.user_ids):  # de-dupe, keep order
        try:
            member = await _validate_assignee(uid, org_id)
        except HTTPException as exc:
            skipped.append({"user_id": uid, "reason": exc.detail})
            continue
        a = await _write_assignment(org_id, job_id, user["id"], uid, perms, targets, body.deadline, body.note, status)
        assigned.append(_assignment_view(a, member))
    return {"assigned": assigned, "skipped": skipped}


@router.get("/{job_id}/assignments")
async def list_assignments(job_id: str, user: dict = Depends(permissions.require_capability("assign_jobs"))):
    org_id = user["org_id"]
    await _manager_job_or_404(job_id, org_id)
    rows = await job_assignments.find(
        {"job_id": job_id, "org_id": org_id, "status": {"$in": list(ACTIVE_ASSIGNMENT_STATUSES)}},
        {"_id": 0},
    ).to_list(1000)
    members = {}
    async for m in users.find({"org_id": org_id}, {"_id": 0, "id": 1, "name": 1, "email": 1, "status": 1}):
        members[m["id"]] = m
    return [_assignment_view(a, members.get(a["user_id"])) for a in rows]


@router.delete("/{job_id}/assignments/{member_id}")
async def revoke_assignment(job_id: str, member_id: str, user: dict = Depends(permissions.require_capability("assign_jobs"))):
    org_id = user["org_id"]
    await _manager_job_or_404(job_id, org_id)
    assignment = await job_assignments.find_one(
        {"job_id": job_id, "user_id": member_id, "org_id": org_id}, {"_id": 0}
    )
    if not assignment or assignment.get("status") == "revoked":
        raise HTTPException(status_code=404, detail="Assignment not found")
    now = _now_iso()
    await job_assignments.update_one(
        {"id": assignment["id"]}, {"$set": {"status": "revoked", "updated_at": now}}
    )
    # The recruiter loses access, so their personal JD override for this job is
    # meaningless now — drop it. Candidates they sourced are preserved (§4.3).
    await job_jd_overrides.delete_one({"job_id": job_id, "user_id": member_id})
    return {"success": True}


# ---------------------------------------------------------------------------
# A recruiter's own assignments
# ---------------------------------------------------------------------------

@mine_router.get("/mine")
async def my_assignments(user: dict = Depends(permissions.require_org_member)):
    """Active assignments for the caller, with the job basics attached. A manager
    has no assignments (they see every org job), so this is an empty list for them."""
    if permissions.is_manager(user):
        return []
    rows = await job_assignments.find(
        {"org_id": user["org_id"], "user_id": user["id"], "status": "active"}, {"_id": 0}
    ).to_list(1000)
    job_ids = [r["job_id"] for r in rows]
    jobs_by_id = {}
    if job_ids:
        async for j in jobs.find({"id": {"$in": job_ids}}, {"_id": 0, "id": 1, "title": 1, "status": 1, "department": 1}):
            jobs_by_id[j["id"]] = j
    out = []
    for a in rows:
        job = jobs_by_id.get(a["job_id"])
        out.append({
            "assignment_id": a["id"],
            "job_id": a["job_id"],
            "job_title": (job or {}).get("title"),
            "job_status": (job or {}).get("status"),
            "department": (job or {}).get("department"),
            "permissions": a.get("permissions", {}),
            "targets": a.get("targets", {}),
            "deadline": a.get("deadline"),
            "note": a.get("note"),
            "assigned_at": a.get("assigned_at"),
        })
    return out


# ---------------------------------------------------------------------------
# Personal JD override (recruiter with can_edit_jd)
# ---------------------------------------------------------------------------

@router.put("/{job_id}/jd-override")
async def set_jd_override(job_id: str, body: JDOverrideUpdate, user: dict = Depends(get_current_user)):
    access = await permissions.resolve_job_access(user, job_id)  # 404 if no access
    if access.scope != "assigned":
        raise HTTPException(status_code=400, detail="Admins edit the job description directly; personal overrides are for recruiters.")
    permissions.require_permission(access, "can_edit_jd")  # 403 with a human message

    now = _now_iso()
    existing = await job_jd_overrides.find_one({"job_id": job_id, "user_id": user["id"]}, {"_id": 0})
    doc = {
        "job_id": job_id,
        "user_id": user["id"],
        "org_id": access.org_id,
        "jd_text": body.jd_text or "",
        "jd_enhanced": body.jd_enhanced,
        "updated_at": now,
    }
    if existing:
        await job_jd_overrides.update_one({"id": existing["id"]}, {"$set": doc})
    else:
        doc["id"] = str(uuid.uuid4())
        doc["created_at"] = now
        await job_jd_overrides.insert_one(dict(doc))
    return {"jd_text": doc["jd_text"], "jd_enhanced": doc.get("jd_enhanced"), "jd_source": "personal"}


@router.delete("/{job_id}/jd-override")
async def clear_jd_override(job_id: str, user: dict = Depends(get_current_user)):
    access = await permissions.resolve_job_access(user, job_id)  # 404 if no access
    if access.scope != "assigned":
        raise HTTPException(status_code=400, detail="Admins edit the job description directly; personal overrides are for recruiters.")
    await job_jd_overrides.delete_one({"job_id": job_id, "user_id": user["id"]})
    # Reverted to the shared job JD.
    jd = await permissions.resolve_jd(access, user["id"])
    return {"jd_text": jd["jd_text"], "jd_enhanced": jd["jd_enhanced"], "jd_source": jd["jd_source"]}
