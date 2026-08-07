import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from database import jobs, candidates, stage_transitions, job_assignments, job_jd_overrides, activity_events
from auth import get_current_user
from models import JobCreate, JobUpdate
import permissions

router = APIRouter(prefix="/jobs", tags=["jobs"])

HIRED_STAGE = "Selected"

# Lower-cased default pipeline names, used only to keep custom stages from
# duplicating a built-in one (the canonical list lives in routes_candidates).
_DEFAULT_STAGE_KEYS = {
    "applied", "ai ranked", "shortlisted", "contact pending", "contacted",
    "interview scheduled", "interview done", "selected", "rejected", "on hold",
}
MAX_CUSTOM_STAGES = 12


def _clean_stages(raw) -> list:
    """Sanitise manager-supplied extra stages: trim, cap length/count, drop
    blanks, de-duplicate, and drop anything that collides with a default stage."""
    if not isinstance(raw, list):
        return []
    seen, out = set(), []
    for item in raw:
        name = str(item or "").strip()[:40]
        key = name.lower()
        if not name or key in seen or key in _DEFAULT_STAGE_KEYS:
            continue
        seen.add(key)
        out.append(name)
        if len(out) >= MAX_CUSTOM_STAGES:
            break
    return out


def _apply_counts(job: dict, counts: dict) -> dict:
    stats = counts.get(job["id"], {})
    job["candidate_count"] = stats.get("total", 0)
    job["hired_count"] = stats.get("hired", 0)
    job["in_pipeline_count"] = stats.get("in_pipeline", 0)
    return job


async def _counts_for_jobs(job_ids: list) -> dict:
    """Candidate counts for many jobs in ONE query, keyed by job id."""
    if not job_ids:
        return {}
    counts: dict = {}
    cursor = candidates.find(
        {"job_id": {"$in": job_ids}}, {"_id": 0, "job_id": 1, "stage": 1}
    )
    async for c in cursor:
        stats = counts.setdefault(c["job_id"], {"total": 0, "hired": 0, "in_pipeline": 0})
        stats["total"] += 1
        stage = c.get("stage")
        if stage == HIRED_STAGE:
            stats["hired"] += 1
        elif stage != "Rejected":
            stats["in_pipeline"] += 1
    return counts


async def _job_stats(job: dict) -> dict:
    return _apply_counts(job, await _counts_for_jobs([job["id"]]))


@router.get("")
async def list_jobs(user: dict = Depends(permissions.require_org_member)):
    """List postings with candidate counts, scoped to the caller.

    Manager → every org job + their own personal jobs. Recruiter → jobs they have
    an active assignment on + their own personal jobs. Personal jobs never leak.
    """
    org_id = user["org_id"]
    is_mgr = permissions.is_manager(user)
    query = await permissions.visible_jobs_query(user)
    docs = await jobs.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    counts = await _counts_for_jobs([d["id"] for d in docs])
    result = [_apply_counts(d, counts) for d in docs]

    # For a recruiter, attach their own assignment's deadline/targets so the job
    # card can show them (managers see all org jobs and have no assignment).
    if not is_mgr and result:
        rows = await job_assignments.find(
            {"org_id": org_id, "user_id": user["id"], "status": "active",
             "job_id": {"$in": [d["id"] for d in result]}},
            {"_id": 0, "job_id": 1, "deadline": 1, "targets": 1},
        ).to_list(1000)
        by_job = {r["job_id"]: r for r in rows}
        for d in result:
            a = by_job.get(d["id"])
            if a:
                d["my_deadline"] = a.get("deadline")
                d["my_targets"] = a.get("targets") or {}
    return result


@router.post("")
async def create_job(body: JobCreate, user: dict = Depends(permissions.require_org_member)):
    """A manager ("Admin") creates an **org** job (visible to the org + assigned
    recruiters). A recruiter ("User") creates a **personal** job, visible only to
    them."""
    if not body.title or not body.title.strip():
        raise HTTPException(status_code=400, detail="Job title is required")
    if body.openings_needed < 1:
        raise HTTPException(status_code=400, detail="Openings must be at least 1")

    now = datetime.now(timezone.utc).isoformat()
    origin = "org" if permissions.is_manager(user) else "personal"
    job = {
        "id": str(uuid.uuid4()),
        "org_id": user["org_id"],
        "created_by": user["id"],
        "origin": origin,
        "user_id": user["id"],  # retained for backward compatibility with old reads
        "title": body.title.strip(),
        "department": body.department,
        "openings_needed": body.openings_needed,
        "jd_text": body.jd_text,
        "jd_enhanced": body.jd_enhanced,
        "status": body.status or "active",
        "deadline": body.deadline,
        "hiring_for": (body.hiring_for or "").strip() or None,
        "custom_stages": _clean_stages(body.custom_stages),
        "created_at": now,
        "updated_at": now,
    }
    await jobs.insert_one(job)
    job.pop("_id", None)
    await activity_events.insert_one({
        "id": str(uuid.uuid4()), "org_id": user["org_id"], "actor_id": user["id"],
        "job_id": job["id"], "candidate_id": None, "type": "job_created",
        "meta": {"title": job["title"]}, "created_at": now,
    })
    return await _job_stats(job)


