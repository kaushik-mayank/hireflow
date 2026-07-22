import uuid
from datetime import datetime, timezone, timedelta

from database import users, jobs, candidates, stage_transitions
from auth import hash_password


def _now_iso(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


SAMPLE_RESUME = (
    "{name}\n{email} | {phone}\n\nSUMMARY\nExperienced professional with {years} years building "
    "scalable products.\n\nSKILLS\n{skills}\n\nEXPERIENCE\nSenior role at TechCorp leading teams "
    "and shipping features.\n\nEDUCATION\nB.S. Computer Science"
)


async def _seed_users() -> tuple[str, str]:
    """Insert demo admin + HR users. Returns (admin_id, hr_id)."""
    admin_id, hr_id = str(uuid.uuid4()), str(uuid.uuid4())
    await users.insert_many([
        {
            "id": admin_id, "name": "Alex Admin", "email": "admin@hireflow.com",
            "password_hash": hash_password("Admin@1234"), "company": "HireFlow Inc",
            "role": "admin", "is_active": 1, "last_login_at": _now_iso(0), "created_at": _now_iso(40),
        },
        {
            "id": hr_id, "name": "Sarah Chen", "email": "sarah@hireflow.com",
            "password_hash": hash_password("Sarah@1234"), "company": "Acme Corp",
            "role": "hr", "is_active": 1, "last_login_at": _now_iso(0), "created_at": _now_iso(30),
        },
    ])
    return admin_id, hr_id


async def _seed_jobs(hr_id: str) -> tuple[str, str]:
    """Insert two demo jobs for the HR user. Returns (job1_id, job2_id)."""
    job1, job2 = str(uuid.uuid4()), str(uuid.uuid4())
    await jobs.insert_many([
        {
            "id": job1, "user_id": hr_id, "title": "Senior Frontend Engineer",
            "department": "Engineering", "openings_needed": 2,
            "jd_text": "We are hiring a Senior Frontend Engineer experienced in React, TypeScript, "
                       "state management, performance optimization, and design systems. 5+ years required. "
                       "Bonus: Next.js, testing, accessibility.",
            "jd_enhanced": None, "status": "active", "deadline": _now_iso(-20),
            "created_at": _now_iso(25), "updated_at": _now_iso(5),
        },
        {
            "id": job2, "user_id": hr_id, "title": "Product Designer",
            "department": "Design", "openings_needed": 1,
            "jd_text": "Seeking a Product Designer skilled in Figma, user research, prototyping, "
                       "interaction design, and design systems. 3+ years in SaaS preferred.",
            "jd_enhanced": None, "status": "active", "deadline": _now_iso(-15),
            "created_at": _now_iso(18), "updated_at": _now_iso(2),
        },
    ])
    return job1, job2


def _candidate_samples(job1: str, job2: str) -> list:
    # (job, name, email, phone, years, skills, stage, score, summary, matched, missing, flags, days)
    return [
        (job1, "Priya Sharma", "priya.sharma@email.com", "+1 415 555 0101", 7,
         "React, TypeScript, Next.js, Redux, Jest, Accessibility",
         "Shortlisted", 92, "Outstanding frontend engineer with deep React and TypeScript expertise and a strong design-systems background.",
         ["React", "TypeScript", "Next.js", "Design Systems"], ["GraphQL"], [], 22),
        (job1, "Marcus Lee", "marcus.lee@email.com", "+1 415 555 0102", 5,
         "React, JavaScript, CSS, Redux, REST APIs",
         "Interview Scheduled", 81, "Solid mid-senior engineer with good React fundamentals; lighter on TypeScript.",
         ["React", "Redux", "REST APIs"], ["TypeScript", "Testing"], ["Limited TypeScript experience"], 20),
        (job1, "Dana Whitfield", "dana.w@email.com", "+1 415 555 0103", 3,
         "Vue, JavaScript, HTML, CSS",
         "AI Ranked", 54, "Frontend developer with Vue background; would need ramp-up on the React ecosystem.",
         ["JavaScript", "CSS"], ["React", "TypeScript", "Next.js"], ["No React experience", "Below required seniority"], 18),
        (job1, "Tom Baker", "tom.baker@email.com", "+1 415 555 0104", 6,
         "React, TypeScript, Webpack, Performance",
         "Contact Pending", 88, "Strong performance-focused engineer with React and TypeScript depth.",
         ["React", "TypeScript", "Performance"], ["Design Systems"], [], 15),
        (job2, "Elena Rossi", "elena.rossi@email.com", "+1 415 555 0105", 4,
         "Figma, User Research, Prototyping, Design Systems",
         "Selected", 90, "Excellent product designer with strong research and systems thinking.",
         ["Figma", "User Research", "Design Systems"], [], [], 16),
        (job2, "Carlos Mendes", "carlos.m@email.com", "+1 415 555 0106", 2,
         "Figma, UI Design, Illustration",
         "Applied", None, None, [], [], [], 4),
    ]


def _build_candidate_record(sample: tuple) -> tuple[dict, dict | None]:
    """Build a candidate doc (and optional transition doc) from a sample tuple."""
    (job, name, email, phone, years, skills, stage, score, summary, matched, missing, flags, days) = sample
    cid = str(uuid.uuid4())
    analyzed = score is not None
    cand = {
        "id": cid, "job_id": job, "name": name, "email": email, "phone": phone,
        "resume_text": SAMPLE_RESUME.format(name=name, email=email, phone=phone, years=years, skills=skills),
        "pdf_path": None, "pdf_original_name": f"{name.replace(' ', '_')}_Resume.pdf",
        "stage": stage, "ai_score": score, "ai_summary": summary,
        "matched_skills": matched, "missing_skills": missing, "red_flags": flags,
        "notes": [], "uploaded_at": _now_iso(days), "analyzed_at": _now_iso(days - 1) if analyzed else None,
    }
    transition = None
    if stage != "Applied":
        transition = {
            "id": str(uuid.uuid4()), "candidate_id": cid, "from_stage": "AI Ranked",
            "to_stage": stage, "note": None, "moved_by": "Sarah Chen",
            "moved_at": _now_iso(max(days - 3, 0)),
        }
    return cand, transition


async def _seed_candidates(job1: str, job2: str):
    cand_docs, transition_docs = [], []
    for sample in _candidate_samples(job1, job2):
        cand, transition = _build_candidate_record(sample)
        cand_docs.append(cand)
        if transition:
            transition_docs.append(transition)
    await candidates.insert_many(cand_docs)
    if transition_docs:
        await stage_transitions.insert_many(transition_docs)


async def seed_if_empty():
    if await users.count_documents({}) > 0:
        return
    _admin_id, hr_id = await _seed_users()
    job1, job2 = await _seed_jobs(hr_id)
    await _seed_candidates(job1, job2)
