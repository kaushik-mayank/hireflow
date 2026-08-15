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
# A Sub-Admin *viewing* a team job they neither own nor are assigned to gets
# visibility only — they can see the job and its candidates for oversight, but
# every content action (upload, move, reject, AI, close) is off. Job-level
# management for them comes from their explicit capabilities, not this map.
READONLY_PERMISSIONS = {flag: False for flag in DEFAULT_PERMISSIONS}


def sanitize_permissions(raw) -> dict:
    """Keep only the known permission flags from caller-supplied input, coerced
    to bool. Unknown keys are dropped so a client can never invent a flag, and
    the result is safe to merge onto DEFAULT_PERMISSIONS when saving an
    assignment."""
    if not isinstance(raw, dict):
        return {}
    return {flag: bool(raw[flag]) for flag in PERMISSION_FLAGS if flag in raw}


# ---------------------------------------------------------------------------
# Sub-Admin capabilities (Cycle 5)
#
# The org "Admin" (manager) can promote a recruiter to a **Sub-Admin** and grant
# a subset of these org-admin capabilities. Each maps to real existing manager-
# only functionality. A manager implicitly has all of them; a sub-admin has only
# the ones stored in their user doc's `admin_permissions`. A normal recruiter has
# none. Only a manager can grant/modify/revoke them (never a sub-admin), which is
# enforced where those endpoints live.
#
# NOTE (Cycle 5 correction): `post_jobs` was removed. Every user can already
# create their own (personal) job, so a "post jobs" grant added nothing
# meaningful — the real team-level job capability is `assign_jobs`. A Sub-Admin's
# created jobs become *team* jobs automatically by virtue of the role (see
# `create_job` / `resolve_job_access`), not through a separate permission.
# ---------------------------------------------------------------------------
ADMIN_CAPABILITIES = (
    "delete_jobs",    # close / delete team jobs (not just your own)
    "manage_team",    # approve / suspend / remove teammates
    "assign_jobs",    # assign team jobs to recruiters, set permissions/targets
    "view_reports",   # the team report (Overview + Team) + CSV export
)
_CAP_DENIED = "You don't have permission to do this. Ask your admin."


def sanitize_capabilities(raw) -> list:
    """Keep only known capabilities, de-duplicated and ordered — a client can
    never invent or smuggle in an unknown capability."""
    if not isinstance(raw, list):
        return []
    out = []
    for cap in ADMIN_CAPABILITIES:  # canonical order
        if cap in raw and cap not in out:
            out.append(cap)
    return out


def has_capability(user: dict, cap: str) -> bool:
    """A manager has every capability; a sub-admin has exactly the ones granted."""
    if is_manager(user):
        return True
    return cap in (user.get("admin_permissions") or [])


def is_subadmin(user: dict) -> bool:
    return bool(user) and not is_manager(user) and bool(user.get("admin_permissions"))


def require_capability(cap: str):
    """Dependency factory: allow a manager, or a sub-admin granted `cap`. A normal
    recruiter (or anyone without the capability) gets a 403 — enforced server-side,
    never just hidden in the UI."""
    async def dep(user: dict = Depends(get_current_user)) -> dict:
        if not user.get("org_id"):
            raise HTTPException(status_code=403, detail="Your account isn't part of an organisation yet.")
        if not has_capability(user, cap):
            raise HTTPException(status_code=403, detail=_CAP_DENIED)
        return user
    return dep

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

    # A personal job (a normal user's own) is visible ONLY to its creator, who has
    # full control over it. Not even the org's manager or a Sub-Admin can see
    # someone else's personal job — that privacy is deliberate and preserved.
    if job.get("origin") == "personal":
        if job.get("created_by") == user["id"]:
            return JobAccess(job=job, assignment=None, permissions=dict(MANAGER_PERMISSIONS),
                             scope="owner", org_id=org_id)
        raise HTTPException(status_code=404, detail=_NOT_FOUND)

    # --- Team (org) job ---
    # A manager controls every team job. The job's own creator (a manager or a
    # Sub-Admin) fully controls what they created. Any *other* Sub-Admin gets
    # read-only visibility (role hierarchy: admins/sub-admins see team jobs whether
    # or not they're assigned — §5). A normal recruiter reaches it only via an
    # active assignment; otherwise it 404s (we don't confirm it exists).
    if is_manager(user):
        return JobAccess(job=job, assignment=None, permissions=dict(MANAGER_PERMISSIONS),
                         scope="manager", org_id=org_id)
    if job.get("created_by") == user["id"]:
        return JobAccess(job=job, assignment=None, permissions=dict(MANAGER_PERMISSIONS),
                         scope="owner", org_id=org_id)
    if is_subadmin(user):
        return JobAccess(job=job, assignment=None, permissions=dict(READONLY_PERMISSIONS),
                         scope="subadmin", org_id=org_id)

    assignment = await job_assignments.find_one(
        {"job_id": job_id, "user_id": user["id"], "status": "active"}, {"_id": 0}
    )
    if not assignment:
        # Recruiter with no active assignment on this job — do not confirm it exists.
        raise HTTPException(status_code=404, detail=_NOT_FOUND)

    permissions = {**DEFAULT_PERMISSIONS, **(assignment.get("permissions") or {})}
    return JobAccess(job=job, assignment=assignment, permissions=permissions,
                     scope="assigned", org_id=org_id)


