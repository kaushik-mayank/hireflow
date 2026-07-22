from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Optional
from collections import Counter

from database import jobs, candidates, stage_transitions
from auth import get_current_user

router = APIRouter(prefix="/reports", tags=["reports"])

STAGES = [
    "Applied", "AI Ranked", "Shortlisted", "Contact Pending", "Contacted",
    "Interview Scheduled", "Interview Done", "Selected", "Rejected", "On Hold",
]
HIRED_STAGE = "Selected"


def _parse(dt: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(dt)
    except (ValueError, TypeError):
        return None


async def _time_to_hire(user_jobs: list, cands_by_job: dict) -> list:
    """Avg days from upload to Selected per job."""
    results = []
    for j in user_jobs:
        cs = cands_by_job.get(j["id"], [])
        selected = [c for c in cs if c.get("stage") == HIRED_STAGE]
        if not selected:
            continue
        durations = []
        for c in selected:
            trans = await stage_transitions.find_one(
                {"candidate_id": c["id"], "to_stage": HIRED_STAGE}, {"_id": 0}, sort=[("moved_at", -1)]
            )
            start = _parse(c.get("uploaded_at"))
            end = _parse(trans["moved_at"]) if trans else None
            if start and end:
                durations.append(max((end - start).days, 0))
        if durations:
            results.append({"job": j["title"], "avg_days": round(sum(durations) / len(durations), 1)})
    return results


def _stage_funnel(all_cands: list) -> list:
    counts = Counter(c.get("stage") for c in all_cands)
    return [{"stage": s, "count": counts.get(s, 0)} for s in STAGES]


def _skill_gap(all_cands: list) -> list:
    counter: Counter = Counter()
    for c in all_cands:
        if c.get("stage") == "Rejected":
            for skill in (c.get("missing_skills") or []):
                counter[skill] += 1
    # Fallback: if no rejections yet, use all analyzed candidates' missing skills
    if not counter:
        for c in all_cands:
            for skill in (c.get("missing_skills") or []):
                counter[skill] += 1
    return [{"skill": k, "count": v} for k, v in counter.most_common(10)]


def _quota_tracker(user_jobs: list, cands_by_job: dict) -> list:
    rows = []
    for j in user_jobs:
        cs = cands_by_job.get(j["id"], [])
        hired = sum(1 for c in cs if c.get("stage") == HIRED_STAGE)
        in_pipeline = sum(1 for c in cs if c.get("stage") not in (HIRED_STAGE, "Rejected"))
        needed = j.get("openings_needed", 1)
        remaining = max(needed - hired, 0)
        # naive estimate: 14 days per remaining hire
        est = None
        if remaining > 0:
            est = (datetime.now(timezone.utc) + timedelta(days=14 * remaining)).date().isoformat()
        rows.append({
            "job": j["title"],
            "needed": needed,
            "hired": hired,
            "in_pipeline": in_pipeline,
            "est_completion": est,
            "complete": remaining == 0,
        })
    return rows


@router.get("")
async def reports(user: dict = Depends(get_current_user)) -> dict:
    user_jobs = await jobs.find({"user_id": user["id"]}, {"_id": 0}).to_list(1000)
    job_ids = [j["id"] for j in user_jobs]
    all_cands = await candidates.find(
        {"job_id": {"$in": job_ids}}, {"_id": 0, "resume_text": 0}
    ).to_list(50000)

    cands_by_job = {}
    for c in all_cands:
        cands_by_job.setdefault(c["job_id"], []).append(c)

    return {
        "time_to_hire": await _time_to_hire(user_jobs, cands_by_job),
        "stage_funnel": _stage_funnel(all_cands),
        "skill_gap": _skill_gap(all_cands),
        "quota_tracker": _quota_tracker(user_jobs, cands_by_job),
    }
