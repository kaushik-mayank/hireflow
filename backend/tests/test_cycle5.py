"""Cycle 5 end-to-end tests: Resume DB + Sub-Admins.

Proves the routes actually enforce the Cycle 5 rules — not just that helpers are
correct in isolation:

- **Resume DB**: an upload creates a repository record with the parsed JSON; the
  same person's newest resume wins and the old one is replaced at DB level; the
  stored file is reused (never duplicated); listing/filter/search run server-side;
  a private record is invisible to other users and across orgs (404); sharing is
  dynamic + reversible with owner/manager-only authorization; move-to-job reuses
  the file, records source "Internal Database" and remembers its origin.
- **Sub-Admins**: a manager can promote/modify/revoke capabilities; a Sub-Admin
  may do only what was granted, can never promote others or escalate, and can
  never touch a manager or another admin; normal recruiters are unaffected.

Offline, following the established stub-merge pattern (test_org_isolation.py):
fastapi / database / auth / models / ai_service / resume_pdf are stubbed so no
real Mongo, FastAPI, JWT, network or reportlab is needed. Every module's
collection references are rebound to the *same* fakes so the spine (permissions,
resume_store) and the routes act on one shared dataset. Written to stay green in
forward AND reverse test order.
"""

import asyncio
import re
import sys
import tempfile
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---------------------------------------------------------------------------
# Fake async Mongo with the operators these routes use ($and/$or/$in/$ne/$gte/
# $lte/$regex/$elemMatch) plus sort/skip/limit paging.
# ---------------------------------------------------------------------------

def _match_value(val, cond) -> bool:
    if isinstance(cond, dict) and any(k.startswith("$") for k in cond):
        for op, opv in cond.items():
            if op == "$in":
                if val not in opv:
                    return False
            elif op == "$nin":
                if val in opv:
                    return False
            elif op == "$ne":
                if val == opv:
                    return False
            elif op == "$gte":
                if val is None or val < opv:
                    return False
            elif op == "$lte":
                if val is None or val > opv:
                    return False
            elif op == "$regex":
                flags = re.I if "i" in cond.get("$options", "") else 0
                if not re.search(opv, str(val if val is not None else ""), flags):
                    return False
            elif op == "$options":
                continue
            elif op == "$elemMatch":
                arr = val if isinstance(val, list) else []
                if not any(_match_value(item, opv) for item in arr):
                    return False
            else:
                return False
        return True
    return val == cond


def _matches(doc, query) -> bool:
    for k, v in query.items():
        if k == "$and":
            if not all(_matches(doc, sub) for sub in v):
                return False
        elif k == "$or":
            if not any(_matches(doc, sub) for sub in v):
                return False
        else:
            if not _match_value(doc.get(k), v):
                return False
    return True


class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, field, direction=1):
        self._docs = sorted(self._docs, key=lambda d: (d.get(field) is None, d.get(field)),
                            reverse=(direction == -1))
        return self

    def skip(self, n):
        self._docs = self._docs[n:]
        return self

    def limit(self, n):
        self._docs = self._docs[:n] if n else self._docs
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

    async def update_many(self, query, update):
        for d in self.docs:
            if _matches(d, query):
                d.update(update.get("$set", {}))

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    async def delete_one(self, query):
        for i, d in enumerate(self.docs):
            if _matches(d, query):
                del self.docs[i]
                return

    async def delete_many(self, query):
        self.docs = [d for d in self.docs if not _matches(d, query)]


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

    get = post = put = patch = delete = _decorator


class _HTTPException(Exception):
    def __init__(self, status_code=None, detail=None):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


# ---------------------------------------------------------------------------
# Actors / fixtures
# ---------------------------------------------------------------------------

MANAGER_A = {"id": "mgr-A", "org_id": "org-A", "org_role": "manager", "name": "Mgr A"}
REC_A = {"id": "rec-A", "org_id": "org-A", "org_role": "recruiter", "name": "Rec A"}
REC_A2 = {"id": "rec-A2", "org_id": "org-A", "org_role": "recruiter", "name": "Rec A2"}
MANAGER_B = {"id": "mgr-B", "org_id": "org-B", "org_role": "manager", "name": "Mgr B"}


