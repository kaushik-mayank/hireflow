from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict

from database import users, jobs, candidates, ai_usage_log, login_activity
from auth import require_admin
from admin_identity import effective_role, is_admin_identity

router = APIRouter(prefix="/admin", tags=["admin"])

ACTION_LABELS = {
    "rank": "Resume Ranking",
    "questions": "Screening Questions",
    "email": "Email Draft",
    "enhance-jd": "JD Enhancement",
    "compare": "Candidate Compare",
    "summary": "Deep Summary",
    "pipeline-health": "Pipeline Health",
}


class StatusUpdate(BaseModel):
    is_active: bool


class RoleUpdate(BaseModel):
    role: str


def _parse(dt: str):
    try:
        return datetime.fromisoformat(dt)
    except (ValueError, TypeError):
        return None


async def _enrich_users() -> list:
    """Attach jobs_count, resumes_count, ai_calls to every user."""
    all_users = await users.find({}, {"_id": 0, "password_hash": 0}).to_list(2000)
    all_jobs = await jobs.find({}, {"_id": 0, "id": 1, "user_id": 1}).to_list(20000)
    job_owner = {j["id"]: j["user_id"] for j in all_jobs}

    jobs_count = Counter(j["user_id"] for j in all_jobs)
    resumes_count = Counter()
    async for c in candidates.find({}, {"_id": 0, "job_id": 1}):
        owner = job_owner.get(c["job_id"])
        if owner:
            resumes_count[owner] += 1
    ai_count = Counter()
    async for a in ai_usage_log.find({}, {"_id": 0, "user_id": 1}):
        if a.get("user_id"):
            ai_count[a["user_id"]] += 1

    for u in all_users:
        u["jobs_count"] = jobs_count.get(u["id"], 0)
        u["resumes_count"] = resumes_count.get(u["id"], 0)
        u["ai_calls"] = ai_count.get(u["id"], 0)
        # Report the role the system will actually enforce, not the stored
        # field — otherwise the admin UI would show stale or escalated values.
        u["role"] = effective_role(u)
    return all_users


