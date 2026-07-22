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

import re
import sys
from pathlib import Path

import pytest


def norm(text: str) -> str:
    """Collapse whitespace so assertions survive prompt text being re-wrapped."""
    return re.sub(r"\s+", " ", text)


def contains_word(haystack: str, word: str) -> bool:
    """Whole-word match. Substring matching gives false positives — 'reward'
    contains 'ward', 'engineering' contains 'engineer'."""
    return re.search(rf"\b{re.escape(word)}s?\b", haystack, re.IGNORECASE) is not None

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

    # Merge into any stub another test module already installed rather than
    # skipping when the name exists — otherwise whichever suite runs first
    # decides which attributes are available to the rest.
    def stub(name, **attrs):
        module = sys.modules.get(name) or types.ModuleType(name)
        for key, value in attrs.items():
            if not hasattr(module, key):
                setattr(module, key, value)
        sys.modules[name] = module

    stub("groq", AsyncGroq=lambda **kwargs: None)
    stub("database", ai_usage_log=None)

    import ai_service
    return ai_service


# --------------------------------------------------------------------------
# Three deliberately unlike roles, used throughout.
# --------------------------------------------------------------------------

# The original three validation niches, kept as regression fixtures.
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

# Deliberately far beyond the three validation niches. The architecture must be
# JD-driven, so these need no special handling anywhere in the code — if adding
# an industry ever required a code change, that would be the bug.
FINANCE_JD = (
    "Financial Controller for a mid-market group. ACA or ACCA qualified with post-qualified "
    "experience. Statutory reporting under IFRS, group consolidation, audit liaison and "
    "treasury oversight. Experience with NetSuite preferred."
)
LEGAL_JD = (
    "Commercial Solicitor, 3-5 years PQE. Must hold a current practising certificate with "
    "the SRA. Drafting and negotiating supply, licensing and outsourcing agreements. "
    "Experience of data protection and competition matters an advantage."
)
SALES_JD = (
    "Enterprise Account Executive covering EMEA. Consistent quota attainment on six-figure "
    "annual contract values, MEDDIC or similar qualification methodology, Salesforce "
    "proficiency. Extensive travel expected."
)
MARKETING_JD = (
    "Performance Marketing Manager owning paid acquisition. Hands-on with Google Ads, Meta "
    "and programmatic buying, attribution modelling and budget accountability above six "
    "figures monthly. GA4 and SQL literacy required."
)
MANUFACTURING_JD = (
    "CNC Machinist for precision aerospace components. Must read engineering drawings to "
    "GD&T, set and operate 5-axis mills, and work to AS9100 quality standards. Fanuc "
    "programming and micrometer/CMM inspection experience required. Continental shift."
)
CONSTRUCTION_JD = (
    "Site Manager for commercial fit-out projects. Valid SMSTS, CSCS Black Card and First "
    "Aid at Work certification required. Responsible for programme, subcontractor "
    "coordination, RAMS approval and CDM compliance across concurrent sites."
)
HOSPITALITY_JD = (
    "Head Chef for a 120-cover brasserie. Level 3 Food Safety required. Menu development, "
    "gross profit control, supplier negotiation, allergen compliance and brigade "
    "management across split shifts including weekends."
)
EDUCATION_JD = (
    "Secondary Mathematics Teacher. QTS required, ECTs welcome. Teaching to Key Stage 4 "
    "with some A-level. Enhanced DBS clearance required before start. Form tutor "
    "responsibilities and one extracurricular commitment expected."
)

REGRESSION_JDS = [
    pytest.param(NURSE_JD, id="icu-nurse"),
    pytest.param(FORKLIFT_JD, id="forklift-operator"),
    pytest.param(ENGINEER_JD, id="backend-engineer"),
]

