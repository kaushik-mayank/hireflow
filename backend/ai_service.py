import os
import re
import json
import logging
import uuid
from datetime import datetime, timezone

from groq import AsyncGroq
from database import ai_usage_log

logger = logging.getLogger(__name__)

# GROQ (GroqCloud) and GROK (x.ai) are different companies. The committed .env
# used the latter spelling, so `os.environ["GROQ_API_KEY"]` raised KeyError at
# import time — and because server.py imports routes_ai, that killed the entire
# API on startup rather than just the AI endpoints. The misspelling is accepted
# as an alias with a warning, and a missing key no longer prevents boot.
GROQ_API_KEY = (
    os.environ.get("GROQ_API_KEY") or os.environ.get("GROK_API_KEY") or ""
).strip()

if not os.environ.get("GROQ_API_KEY") and os.environ.get("GROK_API_KEY"):
    logger.warning(
        "Using GROK_API_KEY. The correct name is GROQ_API_KEY (GroqCloud, not x.ai) — "
        "please rename it."
    )

AI_MODEL = os.environ.get("AI_MODEL", "llama-3.3-70b-versatile")

# x.ai model ids will not resolve against GroqCloud and produce a confusing
# upstream 404, so say so plainly at boot instead.
if AI_MODEL.startswith("grok"):
    logger.warning(
        "AI_MODEL is set to %r, which is an x.ai model id. This backend talks to "
        "GroqCloud — expect model-not-found errors. Try llama-3.3-70b-versatile.",
        AI_MODEL,
    )

if not GROQ_API_KEY:
    logger.warning(
        "No Groq API key configured. The app will run, but every AI feature will "
        "return a clear error until GROQ_API_KEY is set."
    )

_ai_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


class AIUnavailable(Exception):
    """Raised when an AI feature is used but the provider is not configured."""


def is_configured() -> bool:
    return _ai_client is not None


