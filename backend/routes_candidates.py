import os
import re
import uuid
import io
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pypdf import PdfReader

from database import jobs, candidates, stage_transitions, UPLOAD_DIR
from auth import get_current_user
from models import StageUpdate, NoteUpdate, BulkStageUpdate

router = APIRouter(prefix="/candidates", tags=["candidates"])

STAGES = [
    "Applied", "AI Ranked", "Shortlisted", "Contact Pending", "Contacted",
    "Interview Scheduled", "Interview Done", "Selected", "Rejected", "On Hold",
]
HIRED_STAGE = "Selected"

# Where a candidate came from. Free text so any channel works — job boards,
# agencies, referrals, walk-ins, notice boards, WhatsApp groups — but the UI
# offers these as quick picks. Reports group by whatever value is stored.
UNKNOWN_SOURCE = "Unknown"

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")


def extract_pdf_text(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        return text.strip()
    except Exception:
        return ""


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
    source: str = Form(UNKNOWN_SOURCE),
    user: dict = Depends(get_current_user),
):
    job = await jobs.find_one({"id": job_id, "user_id": user["id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    created = []
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"{f.filename} is not a PDF")
        content = await f.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"{f.filename} exceeds 5MB")

        text = extract_pdf_text(content)
        stored_name = f"{uuid.uuid4()}.pdf"
        with open(UPLOAD_DIR / stored_name, "wb") as out:
            out.write(content)

        email_match = EMAIL_RE.search(text)
        phone_match = PHONE_RE.search(text)
        now = datetime.now(timezone.utc).isoformat()
        cand = {
            "id": str(uuid.uuid4()),
            "job_id": job_id,
            "name": guess_name(text, f.filename),
            "email": email_match.group(0) if email_match else None,
            "phone": phone_match.group(0).strip() if phone_match else None,
            "resume_text": text or "(Could not extract text from PDF)",
            "pdf_path": stored_name,
            "pdf_original_name": f.filename,
            "source": (source or "").strip() or UNKNOWN_SOURCE,
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
        created.append(cand)
    return {"created": created, "count": len(created)}


@router.get("/job/{job_id}")
async def list_candidates(job_id: str, user: dict = Depends(get_current_user)):
    job = await jobs.find_one({"id": job_id, "user_id": user["id"]})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    docs = await candidates.find({"job_id": job_id}, {"_id": 0}).to_list(5000)
    return docs


async def _owns_candidate(candidate_id: str, user: dict):
    cand = await candidates.find_one({"id": candidate_id}, {"_id": 0})
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")
    job = await jobs.find_one({"id": cand["job_id"], "user_id": user["id"]})
    if not job:
        raise HTTPException(status_code=403, detail="Not authorized for this candidate")
    return cand, job


@router.get("/{candidate_id}")
async def get_candidate(candidate_id: str, user: dict = Depends(get_current_user)):
    cand, job = await _owns_candidate(candidate_id, user)
    transitions = await stage_transitions.find(
        {"candidate_id": candidate_id}, {"_id": 0}
    ).sort("moved_at", -1).to_list(500)
    cand["job"] = {"id": job["id"], "title": job["title"], "department": job.get("department")}
    cand["transitions"] = transitions
    return cand


async def _move_stage(cand: dict, to_stage: str, note: str, user: dict):
    from_stage = cand.get("stage")
    now = datetime.now(timezone.utc).isoformat()
    await candidates.update_one({"id": cand["id"]}, {"$set": {"stage": to_stage}})
    await stage_transitions.insert_one({
        "id": str(uuid.uuid4()),
        "candidate_id": cand["id"],
        "from_stage": from_stage,
        "to_stage": to_stage,
        "note": note,
        "moved_by": user["name"],
        "moved_at": now,
    })


@router.put("/{candidate_id}/stage")
async def update_stage(candidate_id: str, body: StageUpdate, user: dict = Depends(get_current_user)):
    if body.stage not in STAGES:
        raise HTTPException(status_code=400, detail="Invalid stage")
    cand, job = await _owns_candidate(candidate_id, user)
    await _move_stage(cand, body.stage, body.note, user)

    quota_met = False
    if body.stage == HIRED_STAGE:
        hired = await candidates.count_documents({"job_id": job["id"], "stage": HIRED_STAGE})
        quota_met = hired >= job.get("openings_needed", 1)
    return {"success": True, "stage": body.stage, "quota_met": quota_met}


@router.put("/bulk-stage")
async def bulk_update_stage(body: BulkStageUpdate, user: dict = Depends(get_current_user)):
    if body.stage not in STAGES:
        raise HTTPException(status_code=400, detail="Invalid stage")
    updated = 0
    for cid in body.candidate_ids:
        cand = await candidates.find_one({"id": cid}, {"_id": 0})
        if not cand:
            continue
        job = await jobs.find_one({"id": cand["job_id"], "user_id": user["id"]})
        if not job:
            continue
        await _move_stage(cand, body.stage, body.note, user)
        updated += 1
    return {"success": True, "updated": updated}


@router.post("/{candidate_id}/note")
async def add_note(candidate_id: str, body: NoteUpdate, user: dict = Depends(get_current_user)):
    cand, _ = await _owns_candidate(candidate_id, user)
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
    cand, _ = await _owns_candidate(candidate_id, user)
    if cand.get("pdf_path"):
        try:
            os.remove(UPLOAD_DIR / cand["pdf_path"])
        except OSError:
            pass
    await stage_transitions.delete_many({"candidate_id": candidate_id})
    await candidates.delete_one({"id": candidate_id})
    return {"success": True}
