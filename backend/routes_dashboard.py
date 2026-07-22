from fastapi import APIRouter, Depends
from database import jobs, candidates
from auth import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

HIRED_STAGE = "Selected"


def _group_by_job(all_cands: list) -> dict:
    by_job = {}
    for c in all_cands:
        by_job.setdefault(c["job_id"], []).append(c)
    return by_job


def _compute_stats(user_jobs: list, all_cands: list) -> dict:
    scored = [c["ai_score"] for c in all_cands if c.get("ai_score") is not None]
    return {
        "active_jobs": sum(1 for j in user_jobs if j.get("status") == "active"),
        "total_hired": sum(1 for c in all_cands if c.get("stage") == HIRED_STAGE),
        "in_pipeline": sum(1 for c in all_cands if c.get("stage") not in (HIRED_STAGE, "Rejected")),
        "contact_pending": sum(1 for c in all_cands if c.get("stage") == "Contact Pending"),
        "avg_score": round(sum(scored) / len(scored)) if scored else 0,
    }


def _build_jobs_summary(user_jobs: list, by_job: dict) -> list:
    summary = []
    for j in user_jobs:
        cs = by_job.get(j["id"], [])
        summary.append({
            "id": j["id"],
            "title": j["title"],
            "department": j.get("department"),
            "openings_needed": j.get("openings_needed", 1),
            "hired": sum(1 for c in cs if c.get("stage") == HIRED_STAGE),
            "candidate_count": len(cs),
            "status": j.get("status"),
            "created_at": j.get("created_at"),
        })
    return summary


def _build_action_items(user_jobs: list, all_cands: list, by_job: dict, contact_pending: int) -> list:
    items = []
    if contact_pending > 0:
        items.append({"type": "contact_pending", "text": f"{contact_pending} candidate(s) waiting in Contact Pending", "count": contact_pending})
    unanalyzed = sum(1 for c in all_cands if not c.get("analyzed_at"))
    if unanalyzed > 0:
        items.append({"type": "unanalyzed", "text": f"{unanalyzed} candidate(s) have no AI analysis yet", "count": unanalyzed})
    empty_jobs = sum(1 for j in user_jobs if not by_job.get(j["id"]))
    if empty_jobs > 0:
        items.append({"type": "empty_jobs", "text": f"{empty_jobs} job(s) have 0 resumes uploaded", "count": empty_jobs})
    return items


def _build_upcoming(user_jobs: list, all_cands: list) -> list:
    name_to_job = {j["id"]: j["title"] for j in user_jobs}
    return [
        {"id": c["id"], "name": c.get("name"), "job_title": name_to_job.get(c["job_id"]), "note": None}
        for c in all_cands if c.get("stage") == "Interview Scheduled"
    ]


@router.get("")
async def dashboard(user: dict = Depends(get_current_user)):
    user_jobs = await jobs.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    job_ids = [j["id"] for j in user_jobs]
    all_cands = await candidates.find({"job_id": {"$in": job_ids}}, {"_id": 0}).to_list(10000)

    by_job = _group_by_job(all_cands)
    stats = _compute_stats(user_jobs, all_cands)

    return {
        "stats": stats,
        "jobs_summary": _build_jobs_summary(user_jobs, by_job),
        "action_items": _build_action_items(user_jobs, all_cands, by_job, stats["contact_pending"]),
        "upcoming_interviews": _build_upcoming(user_jobs, all_cands),
    }