@pytest.fixture(scope="module")
def world():
    import os
    os.environ.setdefault("GROQ_API_KEY", "test-key-not-used")
    upload_dir = Path(tempfile.mkdtemp(prefix="hf-cycle5-"))

    _merge_stub("fastapi", HTTPException=_HTTPException, Depends=lambda dep=None: None,
                APIRouter=_APIRouter, UploadFile=object, File=lambda *a, **k: None,
                Form=lambda *a, **k: None, Query=lambda default=None, **k: default)
    _merge_stub("fastapi.responses", PlainTextResponse=object, Response=_FakeResponse)

    colls = {
        "jobs": FakeColl(),
        "candidates": FakeColl(),
        "users": FakeColl(),
        "job_assignments": FakeColl(),
        "job_jd_overrides": FakeColl(),
        "stage_transitions": FakeColl(),
        "activity_events": FakeColl(),
        "ai_usage_log": FakeColl(),
        "resume_db": FakeColl(),
        "organizations": FakeColl(),
    }
    _merge_stub("database", UPLOAD_DIR=upload_dir, **colls)
    _merge_stub("auth", get_current_user=lambda: None, hash_password=lambda p: p,
                verify_password=lambda p, h: True, create_token=lambda u: "tok")
    _merge_stub("groq", AsyncGroq=lambda **kwargs: None)

    for mdl in ("StageUpdate", "NoteUpdate", "BulkStageUpdate", "ResumeShareUpdate",
                "ResumeMoveToJob", "SubAdminPermissions", "MemberCreate",
                "BulkMemberCreate", "MemberStatusUpdate", "MemberRemove"):
        _merge_stub("models", **{mdl: object})

    import ai_service

    async def _fake_log_usage(*a, **k):
        return None

    ai_service.log_usage = _fake_log_usage

    # resume_pdf imports cleanly (reportlab is lazy inside build_resume_pdf); swap
    # the one function so the PDF endpoints need no reportlab, regardless of which
    # suite imported the real module first (merge-stubs can't replace it then).
    import resume_pdf
    resume_pdf.build_resume_pdf = lambda structured, base: b"%PDF-1.4 fake"

    import permissions
    import resume_store
    import routes_candidates
    import routes_resume_db
    import routes_orgs

    modules = (permissions, resume_store, routes_candidates, routes_resume_db, routes_orgs)
    for module in modules:
        for name, coll in colls.items():
            if hasattr(module, name):
                setattr(module, name, coll)
        if hasattr(module, "UPLOAD_DIR"):
            module.UPLOAD_DIR = upload_dir
    # Bind the PDF Response to our fake regardless of which suite stubbed
    # `fastapi.responses` first (merge-stubs never override an existing attr).
    routes_resume_db.Response = _FakeResponse
    routes_candidates.Response = _FakeResponse

    return types.SimpleNamespace(
        p=permissions, store=resume_store, cand_r=routes_candidates,
        rdb=routes_resume_db, orgs=routes_orgs, colls=colls, upload_dir=upload_dir,
        ai=ai_service, exc=sys.modules["fastapi"].HTTPException,
    )


class _FakeResponse:
    def __init__(self, content=None, media_type=None, headers=None):
        self.content = content
        self.media_type = media_type
        self.headers = headers or {}


class _FakeUpload:
    def __init__(self, filename, content: bytes):
        self.filename = filename
        self._content = content

    async def read(self):
        return self._content


def run(coro):
    return asyncio.run(coro)


def _ns(**kw):
    return types.SimpleNamespace(**kw)


def _reset(world):
    for coll in world.colls.values():
        coll.docs = []


JOB_A = {"id": "job-A", "org_id": "org-A", "title": "Engineer", "status": "active",
         "openings_needed": 1, "created_at": "2026-01-01T00:00:00+00:00"}


# ===========================================================================
# resume_store — identity, freshness, visibility, derived fields
# ===========================================================================

def test_uid_is_stable_and_email_normalised(world):
    a = world.store.candidate_uid("  Jane@Example.COM ", "f1")
    b = world.store.candidate_uid("jane@example.com", "f2")
    assert a == b  # case/whitespace normalised → same identity