def can_assign_job(user: dict, access: "JobAccess") -> bool:
    """May the caller assign this job to recruiters? Managers always; a Sub-Admin
    only with `assign_jobs`. Never a personal job (those aren't team-assignable)."""
    if access.job.get("origin") == "personal":
        return False
    return is_manager(user) or has_capability(user, "assign_jobs")


def can_close_or_delete_job(user: dict, access: "JobAccess") -> bool:
    """May the caller close/delete this job? The owner/manager always; a Sub-Admin
    with `delete_jobs` may close/delete any *team* job (the 'Close & delete jobs'
    capability). A personal job is only ever its owner's to remove."""
    if access.scope in ("manager", "owner"):
        return True
    if access.job.get("origin") != "personal" and has_capability(user, "delete_jobs"):
        return True
    return False


def require_permission(access: JobAccess, flag: str) -> None:
    """Raise 403 with a human message if the caller lacks `flag` on this job."""
    if not access.can(flag):
        raise HTTPException(status_code=403, detail=_DENIED_MESSAGE.get(flag, "You don't have permission to do this."))


def ensure_job_open(access: JobAccess) -> None:
    """Block changes on a closed job. A closed job stays visible and readable for
    the record, but candidates can't be added and stages can't be changed."""
    if access.job.get("status") == "closed":
        raise HTTPException(status_code=409, detail="This job is closed, so it's read-only. You can still view its candidates and data.")


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


def sees_all_org_jobs(user: dict) -> bool:
    """True for anyone in the admin tier — a manager or *any* Sub-Admin. They see
    every team (org-origin) job in their org, assigned or not, because a
    Sub-Admin's created jobs are team jobs and admins/sub-admins oversee the team
    (§5). A plain recruiter is False (assignment-scoped)."""
    return is_manager(user) or is_subadmin(user)


async def visible_jobs_query(user: dict) -> dict:
    """A Mongo filter for the jobs this user's **personal metrics** cover (reports
    Overview, dashboard): a **manager** aggregates the whole org; everyone else —
    including a Sub-Admin — sees only the jobs they're assigned to plus their own,
    so a Sub-Admin's *own activity* stays their own. Job *listing* visibility is
    broader for the admin tier; use `team_visible_jobs_query` for that.
    """
    org_id = user.get("org_id")
    own_personal = {"origin": "personal", "created_by": user["id"]}
    if is_manager(user):
        return {"org_id": org_id, "$or": [{"origin": {"$ne": "personal"}}, own_personal]}
    rows = await job_assignments.find(
        {"org_id": org_id, "user_id": user["id"], "status": "active"},
        {"_id": 0, "job_id": 1},
    ).to_list(100000)
    assigned = [r["job_id"] for r in rows]
    return {"org_id": org_id, "$or": [{"id": {"$in": assigned}}, own_personal]}


async def team_visible_jobs_query(user: dict) -> dict:
    """A Mongo filter for the jobs shown in the **Jobs list**:
    - a **manager or Sub-Admin** sees every team (org-origin) job — created by any
      admin/sub-admin — plus their own personal jobs (regardless of assignment);
    - a **recruiter** sees the team jobs they're actively assigned to, plus their
      own personal jobs.
    Personal jobs stay visible only to their creator, so a normal user's private
    job never leaks and a normal user never sees the whole org's jobs.
    """
    org_id = user.get("org_id")
    own_personal = {"origin": "personal", "created_by": user["id"]}
    if sees_all_org_jobs(user):
        return {"org_id": org_id, "$or": [{"origin": {"$ne": "personal"}}, own_personal]}
    rows = await job_assignments.find(
        {"org_id": org_id, "user_id": user["id"], "status": "active"},
        {"_id": 0, "job_id": 1},
    ).to_list(100000)
    assigned = [r["job_id"] for r in rows]
    return {"org_id": org_id, "$or": [{"id": {"$in": assigned}}, own_personal]}


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