@router.get("/{job_id}")
async def get_job(job_id: str, user: dict = Depends(get_current_user)):
    access = await permissions.resolve_job_access(user, job_id)
    job = dict(access.job)
    # The JD the caller should see (their personal override if any, else the org JD).
    jd = await permissions.resolve_jd(access, user["id"])
    job["jd_text"] = jd["jd_text"]
    job["jd_enhanced"] = jd["jd_enhanced"]
    job["jd_source"] = jd["jd_source"]
    job["effective_permissions"] = access.permissions
    job["access_scope"] = access.scope
    # Notice for a recruiter whose personal JD override predates the admin's last
    # edit of the shared JD — "the admin updated the job description" (§12).
    job["jd_org_updated"] = False
    if jd["jd_source"] == "personal":
        ov = await job_jd_overrides.find_one(
            {"job_id": job_id, "user_id": user["id"]}, {"_id": 0, "updated_at": 1}
        )
        jd_updated_at = access.job.get("jd_updated_at")
        if ov and jd_updated_at and ov.get("updated_at") and ov["updated_at"] < jd_updated_at:
            job["jd_org_updated"] = True
    return await _job_stats(job)


VALID_STATUSES = ("active", "paused", "closed")


@router.put("/{job_id}")
async def update_job(job_id: str, body: JobUpdate, user: dict = Depends(get_current_user)):
    access = await permissions.resolve_job_access(user, job_id)
    # A manager edits org jobs; a recruiter edits only their own personal job.
    if access.scope not in ("manager", "owner"):
        raise HTTPException(status_code=403, detail="Only an admin can edit this job.")
    job = access.job

    # `exclude_unset` rather than dropping falsy values: the old filter meant a
    # field could never be cleared back to empty, because "" and None both
    # looked like "not supplied".
    updates = body.model_dump(exclude_unset=True)
    if "status" in updates and updates["status"] not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Status must be one of: {', '.join(VALID_STATUSES)}",
        )
    if "openings_needed" in updates and updates["openings_needed"] is not None and updates["openings_needed"] < 1:
        raise HTTPException(status_code=400, detail="Openings must be at least 1")
    if "custom_stages" in updates:
        updates["custom_stages"] = _clean_stages(updates["custom_stages"])
    if "hiring_for" in updates:
        updates["hiring_for"] = (updates["hiring_for"] or "").strip() or None
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    # Track JD edits separately so a recruiter's stale personal override can be
    # detected without any non-JD edit tripping the "admin updated the JD" notice.
    if "jd_text" in updates or "jd_enhanced" in updates:
        updates["jd_updated_at"] = updates["updated_at"]
    became_closed = updates.get("status") == "closed" and job.get("status") != "closed"
    await jobs.update_one({"id": job_id}, {"$set": updates})
    job.update(updates)
    if became_closed:
        await activity_events.insert_one({
            "id": str(uuid.uuid4()), "org_id": access.org_id, "actor_id": user["id"],
            "job_id": job_id, "candidate_id": None, "type": "job_closed",
            "meta": {}, "created_at": updates["updated_at"],
        })
    return await _job_stats(job)


@router.delete("/{job_id}")
async def delete_job(job_id: str, user: dict = Depends(get_current_user)):
    access = await permissions.resolve_job_access(user, job_id)
    if access.scope not in ("manager", "owner"):
        raise HTTPException(status_code=403, detail="Only an admin can delete this job.")
    cand_ids = [c["id"] async for c in candidates.find({"job_id": job_id}, {"id": 1})]
    if cand_ids:
        await stage_transitions.delete_many({"candidate_id": {"$in": cand_ids}})
    await candidates.delete_many({"job_id": job_id})
    # Clean up assignment/override rows so nothing is orphaned.
    await job_assignments.delete_many({"job_id": job_id})
    await job_jd_overrides.delete_many({"job_id": job_id})
    await jobs.delete_one({"id": job_id})
    return {"success": True}


@router.get("/{job_id}/activity")
async def job_activity(job_id: str, user: dict = Depends(get_current_user)):
    await permissions.resolve_job_access(user, job_id)
    cand_ids = [c["id"] async for c in candidates.find({"job_id": job_id}, {"id": 1})]
    transitions = await stage_transitions.find(
        {"candidate_id": {"$in": cand_ids}}, {"_id": 0}
    ).sort("moved_at", -1).to_list(1000)
    # attach candidate names
    name_map = {}
    async for c in candidates.find({"job_id": job_id}, {"_id": 0, "id": 1, "name": 1}):
        name_map[c["id"]] = c.get("name") or "Unknown"
    for t in transitions:
        t["candidate_name"] = name_map.get(t["candidate_id"], "Unknown")
    return transitions
