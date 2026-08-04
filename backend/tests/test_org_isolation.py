"""End-to-end org-isolation tests for the Cycle 2 routes.

The unit tests in test_permissions.py prove the enforcement spine itself is
correct. These tests prove the *routes actually go through it*: a caller from
another org (or a recruiter with no assignment) must never reach another org's
jobs, candidates, AI runs, dashboard or reports — and cross-org reads must be
404, never 403 (we don't confirm another org's data exists — CYCLE2_AUDIT.md C2).

Offline: stubs fastapi / database / auth / models / ai_service / resume_parser
so no real Mongo, FastAPI, JWT or network is needed. Every module's collection
references are rebound to the *same* fake instances so the spine (permissions)
and the routes see one shared dataset. Follows the stub-merge pattern that keeps
reverse-order runs green.
"""

import asyncio
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---------------------------------------------------------------------------
# Minimal async Mongo fakes (equality + $in matching, sort, to_list, async iter)
# ---------------------------------------------------------------------------

def _matches(doc, query):
    for k, v in query.items():
        if isinstance(v, dict) and "$in" in v:
            if doc.get(k) not in v["$in"]:
                return False
        elif doc.get(k) != v:
            return False
    return True


class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *args, **kwargs):
        return self

    async def to_list(self, _n=None):
        return [dict(d) for d in self._docs]

    def __aiter__(self):
        async def gen():
            for d in self._docs:
                yield dict(d)
        return gen()


class FakeColl:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    async def find_one(self, query, projection=None):
        for d in self.docs:
            if _matches(d, query):
                return dict(d)
        return None

    def find(self, query, projection=None):
        return _Cursor([d for d in self.docs if _matches(d, query)])

    async def count_documents(self, query):
        return sum(1 for d in self.docs if _matches(d, query))

    async def update_one(self, query, update):
        for d in self.docs:
            if _matches(d, query):
                d.update(update.get("$set", {}))
                return
        return

    async def insert_one(self, doc):
        self.docs.append(dict(doc))


def _merge_stub(name, **attrs):
    module = sys.modules.get(name) or types.ModuleType(name)
    for key, value in attrs.items():
        if not hasattr(module, key):
            setattr(module, key, value)
    sys.modules[name] = module
    return module


class _APIRouter:
    def __init__(self, **kwargs):
        pass

    def _decorator(self, *a, **k):
        return lambda fn: fn

    get = post = put = delete = _decorator


# ---------------------------------------------------------------------------
# Fixture: build the stubbed world and import the routes against it
# ---------------------------------------------------------------------------

MANAGER_A = {"id": "mgr-A", "org_id": "org-A", "org_role": "manager", "name": "Mgr A", "company": "A Inc"}
RECRUITER_A = {"id": "rec-A", "org_id": "org-A", "org_role": "recruiter", "name": "Rec A", "company": "A Inc"}
RECRUITER_A2 = {"id": "rec-A2", "org_id": "org-A", "org_role": "recruiter", "name": "Rec A2", "company": "A Inc"}
MANAGER_B = {"id": "mgr-B", "org_id": "org-B", "org_role": "manager", "name": "Mgr B", "company": "B Inc"}

JOB_A = {"id": "job-A", "org_id": "org-A", "title": "Nurse", "jd_text": "org A JD", "status": "active", "openings_needed": 1, "created_at": "2026-01-01T00:00:00+00:00"}
JOB_B = {"id": "job-B", "org_id": "org-B", "title": "Welder", "jd_text": "org B JD", "status": "active", "openings_needed": 1, "created_at": "2026-01-01T00:00:00+00:00"}


class _HTTPException(Exception):
    def __init__(self, status_code=None, detail=None):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@pytest.fixture(scope="module")
