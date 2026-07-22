import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from database import jobs, candidates, stage_transitions
from auth import get_current_user
from models import JobCreate, JobUpdate

router = APIRouter(prefix="/jobs", tags=["jobs"])

HIRED_STAGE = "Selected"


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
async def list_jobs(user: dict = Depends(get_current_user)):
    """List postings with candidate counts.

    This used to issue one candidates query per job inside a loop — a recruiter
    with 30 postings triggered 31 round-trips on every page load. Now two
    queries regardless of how many postings exist.
    """
    docs = await jobs.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    counts = await _counts_for_jobs([d["id"] for d in docs])
    return [_apply_counts(d, counts) for d in docs]


@router.post("")
async def create_job(body: JobCreate, user: dict = Depends(get_current_user)):
    if not body.title or not body.title.strip():
        raise HTTPException(status_code=400, detail="Job title is required")
    if body.openings_needed < 1:
        raise HTTPException(status_code=400, detail="Openings must be at least 1")

    now = datetime.now(timezone.utc).isoformat()
    job = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "title": body.title.strip(),
        "department": body.department,
        "openings_needed": body.openings_needed,
        "jd_text": body.jd_text,
        "jd_enhanced": None,
        "status": body.status or "active",
        "deadline": body.deadline,
        "created_at": now,
        "updated_at": now,
    }
    await jobs.insert_one(job)
    job.pop("_id", None)
    return await _job_stats(job)


@router.get("/{job_id}")
async def get_job(job_id: str, user: dict = Depends(get_current_user)):
    job = await jobs.find_one({"id": job_id, "user_id": user["id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return await _job_stats(job)


@router.put("/{job_id}")
async def update_job(job_id: str, body: JobUpdate, user: dict = Depends(get_current_user)):
    job = await jobs.find_one({"id": job_id, "user_id": user["id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await jobs.update_one({"id": job_id}, {"$set": updates})
    job.update(updates)
    return await _job_stats(job)


@router.delete("/{job_id}")
async def delete_job(job_id: str, user: dict = Depends(get_current_user)):
    job = await jobs.find_one({"id": job_id, "user_id": user["id"]})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    cand_ids = [c["id"] async for c in candidates.find({"job_id": job_id}, {"id": 1})]
    if cand_ids:
        await stage_transitions.delete_many({"candidate_id": {"$in": cand_ids}})
    await candidates.delete_many({"job_id": job_id})
    await jobs.delete_one({"id": job_id})
    return {"success": True}


@router.get("/{job_id}/activity")
async def job_activity(job_id: str, user: dict = Depends(get_current_user)):
    job = await jobs.find_one({"id": job_id, "user_id": user["id"]})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
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
