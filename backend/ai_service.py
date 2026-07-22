import os
import re
import json
import uuid
from datetime import datetime, timezone

from groq import AsyncGroq
from database import ai_usage_log

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
AI_MODEL = os.environ.get("AI_MODEL", "llama-3.3-70b-versatile")

_ai_client = AsyncGroq(api_key=GROQ_API_KEY)


async def call_ai(system_message: str, prompt: str) -> str:
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
    "This platform is used to hire for every kind of work: clinical and care roles, "
    "skilled trades, warehouse and logistics, manufacturing, transport and driving, "
    "hospitality and food, retail, education, field service, agriculture, security, "
    "public sector, seasonal and gig work, as well as office, creative and technical "
    "roles. Never assume an office or corporate setting. Work out from the job "
    "description what kind of work this actually is, and apply the norms, vocabulary "
    "and hiring standards of that occupation."
)

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

First work out what kind of role this is: the occupation, the setting, the seniority, and
what actually determines whether someone succeeds in it. Then judge every candidate by that
standard. What makes a strong ICU nurse, a strong forklift operator and a strong backend
engineer are completely different things, and each should be assessed on its own terms.

JOB DESCRIPTION:
{jd_text[:6000]}

CANDIDATES:
{cands}

For EACH candidate return an object with:
- id: the candidate id exactly as given
- score: integer 0-100, measured against the requirements of THIS role only. Do not reward
  credentials the role does not ask for, and do not penalise a candidate for lacking them.
- summary: 2-3 sentence assessment in plain, concrete language
- matched_skills: array of strings — skills, certifications, licences, tickets, equipment,
  systems or practical capabilities the candidate has that this role calls for
- missing_skills: array of strings — requirements of this role the candidate does not
  evidence, including any mandatory licence or certification they appear to lack
- red_flags: array of strings, or [] if none. Only raise genuine, evidence-based concerns
  for THIS occupation: a missing legally-required licence or certification, an unexplained
  gap, experience clearly below what the role requires, or a contradiction in the resume.
  Do NOT treat short tenures or frequent job changes as a concern in fields where they are
  normal — agency, locum, seasonal, temporary, contract, hospitality, construction, events
  and gig work all routinely involve short engagements. Mention tenure only where it would
  genuinely be considered unusual within this specific occupation.

Return ONLY a JSON array of these objects. No prose, no markdown."""


QUESTIONS_SYSTEM = (
    "You are an expert interviewer who writes sharp, role-specific screening questions. "
    + UNIVERSAL_CONTEXT
    + " You ask what a seasoned hiring manager in that particular trade or profession "
    "would actually ask."
)


def build_questions_prompt(jd_text: str, candidate: dict) -> str:
    return f"""Based on this job description and candidate resume, generate 6-8 tailored screening questions.

First work out what kind of role this is and what genuinely needs checking before hiring
someone into it. Let that drive the questions. A ward nurse should be asked about clinical
judgement, escalation and shift patterns; a forklift operator about certification currency,
load safety and warehouse systems; an engineer about technical depth and trade-offs; a chef
about service volume, food safety and kitchen pressure. Ask what matters for THIS job.

JOB DESCRIPTION:
{jd_text[:4000]}

CANDIDATE RESUME:
{candidate.get('resume_text','')[:4000]}

Return ONLY a JSON array of objects, each with:
- type: a short category label that fits this role. Pick whichever genuinely applies, for
  example: "Technical", "Practical Skills", "Safety", "Certification", "Compliance",
  "Experience", "Situational", "Behavioral", "Availability", "Customer Interaction",
  "Physical Requirements", "Team Fit". Use a different short label if none of these fit
  the occupation well.
- question: the question text, specific to this candidate's background and this role

Ground the questions in what the resume actually says wherever you can, rather than asking
generically. No prose, no markdown."""


ENHANCE_SYSTEM = (
    "You are an expert job description writer who creates clear, inclusive, well-structured "
    "job postings. " + UNIVERSAL_CONTEXT + " You write in the register the audience for that "
    "role actually expects — direct and concrete for hands-on work, precise about clinical or "
    "regulatory detail where that matters, without corporate padding anywhere."
)


def build_enhance_prompt(jd_text: str, title: str) -> str:
    return f"""Improve and professionally format the following job posting for the role "{title}".

First work out what kind of role this is and who will be reading the advert. Then choose the
sections that genuinely belong in a posting for THAT job, and leave out the ones that do not.
Depending on the role, useful sections include: Overview, Responsibilities, Requirements,
Certifications & Licences Required, Shift Pattern & Hours, Pay & Rate, Location / Site,
Physical Requirements, Equipment & Tools, Training Provided, Career Progression,
Nice to have, Benefits, and How to Apply.

Include a section only where the original gives you something real to put in it. A warehouse
or care posting usually needs shifts, pay basis and site; a licensed trade or clinical role
needs its certifications stated plainly; a salaried professional role may need none of those.
Do not force every role into the same shape.

Write plainly. Avoid corporate filler and unexplained jargon. Use inclusive language, and do
not state requirements the original does not support. Keep it truthful to the input — never
invent specifics such as salary figures, shift times, locations or benefits that are not
already there or clearly implied.

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

First work out what kind of role this is and pitch the message accordingly. A message about
a warehouse shift, a nursing post and a senior engineering role should not read the same
way. Match the formality the reader would expect, keep it short enough to read on a phone,
and use plain everyday language rather than corporate phrasing. Be warm and respectful in
every case — especially in a rejection, where brevity and clarity are kinder than padding.

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

Work out first what this role really demands day to day, then weigh the two candidates on
that basis rather than on general prestige. Reliability, certification currency, physical
capability, availability or customer manner may matter far more than seniority or education
depending on the job.

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

Work out what kind of role this is first, and assess the candidate by the standards of that
occupation rather than a generic professional template.

JOB DESCRIPTION:
{jd_text[:4000]}

CANDIDATE RESUME:
{candidate.get('resume_text','')[:5000]}

Return ONLY a JSON object with:
- overall_fit: 1-2 sentence verdict
- strengths: array of strings, relevant to what this role actually needs
- concerns: array of strings. Raise only substantive concerns for this occupation. Do not
  treat short tenures or frequent moves as a concern in fields where they are normal
  (agency, locum, seasonal, temporary, contract, hospitality, construction, events, gig).
- experience_highlights: array of strings
- recommendation: one of "Strong Yes", "Yes", "Maybe", "No"

No prose, no markdown."""


HEALTH_SYSTEM = (
    "You are an expert hiring operations analyst who reviews pipeline health. "
    + UNIVERSAL_CONTEXT
    + " Hiring volume, speed and drop-off look very different for high-volume shift "
    "recruitment than for a single specialist vacancy — read the numbers accordingly."
)


def build_health_prompt(stats: dict) -> str:
    return f"""Analyze this hiring pipeline data and give a concise, actionable health report.

PIPELINE DATA (JSON):
{json.dumps(stats, indent=2)}

Provide a short report (plain text, 4-7 sentences) covering: overall health, bottlenecks,
candidates needing action, and 2-3 concrete recommendations. Be specific and reference the numbers.
No markdown headers, just clear prose."""
