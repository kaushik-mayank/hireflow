import uuid
from datetime import datetime, timezone, timedelta

from database import users, jobs, candidates, stage_transitions
from auth import hash_password


def _now_iso(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


# Kept deliberately occupation-neutral: the demo data spans healthcare, logistics
# and software so a first-time viewer sees that HireFlow is not an office-only tool.
SAMPLE_RESUME = (
    "{name}\n{email} | {phone}\n\nSUMMARY\n{summary}\n\n"
    "SKILLS & CERTIFICATIONS\n{skills}\n\nEXPERIENCE\n{experience}\n\nEDUCATION & TRAINING\n{education}"
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
            "password_hash": hash_password("Sarah@1234"), "company": "Meridian Group",
            "role": "hr", "is_active": 1, "last_login_at": _now_iso(0), "created_at": _now_iso(30),
        },
    ])
    return admin_id, hr_id


async def _seed_jobs(hr_id: str) -> tuple[str, str, str]:
    """Insert three demo jobs spanning very different kinds of work.

    Deliberately not all office roles — the demo is often the first thing a
    prospect sees, and it should show that the AI handles a ward rota and a
    warehouse shift as readily as an engineering vacancy.
    """
    job1, job2, job3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await jobs.insert_many([
        {
            "id": job1, "user_id": hr_id, "title": "ICU Registered Nurse",
            "department": "Critical Care — St. Aldate's Hospital", "openings_needed": 3,
            "jd_text": "Registered Nurse required for a 12-bed adult Intensive Care Unit. "
                       "Active NMC registration essential. Minimum 2 years post-registration "
                       "experience, at least 1 of which in critical care or high-dependency. "
                       "Ventilator management, vasoactive infusions, invasive monitoring and "
                       "ALS certification required. Rotating days and nights, 12-hour shifts, "
                       "3 shifts per week. Enhanced DBS check required before start.",
            "jd_enhanced": None, "status": "active", "deadline": _now_iso(-20),
            "created_at": _now_iso(25), "updated_at": _now_iso(5),
        },
        {
            "id": job2, "user_id": hr_id, "title": "Forklift Operator — Night Shift",
            "department": "Distribution Centre — Unit 4", "openings_needed": 4,
            "jd_text": "Counterbalance forklift operators needed for our night distribution "
                       "shift. Valid in-date counterbalance licence (RTITB or ITSSAR) required. "
                       "Experience with reach trucks an advantage. Duties: unloading containers, "
                       "put-away, replenishment and loading outbound trailers, plus RF scanner "
                       "and WMS use. Must be comfortable working in a chilled environment and "
                       "lifting up to 25kg. 22:00-06:00, Sunday to Thursday. Immediate starts.",
            "jd_enhanced": None, "status": "active", "deadline": _now_iso(-15),
            "created_at": _now_iso(18), "updated_at": _now_iso(2),
        },
        {
            "id": job3, "user_id": hr_id, "title": "Backend Software Engineer",
            "department": "Platform Engineering", "openings_needed": 2,
            "jd_text": "Backend engineer to build and scale our internal services. Strong "
                       "Python and PostgreSQL required, plus REST API design and production "
                       "experience with cloud infrastructure. 4+ years commercial experience. "
                       "Bonus: async frameworks, message queues, observability tooling.",
            "jd_enhanced": None, "status": "active", "deadline": _now_iso(-10),
            "created_at": _now_iso(12), "updated_at": _now_iso(1),
        },
    ])
    return job1, job2, job3


