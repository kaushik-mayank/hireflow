"""Tests for the org/permission enforcement spine (permissions.py).

This is the security core of Cycle 2, so it gets the most scrutiny: manager vs
recruiter access, cross-org 404 (never 403 — don't confirm existence), permission
denial, and personal-JD resolution.

Offline: stubs fastapi / database / auth so no real Mongo, FastAPI or JWT libs
are needed. Follows the stub-merge pattern that keeps reverse-order runs green.
"""

import asyncio
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeColl:
    """Minimal async Mongo collection supporting equality find_one."""
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    async def find_one(self, query, projection=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                return dict(d)
        return None


def _merge_stub(name, **attrs):
    module = sys.modules.get(name) or types.ModuleType(name)
    for key, value in attrs.items():
        if not hasattr(module, key):
            setattr(module, key, value)
    sys.modules[name] = module
    return module


@pytest.fixture(scope="module")
def env():
    class _HTTPException(Exception):
        def __init__(self, status_code=None, detail=None):
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)

    _merge_stub("fastapi", HTTPException=_HTTPException, Depends=lambda dep=None: None)

    fake = {"jobs": FakeColl(), "job_assignments": FakeColl(), "job_jd_overrides": FakeColl()}
    _merge_stub("database", **fake)
    _merge_stub("auth", get_current_user=lambda: None)

    import permissions
    # Point the module at our fake collections regardless of import order.
    permissions.jobs = fake["jobs"]
    permissions.job_assignments = fake["job_assignments"]
    permissions.job_jd_overrides = fake["job_jd_overrides"]

    return types.SimpleNamespace(
        p=permissions,
        HTTPException=sys.modules["fastapi"].HTTPException,
        jobs=fake["jobs"],
        assignments=fake["job_assignments"],
        overrides=fake["job_jd_overrides"],
    )


MANAGER = {"id": "u-mgr", "org_id": "org-A", "org_role": "manager"}
RECRUITER = {"id": "u-rec", "org_id": "org-A", "org_role": "recruiter"}
OUTSIDER = {"id": "u-out", "org_id": "org-B", "org_role": "manager"}
NO_ORG = {"id": "u-x", "org_role": "manager"}

JOB_A = {"id": "job-1", "org_id": "org-A", "title": "Nurse", "jd_text": "org JD"}


def run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------
# Permission constants
# --------------------------------------------------------------------------

def test_permission_flags_and_defaults(env):
    p = env.p
    assert set(p.PERMISSION_FLAGS) == set(p.DEFAULT_PERMISSIONS)
    assert p.DEFAULT_PERMISSIONS["can_edit_jd"] is False
    assert p.DEFAULT_PERMISSIONS["can_upload_candidates"] is True
    # Manager has every flag True.
    assert all(p.MANAGER_PERMISSIONS.values())
    assert set(p.MANAGER_PERMISSIONS) == set(p.DEFAULT_PERMISSIONS)


def test_is_manager(env):
    assert env.p.is_manager(MANAGER) is True
    assert env.p.is_manager(RECRUITER) is False
    assert env.p.is_manager({}) is False


# --------------------------------------------------------------------------
# resolve_job_access
# --------------------------------------------------------------------------

def test_manager_sees_any_org_job_with_full_permissions(env):
    env.jobs.docs = [JOB_A]
    access = run(env.p.resolve_job_access(MANAGER, "job-1"))
    assert access.scope == "manager"
    assert access.assignment is None
    assert all(access.permissions.values())
    assert access.can("can_edit_jd") and access.can("can_close_job")


def test_cross_org_job_is_404_not_403(env):
    env.jobs.docs = [JOB_A]  # belongs to org-A
    with pytest.raises(env.HTTPException) as e:
        run(env.p.resolve_job_access(OUTSIDER, "job-1"))  # OUTSIDER is org-B
    assert e.value.status_code == 404  # never confirm the job exists


def test_missing_job_is_404(env):
    env.jobs.docs = []
    with pytest.raises(env.HTTPException) as e:
        run(env.p.resolve_job_access(MANAGER, "nope"))
    assert e.value.status_code == 404


def test_user_without_org_is_404(env):
    env.jobs.docs = [JOB_A]
    with pytest.raises(env.HTTPException) as e:
        run(env.p.resolve_job_access(NO_ORG, "job-1"))
    assert e.value.status_code == 404


