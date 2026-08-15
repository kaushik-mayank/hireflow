import os
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# Collections
users = db.users
jobs = db.jobs
candidates = db.candidates
stage_transitions = db.stage_transitions
ai_usage_log = db.ai_usage_log
login_activity = db.login_activity
feedback = db.feedback

# Cycle 2 — organisations, invitations, assignments, per-recruiter JD overrides,
# and an append-only activity log powering manager KPIs. All additive.
organizations = db.organizations
# `invitations` is reserved for a future emailed-invite / plan-purchase cycle and
# is not written by the current approved-email onboarding flow (see routes_orgs).
invitations = db.invitations
job_assignments = db.job_assignments
job_jd_overrides = db.job_jd_overrides
activity_events = db.activity_events
# Cycle 5 — persistent internal resume repository ("Resume DB"). One record per
# (org, candidate email); reused across jobs, with per-record sharing visibility.
resume_db = db.resume_db

# Upload directory
UPLOAD_DIR = ROOT_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def ensure_indexes() -> None:
    """Indexes matching how the app actually queries.

    Every dashboard and reports request filters candidates by job_id and then
    by stage, and sorts jobs by created_at — none of which were indexed. The
    compound indexes below cover those access paths; MongoDB can use a prefix
    of a compound index, so `candidates(job_id, stage)` also serves lookups on
    job_id alone.
    """
    await users.create_index("email", unique=True)
    # Firebase sign-in resolves accounts by uid; sparse because legacy
    # password accounts have no uid at all.
    await users.create_index("firebase_uid", sparse=True)

    # Jobs are always scoped to a user and listed newest first.
    await jobs.create_index([("user_id", 1), ("created_at", -1)])
    await jobs.create_index([("user_id", 1), ("status", 1)])
    await jobs.create_index("id")

    # Candidates are fetched per job, then counted or filtered by stage.
    await candidates.create_index([("job_id", 1), ("stage", 1)])
    await candidates.create_index([("job_id", 1), ("uploaded_at", -1)])
    await candidates.create_index("id")
    # Admin resume list sorts globally by upload date.
    await candidates.create_index([("uploaded_at", -1)])

    # Reports read the whole transition trail for a set of candidates.
    await stage_transitions.create_index([("candidate_id", 1), ("moved_at", -1)])

    await ai_usage_log.create_index("user_id")
    await ai_usage_log.create_index([("created_at", -1)])
    await login_activity.create_index("user_id")
    await login_activity.create_index([("created_at", -1)])
    await feedback.create_index([("created_at", -1)])
    await feedback.create_index([("user_id", 1), ("created_at", -1)])
    await feedback.create_index("status")

    # --- Cycle 2 (all additive; create_index is idempotent) ---
    await users.create_index([("org_id", 1), ("status", 1)])

    await organizations.create_index("id")
    await organizations.create_index("owner_user_id")

    await invitations.create_index("token_hash")
    await invitations.create_index([("org_id", 1), ("status", 1)])
    # At most one PENDING invite per (org, email); accepted/revoked don't collide.
    await invitations.create_index(
        [("org_id", 1), ("email", 1)],
        unique=True,
        partialFilterExpression={"status": "pending"},
        name="uniq_pending_invite_per_org_email",
    )

    await jobs.create_index([("org_id", 1), ("status", 1), ("created_at", -1)])
    await jobs.create_index([("org_id", 1), ("created_by", 1)])

    await job_assignments.create_index([("org_id", 1), ("user_id", 1), ("status", 1)])
    await job_assignments.create_index("job_id")
    await job_assignments.create_index([("job_id", 1), ("user_id", 1)], unique=True)

    await job_jd_overrides.create_index([("job_id", 1), ("user_id", 1)], unique=True)

    await candidates.create_index([("org_id", 1), ("sourced_by", 1), ("stage", 1)])

    await activity_events.create_index([("org_id", 1), ("created_at", -1)])
    await activity_events.create_index([("actor_id", 1), ("created_at", -1)])

    # Resume DB: one row per (org, candidate_uid). Uploader + shared drive
    # visibility; uploaded_at drives the freshness (newest-wins) rule.
    await resume_db.create_index([("org_id", 1), ("candidate_uid", 1)], unique=True)
    await resume_db.create_index([("org_id", 1), ("uploader_id", 1)])
    await resume_db.create_index([("org_id", 1), ("shared", 1), ("uploaded_at", -1)])
    await resume_db.create_index("id")