def world():
    import os
    os.environ.setdefault("GROQ_API_KEY", "test-key-not-used")

    _merge_stub("fastapi", HTTPException=_HTTPException, Depends=lambda dep=None: None,
                APIRouter=_APIRouter, UploadFile=object, File=lambda *a, **k: None,
                Form=lambda *a, **k: None)

    colls = {
        "jobs": FakeColl(),
        "candidates": FakeColl(),
        "job_assignments": FakeColl(),
        "job_jd_overrides": FakeColl(),
        "stage_transitions": FakeColl(),
        "activity_events": FakeColl(),
        "ai_usage_log": FakeColl(),
    }
    _merge_stub("database", UPLOAD_DIR=Path("."), **colls)
    _merge_stub("auth", get_current_user=lambda: None)
    # ai_service needs the groq SDK stubbed to import offline (see test_prompts).
    _merge_stub("groq", AsyncGroq=lambda **kwargs: None)

    # models needs pydantic (absent offline) and no other offline test imports
    # it, so it alone is stubbed with placeholder request classes — the routes
    # only use them as type hints; tests pass a SimpleNamespace as the body.
    for mdl in ("RankRequest", "EnhanceJDRequest", "QuestionsRequest", "EmailRequest",
                "CompareRequest", "SummaryRequest", "StructureRequest",
                "JobCreate", "JobUpdate", "StageUpdate", "NoteUpdate", "BulkStageUpdate"):
        _merge_stub("models", **{mdl: object})

    # ai_service and resume_parser are real modules other suites import for real,
    # so import the real ones (not fakes that would shadow them) and monkeypatch
    # just the two functions that would otherwise hit the network / DB.
    import ai_service

    async def _fake_call_ai(*a, **k):
        return "[]"

    async def _fake_log_usage(*a, **k):
        return None

    ai_service.call_ai = _fake_call_ai
    ai_service.log_usage = _fake_log_usage

    import permissions
    import routes_jobs
    import routes_candidates
    import routes_ai
    import routes_dashboard
    import routes_reports

    # Rebind every module's collection references to the shared fakes, regardless
    # of import order, so the spine and the routes act on one dataset.
    for module in (permissions, routes_jobs, routes_candidates, routes_ai,
                   routes_dashboard, routes_reports):
        for name, coll in colls.items():
            if hasattr(module, name):
                setattr(module, name, coll)

    return types.SimpleNamespace(
        p=permissions, jobs_r=routes_jobs, cand_r=routes_candidates, ai_r=routes_ai,
        dash_r=routes_dashboard, rep_r=routes_reports, colls=colls,
        # The HTTPException class the routes actually raise is whichever module
        # stubbed `fastapi` first (merge never overrides), so assert against that
        # one — not our local _HTTPException, which may not be the same class.
        exc=sys.modules["fastapi"].HTTPException,
    )


def run(coro):
    return asyncio.run(coro)


def _reset(world, *, jobs=(), candidates=(), assignments=(), overrides=()):
    world.colls["jobs"].docs = [dict(j) for j in jobs]
    world.colls["candidates"].docs = [dict(c) for c in candidates]
    world.colls["job_assignments"].docs = [dict(a) for a in assignments]
    world.colls["job_jd_overrides"].docs = [dict(o) for o in overrides]
    world.colls["stage_transitions"].docs = []
    world.colls["activity_events"].docs = []


def _ns(**kw):
    return types.SimpleNamespace(**kw)


# ===========================================================================
# Jobs
# ===========================================================================

def test_get_job_cross_org_is_404(world):
    _reset(world, jobs=[JOB_A, JOB_B])
    # Manager B tries to read org-A's job.
    with pytest.raises(world.exc) as e:
        run(world.jobs_r.get_job("job-A", MANAGER_B))
    assert e.value.status_code == 404


def test_list_jobs_manager_sees_only_own_org(world):
    _reset(world, jobs=[JOB_A, JOB_B])
    rows = run(world.jobs_r.list_jobs(MANAGER_A))
    assert {r["id"] for r in rows} == {"job-A"}


def test_list_jobs_recruiter_sees_only_assigned(world):
    _reset(
        world,
        jobs=[JOB_A, {**JOB_A, "id": "job-A2"}],
        assignments=[{"id": "as1", "org_id": "org-A", "job_id": "job-A", "user_id": "rec-A", "status": "active", "permissions": {}}],
    )
    rows = run(world.jobs_r.list_jobs(RECRUITER_A))
    assert {r["id"] for r in rows} == {"job-A"}  # not job-A2 (unassigned)


def test_recruiter_cannot_create_job(world):
    _reset(world, jobs=[JOB_A])
    # require_manager is the dependency; call it directly to prove it blocks.
    with pytest.raises(world.exc) as e:
        run(world.p.require_manager(RECRUITER_A))
    assert e.value.status_code == 403


# ===========================================================================
# Candidates
# ===========================================================================

CAND_A = {"id": "cand-A", "org_id": "org-A", "job_id": "job-A", "sourced_by": "rec-A", "stage": "Applied", "name": "Amy", "uploaded_at": "2026-01-02T00:00:00+00:00"}


