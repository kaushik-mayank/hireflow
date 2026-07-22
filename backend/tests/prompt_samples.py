"""Generate real AI output for three deliberately unlike roles.

This is the live counterpart to test_prompts.py. That suite proves the prompt
*text* is right offline; this one proves the *model behaviour* is right by
actually calling Groq, which needs a working key.

    cd backend
    set GROQ_API_KEY=gsk_...        # Windows;  export GROQ_API_KEY=... on Unix
    python tests/prompt_samples.py > ../prompt-samples.md

Output is markdown, ready to paste into PROGRESS.md for review.

The three roles below are regression baselines. Add your own by appending to
ROLES — the prompts derive their criteria from the description, so no code
anywhere needs to know about a new industry.

What to look for when reading the results:
  * The forklift candidate has three short agency placements. Under the old
    prompt that produced a "job hopping" red flag. It must not now — and the
    reasoning should reference the engagement type, not a hardcoded exemption.
  * Screening question `type` labels should be visibly different per role and
    phrased in that field's own vocabulary, not drawn from a fixed set.
  * Each enhanced posting should carry the sections its own candidates would
    look for, and omit ones the source gives nothing to fill.
  * The rejection emails should not all read in the same register.
  * Scores should reflect each role's stated requirements — the engineer being
    marked down against a 4-year bar is correct; a licensed-trade candidate
    should not be penalised for lacking a degree nobody asked for.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if not os.environ.get("GROQ_API_KEY"):
    sys.exit(
        "GROQ_API_KEY is not set.\n"
        "This script makes real API calls. Set the key and re-run:\n"
        "  Windows:  set GROQ_API_KEY=gsk_...\n"
        "  Unix:     export GROQ_API_KEY=gsk_...\n"
    )

# database is imported by ai_service for usage logging, which we don't want here.
import types  # noqa: E402
if "database" not in sys.modules:
    stub = types.ModuleType("database")
    stub.ai_usage_log = None
    sys.modules["database"] = stub

import ai_service as ai  # noqa: E402


# These three are REGRESSION BASELINES, not the supported set. The prompts are
# JD-driven: nothing in the codebase special-cases an industry, so adding a role
# here needs only a description and a resume — no code changes anywhere.
# test_prompts.py exercises eleven industries offline for the same reason.
ROLES = [
    {
        "key": "ICU Registered Nurse",
        "company": "St. Aldate's Hospital",
        "jd": (
            "Registered Nurse required for a 12-bed adult Intensive Care Unit. Active NMC "
            "registration essential. Minimum 2 years post-registration experience, at least 1 "
            "in critical care or high-dependency. Ventilator management, vasoactive infusions, "
            "invasive monitoring and ALS certification required. Rotating days and nights, "
            "12-hour shifts, 3 shifts per week. Enhanced DBS check required before start."
        ),
        "candidate": {
            "id": "nurse-1",
            "name": "Marcus Lee",
            "resume_text": (
                "Marcus Lee\nRegistered Nurse, 3 years post-registration.\n\n"
                "SKILLS: NMC registered (active), acute medical care, respiratory support, "
                "non-invasive ventilation, tracheostomy care, NEWS2 escalation, IV therapy. "
                "ILS certified.\n\n"
                "EXPERIENCE:\nStaff Nurse, Acute Medical Unit (2 years) — high-turnover "
                "admissions ward, deteriorating patients.\nStaff Nurse, Respiratory Ward "
                "(1 year) — NIV and tracheostomy care.\n\nEDUCATION: BSc Adult Nursing"
            ),
            "ai_summary": "Solid acute and respiratory grounding; no formal level 3 ICU time.",
            "ai_score": 76,
        },
    },
    {
        "key": "Forklift Operator — Night Shift",
        "company": "Meridian Distribution",
        "jd": (
            "Counterbalance forklift operators needed for our night distribution shift. Valid "
            "in-date counterbalance licence (RTITB or ITSSAR) required. Experience with reach "
            "trucks an advantage. Duties: unloading containers, put-away, replenishment and "
            "loading outbound trailers, plus RF scanner and WMS use. Must be comfortable in a "
            "chilled environment and lifting up to 25kg. 22:00-06:00, Sunday to Thursday."
        ),
        "candidate": {
            "id": "forklift-1",
            "name": "Aisha Bello",
            # Three short agency placements: the exact shape the old prompt penalised.
            "resume_text": (
                "Aisha Bello\nWarehouse operative and licensed forklift driver, 3 years.\n\n"
                "SKILLS: ITSSAR counterbalance licence (valid), RF scanner, goods-in, manual "
                "handling certified, forklift refresher completed this year.\n\n"
                "EXPERIENCE:\nForklift Operator (agency), Northgate DC — 5 months, peak season.\n"
                "Forklift Operator (agency), Riverside Logistics — 4 months, peak season.\n"
                "Forklift Operator (agency), Kestrel Freight — 6 months, peak season.\n"
                "Goods-in Operative, Bellway Supplies — 1 year, booking in deliveries.\n\n"
                "TRAINING: Level 2 Warehousing, manual handling certification"
            ),
            "ai_summary": "In-date licence and directly relevant distribution experience.",
            "ai_score": 84,
        },
    },
    {
        "key": "Backend Software Engineer",
        "company": "Meridian Group",
        "jd": (
            "Backend engineer to build and scale our internal services. Strong Python and "
            "PostgreSQL required, plus REST API design and production experience with cloud "
            "infrastructure. 4+ years commercial experience. Bonus: async frameworks, message "
            "queues, observability tooling."
        ),
        "candidate": {
            "id": "eng-1",
            "name": "Carlos Mendes",
            "resume_text": (
                "Carlos Mendes\nSoftware developer, 2 years commercial experience.\n\n"
                "SKILLS: Python, Django, MySQL, Git, basic AWS.\n\n"
                "EXPERIENCE:\nJunior Developer, Orbit Software (2 years) — internal tooling "
                "and reporting services.\n\nEDUCATION: BSc Software Engineering"
            ),
            "ai_summary": "Genuine Python foundation but below the stated experience bar.",
            "ai_score": 58,
        },
    },
]


def fence(text, lang=""):
    return f"```{lang}\n{text}\n```"


def as_json(raw):
    parsed = ai.parse_ai_json(raw)
    return json.dumps(parsed, indent=2) if parsed is not None else f"[UNPARSEABLE]\n{raw}"


async def run_role(role):
    jd, cand = role["jd"], role["candidate"]
    out = [f"\n\n## {role['key']}\n", f"**Candidate:** {cand['name']}\n"]

    print(f"  ... {role['key']}: enhance-jd", file=sys.stderr)
    enhanced = await ai.call_ai(ai.ENHANCE_SYSTEM, ai.build_enhance_prompt(jd, role["key"]))
    out += ["### 1. Enhanced job posting\n", fence(enhanced.strip())]

    print(f"  ... {role['key']}: rank", file=sys.stderr)
    ranked = await ai.call_ai(ai.RANK_SYSTEM, ai.build_rank_prompt(jd, [cand]))
    out += ["\n### 2. Resume ranking\n", fence(as_json(ranked), "json")]

    print(f"  ... {role['key']}: questions", file=sys.stderr)
    questions = await ai.call_ai(ai.QUESTIONS_SYSTEM, ai.build_questions_prompt(jd, cand))
    out += ["\n### 3. Screening questions\n", fence(as_json(questions), "json")]

    print(f"  ... {role['key']}: rejection email", file=sys.stderr)
    reject = await ai.call_ai(
        ai.EMAIL_SYSTEM,
        ai.build_email_prompt("rejection", cand, role["key"], role["company"], jd),
    )
    out += ["\n### 4. Rejection email\n", fence(as_json(reject), "json")]

    print(f"  ... {role['key']}: interview invite", file=sys.stderr)
    invite = await ai.call_ai(
        ai.EMAIL_SYSTEM,
        ai.build_email_prompt("interview invite", cand, role["key"], role["company"], jd),
    )
    out += ["\n### 5. Interview invite email\n", fence(as_json(invite), "json")]

    print(f"  ... {role['key']}: deep summary", file=sys.stderr)
    summary = await ai.call_ai(ai.SUMMARY_SYSTEM, ai.build_summary_prompt(jd, cand))
    out += ["\n### 6. Deep candidate summary\n", fence(as_json(summary), "json")]

    return "\n".join(out)


async def main():
    print(f"Model: {ai.AI_MODEL}", file=sys.stderr)
    print("# Phase 4 — AI prompt samples across three niches\n")
    print(f"Generated with `{ai.AI_MODEL}`. Six AI calls per role, eighteen in total.\n")
    print(
        "**Check for:** no 'job hopping' flag on the agency-placement forklift candidate; "
        "screening question `type` labels that differ by trade; shift/licence sections in the "
        "nursing and warehouse postings but not forced into the engineering one; and rejection "
        "emails that do not all share one corporate register."
    )
    for role in ROLES:
        print(await run_role(role))


if __name__ == "__main__":
    asyncio.run(main())