def test_uid_missing_email_does_not_collide(world):
    a = world.store.candidate_uid("", "file-1")
    b = world.store.candidate_uid(None, "file-2")
    assert a != b and a.startswith("anon:")


def test_upsert_newest_wins_replaces_in_place(world):
    _reset(world)
    old = world.store.build_record(
        org_id="org-A", uploader_id="rec-A", parsed={"email": "j@x.com", "text": "old"},
        name="Jane Old", source="LinkedIn", pdf_path="old.pdf", pdf_original_name="old.pdf",
        now="2026-01-01T00:00:00+00:00", shared=True)
    run(world.store.upsert_fresh(old))
    new = world.store.build_record(
        org_id="org-A", uploader_id="rec-A2", parsed={"email": "J@x.com", "text": "new"},
        name="Jane New", source="Referral", pdf_path="new.pdf", pdf_original_name="new.pdf",
        now="2026-05-01T00:00:00+00:00", shared=False)
    run(world.store.upsert_fresh(new))

    rows = world.colls["resume_db"].docs
    assert len(rows) == 1                    # old record replaced, not duplicated
    assert rows[0]["id"] == old["id"]        # same id → references survive
    assert rows[0]["name"] == "Jane New"     # newest content won
    assert rows[0]["pdf_path"] == "new.pdf"
    assert rows[0]["shared"] is True         # original sharing choice preserved


def test_upsert_older_upload_does_not_overwrite(world):
    _reset(world)
    newer = world.store.build_record(
        org_id="org-A", uploader_id="rec-A", parsed={"email": "k@x.com", "text": "current"},
        name="Keep Me", source="LinkedIn", pdf_path="cur.pdf", pdf_original_name="cur.pdf",
        now="2026-05-01T00:00:00+00:00")
    run(world.store.upsert_fresh(newer))
    older = world.store.build_record(
        org_id="org-A", uploader_id="rec-A", parsed={"email": "k@x.com", "text": "stale"},
        name="Overwrite Me", source="Referral", pdf_path="stale.pdf", pdf_original_name="stale.pdf",
        now="2026-02-01T00:00:00+00:00")
    run(world.store.upsert_fresh(older))
    rows = world.colls["resume_db"].docs
    assert len(rows) == 1 and rows[0]["name"] == "Keep Me"  # stale upload ignored


def test_visibility_filter_manager_vs_recruiter(world):
    assert world.store.visibility_filter(MANAGER_A, True) == {"org_id": "org-A"}
    f = world.store.visibility_filter(REC_A, False)
    assert f["org_id"] == "org-A" and "$or" in f


def test_derive_experience_years_conservative(world):
    structured = {"experience": [
        {"dates": "2018 - 2022"},          # 4
        {"dates": "Jan 2015 – Dec 2017"},  # 2
        {"dates": "sometime"},             # unreadable → ignored
    ]}
    assert world.store.derive_experience_years(structured) == 6


def test_derive_experience_years_none_when_unreadable(world):
    assert world.store.derive_experience_years({"experience": [{"dates": "n/a"}]}) is None
    assert world.store.derive_experience_years({}) is None


def test_extract_skills_dedupes_case_insensitively(world):
    out = world.store.extract_skills({"skills": ["Python", "python", "Django", ""]})
    assert out == ["Python", "Django"]


# ===========================================================================
# Upload flow — creates BOTH a candidate and a Resume DB record (no double upload)
# ===========================================================================

def test_upload_creates_candidate_and_resume_db_record(world):
    _reset(world)
    world.colls["jobs"].docs = [dict(JOB_A)]
    files = [_FakeUpload("jane.txt", b"Jane Doe\nEmail: jane@example.com\nPython engineer\n")]
    out = run(world.cand_r.upload_resumes("job-A", files=files, source="LinkedIn", user=MANAGER_A))
    assert out["count"] == 1
    assert len(world.colls["candidates"].docs) == 1
    rec = world.colls["resume_db"].docs
    assert len(rec) == 1                                   # additionally landed in Resume DB
    assert rec[0]["email"] == "jane@example.com"
    assert rec[0]["source"] == "LinkedIn"
    # Same stored file is referenced by both — never duplicated.
    assert rec[0]["pdf_path"] == world.colls["candidates"].docs[0]["pdf_path"]
    assert rec[0]["shared"] is False                       # private by default


