import os
import re
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from database import jobs, candidates, stage_transitions, activity_events, UPLOAD_DIR
from auth import get_current_user
from models import StageUpdate, NoteUpdate, BulkStageUpdate
import resume_parser
import permissions

router = APIRouter(prefix="/candidates", tags=["candidates"])

STAGES = [
    "Applied", "AI Ranked", "Shortlisted", "Contact Pending", "Contacted",
    "Interview Scheduled", "Interview Done", "Selected", "Rejected", "On Hold",
]
HIRED_STAGE = "Selected"

# Where a candidate came from. Now mandatory at upload: the canonical list lives
# in the frontend config (src/config/sources.js), and the value chosen there is
# stored here and grouped on in Reports. "Unknown" is retained only for records
# created before the field became mandatory.
UNKNOWN_SOURCE = "Unknown"

# Accepted resume file types. PDF/DOCX/TXT extract natively; images use OCR when
# a free OCR stack is available on the host, otherwise they store without text.
ALLOWED_EXTENSIONS = resume_parser.SUPPORTED_EXTENSIONS
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _looks_like_name(line: str) -> bool:
    """Heuristic: a short line of 2-4 capitalized words, no email/digits."""
    if "@" in line or len(line) >= 50 or any(ch.isdigit() for ch in line):
        return False
    words = line.split()
    if not (1 < len(words) <= 4):
        return False
    return all(w[0].isupper() for w in words if w[:1].isalpha())


def guess_name(text: str, filename: str) -> str:
    for line in (ln.strip() for ln in text.split("\n")[:8] if ln.strip()):
        if _looks_like_name(line):
            return line
    # fallback: filename without extension
    base = os.path.splitext(filename)[0]
    return re.sub(r"[_-]+", " ", base).strip().title() or "Unknown Candidate"


@router.post("/upload/{job_id}")
async def upload_resumes(
    job_id: str,
    files: list[UploadFile] = File(...),
    source: str = Form(...),
    user: dict = Depends(get_current_user),
):
    access = await permissions.resolve_job_access(user, job_id)
    permissions.require_permission(access, "can_upload_candidates")

    # Source is mandatory (the UI enforces it too); reject a blank value.
    clean_source = (source or "").strip()
    if not clean_source:
        raise HTTPException(status_code=400, detail="A candidate source is required")

    assignment_id = access.assignment["id"] if access.assignment else None
    created = []
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"{f.filename}: unsupported type. Accepted: PDF, DOCX, DOC, TXT, PNG, JPG.",
            )
        content = await f.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=400, detail=f"{f.filename} exceeds 5MB")

        parsed = resume_parser.extract_document(content, f.filename)
        text = parsed["text"]

        # Keep the original file on disk under a safe stored name (extension preserved).
        stored_name = f"{uuid.uuid4()}{ext}"
        with open(UPLOAD_DIR / stored_name, "wb") as out:
            out.write(content)

        now = datetime.now(timezone.utc).isoformat()
        cand_id = str(uuid.uuid4())
        cand = {
            "id": cand_id,
            "job_id": job_id,
            "org_id": access.org_id,
            "sourced_by": user["id"],
            "assignment_id": assignment_id,
            "name": guess_name(text, f.filename),
            "email": parsed["email"],
            "phone": parsed["phone"],
            "resume_text": text or "(Could not extract text from this file)",
            # Embedded hyperlinks pulled from the document (annotations/relationships).
            "links": parsed["links"],
            "linkedin": parsed["linkedin"],
            "github": parsed["github"],
            "portfolio": parsed["portfolio"],
            "pdf_path": stored_name,
            "pdf_original_name": f.filename,
            "source": clean_source,
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
            "job_id": job_id, "candidate_id": cand_id, "type": "candidate_uploaded",
            "meta": {"source": clean_source}, "created_at": now,
        })
        created.append(cand)
    return {"created": created, "count": len(created)}


@router.get("/job/{job_id}")
async def list_candidates(job_id: str, user: dict = Depends(get_current_user)):
    access = await permissions.resolve_job_access(user, job_id)
    query = {"job_id": job_id, **permissions.candidate_scope_filter(access, user)}
    docs = await candidates.find(query, {"_id": 0}).to_list(5000)
    return docs


@router.get("/{candidate_id}")
async def get_candidate(candidate_id: str, user: dict = Depends(get_current_user)):
    cand, access = await permissions.resolve_candidate_access(user, candidate_id)
    job = access.job
    transitions = await stage_transitions.find(
        {"candidate_id": candidate_id}, {"_id": 0}
    ).sort("moved_at", -1).to_list(500)
    cand["job"] = {"id": job["id"], "title": job["title"], "department": job.get("department")}
    cand["transitions"] = transitions
    # The caller's effective permissions on this candidate's job, so the UI can
    # disable controls the recruiter isn't allowed to use (managers get all true).
    cand["effective_permissions"] = access.permissions
    cand["access_scope"] = access.scope
    return cand


async def _move_stage(cand: dict, to_stage: str, note: str, user: dict):
    from_stage = cand.get("stage")
    now = datetime.now(timezone.utc).isoformat()
    org_id = cand.get("org_id")
    await candidates.update_one({"id": cand["id"]}, {"$set": {"stage": to_stage}})
    await stage_transitions.insert_one({
        "id": str(uuid.uuid4()),
        "candidate_id": cand["id"],
        "org_id": org_id,
        "actor_id": user["id"],
        "from_stage": from_stage,
        "to_stage": to_stage,
        "note": note,
        "moved_by": user["name"],
        "moved_at": now,
    })
    await activity_events.insert_one({
        "id": str(uuid.uuid4()), "org_id": org_id, "actor_id": user["id"],
        "job_id": cand.get("job_id"), "candidate_id": cand["id"], "type": "stage_changed",
        "meta": {"from_stage": from_stage, "to_stage": to_stage}, "created_at": now,
    })


