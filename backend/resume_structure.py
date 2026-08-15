"""Shared, dependency-free normaliser for a parsed/structured resume.

The same structured-resume JSON shape powers the candidate "View Resume" viewer,
the server-side PDF (`resume_pdf.py`) and the Resume DB (Cycle 5). Keeping the
normaliser here means all of them use exactly one schema — no drift.
"""


def as_list(value) -> list:
    if isinstance(value, list):
        return [v for v in value if v not in (None, "")]
    return []


def normalize_structure(parsed: dict, base: dict) -> dict:
    """Coerce the model's JSON into the stable shape the viewer relies on, and
    backfill contact + links from what the parser already extracted (`base` is a
    candidate or resume-DB record carrying email/phone/linkedin/github/portfolio)."""
    parsed = parsed if isinstance(parsed, dict) else {}
    contact = parsed.get("contact") if isinstance(parsed.get("contact"), dict) else {}

    experience = []
    for e in as_list(parsed.get("experience")):
        if isinstance(e, dict):
            experience.append({
                "title": str(e.get("title") or ""),
                "organization": str(e.get("organization") or ""),
                "dates": str(e.get("dates") or ""),
                "location": str(e.get("location") or ""),
                "highlights": [str(h) for h in as_list(e.get("highlights"))],
            })

    education = []
    for e in as_list(parsed.get("education")):
        if isinstance(e, dict):
            education.append({
                "qualification": str(e.get("qualification") or ""),
                "institution": str(e.get("institution") or ""),
                "dates": str(e.get("dates") or ""),
            })

    return {
        "name": str(parsed.get("name") or base.get("name") or ""),
        "headline": str(parsed.get("headline") or ""),
        "contact": {
            # Prefer the reliably-parsed values (from the PDF mailto:/text
            # extraction at upload) over the AI's reading of the mangled resume text.
            "email": str(base.get("email") or contact.get("email") or ""),
            "phone": str(base.get("phone") or contact.get("phone") or ""),
            "location": str(contact.get("location") or ""),
        },
        "links": {
            "linkedin": base.get("linkedin") or "",
            "github": base.get("github") or "",
            "portfolio": base.get("portfolio") or "",
        },
        "summary": str(parsed.get("summary") or ""),
        "skills": [str(s) for s in as_list(parsed.get("skills"))],
        "experience": experience,
        "education": education,
        "certifications": [str(c) for c in as_list(parsed.get("certifications"))],
        "languages": [str(le) for le in as_list(parsed.get("languages"))],
    }