def test_upload_surfaces_extraction_warning(world):
    _reset(world)
    world.colls["jobs"].docs = [dict(JOB_A)]
    files = [_FakeUpload("blank.txt", b"   \n   \n")]      # text-bearing but empty
    out = run(world.cand_r.upload_resumes("job-A", files=files, source="LinkedIn", user=MANAGER_A))
    assert out["warnings"] and out["warnings"][0]["filename"] == "blank.txt"


def test_upload_duplicate_email_newest_wins_in_resume_db(world):
    _reset(world)
    world.colls["jobs"].docs = [dict(JOB_A)]
    run(world.cand_r.upload_resumes(
        "job-A", files=[_FakeUpload("v1.txt", b"Jane V1\njane@example.com\n")],
        source="LinkedIn", user=MANAGER_A))
    run(world.cand_r.upload_resumes(
        "job-A", files=[_FakeUpload("v2.txt", b"Jane V2 Updated\njane@example.com\n")],
        source="Referral", user=MANAGER_A))
    # Two candidate records (job history preserved) but ONE Resume DB record.
    assert len(world.colls["candidates"].docs) == 2
    assert len(world.colls["resume_db"].docs) == 1


# ===========================================================================
# Resume DB routes — listing/filter/search, visibility, sharing, move, delete
# ===========================================================================

def _seed_record(world, **over):
    base = {
        "org_id": "org-A", "uploader_id": "rec-A", "email": "a@x.com", "name": "Alpha",
        "phone": None, "resume_text": "python developer react", "skills": ["Python", "React"],
        "experience_years": 5, "source": "LinkedIn", "shared": False, "pdf_path": "a.pdf",
        "pdf_original_name": "a.pdf", "links": [], "linkedin": None, "github": None,
        "portfolio": None, "resume_structured": None,
        "uploaded_at": "2026-03-01T00:00:00+00:00", "updated_at": "2026-03-01T00:00:00+00:00",
    }
    base.update(over)
    base.setdefault("candidate_uid", world.store.candidate_uid(base["email"], base.get("id", "x")))
    base.setdefault("id", "rec-" + base["email"])
    world.colls["resume_db"].docs.append(base)
    return base


def test_list_manager_sees_whole_org(world):
    _reset(world)
    _seed_record(world, id="r1", email="a@x.com", uploader_id="rec-A")
    _seed_record(world, id="r2", email="b@x.com", uploader_id="rec-A2", shared=False)
    out = run(world.rdb.list_resumes(MANAGER_A))
    assert {r["id"] for r in out["results"]} == {"r1", "r2"}
    assert out["total"] == 2


def test_list_recruiter_sees_own_plus_shared_only(world):
    _reset(world)
    _seed_record(world, id="mine", uploader_id="rec-A", email="a@x.com")
    _seed_record(world, id="shared", uploader_id="rec-A2", email="b@x.com", shared=True)
    _seed_record(world, id="private-other", uploader_id="rec-A2", email="c@x.com", shared=False)
    out = run(world.rdb.list_resumes(REC_A))
    assert {r["id"] for r in out["results"]} == {"mine", "shared"}  # not private-other


def test_list_skill_filter_requires_all_terms(world):
    _reset(world)
    _seed_record(world, id="r1", email="a@x.com", skills=["Python", "React"])
    _seed_record(world, id="r2", email="b@x.com", skills=["Python"])
    out = run(world.rdb.list_resumes(MANAGER_A, skills="python,react"))
    assert {r["id"] for r in out["results"]} == {"r1"}  # r2 lacks React


def test_list_search_matches_name_email_text(world):
    _reset(world)
    _seed_record(world, id="r1", email="a@x.com", name="Alice", resume_text="golang")
    _seed_record(world, id="r2", email="bob@x.com", name="Bob", resume_text="rust")
    assert {r["id"] for r in run(world.rdb.list_resumes(MANAGER_A, q="alice"))["results"]} == {"r1"}
    assert {r["id"] for r in run(world.rdb.list_resumes(MANAGER_A, q="bob@x"))["results"]} == {"r2"}
    assert {r["id"] for r in run(world.rdb.list_resumes(MANAGER_A, q="rust"))["results"]} == {"r2"}