def test_recruiter_with_active_assignment_gets_merged_permissions(env):
    env.jobs.docs = [JOB_A]
    env.assignments.docs = [{
        "id": "a1", "org_id": "org-A", "job_id": "job-1", "user_id": "u-rec",
        "status": "active", "permissions": {"can_edit_jd": True, "can_upload_candidates": False},
    }]
    access = run(env.p.resolve_job_access(RECRUITER, "job-1"))
    assert access.scope == "assigned"
    assert access.assignment["id"] == "a1"
    # Overrides applied on top of defaults.
    assert access.can("can_edit_jd") is True
    assert access.can("can_upload_candidates") is False
    # Unset flags fall back to defaults.
    assert access.can("can_move_stage") is True
    assert access.can("can_close_job") is False


def test_recruiter_without_assignment_is_404(env):
    env.jobs.docs = [JOB_A]
    env.assignments.docs = []  # not assigned
    with pytest.raises(env.HTTPException) as e:
        run(env.p.resolve_job_access(RECRUITER, "job-1"))
    assert e.value.status_code == 404


def test_recruiter_with_revoked_assignment_is_404(env):
    env.jobs.docs = [JOB_A]
    env.assignments.docs = [{
        "id": "a1", "org_id": "org-A", "job_id": "job-1", "user_id": "u-rec",
        "status": "revoked", "permissions": {},
    }]
    with pytest.raises(env.HTTPException) as e:
        run(env.p.resolve_job_access(RECRUITER, "job-1"))
    assert e.value.status_code == 404


# --------------------------------------------------------------------------
# require_permission
# --------------------------------------------------------------------------

def test_require_permission_passes_when_true(env):
    env.jobs.docs = [JOB_A]
    access = run(env.p.resolve_job_access(MANAGER, "job-1"))
    env.p.require_permission(access, "can_edit_jd")  # no raise


def test_require_permission_raises_403_with_human_message(env):
    env.jobs.docs = [JOB_A]
    env.assignments.docs = [{
        "id": "a1", "org_id": "org-A", "job_id": "job-1", "user_id": "u-rec",
        "status": "active", "permissions": {"can_edit_jd": False},
    }]
    access = run(env.p.resolve_job_access(RECRUITER, "job-1"))
    with pytest.raises(env.HTTPException) as e:
        env.p.require_permission(access, "can_edit_jd")
    assert e.value.status_code == 403
    assert "admin" in e.value.detail.lower()  # human sentence, not a flag name
    assert "can_edit_jd" not in e.value.detail


# --------------------------------------------------------------------------
# resolve_jd (personal override, §5.3)
# --------------------------------------------------------------------------

def test_manager_always_sees_org_jd(env):
    env.jobs.docs = [JOB_A]
    env.overrides.docs = [{"job_id": "job-1", "user_id": "u-mgr", "jd_text": "should be ignored"}]
    access = run(env.p.resolve_job_access(MANAGER, "job-1"))
    jd = run(env.p.resolve_jd(access, MANAGER["id"]))
    assert jd["jd_source"] == "org"
    assert jd["jd_text"] == "org JD"


def test_recruiter_with_override_sees_personal_jd(env):
    env.jobs.docs = [JOB_A]
    env.assignments.docs = [{
        "id": "a1", "org_id": "org-A", "job_id": "job-1", "user_id": "u-rec",
        "status": "active", "permissions": {"can_edit_jd": True},
    }]
    env.overrides.docs = [{"job_id": "job-1", "user_id": "u-rec", "jd_text": "my personal JD", "jd_enhanced": None}]
    access = run(env.p.resolve_job_access(RECRUITER, "job-1"))
    jd = run(env.p.resolve_jd(access, RECRUITER["id"]))
    assert jd["jd_source"] == "personal"
    assert jd["jd_text"] == "my personal JD"


def test_recruiter_without_override_sees_org_jd(env):
    env.jobs.docs = [JOB_A]
    env.assignments.docs = [{
        "id": "a1", "org_id": "org-A", "job_id": "job-1", "user_id": "u-rec",
        "status": "active", "permissions": {},
    }]
    env.overrides.docs = []
    access = run(env.p.resolve_job_access(RECRUITER, "job-1"))
    jd = run(env.p.resolve_jd(access, RECRUITER["id"]))
    assert jd["jd_source"] == "org"
    assert jd["jd_text"] == "org JD"
