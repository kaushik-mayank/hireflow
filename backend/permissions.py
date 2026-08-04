"""Organisation membership, roles and per-job permission enforcement.

The single place every job/candidate/AI/report route goes through to decide what
the caller may see and do. Rules (Cycle 2):

- A **manager** ("Admin" in the UI) sees and does everything within their org.
- A **recruiter** ("User") sees a job only via an active `job_assignments` row,
  and may do only what that assignment's permission flags allow.
- Cross-org or no-access reads return **404**, never 403 — we do not confirm the
  existence of another org's data (see CYCLE2_AUDIT.md C2).
- Jobs are assignment-only in Cycle 2: recruiters do not create jobs (personal
  jobs are deferred to Cycle 3), so a recruiter's only path to a job is an
  assignment.

`org_id`/`org_role` come from the live DB user document returned by
`get_current_user`, so no JWT change is needed (CYCLE2_AUDIT.md C1).
"""

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException

from auth import get_current_user
from database import jobs, job_assignments, job_jd_overrides, candidates

MANAGER = "manager"
RECRUITER = "recruiter"

# Recruiter defaults for an assigned job (§3.1). Managers implicitly get all True.
DEFAULT_PERMISSIONS = {
    "can_edit_jd": False,
    "can_edit_job_meta": False,
    "can_upload_candidates": True,
    "can_move_stage": True,
    "can_reject_candidates": True,
    "can_use_ai": True,
    "can_view_team_candidates": False,
    "can_close_job": False,
}
PERMISSION_FLAGS = tuple(DEFAULT_PERMISSIONS.keys())
MANAGER_PERMISSIONS = {flag: True for flag in DEFAULT_PERMISSIONS}

# Human sentences for denied permissions (never surface a flag name to a user).
_DENIED_MESSAGE = {
    "can_edit_jd": "You don't have permission to edit this job description. Ask your admin.",
    "can_edit_job_meta": "You don't have permission to edit this job's details. Ask your admin.",
    "can_upload_candidates": "You don't have permission to add candidates to this job. Ask your admin.",
    "can_move_stage": "You don't have permission to move candidates on this job. Ask your admin.",
    "can_reject_candidates": "You don't have permission to reject candidates on this job. Ask your admin.",
    "can_use_ai": "You don't have permission to use AI tools on this job. Ask your admin.",
    "can_view_team_candidates": "You can only see candidates you added on this job.",
    "can_close_job": "You don't have permission to close this job. Ask your admin.",
}

_NOT_FOUND = "Job not found"


def is_manager(user: dict) -> bool:
    return bool(user) and user.get("org_role") == MANAGER


@dataclass
class JobAccess:
    """Resolved access for one (user, job): the job doc, the assignment (recruiters
    only), the effective permission map, and the scope."""
    job: dict
    assignment: Optional[dict]
    permissions: dict
    scope: str  # "manager" | "assigned"
    org_id: str

    def can(self, flag: str) -> bool:
        return bool(self.permissions.get(flag, False))


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

async def require_org_member(user: dict = Depends(get_current_user)) -> dict:
    """Any active member of an organisation. Post-migration every user has an
    org; a user without one is treated as unable to see org data."""
    if not user.get("org_id"):
        raise HTTPException(status_code=403, detail="Your account isn't part of an organisation yet.")
    return user


async def require_manager(user: dict = Depends(get_current_user)) -> dict:
    """Org manager only (UI: "Admin"). Distinct from the platform admin allowlist."""
    if not user.get("org_id") or user.get("org_role") != MANAGER:
        raise HTTPException(status_code=403, detail="Only an admin can do this.")
    return user


# ---------------------------------------------------------------------------
# Job access resolution — the core
# ---------------------------------------------------------------------------

async def resolve_job_access(user: dict, job_id: str) -> JobAccess:
    """Resolve what `user` may see/do on `job_id`, or raise 404 if they can't
    reach it at all. No route may fetch a job by id without going through here."""
    org_id = user.get("org_id")
    if not org_id:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)

    job = await jobs.find_one({"id": job_id, "org_id": org_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)

    if is_manager(user):
        return JobAccess(job=job, assignment=None, permissions=dict(MANAGER_PERMISSIONS),
                         scope="manager", org_id=org_id)

    assignment = await job_assignments.find_one(
        {"job_id": job_id, "user_id": user["id"], "status": "active"}, {"_id": 0}
    )
    if not assignment:
        # Recruiter with no active assignment on this job — do not confirm it exists.
        raise HTTPException(status_code=404, detail=_NOT_FOUND)

    permissions = {**DEFAULT_PERMISSIONS, **(assignment.get("permissions") or {})}
    return JobAccess(job=job, assignment=assignment, permissions=permissions,
                     scope="assigned", org_id=org_id)


def require_permission(access: JobAccess, flag: str) -> None:
    """Raise 403 with a human message if the caller lacks `flag` on this job."""
    if not access.can(flag):
        raise HTTPException(status_code=403, detail=_DENIED_MESSAGE.get(flag, "You don't have permission to do this."))


_CANDIDATE_NOT_FOUND = "Candidate not found"


async def accessible_job_ids(user: dict):
    """Job ids a recruiter may see (active assignments). Returns None for a
    manager, meaning 'every job in the org'."""
    if is_manager(user):
        return None
    rows = await job_assignments.find(
        {"org_id": user.get("org_id"), "user_id": user["id"], "status": "active"},
        {"_id": 0, "job_id": 1},
    ).to_list(100000)
    return [r["job_id"] for r in rows]


def candidate_scope_filter(access: JobAccess, user: dict) -> dict:
    """Extra Mongo filter limiting a recruiter to their own sourced candidates,
    unless they may view the whole team's on this job. Managers add nothing."""
    if access.scope == "assigned" and not access.can("can_view_team_candidates"):
        return {"sourced_by": user["id"]}
    return {}


async def resolve_candidate_access(user: dict, candidate_id: str):
    """(candidate, JobAccess) or 404. Enforces org, job access, and per-recruiter
    candidate visibility — all as 404 so nothing about another org/recruiter's
    data is confirmed."""
    org_id = user.get("org_id")
    if not org_id:
        raise HTTPException(status_code=404, detail=_CANDIDATE_NOT_FOUND)
    cand = await candidates.find_one({"id": candidate_id, "org_id": org_id}, {"_id": 0})
    if not cand:
        raise HTTPException(status_code=404, detail=_CANDIDATE_NOT_FOUND)
    access = await resolve_job_access(user, cand["job_id"])  # 404 if no job access
    if (access.scope == "assigned"
            and not access.can("can_view_team_candidates")
            and cand.get("sourced_by") != user["id"]):
        raise HTTPException(status_code=404, detail=_CANDIDATE_NOT_FOUND)
    return cand, access


async def resolve_jd(access: JobAccess, user_id: str) -> dict:
    """The JD text this caller should see and that their AI runs should use.

    A recruiter with a personal override (job_jd_overrides) sees/uses their
    version; everyone else — including the manager — sees the org JD. Overrides
    never write back to `jobs` (§5.3).
    """
    job = access.job
    if access.scope == "assigned":
        override = await job_jd_overrides.find_one(
            {"job_id": job["id"], "user_id": user_id}, {"_id": 0}
        )
        if override:
            return {
                "jd_text": override.get("jd_text") or "",
                "jd_enhanced": override.get("jd_enhanced"),
                "jd_source": "personal",
            }
    return {
        "jd_text": job.get("jd_text") or "",
        "jd_enhanced": job.get("jd_enhanced"),
        "jd_source": "org",
    }
