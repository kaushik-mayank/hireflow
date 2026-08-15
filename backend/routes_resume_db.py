"""Resume DB — the organisation's persistent internal resume repository (Cycle 5).

Every resume uploaded through the normal job/candidate flow additionally lands
here (see routes_candidates.upload_resumes), keyed by a stable identity derived
from the normalised email so the newest resume per person wins. This module is
the repository's own surface: list/filter/search, view, structured JSON + PDF
(reusing the exact candidate "View Resume" machinery), org-level sharing, and a
"move to a job" action that reuses the stored file with source "Internal
Database" — never a second upload or a duplicated file.

Access rules mirror the rest of the app:
- Everything is org-scoped; a record is reachable only within its own org.
- A **manager** sees every record in the org. A recruiter (or Sub-Admin) sees
  their own uploads plus records shared with the org. Reaching a private record
  you don't own is a 404 — we never confirm another user's private data exists.
- Sharing (shared/private) is dynamic, persisted and reversible; only the record
  owner or a manager may change it.
"""

import os
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from database import resume_db, candidates, activity_events, UPLOAD_DIR
from auth import get_current_user
from models import ResumeShareUpdate, ResumeMoveToJob
import ai_service as ai
import resume_pdf
import resume_store
import permissions
from resume_structure import normalize_structure

router = APIRouter(prefix="/resume-db", tags=["resume-db"])

INTERNAL_DB_SOURCE = "Internal Database"
LIST_LIMIT = 200


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def _list_view(r: dict) -> dict:
    """The compact record the listing renders — candidate name/email/skills/
    experience/upload date/source/status/sharing (§5)."""
    return {
        "id": r["id"],
        "name": r.get("name"),
        "email": r.get("email"),
        "phone": r.get("phone"),
        "skills": r.get("skills") or [],
        "experience_years": r.get("experience_years"),
        "source": r.get("source"),
        "uploaded_at": r.get("uploaded_at"),
        "updated_at": r.get("updated_at"),
        "shared": bool(r.get("shared")),
        "structured_ready": bool(r.get("resume_structured")),
        "uploader_id": r.get("uploader_id"),
    }


def _detail_view(r: dict) -> dict:
    return {
        **_list_view(r),
        "linkedin": r.get("linkedin"),
        "github": r.get("github"),
        "portfolio": r.get("portfolio"),
        "links": r.get("links") or [],
        "resume_text": r.get("resume_text") or "",
        "resume_structured": r.get("resume_structured"),
        "pdf_original_name": r.get("pdf_original_name"),
        "candidate_uid": r.get("candidate_uid"),
    }


async def _get_visible_or_404(record_id: str, user: dict) -> dict:
    """Fetch a record the caller is allowed to see, or 404. Applies the same
    org + owner/shared visibility as the listing."""
    is_mgr = permissions.is_manager(user)
    query = {"id": record_id, **resume_store.visibility_filter(user, is_mgr)}
    record = await resume_db.find_one(query, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="Resume not found")
    return record


def _can_manage_record(record: dict, user: dict) -> bool:
    """Who may change sharing or delete: the record's own uploader, or a manager."""
    return permissions.is_manager(user) or record.get("uploader_id") == user["id"]


# ---------------------------------------------------------------------------
# List + filter/search (server-side)
# ---------------------------------------------------------------------------

