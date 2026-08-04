from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from database import jobs, candidates
from auth import get_current_user
from models import (
    RankRequest, EnhanceJDRequest, QuestionsRequest,
    EmailRequest, CompareRequest, SummaryRequest, StructureRequest,
)
import ai_service as ai
import permissions


def _as_list(value) -> list:
    if isinstance(value, list):
        return [v for v in value if v not in (None, "")]
    return []


def _normalize_structure(parsed: dict, cand: dict) -> dict:
    """Coerce the model's JSON into a stable shape the viewer can rely on, and
    backfill contact + links from what the parser already extracted."""
    parsed = parsed if isinstance(parsed, dict) else {}
    contact = parsed.get("contact") if isinstance(parsed.get("contact"), dict) else {}

    experience = []
    for e in _as_list(parsed.get("experience")):
        if isinstance(e, dict):
            experience.append({
                "title": str(e.get("title") or ""),
                "organization": str(e.get("organization") or ""),
                "dates": str(e.get("dates") or ""),
                "location": str(e.get("location") or ""),
                "highlights": [str(h) for h in _as_list(e.get("highlights"))],
            })

    education = []
    for e in _as_list(parsed.get("education")):
        if isinstance(e, dict):
            education.append({
                "qualification": str(e.get("qualification") or ""),
                "institution": str(e.get("institution") or ""),
                "dates": str(e.get("dates") or ""),
            })

    return {
        "name": str(parsed.get("name") or cand.get("name") or ""),
        "headline": str(parsed.get("headline") or ""),
        "contact": {
            # Prefer the reliably-parsed values (from the PDF mailto:/text
            # extraction at upload) over the AI's reading of the mangled resume
            # text, which is where the wrong email in the formatted view came from.
            "email": str(cand.get("email") or contact.get("email") or ""),
            "phone": str(cand.get("phone") or contact.get("phone") or ""),
            "location": str(contact.get("location") or ""),
        },
        "links": {
            "linkedin": cand.get("linkedin") or "",
            "github": cand.get("github") or "",
            "portfolio": cand.get("portfolio") or "",
        },
        "summary": str(parsed.get("summary") or ""),
        "skills": [str(s) for s in _as_list(parsed.get("skills"))],
        "experience": experience,
        "education": education,
        "certifications": [str(c) for c in _as_list(parsed.get("certifications"))],
        "languages": [str(le) for le in _as_list(parsed.get("languages"))],
    }

router = APIRouter(prefix="/ai", tags=["ai"])