@router.get("/dashboard")
async def admin_dashboard(admin: dict = Depends(require_admin)):
    enriched = await _enrich_users()
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    active_hr = sum(
        1 for u in enriched
        if u.get("role") == "hr" and (_parse(u.get("last_login_at")) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
    )
    total_jobs = await jobs.count_documents({})
    open_jobs = await jobs.count_documents({"status": "active"})
    total_resumes = await candidates.count_documents({})
    total_ai = await ai_usage_log.count_documents({})
    signups_series = _daily_series([u.get("created_at") for u in enriched], 30)

    # recent logins
    logins = await login_activity.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    name_map = {u["id"]: u for u in enriched}
    recent_logins = [
        {
            "id": lg["id"],
            "name": name_map.get(lg["user_id"], {}).get("name", "Unknown"),
            "email": name_map.get(lg["user_id"], {}).get("email", "—"),
            "ip_address": lg.get("ip_address"),
            "created_at": lg.get("created_at"),
        }
        for lg in logins
    ]

    return {
        "stats": {
            "total_users": len(enriched),
            "active_hr": active_hr,
            "total_jobs": total_jobs,
            "open_jobs": open_jobs,
            "closed_jobs": max(total_jobs - open_jobs, 0),
            "total_resumes": total_resumes,
            "total_ai_calls": total_ai,
        },
        "signups": signups_series,
        "users": enriched,
        "recent_logins": recent_logins,
    }


@router.get("/users")
async def admin_users(admin: dict = Depends(require_admin)):
    return await _enrich_users()


@router.put("/users/{user_id}/status")
async def set_user_status(user_id: str, body: StatusUpdate, admin: dict = Depends(require_admin)):
    target = await users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if user_id == admin["id"] and not body.is_active:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    if is_admin_identity(target) and not body.is_active:
        raise HTTPException(
            status_code=400,
            detail="This account is on the admin allowlist and cannot be deactivated here.",
        )
    await users.update_one({"id": user_id}, {"$set": {"is_active": 1 if body.is_active else 0}})
    return {"success": True, "is_active": body.is_active}


@router.put("/users/{user_id}/role")
async def set_user_role(user_id: str, body: RoleUpdate, admin: dict = Depends(require_admin)):
    """Retained so existing clients get a clear answer instead of a 404.

    Role can no longer be changed through the API. Admin is granted only by the
    server-side allowlist in admin_identity.py — previously this endpoint was a
    lateral-movement path that let any admin mint another one.
    """
    target = await users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    raise HTTPException(
        status_code=403,
        detail=(
            "Roles can no longer be changed here. Admin access is granted only by the "
            "server-side admin allowlist (backend/admin.credentials.json or ADMIN_EMAILS)."
        ),
    )


@router.get("/resumes")
async def admin_resumes(
    admin: dict = Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    all_jobs = await jobs.find({}, {"_id": 0, "id": 1, "title": 1, "user_id": 1}).to_list(20000)
    job_map = {j["id"]: j for j in all_jobs}
    all_users = await users.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(2000)
    user_map = {u["id"]: u["name"] for u in all_users}

    total = await candidates.count_documents({})
    skip = (page - 1) * page_size
    cands = await candidates.find(
        {}, {"_id": 0, "resume_text": 0}
    ).sort("uploaded_at", -1).skip(skip).limit(page_size).to_list(page_size)

    items = []
    for c in cands:
        job = job_map.get(c["job_id"], {})
        items.append({
            "id": c["id"],
            "candidate_name": c.get("name"),
            "job_title": job.get("title", "—"),
            "hr_user": user_map.get(job.get("user_id"), "—"),
            "uploaded_at": c.get("uploaded_at"),
            "stage": c.get("stage"),
            "ai_score": c.get("ai_score"),
            "file_name": c.get("pdf_original_name"),
        })
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/resumes/{candidate_id}")
async def admin_resume_detail(candidate_id: str, admin: dict = Depends(require_admin)):
    """Full stored record for one candidate, for support and moderation.

    Returns the raw document including extracted resume text and AI output, so
    an admin can inspect exactly what is held about a candidate.
    """
    cand = await candidates.find_one({"id": candidate_id}, {"_id": 0})
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")

    job = await jobs.find_one({"id": cand.get("job_id")}, {"_id": 0, "id": 1, "title": 1, "user_id": 1})
    owner = None
    if job:
        owner = await users.find_one(
            {"id": job.get("user_id")}, {"_id": 0, "id": 1, "name": 1, "email": 1}
        )
    return {
        "candidate": cand,
        "job": {"id": job.get("id"), "title": job.get("title")} if job else None,
        "hr_user": owner,
    }


def _daily_series(timestamps: list, days: int) -> list:
    today = datetime.now(timezone.utc).date()
    buckets = {(today - timedelta(days=i)).isoformat(): 0 for i in range(days - 1, -1, -1)}
    for ts in timestamps:
        d = _parse(ts)
        if d and d.date().isoformat() in buckets:
            buckets[d.date().isoformat()] += 1
    return [{"date": k, "count": v} for k, v in buckets.items()]


def _weekly_jobs_series(all_jobs: list, weeks: int = 12) -> list:
    today = datetime.now(timezone.utc).date()
    week_buckets = {
        (today - timedelta(days=today.weekday() + 7 * i)).isoformat(): 0
        for i in range(weeks - 1, -1, -1)
    }
    for j in all_jobs:
        d = _parse(j["created_at"])
        if not d:
            continue
        wk = (d.date() - timedelta(days=d.date().weekday())).isoformat()
        if wk in week_buckets:
            week_buckets[wk] += 1
    return [{"week": k, "count": v} for k, v in week_buckets.items()]


def _analytics_metrics(all_users: list, all_jobs: list, all_cands: list, ai_logs: list) -> dict:
    user_name = {u["id"]: u["name"] for u in all_users}
    most_active = Counter(a.get("user_id") for a in ai_logs if a.get("user_id")).most_common(1)
    most_title = Counter(j["title"] for j in all_jobs).most_common(1)
    scored = [c["ai_score"] for c in all_cands if c.get("ai_score") is not None]
    return {
        "most_active_user": user_name.get(most_active[0][0], "—") if most_active else "—",
        "most_popular_title": most_title[0][0] if most_title else "—",
        "avg_resumes_per_job": round(len(all_cands) / len(all_jobs), 1) if all_jobs else 0,
        "avg_ai_score": round(sum(scored) / len(scored)) if scored else 0,
    }


@router.get("/analytics")
async def admin_analytics(admin: dict = Depends(require_admin)) -> dict:
    all_users = await users.find({}, {"_id": 0, "created_at": 1, "name": 1, "id": 1}).to_list(2000)
    all_jobs = await jobs.find({}, {"_id": 0, "created_at": 1, "title": 1, "user_id": 1, "id": 1}).to_list(20000)
    all_cands = await candidates.find({}, {"_id": 0, "uploaded_at": 1, "ai_score": 1, "job_id": 1}).to_list(100000)
    ai_logs = await ai_usage_log.find({}, {"_id": 0, "created_at": 1, "user_id": 1}).to_list(100000)

    return {
        "signups": _daily_series([u["created_at"] for u in all_users], 30),
        "jobs_weekly": _weekly_jobs_series(all_jobs),
        "resumes": _daily_series([c["uploaded_at"] for c in all_cands], 30),
        "ai_usage": _daily_series([a["created_at"] for a in ai_logs], 30),
        "metrics": _analytics_metrics(all_users, all_jobs, all_cands, ai_logs),
    }


async def _ai_usage_summary(total: int, user_map: dict) -> dict:
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    all_logs = await ai_usage_log.find({}, {"_id": 0, "action": 1, "user_id": 1, "created_at": 1}).to_list(100000)
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    this_month = sum(1 for lg in all_logs if (_parse(lg.get("created_at")) or epoch) >= month_start)
    most_feature = Counter(lg.get("action") for lg in all_logs).most_common(1)
    most_user = Counter(lg.get("user_id") for lg in all_logs if lg.get("user_id")).most_common(1)
    return {
        "calls_this_month": this_month,
        "total_calls": len(all_logs),
        "most_used_feature": ACTION_LABELS.get(most_feature[0][0], most_feature[0][0]) if most_feature else "—",
        "most_active_user": user_map.get(most_user[0][0], "—") if most_user else "—",
    }


@router.get("/ai-usage")
async def admin_ai_usage(
    admin: dict = Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict:
    all_users = await users.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(2000)
    user_map = {u["id"]: u["name"] for u in all_users}

    total = await ai_usage_log.count_documents({})
    skip = (page - 1) * page_size
    logs = await ai_usage_log.find({}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(page_size).to_list(page_size)
    items = [
        {
            "id": lg["id"],
            "created_at": lg.get("created_at"),
            "user": user_map.get(lg.get("user_id"), "—"),
            "action": ACTION_LABELS.get(lg.get("action"), lg.get("action")),
            "reference": lg.get("candidate_id") or lg.get("job_id") or "—",
            "tokens_used": lg.get("tokens_used"),
        }
        for lg in logs
    ]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
        "summary": await _ai_usage_summary(total, user_map),
    }