@router.get("")
async def list_resumes(
    user: dict = Depends(permissions.require_org_member),
    q: str = Query(None, description="search name / email / resume text"),
    skills: str = Query(None, description="comma-separated; record must have all"),
    source: str = Query(None),
    min_experience: int = Query(None, ge=0),
    uploaded_from: str = Query(None, description="ISO date lower bound (inclusive)"),
    uploaded_to: str = Query(None, description="ISO date upper bound (inclusive)"),
    shared: bool = Query(None, description="filter by sharing status"),
    limit: int = Query(100, ge=1, le=LIST_LIMIT),
    offset: int = Query(0, ge=0),
):
    """List Resume DB records the caller may see, filtered **in the database** —
    the whole repository is never shipped to the browser (§6).

    All filters are optional and combine with AND. `skills` matches records that
    contain every requested skill (case-insensitive). `q` is a case-insensitive
    substring over name, email and the raw resume text.
    """
    is_mgr = permissions.is_manager(user)
    vis = resume_store.visibility_filter(user, is_mgr)

    # `base` holds the plain-equality/range conditions; `and_conditions` holds the
    # $or clauses (visibility, per-skill, free-text) so none clobbers another.
    query: dict = {"org_id": vis["org_id"]}
    and_conditions: list = []
    if "$or" in vis:  # recruiter/sub-admin: own uploads OR shared
        and_conditions.append({"$or": vis["$or"]})

    if source and source.strip():
        query["source"] = source.strip()
    if shared is not None:
        query["shared"] = bool(shared)
    if min_experience is not None:
        query["experience_years"] = {"$gte": min_experience}

    for term in [s.strip() for s in (skills or "").split(",") if s.strip()]:
        # Every requested skill must be present (case-insensitive exact match).
        and_conditions.append(
            {"skills": {"$elemMatch": {"$regex": f"^{re.escape(term)}$", "$options": "i"}}}
        )

    date_bounds = {}
    if uploaded_from and uploaded_from.strip():
        date_bounds["$gte"] = uploaded_from.strip()
    if uploaded_to and uploaded_to.strip():
        # Inclusive of the whole day when only a date is given.
        ub = uploaded_to.strip()
        date_bounds["$lte"] = ub if "T" in ub else ub + "T23:59:59.999999+00:00"
    if date_bounds:
        query["uploaded_at"] = date_bounds

    if q and q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        and_conditions.append({"$or": [{"name": rx}, {"email": rx}, {"resume_text": rx}]})

    if and_conditions:
        query["$and"] = and_conditions

    total = await resume_db.count_documents(query)
    cursor = resume_db.find(query, {"_id": 0, "resume_text": 0}).sort("uploaded_at", -1).skip(offset).limit(limit)
    rows = await cursor.to_list(limit)
    return {"results": [_list_view(r) for r in rows], "total": total, "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------
# Detail / structured JSON / PDF (reuse the candidate viewer machinery)
# ---------------------------------------------------------------------------

@router.get("/{record_id}")
async def get_resume(record_id: str, user: dict = Depends(permissions.require_org_member)):
    record = await _get_visible_or_404(record_id, user)
    view = _detail_view(record)
    view["can_manage"] = _can_manage_record(record, user)
    return view


@router.post("/{record_id}/structure")
async def structure_resume(record_id: str, user: dict = Depends(permissions.require_org_member)):
    """Return the record's resume as structured data for the formatted viewer,
    generating and caching it once (same AI + normaliser as the candidate view),
    and backfilling `skills`/`experience_years` so filtering works on it (§4)."""
    record = await _get_visible_or_404(record_id, user)
    if record.get("resume_structured"):
        return {"structured": record["resume_structured"], "cached": True}

    raw = await ai.call_ai(ai.STRUCTURE_SYSTEM, ai.build_structure_prompt(record.get("resume_text", "")))
    structured = normalize_structure(ai.parse_ai_json(raw), record)
    updates = {
        "resume_structured": structured,
        "skills": resume_store.extract_skills(structured),
        "experience_years": resume_store.derive_experience_years(structured),
    }
    await resume_db.update_one({"id": record["id"]}, {"$set": updates})
    await ai.log_usage("structure", user_id=user["id"], org_id=record["org_id"])
    return {"structured": structured, "cached": False}


@router.get("/{record_id}/resume.pdf")
async def download_resume_pdf(record_id: str, user: dict = Depends(permissions.require_org_member)):
    """Directly download the resume as a PDF — the same formatted output as the
    candidate download (reuses `resume_pdf.build_resume_pdf`)."""
    record = await _get_visible_or_404(record_id, user)
    pdf_bytes = resume_pdf.build_resume_pdf(record.get("resume_structured") or {}, record)
    safe_name = (record.get("name") or "resume").strip().replace('"', "").replace("\n", " ") or "resume"
    headers = {"Content-Disposition": f'attachment; filename="{safe_name} - Resume.pdf"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


# ---------------------------------------------------------------------------
# Sharing (owner or manager) — dynamic, persisted, reversible
# ---------------------------------------------------------------------------

@router.patch("/{record_id}/share")
async def set_sharing(record_id: str, body: ResumeShareUpdate, user: dict = Depends(permissions.require_org_member)):
    record = await _get_visible_or_404(record_id, user)
    if not _can_manage_record(record, user):
        raise HTTPException(status_code=403, detail="Only the person who added this resume, or an admin, can change its sharing.")
    await resume_db.update_one(
        {"id": record["id"]},
        {"$set": {"shared": bool(body.shared), "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    record["shared"] = bool(body.shared)
    return _list_view(record)


# ---------------------------------------------------------------------------
# Move an existing resume onto a job (reuse the file; source Internal Database)
# ---------------------------------------------------------------------------

@router.post("/{record_id}/move-to-job")
async def move_to_job(record_id: str, body: ResumeMoveToJob, user: dict = Depends(permissions.require_org_member)):
    """Add a Resume DB record to a job as a candidate, reusing the stored file and
    parsed data (no re-upload, no re-parse). The candidate is sourced as
    "Internal Database" and remembers which Resume DB record it came from."""
    record = await _get_visible_or_404(record_id, user)

    # The caller must be able to upload candidates to the target job — same gate
    # as a normal upload (org access, job open, can_upload_candidates).
    access = await permissions.resolve_job_access(user, body.job_id)  # 404 if no access
    permissions.ensure_job_open(access)
    permissions.require_permission(access, "can_upload_candidates")

    # Don't add the same person to the same job twice from the repository.
    if record.get("email"):
        dup = await candidates.find_one(
            {"job_id": body.job_id, "email": record["email"]}, {"_id": 0, "id": 1}
        )
        if dup:
            raise HTTPException(status_code=409, detail="This candidate is already on this job.")

    now = datetime.now(timezone.utc).isoformat()
    cand_id = str(uuid.uuid4())
    cand = {
        "id": cand_id,
        "job_id": body.job_id,
        "org_id": access.org_id,
        "sourced_by": user["id"],
        "assignment_id": access.assignment["id"] if access.assignment else None,
        "name": record.get("name") or "Unknown Candidate",
        "email": record.get("email"),
        "phone": record.get("phone"),
        "resume_text": record.get("resume_text") or "(Could not extract text from this file)",
        "links": record.get("links") or [],
        "linkedin": record.get("linkedin"),
        "github": record.get("github"),
        "portfolio": record.get("portfolio"),
        # Reuse the very same stored file — no duplicate upload/file (§7).
        "pdf_path": record.get("pdf_path"),
        "pdf_original_name": record.get("pdf_original_name"),
        # Carry the already-parsed structured resume so the viewer needn't re-run AI.
        "resume_structured": record.get("resume_structured"),
        "source": INTERNAL_DB_SOURCE,
        "resume_db_id": record["id"],  # provenance: originated from the Resume DB
        "stage": "Applied",
        "ai_score": None,
        "ai_summary": None,
        "matched_skills": [],
        "missing_skills": [],
        "red_flags": [],
        "notes": [],
        "uploaded_at": now,
        "analyzed_at": None,
    }
    await candidates.insert_one(cand)
    cand.pop("_id", None)
    await activity_events.insert_one({
        "id": str(uuid.uuid4()), "org_id": access.org_id, "actor_id": user["id"],
        "job_id": body.job_id, "candidate_id": cand_id, "type": "candidate_uploaded",
        "meta": {"source": INTERNAL_DB_SOURCE, "resume_db_id": record["id"]}, "created_at": now,
    })
    return {"candidate": cand, "job_id": body.job_id}


# ---------------------------------------------------------------------------
# Delete (owner or manager)
# ---------------------------------------------------------------------------

@router.delete("/{record_id}")
async def delete_resume(record_id: str, user: dict = Depends(permissions.require_org_member)):
    record = await _get_visible_or_404(record_id, user)
    if not _can_manage_record(record, user):
        raise HTTPException(status_code=403, detail="Only the person who added this resume, or an admin, can remove it.")
    await resume_db.delete_one({"id": record["id"]})

    # Remove the physical file only if no candidate and no other Resume DB record
    # still references it — never orphan a live reference (§13).
    pdf_path = record.get("pdf_path")
    if pdf_path:
        still_used = await candidates.count_documents({"pdf_path": pdf_path})
        still_used += await resume_db.count_documents({"pdf_path": pdf_path})
        if still_used == 0:
            try:
                os.remove(UPLOAD_DIR / pdf_path)
            except OSError:
                pass
    return {"success": True}
