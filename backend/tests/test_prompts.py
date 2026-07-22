"""Guards for the AI prompt templates.

Two things must stay true after any prompt edit:

1. **Response schemas do not drift.** The frontend renders these keys directly
   (CandidateDetail.jsx, CandidateBoard.jsx, JobDetail.jsx). Losing one from a
   prompt silently breaks a panel in the UI with no build error.

2. **No prompt reintroduces an office-default assumption.** This product hires
   for wards, warehouses and workshops as well as desks.

Runs offline — builds prompt strings only, never calls the AI provider.
Live sample generation lives in prompt_samples.py, which needs a real key.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="module")
def ai():
    """Import ai_service without the groq SDK, a database or an API key.

    The prompt builders are pure string functions, so the I/O modules
    ai_service imports at module level are stubbed out. That keeps this suite
    runnable anywhere, including a CI box with no backend dependencies.
    """
    import os
    import types

    os.environ.setdefault("GROQ_API_KEY", "test-key-not-used")

    if "groq" not in sys.modules:
        groq_stub = types.ModuleType("groq")
        groq_stub.AsyncGroq = lambda **kwargs: None
        sys.modules["groq"] = groq_stub

    if "database" not in sys.modules:
        database_stub = types.ModuleType("database")
        database_stub.ai_usage_log = None
        sys.modules["database"] = database_stub

    import ai_service
    return ai_service


# --------------------------------------------------------------------------
# Three deliberately unlike roles, used throughout.
# --------------------------------------------------------------------------

NURSE_JD = (
    "Registered Nurse for a 12-bed adult Intensive Care Unit. Active NMC registration "
    "essential. Ventilator management, vasoactive infusions and ALS certification required. "
    "Rotating days and nights, 12-hour shifts."
)
FORKLIFT_JD = (
    "Counterbalance forklift operators for our night distribution shift. Valid in-date "
    "counterbalance licence (RTITB or ITSSAR) required. Chilled environment, lifting to 25kg. "
    "22:00-06:00, Sunday to Thursday."
)
ENGINEER_JD = (
    "Backend engineer to build and scale internal services. Strong Python and PostgreSQL "
    "required, plus REST API design and production cloud experience. 4+ years commercial."
)
ALL_JDS = [
    pytest.param(NURSE_JD, id="icu-nurse"),
    pytest.param(FORKLIFT_JD, id="forklift-operator"),
    pytest.param(ENGINEER_JD, id="backend-engineer"),
]

CANDIDATE = {
    "id": "cand-1",
    "name": "Sample Candidate",
    "resume_text": "Ten years of relevant experience. Certifications current.",
    "ai_summary": "Strong match on the core requirements.",
    "ai_score": 88,
}


# --------------------------------------------------------------------------
# 1. Response schemas must not drift
# --------------------------------------------------------------------------

RANK_KEYS = ["id", "score", "summary", "matched_skills", "missing_skills", "red_flags"]
QUESTION_KEYS = ["type", "question"]
EMAIL_KEYS = ["subject", "body"]
SUMMARY_KEYS = ["overall_fit", "strengths", "concerns", "experience_highlights", "recommendation"]
COMPARE_KEYS = ["recommendation", "reasoning", "candidate_a_strengths", "candidate_b_strengths"]


def test_rank_prompt_keeps_schema(ai):
    p = ai.build_rank_prompt(NURSE_JD, [CANDIDATE])
    for key in RANK_KEYS:
        assert f"- {key}" in p, f"rank prompt no longer requests '{key}' — UI reads it"
    assert "JSON array" in p


def test_questions_prompt_keeps_schema(ai):
    p = ai.build_questions_prompt(FORKLIFT_JD, CANDIDATE)
    for key in QUESTION_KEYS:
        assert f"- {key}" in p
    assert "JSON array" in p


def test_email_prompt_keeps_schema(ai):
    p = ai.build_email_prompt("rejection", CANDIDATE, "Forklift Operator", "Acme", FORKLIFT_JD)
    for key in EMAIL_KEYS:
        assert f"- {key}" in p
    assert "JSON object" in p


def test_summary_prompt_keeps_schema(ai):
    p = ai.build_summary_prompt(NURSE_JD, CANDIDATE)
    for key in SUMMARY_KEYS:
        assert f"- {key}" in p
    for verdict in ["Strong Yes", "Yes", "Maybe", "No"]:
        assert verdict in p, "recommendation vocabulary drives Pill colouring in the UI"


def test_compare_prompt_keeps_schema(ai):
    p = ai.build_compare_prompt(ENGINEER_JD, CANDIDATE, dict(CANDIDATE, id="cand-2"))
    for key in COMPARE_KEYS:
        assert f"- {key}" in p


def test_enhance_and_health_stay_plain_text(ai):
    enhance = ai.build_enhance_prompt(FORKLIFT_JD, "Forklift Operator")
    assert "plain text" in enhance and "JSON" not in enhance
    health = ai.build_health_prompt({"total_jobs": 3})
    assert "plain text" in health


# --------------------------------------------------------------------------
# 2. Office-default assumptions must not come back
# --------------------------------------------------------------------------

def test_rank_system_is_not_primed_for_technical_hiring(ai):
    """Was 'expert technical recruiter', which primed tech screening everywhere."""
    assert "technical recruiter" not in ai.RANK_SYSTEM.lower()


@pytest.mark.parametrize("jd", ALL_JDS)
def test_job_hopping_is_never_a_stock_red_flag(ai, jd):
    """The worst offender: it systematically penalised agency, seasonal,
    hospitality, construction and gig candidates for normal career shapes."""
    p = ai.build_rank_prompt(jd, [CANDIDATE]).lower()
    assert "job hopping" not in p
    # And the replacement guidance must actually be present.
    assert "seasonal" in p and "agency" in p
    assert "do not treat short tenures" in p


def test_summary_prompt_also_guards_tenure(ai):
    p = ai.build_summary_prompt(FORKLIFT_JD, CANDIDATE).lower()
    assert "do not" in p and "short tenures" in p


def test_question_types_are_not_locked_to_the_old_four(ai):
    """The old closed enum had no room for Safety, Licensing or Shift questions."""
    p = ai.build_questions_prompt(NURSE_JD, CANDIDATE)
    assert 'one of "Technical", "Behavioral", "Experience", "Culture Fit"' not in p
    for widened in ["Safety", "Certification", "Compliance", "Availability", "Practical Skills"]:
        assert widened in p


def test_enhance_prompt_does_not_hardcode_white_collar_sections(ai):
    """Was a fixed Overview/Responsibilities/Requirements/Nice to have/Benefits list."""
    p = ai.build_enhance_prompt(FORKLIFT_JD, "Forklift Operator")
    for blue_collar in ["Shift Pattern", "Certifications", "Physical Requirements", "Pay"]:
        assert blue_collar in p
    assert "only where the original gives you something real" in p


def test_email_prompt_receives_job_context(ai):
    """It previously saw only a job title, so every message had one register."""
    with_jd = ai.build_email_prompt("rejection", CANDIDATE, "ICU Nurse", "Trust", NURSE_JD)
    assert "NMC registration" in with_jd, "the JD must reach the email prompt"
    assert "match the formality" in with_jd.lower() or "pitch the message" in with_jd.lower()


def test_email_prompt_still_works_without_a_jd(ai):
    """jd_text is optional — a job with no description must not break drafting."""
    p = ai.build_email_prompt("interview invite", CANDIDATE, "Chef", "Kitchen Co")
    assert "JOB DESCRIPTION" not in p
    for key in EMAIL_KEYS:
        assert f"- {key}" in p


@pytest.mark.parametrize("system_name", [
    "RANK_SYSTEM", "QUESTIONS_SYSTEM", "ENHANCE_SYSTEM",
    "EMAIL_SYSTEM", "COMPARE_SYSTEM", "SUMMARY_SYSTEM", "HEALTH_SYSTEM",
])
def test_every_system_message_carries_the_universal_framing(ai, system_name):
    assert ai.UNIVERSAL_CONTEXT in getattr(ai, system_name), (
        f"{system_name} must tell the model not to assume an office setting"
    )


def test_universal_context_names_work_beyond_the_office(ai):
    ctx = ai.UNIVERSAL_CONTEXT.lower()
    for sector in ["clinical", "trades", "warehouse", "transport", "hospitality",
                   "retail", "education", "seasonal"]:
        assert sector in ctx


# --------------------------------------------------------------------------
# 3. The actual job description must reach every prompt
# --------------------------------------------------------------------------

@pytest.mark.parametrize("jd", ALL_JDS)
def test_jd_reaches_every_prompt_that_takes_one(ai, jd):
    marker = jd.split()[0]
    assert marker in ai.build_rank_prompt(jd, [CANDIDATE])
    assert marker in ai.build_questions_prompt(jd, CANDIDATE)
    assert marker in ai.build_summary_prompt(jd, CANDIDATE)
    assert marker in ai.build_compare_prompt(jd, CANDIDATE, CANDIDATE)
    assert marker in ai.build_enhance_prompt(jd, "Some Role")
