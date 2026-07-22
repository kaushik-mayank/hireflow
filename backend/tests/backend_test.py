"""
HireFlow backend regression tests.
Covers: auth (signup/login/me/invalid), jobs CRUD, candidates upload+stage+notes,
dashboard, AI endpoints (rank, enhance-jd, questions, email, summary, compare,
pipeline-health).
"""
import io
import os
import time
import uuid
import pytest
import requests
from reportlab.pdfgen import canvas

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback to frontend/.env
    try:
        with open("/app/frontend/.env") as fh:
            for ln in fh:
                if ln.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = ln.split("=", 1)[1].strip().strip('"').rstrip("/")
                    break
    except FileNotFoundError:
        pass

API = f"{BASE_URL}/api"

# Credentials loaded from environment (fallback to seeded demo accounts for local runs).
HR_EMAIL = os.getenv("HIREFLOW_HR_EMAIL", "sarah@hireflow.com")
HR_PASSWORD = os.getenv("HIREFLOW_HR_PASSWORD", "Sarah@1234")
ADMIN_EMAIL = os.getenv("HIREFLOW_ADMIN_EMAIL", "admin@hireflow.com")
ADMIN_PASSWORD = os.getenv("HIREFLOW_ADMIN_PASSWORD", "Admin@1234")


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def hr_token():
    r = requests.post(f"{API}/auth/login", json={"email": HR_EMAIL, "password": HR_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"HR login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def hr_headers(hr_token):
    return {"Authorization": f"Bearer {hr_token}"}


def _make_pdf(name="Test Candidate", email="test.cand@example.com", phone="+1 415 555 9999",
              skills="React, TypeScript, Next.js, Redux"):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for line in [
        name, f"{email} | {phone}", "",
        "SUMMARY", "Experienced senior frontend engineer with 6 years building scalable products.",
        "", "SKILLS", skills,
        "", "EXPERIENCE", "Senior engineer at TechCorp leading teams.",
        "", "EDUCATION", "B.S. Computer Science",
    ]:
        c.drawString(60, y, line)
        y -= 20
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


# ---------- Auth ----------
class TestAuth:
    def test_hr_login_success(self):
        r = requests.post(f"{API}/auth/login", json={"email": HR_EMAIL, "password": HR_PASSWORD}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "token" in data and isinstance(data["token"], str) and data["token"]
        assert data["user"]["email"] == HR_EMAIL
        assert data["user"]["role"] == "hr"

    def test_admin_login_success(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "admin"

    def test_login_invalid_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": HR_EMAIL, "password": "wrong"}, timeout=15)
        assert r.status_code == 401

    def test_login_unknown_email(self):
        r = requests.post(f"{API}/auth/login", json={"email": "nobody@nowhere.com", "password": "Whatever@1234"}, timeout=15)
        assert r.status_code == 401

    def test_me_returns_user(self, hr_headers):
        r = requests.get(f"{API}/auth/me", headers=hr_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["user"]["email"] == HR_EMAIL

    def test_me_no_token_unauth(self):
        r = requests.get(f"{API}/auth/me", timeout=15)
        assert r.status_code in (401, 403)

    def test_signup_creates_user(self):
        unique = f"test_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/auth/signup", json={
            "name": "TEST User", "email": unique, "password": "Pass@1234", "company": "TEST Co",
        }, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["email"] == unique
        # duplicate signup blocked
        r2 = requests.post(f"{API}/auth/signup", json={
            "name": "TEST User", "email": unique, "password": "Pass@1234",
        }, timeout=15)
        assert r2.status_code == 400


# ---------- Jobs ----------
class TestJobs:
    def test_list_jobs(self, hr_headers):
        r = requests.get(f"{API}/jobs", headers=hr_headers, timeout=15)
        assert r.status_code == 200
        jobs = r.json()
        assert isinstance(jobs, list)
        assert len(jobs) >= 2  # seeded
        for j in jobs:
            assert "id" in j and "title" in j and "candidate_count" in j

    def test_create_get_update_job(self, hr_headers):
        payload = {
            "title": "TEST_Backend Engineer",
            "department": "Engineering",
            "openings_needed": 3,
            "jd_text": "Test JD for backend engineer with Python, FastAPI, MongoDB.",
        }
        r = requests.post(f"{API}/jobs", json=payload, headers=hr_headers, timeout=15)
        assert r.status_code == 200, r.text
        job = r.json()
        assert job["title"] == payload["title"]
        assert job["openings_needed"] == 3
        assert "id" in job

        # GET detail
        g = requests.get(f"{API}/jobs/{job['id']}", headers=hr_headers, timeout=15)
        assert g.status_code == 200
        assert g.json()["title"] == payload["title"]

        # UPDATE pause
        u = requests.put(f"{API}/jobs/{job['id']}", json={"status": "paused"}, headers=hr_headers, timeout=15)
        assert u.status_code == 200
        assert u.json()["status"] == "paused"

        # Activity feed
        a = requests.get(f"{API}/jobs/{job['id']}/activity", headers=hr_headers, timeout=15)
        assert a.status_code == 200
        assert isinstance(a.json(), list)

        # cleanup
        d = requests.delete(f"{API}/jobs/{job['id']}", headers=hr_headers, timeout=15)
        assert d.status_code == 200

    def test_create_job_validation(self, hr_headers):
        r = requests.post(f"{API}/jobs", json={"title": "", "openings_needed": 1}, headers=hr_headers, timeout=15)
        assert r.status_code == 400
        r = requests.post(f"{API}/jobs", json={"title": "Valid", "openings_needed": 0}, headers=hr_headers, timeout=15)
        assert r.status_code == 400

    def test_jobs_unauth(self):
        r = requests.get(f"{API}/jobs", timeout=15)
        assert r.status_code in (401, 403)


# ---------- Candidates ----------
class TestCandidates:
    @pytest.fixture(scope="class")
    def seeded_job_id(self, hr_headers):
        r = requests.get(f"{API}/jobs", headers=hr_headers, timeout=15)
        assert r.status_code == 200
        jobs = r.json()
        # Pick the frontend engineer job
        for j in jobs:
            if "Frontend" in j["title"]:
                return j["id"]
        return jobs[0]["id"]

    def test_list_candidates(self, hr_headers, seeded_job_id):
        r = requests.get(f"{API}/candidates/job/{seeded_job_id}", headers=hr_headers, timeout=15)
        assert r.status_code == 200
        cands = r.json()
        assert isinstance(cands, list) and len(cands) >= 1
        sample = cands[0]
        assert "id" in sample and "name" in sample and "stage" in sample

    def test_upload_pdf_and_lifecycle(self, hr_headers, seeded_job_id):
        pdf_bytes = _make_pdf(name="TEST Upload Candidate", email="test_upload@example.com")
        files = {"files": ("test_upload.pdf", pdf_bytes, "application/pdf")}
        r = requests.post(
            f"{API}/candidates/upload/{seeded_job_id}",
            files=files,
            headers={"Authorization": hr_headers["Authorization"]},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["count"] == 1
        cand = data["created"][0]
        assert cand["stage"] == "Applied"
        # email should be parsed
        assert cand["email"] == "test_upload@example.com"
        cid = cand["id"]

        # GET candidate
        g = requests.get(f"{API}/candidates/{cid}", headers=hr_headers, timeout=15)
        assert g.status_code == 200
        assert g.json()["id"] == cid

        # Update stage
        s = requests.put(f"{API}/candidates/{cid}/stage", json={"stage": "Shortlisted", "note": "looks good"},
                         headers=hr_headers, timeout=15)
        assert s.status_code == 200
        assert s.json()["stage"] == "Shortlisted"

        # Verify persistence
        g2 = requests.get(f"{API}/candidates/{cid}", headers=hr_headers, timeout=15)
        assert g2.json()["stage"] == "Shortlisted"

        # Invalid stage
        bad = requests.put(f"{API}/candidates/{cid}/stage", json={"stage": "Bogus"},
                           headers=hr_headers, timeout=15)
        assert bad.status_code == 400

        # Add note
        n = requests.post(f"{API}/candidates/{cid}/note", json={"note": "TEST note"},
                          headers=hr_headers, timeout=15)
        assert n.status_code == 200
        assert n.json()["text"] == "TEST note"

        # Bulk stage update
        b = requests.put(f"{API}/candidates/bulk-stage",
                         json={"candidate_ids": [cid], "stage": "Contact Pending"},
                         headers=hr_headers, timeout=15)
        assert b.status_code == 200
        assert b.json()["updated"] == 1

        # Delete
        d = requests.delete(f"{API}/candidates/{cid}", headers=hr_headers, timeout=15)
        assert d.status_code == 200

        # Confirm 404 after delete
        g3 = requests.get(f"{API}/candidates/{cid}", headers=hr_headers, timeout=15)
        assert g3.status_code == 404

    def test_upload_rejects_non_pdf(self, hr_headers, seeded_job_id):
        files = {"files": ("bad.txt", b"hello world", "text/plain")}
        r = requests.post(f"{API}/candidates/upload/{seeded_job_id}", files=files,
                          headers={"Authorization": hr_headers["Authorization"]}, timeout=15)
        assert r.status_code == 400


# ---------- Dashboard ----------
class TestDashboard:
    def test_dashboard_payload(self, hr_headers):
        r = requests.get(f"{API}/dashboard", headers=hr_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("stats", "jobs_summary", "action_items", "upcoming_interviews"):
            assert k in d
        for sk in ("active_jobs", "total_hired", "in_pipeline", "contact_pending", "avg_score"):
            assert sk in d["stats"]
        assert isinstance(d["jobs_summary"], list)


# ---------- AI Endpoints (real Claude calls; allow slower) ----------
class TestAI:
    @pytest.fixture(scope="class")
    def seeded_job(self, hr_headers):
        r = requests.get(f"{API}/jobs", headers=hr_headers, timeout=15)
        for j in r.json():
            if "Frontend" in j["title"]:
                return j
        return r.json()[0]

    @pytest.fixture(scope="class")
    def two_candidates(self, hr_headers, seeded_job):
        r = requests.get(f"{API}/candidates/job/{seeded_job['id']}", headers=hr_headers, timeout=15)
        assert r.status_code == 200 and len(r.json()) >= 2
        return r.json()[:2]

    def test_enhance_jd(self, hr_headers):
        r = requests.post(f"{API}/ai/enhance-jd",
                          json={"jd_text": "Looking for a senior backend engineer.", "title": "Senior Backend"},
                          headers=hr_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "enhanced" in data and isinstance(data["enhanced"], str) and len(data["enhanced"]) > 20

    def test_enhance_jd_validation(self, hr_headers):
        r = requests.post(f"{API}/ai/enhance-jd", json={"jd_text": "  ", "title": "X"},
                          headers=hr_headers, timeout=15)
        assert r.status_code == 400

    def test_rank_candidates(self, hr_headers, seeded_job):
        r = requests.post(f"{API}/ai/rank",
                          json={"job_id": seeded_job["id"], "reanalyze": True},
                          headers=hr_headers, timeout=120)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "updated" in data and isinstance(data["updated"], list)
        if data["updated"]:
            c = data["updated"][0]
            assert isinstance(c.get("ai_score"), int)

    def test_questions(self, hr_headers, two_candidates):
        cid = two_candidates[0]["id"]
        r = requests.post(f"{API}/ai/questions", json={"candidate_id": cid},
                          headers=hr_headers, timeout=60)
        assert r.status_code == 200, r.text
        qs = r.json().get("questions", [])
        assert isinstance(qs, list) and len(qs) > 0

    def test_email(self, hr_headers, two_candidates):
        cid = two_candidates[0]["id"]
        r = requests.post(f"{API}/ai/email",
                          json={"candidate_id": cid, "email_type": "interview invite"},
                          headers=hr_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "subject" in data and "body" in data
        assert isinstance(data["body"], str) and len(data["body"]) > 10

    def test_summary(self, hr_headers, two_candidates):
        cid = two_candidates[0]["id"]
        r = requests.post(f"{API}/ai/summary", json={"candidate_id": cid},
                          headers=hr_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        # Must have at least one of the expected keys
        assert any(k in data for k in ("overall_fit", "strengths", "recommendation"))

    def test_compare(self, hr_headers, two_candidates):
        a, b = two_candidates[0]["id"], two_candidates[1]["id"]
        r = requests.post(f"{API}/ai/compare",
                          json={"candidate_id_a": a, "candidate_id_b": b},
                          headers=hr_headers, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "candidate_a_name" in d and "candidate_b_name" in d

    def test_pipeline_health(self, hr_headers):
        r = requests.post(f"{API}/ai/pipeline-health", headers=hr_headers, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "report" in d and "stats" in d
        assert "total_candidates" in d["stats"]