def test_list_min_experience_and_source_filters(world):
    _reset(world)
    _seed_record(world, id="r1", email="a@x.com", experience_years=8, source="LinkedIn")
    _seed_record(world, id="r2", email="b@x.com", experience_years=2, source="Referral")
    assert {r["id"] for r in run(world.rdb.list_resumes(MANAGER_A, min_experience=5))["results"]} == {"r1"}
    assert {r["id"] for r in run(world.rdb.list_resumes(MANAGER_A, source="Referral"))["results"]} == {"r2"}


def test_get_private_record_of_another_is_404(world):
    _reset(world)
    _seed_record(world, id="priv", uploader_id="rec-A2", email="c@x.com", shared=False)
    with pytest.raises(world.exc) as e:
        run(world.rdb.get_resume("priv", REC_A))
    assert e.value.status_code == 404


def test_get_record_cross_org_is_404(world):
    _reset(world)
    _seed_record(world, id="r1", org_id="org-A", email="a@x.com")
    with pytest.raises(world.exc) as e:
        run(world.rdb.get_resume("r1", MANAGER_B))
    assert e.value.status_code == 404


def test_share_toggle_persists_and_is_reversible(world):
    _reset(world)
    _seed_record(world, id="r1", uploader_id="rec-A", email="a@x.com", shared=False)
    run(world.rdb.set_sharing("r1", _ns(shared=True), REC_A))
    assert world.colls["resume_db"].docs[0]["shared"] is True
    run(world.rdb.set_sharing("r1", _ns(shared=False), REC_A))
    assert world.colls["resume_db"].docs[0]["shared"] is False


def test_share_toggle_denied_for_non_owner_recruiter(world):
    _reset(world)
    _seed_record(world, id="shared", uploader_id="rec-A2", email="b@x.com", shared=True)
    # REC_A can SEE it (shared) but may not change its sharing (not owner/manager).
    with pytest.raises(world.exc) as e:
        run(world.rdb.set_sharing("shared", _ns(shared=False), REC_A))
    assert e.value.status_code == 403


def test_manager_can_toggle_any_record_sharing(world):
    _reset(world)
    _seed_record(world, id="r1", uploader_id="rec-A", email="a@x.com", shared=False)
    run(world.rdb.set_sharing("r1", _ns(shared=True), MANAGER_A))
    assert world.colls["resume_db"].docs[0]["shared"] is True


def test_move_to_job_reuses_file_and_sets_internal_source(world):
    _reset(world)
    world.colls["jobs"].docs = [dict(JOB_A)]
    rec = _seed_record(world, id="r1", uploader_id="rec-A", email="a@x.com", pdf_path="shared-file.pdf")
    out = run(world.rdb.move_to_job("r1", _ns(job_id="job-A"), MANAGER_A))
    cand = out["candidate"]
    assert cand["source"] == "Internal Database"
    assert cand["pdf_path"] == "shared-file.pdf"     # reuses the very same file
    assert cand["resume_db_id"] == "r1"              # remembers its origin
    assert len(world.colls["candidates"].docs) == 1


def test_move_to_job_blocks_duplicate_on_same_job(world):
    _reset(world)
    world.colls["jobs"].docs = [dict(JOB_A)]
    _seed_record(world, id="r1", uploader_id="rec-A", email="dup@x.com")
    run(world.rdb.move_to_job("r1", _ns(job_id="job-A"), MANAGER_A))
    with pytest.raises(world.exc) as e:
        run(world.rdb.move_to_job("r1", _ns(job_id="job-A"), MANAGER_A))
    assert e.value.status_code == 409


def test_move_to_job_cross_org_is_404(world):
    _reset(world)
    world.colls["jobs"].docs = [dict(JOB_A)]
    _seed_record(world, id="r1", org_id="org-B", uploader_id="mgr-B", email="a@x.com")
    # Manager B owns the record but job-A is org-A's → no access to the job.
    with pytest.raises(world.exc) as e:
        run(world.rdb.move_to_job("r1", _ns(job_id="job-A"), MANAGER_B))
    assert e.value.status_code == 404


