from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from database import jobs, candidates
from auth import get_current_user
from models import (
    RankRequest, EnhanceJDRequest, QuestionsRequest,
    EmailRequest, CompareRequest, SummaryRequest,
)
import ai_service as ai

router = APIRouter(prefix="/ai", tags=["ai"])


def _chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def _build_rank_set_doc(result: dict, current_stage: str, now: str) -> dict:
    set_doc = {
        "ai_score": int(result.get("score", 0)),
        "ai_summary": result.get("summary"),
        "matched_skills": result.get("matched_skills", []),
        "missing_skills": result.get("missing_skills", []),
        "red_flags": result.get("red_flags", []),
        "analyzed_at": now,
    }
    if current_stage == "Applied":
        set_doc["stage"] = "AI Ranked"
    return set_doc


async def _rank_batch(jd_text: str, batch: list) -> list:
    """Run AI ranking on one batch and persist results. Returns updated candidates."""
    raw = await ai.call_ai(ai.RANK_SYSTEM, ai.build_rank_prompt(jd_text, batch))
    parsed = ai.parse_ai_json(raw)
    if not isinstance(parsed, list):
        return []
    result_map = {str(r.get("id")): r for r in parsed if isinstance(r, dict)}
    now = datetime.now(timezone.utc).isoformat()
    updated = []
    for c in batch:
        result = result_map.get(c["id"])
        if not result:
            continue
        set_doc = _build_rank_set_doc(result, c.get("stage"), now)
        await candidates.update_one({"id": c["id"]}, {"$set": set_doc})
        c.update(set_doc)
        updated.append(c)
    return updated


@router.post("/rank")
async def rank_candidates(body: RankRequest, user: dict = Depends(get_current_user)):
    job = await jobs.find_one({"id": body.job_id, "user_id": user["id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.get("jd_text"):
        raise HTTPException(status_code=400, detail="Add a job description before analyzing candidates")

    query = {"job_id": body.job_id}
    if not body.reanalyze:
        query["analyzed_at"] = None
    cands = await candidates.find(query, {"_id": 0}).to_list(5000)
    if not cands:
        return {"updated": [], "count": 0, "message": "No candidates to analyze"}

    updated = []
    for batch in _chunk(cands, 10):
        updated.extend(await _rank_batch(job["jd_text"], batch))

    await ai.log_usage("rank", user_id=user["id"], job_id=body.job_id)
    return {"updated": updated, "count": len(updated)}


@router.post("/enhance-jd")
async def enhance_jd(body: EnhanceJDRequest, user: dict = Depends(get_current_user)):
    if not body.jd_text or not body.jd_text.strip():
        raise HTTPException(status_code=400, detail="Provide a job description to enhance")
    enhanced = await ai.call_ai(ai.ENHANCE_SYSTEM, ai.build_enhance_prompt(body.jd_text, body.title))
    await ai.log_usage("enhance-jd", user_id=user["id"])
    return {"original": body.jd_text, "enhanced": enhanced.strip()}


async def _get_owned_candidate(candidate_id: str, user: dict):
    cand = await candidates.find_one({"id": candidate_id}, {"_id": 0})
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")
    job = await jobs.find_one({"id": cand["job_id"], "user_id": user["id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=403, detail="Not authorized")
    return cand, job


@router.post("/questions")
async def screening_questions(body: QuestionsRequest, user: dict = Depends(get_current_user)):
    cand, job = await _get_owned_candidate(body.candidate_id, user)
    raw = await ai.call_ai(ai.QUESTIONS_SYSTEM, ai.build_questions_prompt(job.get("jd_text", ""), cand))
    parsed = ai.parse_ai_json(raw)
    if not isinstance(parsed, list):
        parsed = []
    await ai.log_usage("questions", user_id=user["id"], job_id=job["id"], candidate_id=cand["id"])
    return {"questions": parsed}


@router.post("/email")
async def draft_email(body: EmailRequest, user: dict = Depends(get_current_user)):
    cand, job = await _get_owned_candidate(body.candidate_id, user)
    raw = await ai.call_ai(
        ai.EMAIL_SYSTEM,
        ai.build_email_prompt(body.email_type, cand, job["title"], user.get("company")),
    )
    parsed = ai.parse_ai_json(raw)
    if not isinstance(parsed, dict):
        parsed = {"subject": "", "body": raw}
    await ai.log_usage("email", user_id=user["id"], job_id=job["id"], candidate_id=cand["id"])
    return parsed


@router.post("/summary")
async def deep_summary(body: SummaryRequest, user: dict = Depends(get_current_user)):
    cand, job = await _get_owned_candidate(body.candidate_id, user)
    raw = await ai.call_ai(ai.SUMMARY_SYSTEM, ai.build_summary_prompt(job.get("jd_text", ""), cand))
    parsed = ai.parse_ai_json(raw)
    if not isinstance(parsed, dict):
        parsed = {"overall_fit": raw, "strengths": [], "concerns": [], "experience_highlights": [], "recommendation": "Maybe"}
    await ai.log_usage("summary", user_id=user["id"], job_id=job["id"], candidate_id=cand["id"])
    return parsed


@router.post("/compare")
async def compare_candidates(body: CompareRequest, user: dict = Depends(get_current_user)):
    cand_a, job = await _get_owned_candidate(body.candidate_id_a, user)
    cand_b, _ = await _get_owned_candidate(body.candidate_id_b, user)
    raw = await ai.call_ai(ai.COMPARE_SYSTEM, ai.build_compare_prompt(job.get("jd_text", ""), cand_a, cand_b))
    parsed = ai.parse_ai_json(raw)
    if not isinstance(parsed, dict):
        parsed = {"recommendation": "", "reasoning": raw, "candidate_a_strengths": [], "candidate_b_strengths": []}
    parsed["candidate_a_name"] = cand_a.get("name")
    parsed["candidate_b_name"] = cand_b.get("name")
    await ai.log_usage("compare", user_id=user["id"], job_id=job["id"])
    return parsed


@router.post("/pipeline-health")
async def pipeline_health(user: dict = Depends(get_current_user)):
    user_jobs = await jobs.find({"user_id": user["id"]}, {"_id": 0}).to_list(1000)
    job_ids = [j["id"] for j in user_jobs]
    all_cands = await candidates.find({"job_id": {"$in": job_ids}}, {"_id": 0}).to_list(10000)

    stage_counts = {}
    for c in all_cands:
        stage_counts[c.get("stage")] = stage_counts.get(c.get("stage"), 0) + 1

    stats = {
        "total_jobs": len(user_jobs),
        "active_jobs": len([j for j in user_jobs if j.get("status") == "active"]),
        "total_candidates": len(all_cands),
        "stage_breakdown": stage_counts,
        "total_hired": stage_counts.get("Selected", 0),
        "total_openings_needed": sum(j.get("openings_needed", 1) for j in user_jobs),
        "contact_pending": stage_counts.get("Contact Pending", 0),
        "unanalyzed": len([c for c in all_cands if not c.get("analyzed_at")]),
    }
    report = await ai.call_ai(ai.HEALTH_SYSTEM, ai.build_health_prompt(stats))
    await ai.log_usage("pipeline-health", user_id=user["id"])
    return {"report": report.strip(), "stats": stats}