async def call_ai(system_message: str, prompt: str) -> str:
    if not is_configured():
        raise AIUnavailable(
            "AI features are not configured on this server. Set GROQ_API_KEY to enable them."
        )
    response = await _ai_client.chat.completions.create(
        model=AI_MODEL,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


def parse_ai_json(text: str):
    """Safely parse JSON from an AI response that may contain markdown fences or extra prose."""
    if not text:
        return None
    # Strip code fences
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    # Try direct parse
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    # Find first JSON array or object
    for pattern in [r"\[.*\]", r"\{.*\}"]:
        match = re.search(pattern, cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                continue
    return None

COST_TABLE = {
    "rank":            {"tokens": 3000, "cost": 0.003},
    "questions":       {"tokens": 1500, "cost": 0.0015},
    "enhance-jd":      {"tokens": 1200, "cost": 0.0012},
    "draft-email":     {"tokens": 800,  "cost": 0.0008},
    "compare":         {"tokens": 2000, "cost": 0.002},
    "summary":         {"tokens": 1800, "cost": 0.0018},
    "pipeline-health": {"tokens": 1000, "cost": 0.001},
}

async def log_usage(action: str, user_id: str = None, job_id: str = None, candidate_id: str = None):
    est = COST_TABLE.get(action, {"tokens": 1000, "cost": 0.001})
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "job_id": job_id,
        "candidate_id": candidate_id,
        "action": action,
        "tokens_used": est["tokens"],
        "cost_estimate": est["cost"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await ai_usage_log.insert_one(doc)


# ---------------- Prompt builders ----------------
#
# Universal-niche rule: this product hires for every kind of work, so no prompt
# may assume an office or corporate setting as the default. Each prompt tells
# the model to infer the occupation from the job description and apply that
# trade's own norms.
#
# Response schemas are load-bearing — the UI renders these keys directly. Do
# not add, rename or remove a key without checking the components that read it.

UNIVERSAL_CONTEXT = (
    "This platform hires for every kind of work, in every industry, anywhere in the world — "
    "including roles and job families you may rarely see described. Never assume an office "
    "or corporate setting, a particular country's hiring conventions, or a familiar job "
    "family. The job description in front of you is the sole authority on what this role is "
    "and on what good looks like in it. Derive your evaluation criteria from that "
    "description; never apply a template carried over from a different role or industry."
)

# The core of the JD-driven architecture. Every evaluative prompt asks the model
# to derive a role profile FIRST, then judge against that profile — so criteria
# come from the posting rather than from a fixed taxonomy of job types. Adding a
# new industry requires no code change: the description drives everything.
JD_ANALYSIS_DIRECTIVE = """Before evaluating anything, derive a role profile from the job description itself:

1. DOMAIN — the industry, field or sector this belongs to, and the norms and vocabulary that apply within it.
2. FUNCTION — what this person actually does day to day, and what separates an adequate performer from an excellent one in this specific job.
3. SENIORITY — the level being hired at, and what is genuinely reasonable to expect of a candidate at that level.
4. ENGAGEMENT — whether this is permanent, fixed-term, contract, agency, locum, freelance, seasonal, shift-based, casual or project work, and what tenure and mobility patterns are normal for that arrangement in this field.
5. HARD REQUIREMENTS — licences, certifications, registrations, clearances, professional memberships, qualifications or legal eligibility that are mandatory rather than merely desirable.
6. TOOLS & SYSTEMS — the equipment, software, machinery, platforms, methodologies, frameworks or standards the description names.
7. CONTEXT — working environment, physical or cognitive demands, regulatory, safety or compliance obligations, customer/patient/client exposure, travel, and location or right-to-work constraints.

Derive every one of these from the description in front of you. Where it is thin, infer what is reasonable for that specific role rather than importing assumptions from an unrelated field. Then apply the profile you derived — not a generic scoring template — for the rest of this task."""

RANK_SYSTEM = (
    "You are an expert recruiter and resume screener who assesses candidates for any "
    "occupation. " + UNIVERSAL_CONTEXT + " You evaluate candidates against the role as "
    "described, judging them by the standards of their own field rather than a single "
    "template, and you return strict JSON only."
)


def build_rank_prompt(jd_text: str, candidates_batch: list) -> str:
    cand_blocks = []
    for c in candidates_batch:
        cand_blocks.append(
            f"--- CANDIDATE id={c['id']} ---\nNAME: {c.get('name') or 'Unknown'}\nRESUME:\n{c.get('resume_text','')[:6000]}"
        )
    cands = "\n\n".join(cand_blocks)
    return f"""Evaluate each candidate against the JOB DESCRIPTION below.

{JD_ANALYSIS_DIRECTIVE}

Weight your scoring according to the profile you derived. Whatever most determines success
in this particular role should carry the most weight — that will be different for every
posting, and you should let the description tell you what it is here rather than applying a
fixed set of criteria.

JOB DESCRIPTION:
{jd_text[:6000]}

CANDIDATES:
{cands}

For EACH candidate return an object with:
- id: the candidate id exactly as given
- score: integer 0-100 against the profile you derived, and nothing else. Do not reward
  credentials, seniority or prestige the role did not ask for, and do not penalise their
  absence. A candidate who meets this role's stated requirements scores well even if their
  background would be unremarkable for a different role.
- summary: 2-3 sentence assessment in plain, concrete language, using the vocabulary of
  this role's own field
- matched_skills: array of strings — whatever this role actually calls for that the
  candidate evidences: skills, licences, certifications, registrations, tools, systems,
  equipment, domain knowledge, methodologies or practical capabilities
- missing_skills: array of strings — requirements from the profile the candidate does not
  evidence. List anything you identified as a HARD REQUIREMENT first, since a missing
  mandatory credential usually matters more than a missing preference.
- red_flags: array of strings, or [] if none. Raise only substantive, evidence-based
  concerns measured against the profile: a missing mandatory credential, an unexplained
  gap, experience clearly short of the stated level, or a contradiction in the resume.
  Judge tenure against the ENGAGEMENT norms you derived, never against a general preference
  for long service. Frequent moves are expected and unremarkable in contract, agency,
  locum, freelance, seasonal, project and shift-based work, and carry no signal there. The
  same pattern may be worth noting in a role whose description implies long-horizon
  ownership or succession. Apply whichever standard genuinely fits this posting, and say
  nothing about tenure where it is not meaningful.

Return ONLY a JSON array of these objects. No prose, no markdown."""


QUESTIONS_SYSTEM = (
    "You are an expert interviewer who writes sharp, role-specific screening questions. "
    + UNIVERSAL_CONTEXT
    + " You ask what an experienced hiring manager working in that particular field would "
    "actually ask, in that field's own language."
)


def build_questions_prompt(jd_text: str, candidate: dict) -> str:
    return f"""Based on this job description and candidate resume, generate 6-8 tailored screening questions.

{JD_ANALYSIS_DIRECTIVE}

Now decide what genuinely needs verifying before hiring this specific candidate into this
specific role, and let that decide the mix of questions. The right areas to probe come from
the profile you derived — the hard requirements that must be confirmed, the parts of the
function where competence separates candidates, the risks or obligations the context
creates, and anything in the resume that needs clarifying. Do not work from a standard
interview template, and do not force a fixed balance of question categories.

JOB DESCRIPTION:
{jd_text[:4000]}

CANDIDATE RESUME:
{candidate.get('resume_text','')[:4000]}

Return ONLY a JSON array of objects, each with:
- type: a short free-form category label, two or three words at most, describing what the
  question probes, phrased in the vocabulary of THIS role's field. Derive the labels from
  the role rather than choosing from a fixed list — a regulated profession, a machine
  operator role, a client-facing commercial role and a research role should all produce
  visibly different labels. Reuse a label across questions where they probe the same area.
- question: the question text, specific to this candidate's background and this role

Ground each question in something the job description or the resume actually says, rather
than asking generically. No prose, no markdown."""


ENHANCE_SYSTEM = (
    "You are an expert job description writer who creates clear, inclusive, well-structured "
    "job postings. " + UNIVERSAL_CONTEXT + " You write in the register the audience for that "
    "role actually expects — direct and concrete for hands-on work, precise about clinical or "
    "regulatory detail where that matters, without corporate padding anywhere."
)


def build_enhance_prompt(jd_text: str, title: str) -> str:
    return f"""Improve and professionally format the following job posting for the role "{title}".

{JD_ANALYSIS_DIRECTIVE}

Now decide the structure this particular posting needs, and build it from the profile you
derived rather than from a standard layout. Every section you include must earn its place:
include one only where the original gives you something real to put in it, and where a
candidate for THIS role would actually look for that information before applying.

What matters most differs sharply by role and by field — a posting whose candidates need to
check working patterns, pay basis, site, mandatory credentials, equipment or physical
demands before applying should lead with those, while another may need none of them and
should not be padded with empty headings. Let the description and the audience decide.

Write in the register that role's candidates expect. Avoid corporate filler and unexplained
jargon, keep the language inclusive, and do not state requirements the original does not
support. Never invent specifics — pay figures, working hours, locations, benefits or
credentials that are not already present or clearly implied.

ORIGINAL JOB POSTING:
{jd_text[:6000]}

Return ONLY the improved job posting as plain text (markdown headings and bullet points are
fine). No commentary."""


EMAIL_SYSTEM = (
    "You are an expert hiring communication writer. " + UNIVERSAL_CONTEXT + " You match the "
    "tone and length of each message to the role and the reader, and you write so that "
    "anyone can understand it on their phone in one read."
)


def build_email_prompt(
    email_type: str, candidate: dict, job_title: str, company: str, jd_text: str = ""
) -> str:
    jd_block = f"""
JOB DESCRIPTION (for context on the role and the right tone):
{jd_text[:2500]}
""" if jd_text else ""

    return f"""Draft a {email_type} email to this candidate.

Work out from the role and the description below what register this reader expects, and
pitch the message to that. Formality, length, technical vocabulary and how much context to
give all vary by field, seniority and engagement type — infer them rather than defaulting to
one house style. Keep it short enough to read on a phone, use plain language over corporate
phrasing, and be warm and respectful throughout. In a rejection, brevity and clarity are
kinder than padding.

Candidate name: {candidate.get('name') or 'Candidate'}
Role: {job_title}
Organisation: {company or 'our organisation'}
Candidate summary: {candidate.get('ai_summary') or 'N/A'}
{jd_block}
Do not invent specifics — no interview times, pay figures, locations or start dates unless
they appear above. Where a concrete detail is needed but unknown, leave a clearly marked
placeholder in square brackets for the sender to fill in.

Return ONLY a JSON object with:
- subject: the email subject line
- body: the full email body, ready to send, with a greeting and a sign-off placeholder

No prose, no markdown."""


COMPARE_SYSTEM = (
    "You are an experienced hiring manager who compares candidates objectively. "
    + UNIVERSAL_CONTEXT
    + " You weigh candidates on what actually predicts success in the role at hand."
)


def build_compare_prompt(jd_text: str, cand_a: dict, cand_b: dict) -> str:
    return f"""Compare these two candidates for the role.

{JD_ANALYSIS_DIRECTIVE}

Weigh the two candidates on the factors your profile says actually predict success here,
not on general prestige, seniority or education. Which factors those are differs completely
between roles, so let the description decide rather than applying a standard hierarchy.

JOB DESCRIPTION:
{jd_text[:4000]}

CANDIDATE A ({cand_a.get('name')}): score={cand_a.get('ai_score')}
{cand_a.get('resume_text','')[:3000]}

CANDIDATE B ({cand_b.get('name')}): score={cand_b.get('ai_score')}
{cand_b.get('resume_text','')[:3000]}

Return ONLY a JSON object with:
- recommendation: name of the recommended candidate
- reasoning: 2-4 sentence justification
- candidate_a_strengths: array of strings
- candidate_b_strengths: array of strings

No prose, no markdown."""


SUMMARY_SYSTEM = (
    "You are an expert recruiter writing a deep, structured candidate analysis. "
    + UNIVERSAL_CONTEXT
    + " You assess each candidate against the standards of their own occupation."
)


def build_summary_prompt(jd_text: str, candidate: dict) -> str:
    return f"""Write a deep candidate analysis for this person against the role.

{JD_ANALYSIS_DIRECTIVE}

JOB DESCRIPTION:
{jd_text[:4000]}

CANDIDATE RESUME:
{candidate.get('resume_text','')[:5000]}

Return ONLY a JSON object with:
- overall_fit: 1-2 sentence verdict against the profile you derived
- strengths: array of strings, limited to what genuinely matters for this role
- concerns: array of strings. Raise only substantive concerns measured against the profile.
  Judge tenure against the ENGAGEMENT norms you derived rather than a general preference for
  long service: frequent moves carry no signal in contract, agency, locum, freelance,
  seasonal, project or shift-based work, and may carry some in a role whose description
  implies long-horizon ownership. Say nothing about tenure where it is not meaningful here.
- experience_highlights: array of strings
- recommendation: one of "Strong Yes", "Yes", "Maybe", "No"

No prose, no markdown."""


HEALTH_SYSTEM = (
    "You are an expert hiring operations analyst who reviews pipeline health. "
    + UNIVERSAL_CONTEXT
    + " Healthy volume, speed and drop-off differ by orders of magnitude between hiring "
    "patterns — infer from the data which kind of hiring this is before judging whether the "
    "numbers are good or bad, rather than applying a single benchmark."
)


def build_health_prompt(stats: dict) -> str:
    return f"""Analyze this hiring pipeline data and give a concise, actionable health report.

PIPELINE DATA (JSON):
{json.dumps(stats, indent=2)}

Provide a short report (plain text, 4-7 sentences) covering: overall health, bottlenecks,
candidates needing action, and 2-3 concrete recommendations. Be specific and reference the numbers.
No markdown headers, just clear prose."""
