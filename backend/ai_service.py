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

RANK_SYSTEM = (
    "You are an expert technical recruiter and resume screener. You evaluate candidate "
    "resumes against a job description objectively and return strict JSON only."
)


def build_rank_prompt(jd_text: str, candidates_batch: list) -> str:
    cand_blocks = []
    for c in candidates_batch:
        cand_blocks.append(
            f"--- CANDIDATE id={c['id']} ---\nNAME: {c.get('name') or 'Unknown'}\nRESUME:\n{c.get('resume_text','')[:6000]}"
        )
    cands = "\n\n".join(cand_blocks)
    return f"""Evaluate each candidate against the JOB DESCRIPTION below.

JOB DESCRIPTION:
{jd_text[:6000]}

CANDIDATES:
{cands}

For EACH candidate return an object with:
- id: the candidate id exactly as given
- score: integer 0-100 (overall match)
- summary: 2-3 sentence assessment
- matched_skills: array of strings (skills present that match the JD)
- missing_skills: array of strings (key JD skills the candidate lacks)
- red_flags: array of strings (gaps, job hopping, missing requirements, or [] if none)

Return ONLY a JSON array of these objects. No prose, no markdown."""


QUESTIONS_SYSTEM = "You are an expert interviewer who writes sharp, role-specific screening questions."


def build_questions_prompt(jd_text: str, candidate: dict) -> str:
    return f"""Based on this job description and candidate resume, generate 6-8 tailored screening questions.

JOB DESCRIPTION:
{jd_text[:4000]}

CANDIDATE RESUME:
{candidate.get('resume_text','')[:4000]}

Return ONLY a JSON array of objects, each with:
- type: one of "Technical", "Behavioral", "Experience", "Culture Fit"
- question: the question text (specific to this candidate's background and the role)

No prose, no markdown."""


ENHANCE_SYSTEM = "You are an expert job description writer who creates clear, inclusive, structured JDs."


def build_enhance_prompt(jd_text: str, title: str) -> str:
    return f"""Improve and professionally format the following job description for the role "{title}".
Make it well structured with sections (Overview, Responsibilities, Requirements, Nice to have, Benefits where inferable),
clear, inclusive language, and compelling tone. Keep it truthful to the input — do not invent specifics like salary.

ORIGINAL JOB DESCRIPTION:
{jd_text[:6000]}

Return ONLY the enhanced job description as plain text (you may use markdown headings and bullet points). No commentary."""


EMAIL_SYSTEM = "You are an expert HR communication writer who drafts warm, professional recruiting emails."


def build_email_prompt(email_type: str, candidate: dict, job_title: str, company: str) -> str:
    return f"""Draft a {email_type} email.

Candidate name: {candidate.get('name') or 'Candidate'}
Role: {job_title}
Company: {company or 'our company'}
Candidate summary: {candidate.get('ai_summary') or 'N/A'}

Return ONLY a JSON object with:
- subject: the email subject line
- body: the full email body (professional, warm, ready to send, with greeting and sign-off placeholder)

No prose, no markdown."""


COMPARE_SYSTEM = "You are an expert hiring manager who compares candidates objectively for a role."


def build_compare_prompt(jd_text: str, cand_a: dict, cand_b: dict) -> str:
    return f"""Compare these two candidates for the role.

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


SUMMARY_SYSTEM = "You are an expert recruiter writing a deep, structured candidate analysis."


def build_summary_prompt(jd_text: str, candidate: dict) -> str:
    return f"""Write a deep candidate analysis for this person against the role.

JOB DESCRIPTION:
{jd_text[:4000]}

CANDIDATE RESUME:
{candidate.get('resume_text','')[:5000]}

Return ONLY a JSON object with:
- overall_fit: 1-2 sentence verdict
- strengths: array of strings
- concerns: array of strings
- experience_highlights: array of strings
- recommendation: one of "Strong Yes", "Yes", "Maybe", "No"

No prose, no markdown."""


HEALTH_SYSTEM = "You are an expert hiring operations analyst who reviews recruiting pipeline health."


def build_health_prompt(stats: dict) -> str:
    return f"""Analyze this hiring pipeline data and give a concise, actionable health report.

PIPELINE DATA (JSON):
{json.dumps(stats, indent=2)}

Provide a short report (plain text, 4-7 sentences) covering: overall health, bottlenecks,
candidates needing action, and 2-3 concrete recommendations. Be specific and reference the numbers.
No markdown headers, just clear prose."""