def test_get_candidate_cross_org_is_404(world):
    _reset(world, jobs=[JOB_A], candidates=[CAND_A])
    with pytest.raises(world.exc) as e:
        run(world.cand_r.get_candidate("cand-A", MANAGER_B))
    assert e.value.status_code == 404


def test_recruiter_cannot_see_other_recruiters_candidate(world):
    # rec-A2 is assigned to the job but without can_view_team_candidates, so a
    # candidate sourced by rec-A is invisible — and invisibility is 404.
    _reset(
        world,
        jobs=[JOB_A],
        candidates=[CAND_A],
        assignments=[{"id": "as2", "org_id": "org-A", "job_id": "job-A", "user_id": "rec-A2", "status": "active", "permissions": {}}],
    )
    with pytest.raises(world.exc) as e:
        run(world.cand_r.get_candidate("cand-A", RECRUITER_A2))
    assert e.value.status_code == 404


def test_list_candidates_recruiter_scoped_to_own(world):
    other = {**CAND_A, "id": "cand-A-other", "sourced_by": "rec-A2"}
    _reset(
        world,
        jobs=[JOB_A],
        candidates=[CAND_A, other],
        assignments=[{"id": "as1", "org_id": "org-A", "job_id": "job-A", "user_id": "rec-A", "status": "active", "permissions": {}}],
    )
    rows = run(world.cand_r.list_candidates("job-A", RECRUITER_A))
    assert {r["id"] for r in rows} == {"cand-A"}  # only their own sourced


def test_list_candidates_manager_sees_all(world):
    other = {**CAND_A, "id": "cand-A-other", "sourced_by": "rec-A2"}
    _reset(world, jobs=[JOB_A], candidates=[CAND_A, other])
    rows = run(world.cand_r.list_candidates("job-A", MANAGER_A))
    assert {r["id"] for r in rows} == {"cand-A", "cand-A-other"}


# ===========================================================================
# AI
# ===========================================================================

def test_rank_cross_org_is_404(world):
    _reset(world, jobs=[JOB_A], candidates=[CAND_A])
    with pytest.raises(world.exc) as e:
        run(world.ai_r.rank_candidates(_ns(job_id="job-A", reanalyze=False), MANAGER_B))
    assert e.value.status_code == 404


def test_rank_denied_without_can_use_ai(world):
    _reset(
        world,
        jobs=[JOB_A],
        candidates=[CAND_A],
        assignments=[{"id": "as1", "org_id": "org-A", "job_id": "job-A", "user_id": "rec-A", "status": "active", "permissions": {"can_use_ai": False}}],
    )
    with pytest.raises(world.exc) as e:
        run(world.ai_r.rank_candidates(_ns(job_id="job-A", reanalyze=False), RECRUITER_A))
    assert e.value.status_code == 403  # permission denial, human message
    assert "can_use_ai" not in (e.value.detail or "")


# ===========================================================================
# Dashboard
# ===========================================================================

def test_dashboard_recruiter_without_assignment_is_empty(world):
    _reset(world, jobs=[JOB_A], candidates=[CAND_A])
    out = run(world.dash_r.dashboard(RECRUITER_A))
    assert out["jobs_summary"] == []
    assert out["stats"]["total_hired"] == 0


def test_dashboard_manager_scoped_to_org(world):
    _reset(world, jobs=[JOB_A, JOB_B], candidates=[CAND_A, {**CAND_A, "id": "cB", "org_id": "org-B", "job_id": "job-B"}])
    out = run(world.dash_r.dashboard(MANAGER_A))
    assert {j["id"] for j in out["jobs_summary"]} == {"job-A"}


# ===========================================================================
# Reports
# ===========================================================================

def test_reports_recruiter_no_assignment_is_empty(world):
    _reset(world, jobs=[JOB_A], candidates=[CAND_A])
    out = run(world.rep_r.reports(RECRUITER_A))
    assert out["totals"]["jobs"] == 0
    assert out["totals"]["candidates"] == 0


def test_reports_manager_scoped_to_own_org(world):
    _reset(world, jobs=[JOB_A, JOB_B], candidates=[CAND_A, {**CAND_A, "id": "cB", "org_id": "org-B", "job_id": "job-B"}])
    out = run(world.rep_r.reports(MANAGER_A))
    assert out["totals"]["jobs"] == 1
    assert out["totals"]["candidates"] == 1  # org-B's candidate excluded