def _allowed_stages(job: dict) -> list:
    """Default pipeline plus any custom stages this job's admin added."""
    return STAGES + list(job.get("custom_stages") or [])


@router.put("/{candidate_id}/stage")
async def update_stage(candidate_id: str, body: StageUpdate, user: dict = Depends(get_current_user)):
    cand, access = await permissions.resolve_candidate_access(user, candidate_id)
    if body.stage not in _allowed_stages(access.job):
        raise HTTPException(status_code=400, detail="Invalid stage")
    # Rejecting is a separate, more sensitive permission from an ordinary move.
    permissions.require_permission(
        access, "can_reject_candidates" if body.stage == "Rejected" else "can_move_stage"
    )
    await _move_stage(cand, body.stage, body.note, user)

    job = access.job
    quota_met = False
    if body.stage == HIRED_STAGE:
        hired = await candidates.count_documents({"job_id": job["id"], "stage": HIRED_STAGE})
        quota_met = hired >= job.get("openings_needed", 1)
    return {"success": True, "stage": body.stage, "quota_met": quota_met}


@router.put("/bulk-stage")
async def bulk_update_stage(body: BulkStageUpdate, user: dict = Depends(get_current_user)):
    """Move many candidates at once.

    Previously issued two queries per candidate id inside a loop, then one
    update plus one transition insert each — moving 50 candidates cost over 200
    round-trips. Now a fixed number of queries plus two bulk writes.
    """
    # A custom stage is valid only for the jobs that define it, so per-candidate
    # validity is checked in the loop below; here we only reject an empty value.
    if not body.stage or not body.stage.strip():
        raise HTTPException(status_code=400, detail="Invalid stage")
    if not body.candidate_ids:
        return {"success": True, "updated": 0}

    # Org-scope first, then resolve access once per job (cached) and apply the
    # recruiter's candidate visibility — so a bulk move can never reach another
    # org's or another recruiter's candidates.
    cands = await candidates.find(
        {"id": {"$in": body.candidate_ids}, "org_id": user.get("org_id")}, {"_id": 0}
    ).to_list(len(body.candidate_ids))
    if not cands:
        return {"success": True, "updated": 0}

    access_by_job: dict = {}
    movable = []
    for c in cands:
        job_id = c.get("job_id")
        if job_id not in access_by_job:
            try:
                access_by_job[job_id] = await permissions.resolve_job_access(user, job_id)
            except HTTPException:
                access_by_job[job_id] = None
        access = access_by_job[job_id]
        if access is None:
            continue
        if (access.scope == "assigned"
                and not access.can("can_view_team_candidates")
                and c.get("sourced_by") != user["id"]):
            continue
        # The target stage must be valid for THIS candidate's job (defaults +
        # that job's custom stages).
        if body.stage not in _allowed_stages(access.job):
            continue
        # Same permission gate as a single move: skip (don't fail the batch)
        # candidates on jobs where the caller can't make this move.
        move_flag = "can_reject_candidates" if body.stage == "Rejected" else "can_move_stage"
        if not access.can(move_flag):
            continue
        movable.append(c)
    if not movable:
        return {"success": True, "updated": 0}

    now = datetime.now(timezone.utc).isoformat()
    await candidates.update_many(
        {"id": {"$in": [c["id"] for c in movable]}}, {"$set": {"stage": body.stage}}
    )
    await stage_transitions.insert_many([
        {
            "id": str(uuid.uuid4()),
            "candidate_id": c["id"],
            "org_id": c.get("org_id"),
            "actor_id": user["id"],
            "from_stage": c.get("stage"),
            "to_stage": body.stage,
            "note": body.note,
            "moved_by": user["name"],
            "moved_at": now,
        }
        for c in movable
    ])
    await activity_events.insert_many([
        {
            "id": str(uuid.uuid4()), "org_id": c.get("org_id"), "actor_id": user["id"],
            "job_id": c.get("job_id"), "candidate_id": c["id"], "type": "stage_changed",
            "meta": {"from_stage": c.get("stage"), "to_stage": body.stage}, "created_at": now,
        }
        for c in movable
    ])
    return {"success": True, "updated": len(movable)}


@router.post("/{candidate_id}/note")
async def add_note(candidate_id: str, body: NoteUpdate, user: dict = Depends(get_current_user)):
    cand, _ = await permissions.resolve_candidate_access(user, candidate_id)
    note = {
        "id": str(uuid.uuid4()),
        "text": body.note,
        "author": user["name"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    notes = cand.get("notes") or []
    if isinstance(notes, str):
        notes = []
    notes.append(note)
    await candidates.update_one({"id": candidate_id}, {"$set": {"notes": notes}})
    return note


@router.delete("/{candidate_id}")
async def delete_candidate(candidate_id: str, user: dict = Depends(get_current_user)):
    cand, access = await permissions.resolve_candidate_access(user, candidate_id)
    # A recruiter may remove a candidate they sourced; a manager may remove any.
    if access.scope != "manager" and cand.get("sourced_by") != user["id"]:
        raise HTTPException(status_code=403, detail="You can only remove candidates you added.")
    if cand.get("pdf_path"):
        try:
            os.remove(UPLOAD_DIR / cand["pdf_path"])
        except OSError:
            pass
    await stage_transitions.delete_many({"candidate_id": candidate_id})
    await candidates.delete_one({"id": candidate_id})
    return {"success": True}
