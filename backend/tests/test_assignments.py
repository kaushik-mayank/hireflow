"""Route-level tests for job assignments and personal JD overrides (Phase 12).

Offline: stubs fastapi / database / auth / models and imports the REAL
permissions + routes_assignments so the enforcement actually runs. Collection
references are rebound to shared fakes regardless of import order (stub-merge
pattern), so reverse-order runs stay green.
"""

import asyncio
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _matches(doc, query):
    for k, v in query.items():
        if isinstance(v, dict):
            # `_manager_job_or_404` now filters `origin: {"$ne": "personal"}`, so the
            # fake matcher must understand $ne (and keep supporting $in).
            if "$in" in v and doc.get(k) not in v["$in"]:
                return False
            if "$ne" in v and doc.get(k) == v["$ne"]:
                return False
            if not ("$in" in v or "$ne" in v) and doc.get(k) != v:
                return False
        elif doc.get(k) != v:
            return False
    return True


class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *a, **k):
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

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    async def update_one(self, query, update):
        for d in self.docs:
            if _matches(d, query):
                d.update(update.get("$set", {}))
                return

    async def delete_one(self, query):
        for i, d in enumerate(self.docs):
            if _matches(d, query):
                del self.docs[i]
                return


def _merge_stub(name, **attrs):
    module = sys.modules.get(name) or types.ModuleType(name)
    for key, value in attrs.items():
        if not hasattr(module, key):
            setattr(module, key, value)
    sys.modules[name] = module
    return module


class _HTTPException(Exception):
    def __init__(self, status_code=None, detail=None):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class _APIRouter:
    def __init__(self, **kwargs):
        pass

    def _decorator(self, *a, **k):
        return lambda fn: fn

    get = post = put = patch = delete = _decorator


MANAGER_A = {"id": "mgr-A", "org_id": "org-A", "org_role": "manager", "status": "active", "name": "Mgr A"}
MANAGER_B = {"id": "mgr-B", "org_id": "org-B", "org_role": "manager", "status": "active", "name": "Mgr B"}
REC_A = {"id": "rec-A", "org_id": "org-A", "org_role": "recruiter", "status": "active", "name": "Rec A", "email": "rec@a.com"}
JOB_A = {"id": "job-A", "org_id": "org-A", "title": "Nurse", "jd_text": "org JD", "status": "active"}


@pytest.fixture(scope="module")
def world():
    _merge_stub("fastapi", HTTPException=_HTTPException, Depends=lambda dep=None: None, APIRouter=_APIRouter)
    colls = {name: FakeColl() for name in (
        "jobs", "users", "candidates", "job_assignments", "job_jd_overrides", "activity_events",
    )}
    _merge_stub("database", **colls)
    _merge_stub("auth", get_current_user=lambda: None)
    for mdl in ("AssignmentUpsert", "BulkAssignmentUpsert", "JDOverrideUpdate"):
        _merge_stub("models", **{mdl: object})

    import permissions
    import routes_assignments

    for module in (permissions, routes_assignments):
        for name, coll in colls.items():
            if hasattr(module, name):
                setattr(module, name, coll)

    return types.SimpleNamespace(
        r=routes_assignments, p=permissions, colls=colls,
        exc=sys.modules["fastapi"].HTTPException,
    )


def run(coro):
    return asyncio.run(coro)


def _seed(world, *, jobs=(JOB_A,), users=(MANAGER_A, REC_A), assignments=(), overrides=()):
    world.colls["jobs"].docs = [dict(j) for j in jobs]
    world.colls["users"].docs = [dict(u) for u in users]
    world.colls["job_assignments"].docs = [dict(a) for a in assignments]
    world.colls["job_jd_overrides"].docs = [dict(o) for o in overrides]
    world.colls["activity_events"].docs = []


def _body(**kw):
    base = {"user_id": "rec-A", "permissions": None, "shortlist_target": None,
            "sourced_target": None, "interview_target": None, "deadline": None,
            "note": None, "status": None}
    base.update(kw)
    return types.SimpleNamespace(**base)


def _assignment(**kw):
    base = {"id": "as-1", "org_id": "org-A", "job_id": "job-A", "user_id": "rec-A",
            "assigned_by": "mgr-A", "status": "active",
            "permissions": {**{f: False for f in ()}, "can_edit_jd": False}, "targets": {},
            "deadline": None, "note": None}
    base.update(kw)
    return base


# ===========================================================================
# upsert_assignment
# ===========================================================================

def test_assign_creates_with_merged_permissions(world):
    _seed(world)
    out = run(world.r.upsert_assignment("job-A", _body(
        permissions={"can_edit_jd": True, "bogus": True}, shortlist_target=5, deadline="2026-09-01"
    ), MANAGER_A))
    assert out["user_id"] == "rec-A"
    # Override applied, unknown flag dropped, unset flags default.
    assert out["permissions"]["can_edit_jd"] is True
    assert "bogus" not in out["permissions"]
    assert out["permissions"]["can_upload_candidates"] is True  # default
    assert out["targets"]["shortlist_target"] == 5
    assert out["deadline"] == "2026-09-01"
    assert len(world.colls["job_assignments"].docs) == 1
    assert world.colls["activity_events"].docs[0]["type"] == "job_assigned"


def test_assign_is_idempotent(world):
    _seed(world)
    run(world.r.upsert_assignment("job-A", _body(shortlist_target=3), MANAGER_A))
    run(world.r.upsert_assignment("job-A", _body(shortlist_target=9), MANAGER_A))
    assert len(world.colls["job_assignments"].docs) == 1  # updated, not duplicated
    assert world.colls["job_assignments"].docs[0]["targets"]["shortlist_target"] == 9