def test_delete_keeps_file_when_still_referenced(world):
    _reset(world)
    (world.upload_dir / "shared-file.pdf").write_bytes(b"x")
    _seed_record(world, id="r1", uploader_id="rec-A", email="a@x.com", pdf_path="shared-file.pdf")
    # A candidate still references the same stored file.
    world.colls["candidates"].docs = [{"id": "c1", "org_id": "org-A", "pdf_path": "shared-file.pdf"}]
    run(world.rdb.delete_resume("r1", MANAGER_A))
    assert (world.upload_dir / "shared-file.pdf").exists()   # not orphaned/removed
    assert world.colls["resume_db"].docs == []              # record gone


def test_delete_removes_unreferenced_file(world):
    _reset(world)
    (world.upload_dir / "lonely.pdf").write_bytes(b"x")
    _seed_record(world, id="r1", uploader_id="rec-A", email="a@x.com", pdf_path="lonely.pdf")
    run(world.rdb.delete_resume("r1", MANAGER_A))
    assert not (world.upload_dir / "lonely.pdf").exists()


def test_delete_denied_for_non_owner_recruiter(world):
    _reset(world)
    _seed_record(world, id="shared", uploader_id="rec-A2", email="b@x.com", shared=True)
    with pytest.raises(world.exc) as e:
        run(world.rdb.delete_resume("shared", REC_A))
    assert e.value.status_code == 403


def test_structure_generates_and_backfills_skills(world):
    _reset(world)
    _seed_record(world, id="r1", uploader_id="rec-A", email="a@x.com",
                 resume_text="Jane, python & django, 2018-2022", skills=[], experience_years=None)

    async def _fake_call_ai(*a, **k):
        return ('{"skills":["Python","Django"],'
                '"experience":[{"title":"Engineer","organization":"X","dates":"2018 - 2022","highlights":[]}]}')

    world.ai.call_ai = _fake_call_ai
    out = run(world.rdb.structure_resume("r1", MANAGER_A))
    assert out["cached"] is False
    stored = world.colls["resume_db"].docs[0]
    assert stored["skills"] == ["Python", "Django"]         # backfilled for filtering
    assert stored["experience_years"] == 4
    # Second call returns the cached structure without re-generating.
    assert run(world.rdb.structure_resume("r1", MANAGER_A))["cached"] is True


def test_download_pdf_reuses_resume_pdf(world):
    _reset(world)
    _seed_record(world, id="r1", uploader_id="rec-A", email="a@x.com")
    resp = run(world.rdb.download_resume_pdf("r1", MANAGER_A))
    assert resp.content == b"%PDF-1.4 fake"
    assert resp.media_type == "application/pdf"


# ===========================================================================
# Sub-Admins — capabilities, promotion, enforcement, no escalation
# ===========================================================================

def _subadmin(caps):
    return {"id": "sub-A", "org_id": "org-A", "org_role": "recruiter", "name": "Sub A",
            "admin_permissions": list(caps)}


def test_has_capability_manager_has_all(world):
    for cap in world.p.ADMIN_CAPABILITIES:
        assert world.p.has_capability(MANAGER_A, cap) is True


def test_has_capability_recruiter_only_granted(world):
    sub = _subadmin(["post_jobs"])
    assert world.p.has_capability(sub, "post_jobs") is True
    assert world.p.has_capability(sub, "manage_team") is False
    assert world.p.has_capability(REC_A, "post_jobs") is False


def test_is_subadmin_detection(world):
    assert world.p.is_subadmin(_subadmin(["post_jobs"])) is True
    assert world.p.is_subadmin(REC_A) is False
    assert world.p.is_subadmin(MANAGER_A) is False  # a manager isn't a "sub"-admin


def test_require_capability_allows_and_denies(world):
    dep = world.p.require_capability("manage_team")
    assert run(dep(MANAGER_A)) is MANAGER_A                 # manager passes
    sub = _subadmin(["manage_team"])
    assert run(dep(sub)) is sub                             # granted sub-admin passes
    with pytest.raises(world.exc) as e:
        run(dep(REC_A))                                    # ungranted recruiter denied
    assert e.value.status_code == 403


def test_sanitize_capabilities_drops_unknown(world):
    assert world.p.sanitize_capabilities(["post_jobs", "hack_everything", "manage_team"]) == \
        ["post_jobs", "manage_team"]
    assert world.p.sanitize_capabilities("not a list") == []