def _chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def _as_str_list(value) -> list:
    """Coerce a model-supplied field to a list of strings.

    The AI returns free-form JSON, so these fields can arrive as a bare string,
    null, or a list of objects. Writing that straight to Mongo makes the UI
    render "[object Object]" or crash on .map(), so it is normalised here.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(v).strip() for v in value if v is not None and str(v).strip()]
    return [str(value)]


def _as_score(value) -> int:
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return 0


def _build_rank_set_doc(result: dict, current_stage: str, now: str, jd_source: str) -> dict:
    summary = result.get("summary")
    set_doc = {
        "ai_score": _as_score(result.get("score")),
        "ai_summary": summary if isinstance(summary, str) else None,
        "matched_skills": _as_str_list(result.get("matched_skills")),
        "missing_skills": _as_str_list(result.get("missing_skills")),
        "red_flags": _as_str_list(result.get("red_flags")),
        "analyzed_at": now,
        # Which JD text produced this analysis, so results stay explainable when a
        # recruiter uses a personal JD override (§5.3).
        "analyzed_jd_source": jd_source,
    }
    if current_stage == "Applied":
        set_doc["stage"] = "AI Ranked"
    return set_doc


async def _rank_batch(jd_text: str, batch: list, jd_source: str) -> list:
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
        set_doc = _build_rank_set_doc(result, c.get("stage"), now, jd_source)
        await candidates.update_one({"id": c["id"]}, {"$set": set_doc})
        c.update(set_doc)
        updated.append(c)
    return updated


@router.post("/rank")
async def rank_candidates(body: RankRequest, user: dict = Depends(get_current_user)):
    access = await permissions.resolve_job_access(user, body.job_id)
    permissions.require_permission(access, "can_use_ai")
    jd = await permissions.resolve_jd(access, user["id"])
    if not jd["jd_text"]:
        raise HTTPException(status_code=400, detail="Add a job description before analyzing candidates")

    # Only rank candidates the caller can see (own sourced unless manager /
    # can_view_team_candidates).
    query = {"job_id": body.job_id, **permissions.candidate_scope_filter(access, user)}
    if not body.reanalyze:
        query["analyzed_at"] = None
    cands = await candidates.find(query, {"_id": 0}).to_list(5000)
    if not cands:
        return {"updated": [], "count": 0, "message": "No candidates to analyze"}

    updated = []
    for batch in _chunk(cands, 10):
        updated.extend(await _rank_batch(jd["jd_text"], batch, jd["jd_source"]))

    await ai.log_usage("rank", user_id=user["id"], job_id=body.job_id, org_id=access.org_id)
    return {"updated": updated, "count": len(updated)}


@router.post("/enhance-jd")
async def enhance_jd(body: EnhanceJDRequest, user: dict = Depends(permissions.require_org_member)):
    if not body.jd_text or not body.jd_text.strip():
        raise HTTPException(status_code=400, detail="Provide a job description to enhance")
    enhanced = await ai.call_ai(ai.ENHANCE_SYSTEM, ai.build_enhance_prompt(body.jd_text, body.title))
    await ai.log_usage("enhance-jd", user_id=user["id"], org_id=user.get("org_id"))
    return {"original": body.jd_text, "enhanced": enhanced.strip()}


async def _get_owned_candidate(candidate_id: str, user: dict):
    """Resolve a candidate the caller may act on (org + assignment + visibility),
    plus the JD text/source their AI runs should use. Every caller is an AI tool,
    so the can_use_ai permission is enforced here once."""
    cand, access = await permissions.resolve_candidate_access(user, candidate_id)
    permissions.require_permission(access, "can_use_ai")
    jd = await permissions.resolve_jd(access, user["id"])
    return cand, access, jd


@router.post("/questions")
async def screening_questions(body: QuestionsRequest, user: dict = Depends(get_current_user)):
    cand, access, jd = await _get_owned_candidate(body.candidate_id, user)
    raw = await ai.call_ai(ai.QUESTIONS_SYSTEM, ai.build_questions_prompt(jd["jd_text"], cand))
    parsed = ai.parse_ai_json(raw)
    if not isinstance(parsed, list):
        parsed = []
    await ai.log_usage("questions", user_id=user["id"], job_id=access.job["id"],
                       candidate_id=cand["id"], org_id=access.org_id)
    return {"questions": parsed}


@router.post("/email")
async def draft_email(body: EmailRequest, user: dict = Depends(get_current_user)):
    cand, access, jd = await _get_owned_candidate(body.candidate_id, user)
    job = access.job
    company = user.get("company") or ""
    sender_name = user.get("name") or ""
    raw = await ai.call_ai(
        ai.EMAIL_SYSTEM,
        # The JD is passed so the draft can match the register of the actual role
        # rather than defaulting to a single corporate tone. The signer's name
        # and organisation are passed so the signature is real, not a placeholder.
        ai.build_email_prompt(
            body.email_type, cand, job["title"], company,
            jd["jd_text"], sender_name,
        ),
    )
    # Plain-text parse (emails are no longer JSON — see parse_email_output).
    parsed = ai.parse_email_output(raw)
    # Return the values used to sign the email so the frontend can offer them as
    # editable fields before the recruiter sends or copies the draft.
    parsed["sender_name"] = sender_name
    parsed["organization"] = company
    await ai.log_usage("email", user_id=user["id"], job_id=job["id"],
                       candidate_id=cand["id"], org_id=access.org_id)
    return parsed


@router.post("/summary")
async def deep_summary(body: SummaryRequest, user: dict = Depends(get_current_user)):
    cand, access, jd = await _get_owned_candidate(body.candidate_id, user)
    raw = await ai.call_ai(ai.SUMMARY_SYSTEM, ai.build_summary_prompt(jd["jd_text"], cand))
    parsed = ai.parse_ai_json(raw)
    if not isinstance(parsed, dict):
        parsed = {"overall_fit": raw, "strengths": [], "concerns": [], "experience_highlights": [], "recommendation": "Maybe"}
    await ai.log_usage("summary", user_id=user["id"], job_id=access.job["id"],
                       candidate_id=cand["id"], org_id=access.org_id)
    return parsed


@router.post("/structure")
async def structure_resume(body: StructureRequest, user: dict = Depends(get_current_user)):
    """Return a candidate's resume as structured data for the formatted viewer.

    Generated once by the AI, then cached on the candidate record, so a resume
    is only ever parsed the first time someone views it — the cost-efficient
    path. Pass refresh=true to regenerate.
    """
    cand, access, _jd = await _get_owned_candidate(body.candidate_id, user)

    if cand.get("resume_structured") and not body.refresh:
        return {"structured": cand["resume_structured"], "cached": True}

    raw = await ai.call_ai(ai.STRUCTURE_SYSTEM, ai.build_structure_prompt(cand.get("resume_text", "")))
    structured = _normalize_structure(ai.parse_ai_json(raw), cand)
    await candidates.update_one({"id": cand["id"]}, {"$set": {"resume_structured": structured}})
    await ai.log_usage("structure", user_id=user["id"], job_id=access.job["id"],
                       candidate_id=cand["id"], org_id=access.org_id)
    return {"structured": structured, "cached": False}


@router.post("/compare")
async def compare_candidates(body: CompareRequest, user: dict = Depends(get_current_user)):
    cand_a, access_a, jd = await _get_owned_candidate(body.candidate_id_a, user)
    cand_b, access_b, _ = await _get_owned_candidate(body.candidate_id_b, user)
    # Both candidates must belong to the same job — comparing across jobs is meaningless.
    if cand_a.get("job_id") != cand_b.get("job_id"):
        raise HTTPException(status_code=400, detail="Candidates must be on the same job to compare.")
    raw = await ai.call_ai(ai.COMPARE_SYSTEM, ai.build_compare_prompt(jd["jd_text"], cand_a, cand_b))
    parsed = ai.parse_ai_json(raw)
    if not isinstance(parsed, dict):
        parsed = {"recommendation": "", "reasoning": raw, "candidate_a_strengths": [], "candidate_b_strengths": []}
    parsed["candidate_a_name"] = cand_a.get("name")
    parsed["candidate_b_name"] = cand_b.get("name")
    await ai.log_usage("compare", user_id=user["id"], job_id=access_a.job["id"], org_id=access_a.org_id)
    return parsed


@router.post("/pipeline-health")
async def pipeline_health(user: dict = Depends(permissions.require_org_member)):
    # Org-scoped: manager sees the whole org's pipeline; recruiter sees their
    # assigned jobs' pipeline.
    accessible = await permissions.accessible_job_ids(user)
    job_query = {"org_id": user["org_id"]}
    if accessible is not None:
        if not accessible:
            user_jobs = []
        job_query["id"] = {"$in": accessible}
    user_jobs = await jobs.find(job_query, {"_id": 0}).to_list(1000)
    job_ids = [j["id"] for j in user_jobs]
    cand_query = {"job_id": {"$in": job_ids}}
    if accessible is not None:
        # Recruiter without team visibility sees only their sourced candidates.
        cand_query["sourced_by"] = user["id"]
    all_cands = await candidates.find(cand_query, {"_id": 0}).to_list(10000)

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
    await ai.log_usage("pipeline-health", user_id=user["id"], org_id=user["org_id"])
    return {"report": report.strip(), "stats": stats}
