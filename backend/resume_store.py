"""Resume DB persistence — the internal resume repository (Cycle 5).

One record per (organisation, candidate identity), where identity is derived
from the normalised email. Uploading through the existing job flow also upserts
here (newest-by-email wins). Records reference the same stored file the candidate
record uses, so no file is duplicated. Structured JSON / PDF reuse the candidate
"View Resume" machinery (`resume_structure`, `resume_pdf`).
"""

import hashlib
import re
import uuid
from datetime import datetime, timezone

from database import resume_db


def normalize_email(email) -> str:
    return (email or "").strip().lower()


def derive_experience_years(structured: dict):
    """A conservative total years of experience from the structured resume's
    experience date ranges. Returns an int, or None when it can't be read
    honestly — we never invent a number (§6: don't fabricate fields).

    Only entries whose `dates` contains two 4-digit years (or one year + a
    'present'/'current' end) contribute; the span is the later year minus the
    earlier, summed across entries and clamped to a sane range."""
    entries = (structured or {}).get("experience")
    if not isinstance(entries, list) or not entries:
        return None
    now_year = datetime.now(timezone.utc).year
    total, counted = 0, 0
    for e in entries:
        dates = str((e or {}).get("dates") or "")
        years = [int(m.group(0)) for m in re.finditer(r"(?:19|20)\d{2}", dates)]
        low = end = None
        if years:
            low = min(years)
            end = max(years)
        if low is not None and re.search(r"present|current|now", dates, re.I):
            end = now_year
        if low is None or end is None or end < low or end > now_year + 1:
            continue
        total += (end - low)
        counted += 1
    if not counted:
        return None
    return max(0, min(total, 60))


def extract_skills(structured: dict) -> list:
    """Normalised, de-duplicated skills list for filtering/display."""
    out, seen = [], set()
    for s in (structured or {}).get("skills") or []:
        text = str(s).strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            out.append(text)
    return out


def candidate_uid(email, fallback: str) -> str:
    """Stable identity for de-duplication. Same email → same candidate; a missing
    email falls back to a per-record token so those never collide/merge."""
    e = normalize_email(email)
    if e:
        return "email:" + hashlib.sha256(e.encode("utf-8")).hexdigest()[:40]
    return "anon:" + fallback


def build_record(*, org_id, uploader_id, parsed, name, source, pdf_path,
                 pdf_original_name, now=None, shared=False) -> dict:
    """Assemble a Resume DB record from an `extract_document` result."""
    now = now or datetime.now(timezone.utc).isoformat()
    email = normalize_email(parsed.get("email"))
    return {
        "id": str(uuid.uuid4()),
        "org_id": org_id,
        "uploader_id": uploader_id,
        "candidate_uid": candidate_uid(email, uuid.uuid4().hex),
        "email": email or None,
        "name": name,
        "phone": parsed.get("phone"),
        "resume_text": parsed.get("text") or "",
        "links": parsed.get("links") or [],
        "linkedin": parsed.get("linkedin"),
        "github": parsed.get("github"),
        "portfolio": parsed.get("portfolio"),
        "pdf_path": pdf_path,                 # shared reference to the stored file
        "pdf_original_name": pdf_original_name,
        "source": source,
        "shared": bool(shared),
        "resume_structured": None,            # generated lazily, like candidates
        "skills": [],                          # filled when structured is generated
        "uploaded_at": now,
        "updated_at": now,
    }


async def upsert_fresh(record: dict) -> dict:
    """Insert, or replace the existing (org, uid) record when this upload is newer
    (the freshness rule). The record id and the uploader's sharing choice are
    preserved so existing links/visibility survive a refresh. Handles the
    unique-index race by falling back to an update."""
    key = {"org_id": record["org_id"], "candidate_uid": record["candidate_uid"]}
    existing = await resume_db.find_one(key, {"_id": 0})
    if existing is None:
        try:
            await resume_db.insert_one(dict(record))
            return record
        except Exception:
            # Concurrent insert of the same (org, uid) — re-read and fall through.
            existing = await resume_db.find_one(key, {"_id": 0})
            if existing is None:
                raise

    # Newest wins. On a live upload the incoming record is newer, so refresh the
    # stored data in place (same id → any references keep working), but keep the
    # existing record's sharing visibility.
    if record.get("uploaded_at", "") >= existing.get("uploaded_at", ""):
        updates = {k: v for k, v in record.items() if k not in ("id", "shared")}
        updates["updated_at"] = record.get("uploaded_at")
        await resume_db.update_one({"id": existing["id"]}, {"$set": updates})
        return {**existing, **updates, "id": existing["id"]}
    return existing  # the stored version is newer; leave it


def visibility_filter(user: dict, is_manager: bool) -> dict:
    """Mongo filter for the Resume DB records this user may see: a manager sees
    the whole org; everyone else sees their own uploads plus shared ones."""
    org_id = user.get("org_id")
    if is_manager:
        return {"org_id": org_id}
    return {"org_id": org_id, "$or": [{"uploader_id": user["id"]}, {"shared": True}]}