def _candidate_samples(job1: str, job2: str, job3: str) -> list:
    """(job, name, email, phone, summary, skills, experience, education,
        stage, score, ai_summary, matched, missing, flags, days)"""
    return [
        # --- ICU Registered Nurse ---
        (job1, "Priya Sharma", "priya.sharma@email.com", "+44 7700 900101",
         "Registered Nurse with 6 years post-registration experience, 4 in adult critical care.",
         "NMC registered (active) | ALS certified | Ventilator management | Vasoactive infusions | "
         "Invasive haemodynamic monitoring | CVC care | Mentorship",
         "Senior Staff Nurse, Adult ICU — 12-bed unit, level 3 patients, shift coordinator on nights.\n"
         "Staff Nurse, High Dependency Unit — post-operative and respiratory support.",
         "BSc (Hons) Adult Nursing | ALS provider, renewed this year",
         "Shortlisted", 94,
         "Exceptionally well matched: active NMC registration, four years of level 3 critical care and current ALS. Already works the rotating 12-hour pattern this post requires.",
         ["NMC registration", "Critical care experience", "Ventilator management", "ALS certification"],
         [], [], 22),
        (job1, "Marcus Lee", "marcus.lee@email.com", "+44 7700 900102",
         "Registered Nurse with 3 years experience across acute medical and respiratory wards.",
         "NMC registered (active) | Acute medical care | Respiratory support | NEWS2 escalation | IV therapy",
         "Staff Nurse, Acute Medical Unit — high-turnover admissions ward.\n"
         "Staff Nurse, Respiratory Ward — non-invasive ventilation, tracheostomy care.",
         "BSc Adult Nursing | ILS certified",
         "Interview Scheduled", 76,
         "Solid acute and respiratory grounding with relevant ventilation exposure, but no formal level 3 ICU time and holds ILS rather than the ALS this post specifies.",
         ["NMC registration", "Respiratory support", "Acute care"],
         ["Critical care experience", "ALS certification"],
         ["Holds ILS, not the ALS certification the role requires"], 20),
        (job1, "Dana Whitfield", "dana.w@email.com", "+44 7700 900103",
         "Registered Nurse returning to practice after two years in community nursing.",
         "NMC registered (active) | Community nursing | Wound care | Long-term condition management",
         "Community Staff Nurse — district caseload, home visits.\n"
         "Staff Nurse, Care of the Elderly ward.",
         "Diploma in Adult Nursing",
         "AI Ranked", 48,
         "Valid registration and genuine nursing experience, but none of it in critical care. Would need a substantial supported preceptorship for a level 3 unit.",
         ["NMC registration"],
         ["Critical care experience", "Ventilator management", "ALS certification"],
         ["No critical care or high-dependency experience for a level 3 post"], 18),

        # --- Forklift Operator, Night Shift ---
        (job2, "Tomasz Baran", "t.baran@email.com", "+44 7700 900104",
         "Warehouse operative and licensed forklift driver with 7 years in chilled distribution.",
         "RTITB counterbalance licence (valid to next year) | Reach truck licence | RF scanner | "
         "SAP WMS | Container unloading | Manual handling certified",
         "Forklift Operator, chilled distribution centre — night shift, container unloading and "
         "outbound loading.\nWarehouse Operative — picking, replenishment, stock counts.",
         "Level 2 Warehousing & Storage | Manual handling certification",
         "Selected", 95,
         "Ideal match: in-date counterbalance and reach licences, seven years in chilled distribution and already working nights on the same shift pattern.",
         ["RTITB counterbalance licence", "Reach truck", "Chilled environment", "WMS/RF scanner", "Night shift"],
         [], [], 16),
        (job2, "Aisha Bello", "aisha.bello@email.com", "+44 7700 900105",
         "Warehouse operative with 3 years across seasonal peak contracts and agency placements.",
         "ITSSAR counterbalance licence (valid) | RF scanner | Goods-in | Manual handling",
         "Forklift Operator (agency) — multiple peak-season placements across three distribution sites.\n"
         "Goods-in Operative — booking in deliveries, pallet handling.",
         "Manual handling certification | Forklift refresher completed this year",
         "Contact Pending", 84,
         "Valid in-date counterbalance licence and directly relevant distribution experience. Agency and seasonal placements are the norm in this sector and show breadth across sites rather than instability.",
         ["ITSSAR counterbalance licence", "RF scanner", "Distribution experience"],
         ["Reach truck", "Chilled environment experience"], [], 12),
        (job2, "Kevin O'Doherty", "kevin.od@email.com", "+44 7700 900106",
         "General labourer looking to move into warehouse work.",
         "Manual handling | Stock replenishment | Willing to train",
         "Warehouse Assistant — picking and packing, no powered equipment.\n"
         "General Labourer — construction site support.",
         "Secondary education",
         "Applied", None, None, [], [], [], 4),

        # --- Backend Software Engineer ---
        (job3, "Elena Rossi", "elena.rossi@email.com", "+44 7700 900107",
         "Backend engineer with 6 years building production Python services.",
         "Python | PostgreSQL | FastAPI | REST API design | AWS | Docker | Celery | Observability",
         "Senior Backend Engineer — owned billing and reporting services at scale.\n"
         "Backend Engineer — API development and database optimisation.",
         "BSc Computer Science",
         "Interview Scheduled", 91,
         "Strong match on every core requirement: deep production Python, PostgreSQL and REST API design, with cloud and async experience beyond what the role asks for.",
         ["Python", "PostgreSQL", "REST API design", "Cloud infrastructure"], [], [], 14),
        (job3, "Carlos Mendes", "carlos.m@email.com", "+44 7700 900108",
         "Software developer with 2 years commercial experience.",
         "Python | Django | MySQL | Git | Basic AWS",
         "Junior Developer — internal tooling and reporting.",
         "BSc Software Engineering",
         "AI Ranked", 58,
         "Genuine Python foundation but roughly two years of commercial experience against a stated four-year requirement, and no PostgreSQL in evidence.",
         ["Python"], ["PostgreSQL", "Production cloud experience"],
         ["Experience below the level the role specifies"], 6),
    ]


_SEED_SOURCES = ["Job board", "Referral", "Agency", "Careers page", "Walk-in"]


def _build_candidate_record(sample: tuple) -> tuple[dict, dict | None]:
    """Build a candidate doc (and optional transition doc) from a sample tuple."""
    (job, name, email, phone, profile, skills, experience, education,
     stage, score, summary, matched, missing, flags, days) = sample
    cid = str(uuid.uuid4())
    analyzed = score is not None
    cand = {
        "id": cid, "job_id": job, "name": name, "email": email, "phone": phone,
        # Rotated across channels so source-effectiveness reporting has something
        # to show in the demo. Real uploads capture this at upload time.
        "source": _SEED_SOURCES[hash(cid) % len(_SEED_SOURCES)],
        "resume_text": SAMPLE_RESUME.format(
            name=name, email=email, phone=phone,
            summary=profile, skills=skills, experience=experience, education=education,
        ),
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


async def _seed_candidates(job1: str, job2: str, job3: str):
    cand_docs, transition_docs = [], []
    for sample in _candidate_samples(job1, job2, job3):
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
    job1, job2, job3 = await _seed_jobs(hr_id)
    await _seed_candidates(job1, job2, job3)