def test_assign_cross_org_job_is_404(world):
    _seed(world)
    with pytest.raises(world.exc) as e:
        run(world.r.upsert_assignment("job-A", _body(), MANAGER_B))
    assert e.value.status_code == 404


def test_bulk_assign_assigns_and_skips(world):
    other = {"id": "rec-A2", "org_id": "org-A", "org_role": "recruiter", "status": "active", "name": "R2", "email": "r2@a.com"}
    _seed(world, users=(MANAGER_A, REC_A, other))
    body = types.SimpleNamespace(
        user_ids=["rec-A", "rec-A2", "rec-A", "ghost"], permissions={"can_edit_jd": True},
        shortlist_target=3, sourced_target=None, interview_target=None, deadline=None, note=None, status=None,
    )
    out = run(world.r.bulk_upsert_assignments("job-A", body, MANAGER_A))
    assert {a["user_id"] for a in out["assigned"]} == {"rec-A", "rec-A2"}  # de-duped
    assert any(s["user_id"] == "ghost" for s in out["skipped"])
    assert len(world.colls["job_assignments"].docs) == 2
    assert out["assigned"][0]["permissions"]["can_edit_jd"] is True


def test_assign_unknown_member_is_404(world):
    _seed(world)
    with pytest.raises(world.exc) as e:
        run(world.r.upsert_assignment("job-A", _body(user_id="ghost"), MANAGER_A))
    assert e.value.status_code == 404


def test_assign_to_manager_is_400(world):
    other_mgr = {"id": "mgr2", "org_id": "org-A", "org_role": "manager", "status": "active", "name": "M2"}
    _seed(world, users=(MANAGER_A, other_mgr))
    with pytest.raises(world.exc) as e:
        run(world.r.upsert_assignment("job-A", _body(user_id="mgr2"), MANAGER_A))
    assert e.value.status_code == 400


def test_assign_to_disabled_member_is_400(world):
    _seed(world, users=(MANAGER_A, {**REC_A, "status": "disabled"}))
    with pytest.raises(world.exc) as e:
        run(world.r.upsert_assignment("job-A", _body(), MANAGER_A))
    assert e.value.status_code == 400


# ===========================================================================
# list / revoke
# ===========================================================================

def test_list_assignments_enriched(world):
    _seed(world, assignments=[_assignment()])
    rows = run(world.r.list_assignments("job-A", MANAGER_A))
    assert len(rows) == 1
    assert rows[0]["user_name"] == "Rec A" and rows[0]["user_email"] == "rec@a.com"


def test_revoke_sets_status_and_drops_override(world):
    _seed(world, assignments=[_assignment()],
          overrides=[{"id": "o1", "job_id": "job-A", "user_id": "rec-A", "jd_text": "mine"}])
    out = run(world.r.revoke_assignment("job-A", "rec-A", MANAGER_A))
    assert out["success"] is True
    assert world.colls["job_assignments"].docs[0]["status"] == "revoked"
    assert world.colls["job_jd_overrides"].docs == []


def test_revoke_missing_is_404(world):
    _seed(world, assignments=[])
    with pytest.raises(world.exc) as e:
        run(world.r.revoke_assignment("job-A", "rec-A", MANAGER_A))
    assert e.value.status_code == 404


# ===========================================================================
# my_assignments
# ===========================================================================

def test_my_assignments_for_recruiter(world):
    _seed(world, assignments=[_assignment(targets={"shortlist_target": 4})])
    out = run(world.r.my_assignments(REC_A))
    assert len(out) == 1
    assert out[0]["job_title"] == "Nurse"
    assert out[0]["targets"]["shortlist_target"] == 4


def test_my_assignments_empty_for_manager(world):
    _seed(world, assignments=[_assignment()])
    assert run(world.r.my_assignments(MANAGER_A)) == []


# ===========================================================================
# JD override
# ===========================================================================

def test_set_jd_override_requires_permission(world):
    _seed(world, assignments=[_assignment(permissions={"can_edit_jd": False})])
    with pytest.raises(world.exc) as e:
        run(world.r.set_jd_override("job-A", types.SimpleNamespace(jd_text="mine", jd_enhanced=None), REC_A))
    assert e.value.status_code == 403


def test_set_jd_override_saves_personal(world):
    _seed(world, assignments=[_assignment(permissions={"can_edit_jd": True})])
    out = run(world.r.set_jd_override("job-A", types.SimpleNamespace(jd_text="my JD", jd_enhanced=None), REC_A))
    assert out["jd_source"] == "personal" and out["jd_text"] == "my JD"
    assert len(world.colls["job_jd_overrides"].docs) == 1


def test_manager_cannot_set_personal_override(world):
    _seed(world)
    with pytest.raises(world.exc) as e:
        run(world.r.set_jd_override("job-A", types.SimpleNamespace(jd_text="x", jd_enhanced=None), MANAGER_A))
    assert e.value.status_code == 400


def test_set_jd_override_cross_org_is_404(world):
    _seed(world)
    with pytest.raises(world.exc) as e:
        run(world.r.set_jd_override("job-A", types.SimpleNamespace(jd_text="x", jd_enhanced=None), MANAGER_B))
    assert e.value.status_code == 404


def test_clear_jd_override_reverts_to_org(world):
    _seed(world, assignments=[_assignment(permissions={"can_edit_jd": True})],
          overrides=[{"id": "o1", "job_id": "job-A", "user_id": "rec-A", "jd_text": "mine"}])
    out = run(world.r.clear_jd_override("job-A", REC_A))
    assert out["jd_source"] == "org" and out["jd_text"] == "org JD"
    assert world.colls["job_jd_overrides"].docs == []
