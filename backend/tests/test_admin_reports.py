"""
HireFlow Admin Panel + Reports backend tests (Phase 2).
Covers:
  - /api/admin/* guard (HR=403, admin=200)
  - GET /api/admin/dashboard, /users, /resumes, /analytics, /ai-usage
  - PUT /api/admin/users/{id}/status (deactivate, reactivate, self-deactivate block, login while deactivated)
  - PUT /api/admin/users/{id}/role (hr<->admin)
  - GET /api/reports (HR-scoped)
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as fh:
        for ln in fh:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().strip('"').rstrip("/")
                break
API = f"{BASE_URL}/api"

HR_EMAIL = os.getenv("HIREFLOW_HR_EMAIL", "sarah@hireflow.com")
HR_PASSWORD = os.getenv("HIREFLOW_HR_PASSWORD", "Sarah@1234")
ADMIN_EMAIL = os.getenv("HIREFLOW_ADMIN_EMAIL", "admin@hireflow.com")
ADMIN_PASSWORD = os.getenv("HIREFLOW_ADMIN_PASSWORD", "Admin@1234")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    return r


@pytest.fixture(scope="module")
def hr_token():
    r = _login(HR_EMAIL, HR_PASSWORD)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    r = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def hr_headers(hr_token):
    return {"Authorization": f"Bearer {hr_token}"}


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def admin_user_id(admin_headers):
    r = requests.get(f"{API}/auth/me", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    return r.json()["user"]["id"]


@pytest.fixture(scope="module")
def hr_user_id(hr_headers):
    r = requests.get(f"{API}/auth/me", headers=hr_headers, timeout=15)
    assert r.status_code == 200
    return r.json()["user"]["id"]


@pytest.fixture(scope="module")
def throwaway_user():
    """Create a throwaway HR user for destructive status/role tests."""
    email = f"test_throwaway_{uuid.uuid4().hex[:8]}@example.com"
    pw = "Pass@1234"
    r = requests.post(f"{API}/auth/signup", json={
        "name": "TEST Throwaway", "email": email, "password": pw, "company": "TEST Co",
    }, timeout=15)
    assert r.status_code == 200, r.text
    return {"id": r.json()["user"]["id"], "email": email, "password": pw}


# ---------- Admin auth guard ----------
class TestAdminGuard:
    @pytest.mark.parametrize("path", [
        "/admin/dashboard", "/admin/users", "/admin/resumes",
        "/admin/analytics", "/admin/ai-usage",
    ])
    def test_hr_forbidden(self, hr_headers, path):
        r = requests.get(f"{API}{path}", headers=hr_headers, timeout=15)
        assert r.status_code == 403, f"{path} expected 403 got {r.status_code}"

    @pytest.mark.parametrize("path", [
        "/admin/dashboard", "/admin/users", "/admin/resumes",
        "/admin/analytics", "/admin/ai-usage",
    ])
    def test_admin_ok(self, admin_headers, path):
        r = requests.get(f"{API}{path}", headers=admin_headers, timeout=20)
        assert r.status_code == 200, f"{path} expected 200 got {r.status_code} {r.text}"

    def test_unauth_blocked(self):
        r = requests.get(f"{API}/admin/dashboard", timeout=15)
        assert r.status_code in (401, 403)


# ---------- Admin dashboard ----------
class TestAdminDashboard:
    def test_dashboard_shape(self, admin_headers):
        r = requests.get(f"{API}/admin/dashboard", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ("stats", "users", "recent_logins"):
            assert k in d
        for sk in ("total_users", "active_hr", "total_jobs", "total_resumes", "total_ai_calls"):
            assert sk in d["stats"], f"missing stats.{sk}"
            assert isinstance(d["stats"][sk], int)
        assert isinstance(d["users"], list) and len(d["users"]) >= 1
        u0 = d["users"][0]
        for k in ("jobs_count", "resumes_count", "ai_calls", "email", "role"):
            assert k in u0, f"user missing {k}"
        # recent logins
        assert isinstance(d["recent_logins"], list)
        if d["recent_logins"]:
            lg = d["recent_logins"][0]
            for k in ("id", "name", "email", "created_at"):
                assert k in lg


# ---------- Admin users ----------
class TestAdminUsers:
    def test_users_list_enriched(self, admin_headers):
        r = requests.get(f"{API}/admin/users", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        users_list = r.json()
        assert isinstance(users_list, list) and len(users_list) >= 2
        for u in users_list:
            assert "id" in u and "email" in u and "role" in u
            assert "jobs_count" in u and "resumes_count" in u and "ai_calls" in u
            assert "password_hash" not in u

    def test_status_toggle_lifecycle(self, admin_headers, throwaway_user):
        uid = throwaway_user["id"]
        # Deactivate
        r = requests.put(f"{API}/admin/users/{uid}/status",
                         json={"is_active": False}, headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["is_active"] is False

        # Verify deactivated user cannot login
        r2 = _login(throwaway_user["email"], throwaway_user["password"])
        # login route returns 401 OR 403 if user inactive
        assert r2.status_code in (401, 403), f"deactivated login allowed: {r2.status_code} {r2.text}"

        # Reactivate
        r3 = requests.put(f"{API}/admin/users/{uid}/status",
                          json={"is_active": True}, headers=admin_headers, timeout=15)
        assert r3.status_code == 200
        assert r3.json()["is_active"] is True

        # Login should succeed now
        r4 = _login(throwaway_user["email"], throwaway_user["password"])
        assert r4.status_code == 200

    def test_admin_cannot_deactivate_self(self, admin_headers, admin_user_id):
        r = requests.put(f"{API}/admin/users/{admin_user_id}/status",
                         json={"is_active": False}, headers=admin_headers, timeout=15)
        assert r.status_code == 400, r.text

    def test_role_toggle_lifecycle(self, admin_headers, throwaway_user):
        uid = throwaway_user["id"]
        # hr -> admin
        r = requests.put(f"{API}/admin/users/{uid}/role",
                         json={"role": "admin"}, headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["role"] == "admin"
        # admin -> hr (reset)
        r2 = requests.put(f"{API}/admin/users/{uid}/role",
                          json={"role": "hr"}, headers=admin_headers, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["role"] == "hr"

    def test_role_invalid(self, admin_headers, throwaway_user):
        r = requests.put(f"{API}/admin/users/{throwaway_user['id']}/role",
                         json={"role": "superuser"}, headers=admin_headers, timeout=15)
        assert r.status_code == 400


# ---------- Admin resumes ----------
class TestAdminResumes:
    def test_resumes_pagination(self, admin_headers):
        r = requests.get(f"{API}/admin/resumes?page=1&page_size=50", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ("total", "page", "page_size", "items"):
            assert k in d
        assert d["page"] == 1 and d["page_size"] == 50
        assert isinstance(d["items"], list)
        if d["items"]:
            it = d["items"][0]
            for k in ("id", "candidate_name", "job_title", "hr_user", "stage", "file_name"):
                assert k in it

    def test_resumes_page2(self, admin_headers):
        r = requests.get(f"{API}/admin/resumes?page=2&page_size=2", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["page"] == 2


# ---------- Admin analytics ----------
class TestAdminAnalytics:
    def test_analytics_payload(self, admin_headers):
        r = requests.get(f"{API}/admin/analytics", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ("signups", "jobs_weekly", "resumes", "ai_usage", "metrics"):
            assert k in d
        assert isinstance(d["signups"], list) and len(d["signups"]) == 30
        assert isinstance(d["resumes"], list) and len(d["resumes"]) == 30
        assert isinstance(d["ai_usage"], list) and len(d["ai_usage"]) == 30
        assert isinstance(d["jobs_weekly"], list) and len(d["jobs_weekly"]) == 12
        for sk in ("most_active_user", "most_popular_title", "avg_resumes_per_job", "avg_ai_score"):
            assert sk in d["metrics"]


# ---------- Admin AI usage ----------
class TestAdminAIUsage:
    def test_ai_usage_payload(self, admin_headers):
        r = requests.get(f"{API}/admin/ai-usage?page=1&page_size=50", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ("total", "items", "summary"):
            assert k in d
        for sk in ("calls_this_month", "total_calls", "most_used_feature", "most_active_user"):
            assert sk in d["summary"]
        if d["items"]:
            it = d["items"][0]
            for k in ("id", "created_at", "user", "action"):
                assert k in it


# ---------- Reports (HR-scoped) ----------
class TestReports:
    def test_reports_hr_payload(self, hr_headers):
        r = requests.get(f"{API}/reports", headers=hr_headers, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("time_to_hire", "stage_funnel", "skill_gap", "quota_tracker"):
            assert k in d
        # Stage funnel must have 10 stages
        assert isinstance(d["stage_funnel"], list) and len(d["stage_funnel"]) == 10
        expected_stages = {"Applied", "AI Ranked", "Shortlisted", "Contact Pending", "Contacted",
                           "Interview Scheduled", "Interview Done", "Selected", "Rejected", "On Hold"}
        got_stages = {row["stage"] for row in d["stage_funnel"]}
        assert got_stages == expected_stages
        # quota tracker should have one row per job
        assert isinstance(d["quota_tracker"], list)
        if d["quota_tracker"]:
            row = d["quota_tracker"][0]
            for k in ("job", "needed", "hired", "in_pipeline", "est_completion", "complete"):
                assert k in row
        assert isinstance(d["skill_gap"], list)
        assert isinstance(d["time_to_hire"], list)

    def test_reports_requires_auth(self):
        r = requests.get(f"{API}/reports", timeout=15)
        assert r.status_code in (401, 403)

    def test_reports_admin_works_but_empty(self, admin_headers):
        # admin has no jobs, so reports is empty arrays but still 200
        r = requests.get(f"{API}/reports", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        # admin has no jobs => quota_tracker empty, time_to_hire empty
        assert d["quota_tracker"] == []
        assert d["time_to_hire"] == []