ALL_JDS = REGRESSION_JDS + [
    pytest.param(FINANCE_JD, id="finance-controller"),
    pytest.param(LEGAL_JD, id="legal-solicitor"),
    pytest.param(SALES_JD, id="sales-account-exec"),
    pytest.param(MARKETING_JD, id="marketing-performance"),
    pytest.param(MANUFACTURING_JD, id="manufacturing-machinist"),
    pytest.param(CONSTRUCTION_JD, id="construction-site-manager"),
    pytest.param(HOSPITALITY_JD, id="hospitality-head-chef"),
    pytest.param(EDUCATION_JD, id="education-teacher"),
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
    """The worst offender: it systematically penalised candidates whose sector
    makes short engagements completely normal."""
    p = norm(ai.build_rank_prompt(jd, [CANDIDATE]))
    assert "job hopping" not in p.lower()
    # The replacement must be reasoning, not merely a deletion.
    assert "ENGAGEMENT norms you derived" in p
    assert "carry no signal there" in p


def test_summary_prompt_also_guards_tenure(ai):
    p = norm(ai.build_summary_prompt(FORKLIFT_JD, CANDIDATE))
    assert "job hopping" not in p.lower()
    assert "ENGAGEMENT norms you derived" in p
    assert "carry no signal" in p


def test_question_types_are_free_form_not_a_fixed_list(ai):
    """The old closed enum had no room for Safety, Licensing or Shift questions.

    The replacement must not simply be a longer closed list either — labels are
    derived from the role so unfamiliar fields get their own vocabulary.
    """
    p = ai.build_questions_prompt(NURSE_JD, CANDIDATE)
    assert 'one of "Technical", "Behavioral", "Experience", "Culture Fit"' not in p
    assert "free-form" in p
    assert "Derive the labels from" in p


def test_enhance_prompt_does_not_prescribe_a_section_list(ai):
    """Was a fixed Overview/Responsibilities/Requirements/Nice to have/Benefits list.

    It must now derive structure from the role rather than swapping one fixed
    list for another.
    """
    p = ai.build_enhance_prompt(FORKLIFT_JD, "Forklift Operator")
    assert "must earn its place" in p
    assert "standard layout" in p


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


def test_universal_context_states_a_principle_not_a_sector_list(ai):
    """A finite sector list would silently exclude whatever it omitted. The
    framing must generalise instead of enumerating."""
    ctx = ai.UNIVERSAL_CONTEXT.lower()
    assert "every industry" in ctx
    assert "sole authority" in ctx
    assert "never apply a template" in ctx


# --------------------------------------------------------------------------
# 3. The architecture must be JD-driven, not tuned to known niches
# --------------------------------------------------------------------------

EVALUATIVE_PROMPTS = ["rank", "questions", "enhance", "compare", "summary"]


def _build(ai, which, jd, title="Some Role"):
    if which == "rank":
        return ai.build_rank_prompt(jd, [CANDIDATE])
    if which == "questions":
        return ai.build_questions_prompt(jd, CANDIDATE)
    if which == "enhance":
        return ai.build_enhance_prompt(jd, title)
    if which == "compare":
        return ai.build_compare_prompt(jd, CANDIDATE, dict(CANDIDATE, id="cand-2"))
    if which == "summary":
        return ai.build_summary_prompt(jd, CANDIDATE)
    raise AssertionError(which)


@pytest.mark.parametrize("which", EVALUATIVE_PROMPTS)
def test_every_evaluative_prompt_derives_a_role_profile_first(ai, which):
    """The core of the JD-driven design: derive criteria, then judge against them."""
    p = _build(ai, which, ENGINEER_JD)
    assert ai.JD_ANALYSIS_DIRECTIVE in p, f"{which} prompt must derive a role profile first"


def test_role_profile_covers_the_dimensions_that_vary_by_industry(ai):
    d = ai.JD_ANALYSIS_DIRECTIVE
    for dimension in ["DOMAIN", "FUNCTION", "SENIORITY", "ENGAGEMENT",
                      "HARD REQUIREMENTS", "TOOLS & SYSTEMS", "CONTEXT"]:
        assert dimension in d, f"role profile is missing {dimension}"
    assert "licences, certifications, registrations" in d
    assert "never apply a template" in ai.UNIVERSAL_CONTEXT.lower()


# A sentinel stands in for the job description so only TEMPLATE text is examined —
# occupation words coming from a real JD are legitimate and would mask the check.
SENTINEL_JD = "SENTINEL_JOB_DESCRIPTION_BODY"

# Naming occupations in the template biases every evaluation toward the examples
# chosen, and quietly disadvantages roles that resemble none of them.
FORBIDDEN_IN_TEMPLATES = [
    "nurse", "forklift", "chef", "engineer", "teacher", "driver", "warehouse",
    "ward", "solicitor", "accountant", "machinist", "barista", "electrician",
]


@pytest.mark.parametrize("which", EVALUATIVE_PROMPTS)
def test_prompt_templates_name_no_specific_occupation(ai, which):
    template = _build(ai, which, SENTINEL_JD, title="SENTINEL_TITLE")
    template = template.replace(SENTINEL_JD, "")
    for word in FORBIDDEN_IN_TEMPLATES:
        assert not contains_word(template, word), (
            f"{which} prompt hardcodes the occupation '{word}'. Criteria must be derived "
            f"from the job description, not from baked-in examples."
        )


def test_email_template_names_no_specific_occupation(ai):
    template = ai.build_email_prompt(
        "rejection", CANDIDATE, "SENTINEL_TITLE", "SENTINEL_ORG", SENTINEL_JD
    ).replace(SENTINEL_JD, "")
    for word in FORBIDDEN_IN_TEMPLATES:
        assert not contains_word(template, word), (
            f"email prompt hardcodes the occupation '{word}'"
        )


@pytest.mark.parametrize("system_name", [
    "RANK_SYSTEM", "QUESTIONS_SYSTEM", "ENHANCE_SYSTEM",
    "EMAIL_SYSTEM", "COMPARE_SYSTEM", "SUMMARY_SYSTEM", "HEALTH_SYSTEM",
])
def test_system_messages_name_no_specific_occupation(ai, system_name):
    text = getattr(ai, system_name)
    for word in FORBIDDEN_IN_TEMPLATES:
        assert not contains_word(text, word), (
            f"{system_name} hardcodes the occupation '{word}'"
        )


def test_scoring_is_not_a_generic_template(ai):
    p = norm(ai.build_rank_prompt(SALES_JD, [CANDIDATE]))
    assert "against the profile you derived" in p
    assert "Do not reward" in p and "did not ask for" in p


def test_tenure_is_judged_against_derived_engagement_norms(ai):
    """The user's example: a short stint means different things for a contractor
    than for an executive. This must be reasoned, not a sector allowlist."""
    for prompt in [ai.build_rank_prompt(LEGAL_JD, [CANDIDATE]),
                   ai.build_summary_prompt(LEGAL_JD, CANDIDATE)]:
        p = norm(prompt)
        assert "ENGAGEMENT norms you derived" in p
        assert "long-horizon ownership" in p
        assert "carry no signal" in p


# --------------------------------------------------------------------------
# 4. The actual job description must reach every prompt, for any industry
# --------------------------------------------------------------------------

@pytest.mark.parametrize("jd", ALL_JDS)
@pytest.mark.parametrize("which", EVALUATIVE_PROMPTS)
def test_jd_reaches_every_prompt_across_industries(ai, which, jd):
    """Eleven industries against five prompts. None of them needs bespoke
    handling — that is the point of a JD-driven design."""
    built = _build(ai, which, jd)
    # A distinctive phrase from deep inside each description, not just its first word.
    assert jd[-40:] in built


@pytest.mark.parametrize("jd", ALL_JDS)
def test_hard_requirements_survive_into_the_prompt(ai, jd):
    """Licences, registrations and certifications differ wildly by field and are
    exactly what a generic template would drop."""
    built = ai.build_rank_prompt(jd, [CANDIDATE])
    assert jd in built
    assert "HARD REQUIREMENTS" in built