def test_manager_promotes_and_revokes_subadmin(world):
    _reset(world)
    world.colls["users"].docs = [{**REC_A, "status": "active"}]
    out = run(world.orgs.set_member_permissions("rec-A", _ns(admin_permissions=["post_jobs", "view_reports"]), MANAGER_A))
    assert out["is_subadmin"] is True
    assert set(out["admin_permissions"]) == {"post_jobs", "view_reports"}
    assert world.colls["users"].docs[0]["admin_permissions"] == ["post_jobs", "view_reports"]
    # Revoke by sending an empty list → back to an ordinary recruiter.
    out2 = run(world.orgs.set_member_permissions("rec-A", _ns(admin_permissions=[]), MANAGER_A))
    assert out2["is_subadmin"] is False and out2["admin_permissions"] == []


def test_promotion_rejects_self_and_manager_target(world):
    _reset(world)
    world.colls["users"].docs = [dict(MANAGER_A)]
    with pytest.raises(world.exc) as e:
        run(world.orgs.set_member_permissions("mgr-A", _ns(admin_permissions=["post_jobs"]), MANAGER_A))
    assert e.value.status_code == 400  # can't set own permissions


def test_promotion_target_must_be_recruiter(world):
    _reset(world)
    world.colls["users"].docs = [dict(MANAGER_A), {"id": "mgr-A2", "org_id": "org-A", "org_role": "manager",
                                                    "name": "Mgr A2", "status": "active"}]
    with pytest.raises(world.exc) as e:
        run(world.orgs.set_member_permissions("mgr-A2", _ns(admin_permissions=["post_jobs"]), MANAGER_A))
    assert e.value.status_code == 400  # admins already have every capability


def test_subadmin_cannot_promote_others(world):
    # The promotion route is manager-only (require_manager); a sub-admin is refused
    # by that dependency regardless of holding manage_team.
    with pytest.raises(world.exc) as e:
        run(world.p.require_manager(_subadmin(["manage_team"])))
    assert e.value.status_code == 403


def test_subadmin_cannot_suspend_a_manager(world):
    _reset(world)
    world.colls["users"].docs = [dict(MANAGER_A), {"id": "mgr-A2", "org_id": "org-A",
                                                    "org_role": "manager", "status": "active"}]
    sub = _subadmin(["manage_team"])
    with pytest.raises(world.exc) as e:
        run(world.orgs.update_member("mgr-A2", _ns(status="disabled"), sub))
    assert e.value.status_code == 403  # a sub-admin may not touch a manager


def test_subadmin_cannot_remove_another_subadmin(world):
    _reset(world)
    other_sub = {"id": "sub-B", "org_id": "org-A", "org_role": "recruiter",
                 "status": "active", "admin_permissions": ["post_jobs"]}
    world.colls["users"].docs = [other_sub]
    sub = _subadmin(["manage_team"])
    with pytest.raises(world.exc) as e:
        run(world.orgs.remove_member("sub-B", _ns(reassign_to=None), sub))
    assert e.value.status_code == 403


def test_subadmin_can_manage_ordinary_recruiter(world):
    _reset(world)
    world.colls["users"].docs = [{"id": "rec-A", "org_id": "org-A", "org_role": "recruiter",
                                  "status": "active", "name": "Rec A"}]
    sub = _subadmin(["manage_team"])
    out = run(world.orgs.update_member("rec-A", _ns(status="disabled"), sub))
    assert out["status"] == "disabled"  # a normal recruiter can be managed


def test_manager_unaffected_can_manage_recruiter(world):
    _reset(world)
    world.colls["users"].docs = [{"id": "rec-A", "org_id": "org-A", "org_role": "recruiter",
                                  "status": "active", "name": "Rec A"}]
    out = run(world.orgs.update_member("rec-A", _ns(status="disabled"), MANAGER_A))
    assert out["status"] == "disabled"


def test_member_view_exposes_capabilities(world):
    sub = {"id": "sub-A", "org_role": "recruiter", "admin_permissions": ["post_jobs", "bogus"]}
    view = world.orgs._member_view(sub)
    assert view["admin_permissions"] == ["post_jobs"]  # sanitised
    assert view["is_subadmin"] is True
