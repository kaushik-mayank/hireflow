"""Hiring analytics, scoped to the signed-in user.

Everything here is computed from real records — there are no sampled or
synthetic figures. Where a number cannot be derived honestly it is omitted
rather than estimated.

`stage_transitions` is the backbone: it holds a timestamped audit trail of
every stage change, which is what makes a true conversion funnel, per-stage
dwell time and stalled-posting detection possible.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends

from database import jobs, candidates, stage_transitions
from auth import get_current_user

router = APIRouter(prefix="/reports", tags=["reports"])

STAGES = [
    "Applied", "AI Ranked", "Shortlisted", "Contact Pending", "Contacted",
    "Interview Scheduled", "Interview Done", "Selected", "Rejected", "On Hold",
]

# The funnel is the progression path only. Rejected and On Hold are outcomes
# that can happen at any point, not steps candidates advance through.
FUNNEL_STAGES = [
    "Applied", "AI Ranked", "Shortlisted", "Contact Pending", "Contacted",
    "Interview Scheduled", "Interview Done", "Selected",
]
FUNNEL_INDEX = {s: i for i, s in enumerate(FUNNEL_STAGES)}

HIRED_STAGE = "Selected"
REJECTED_STAGE = "Rejected"
UNKNOWN_SOURCE = "Unknown"

# A posting with no candidate movement for this long is worth a second look.
STALE_DAYS = 14
# Enough history to say something about a trend without over-reading noise.
TREND_WINDOW_DAYS = 30
# Below this, percentages are too noisy to present as insight.
MIN_SAMPLE_FOR_INSIGHT = 5


def _parse(dt: Optional[str]) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(dt)
    except (ValueError, TypeError):
        return None
    # Older rows may be naive; treat them as UTC so comparisons never explode.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _days_between(start: Optional[datetime], end: Optional[datetime]) -> Optional[int]:
    if not start or not end:
        return None
    return max((end - start).days, 0)


def _pct(part: int, whole: int) -> float:
    return round((part / whole) * 100, 1) if whole else 0.0


# ---------------------------------------------------------------------------
# Time to hire
# ---------------------------------------------------------------------------

def _time_to_hire(user_jobs: list, cands_by_job: dict, hire_events: dict) -> dict:
    """Days from application to hire, per posting and overall.

    Previously this ran one query per hired candidate inside a loop. Hire
    timestamps are now fetched once by the caller and passed in.
    """
    per_job, all_durations = [], []
    recent, previous = [], []
    cutoff = datetime.now(timezone.utc) - timedelta(days=TREND_WINDOW_DAYS)

    for job in user_jobs:
        durations = []
        for cand in cands_by_job.get(job["id"], []):
            if cand.get("stage") != HIRED_STAGE:
                continue
            hired_at = hire_events.get(cand["id"])
            days = _days_between(_parse(cand.get("uploaded_at")), hired_at)
            if days is None:
                continue
            durations.append(days)
            (recent if hired_at >= cutoff else previous).append(days)
        if durations:
            avg = round(sum(durations) / len(durations), 1)
            per_job.append({"job": job["title"], "avg_days": avg, "hires": len(durations)})
            all_durations.extend(durations)

    def mean(values):
        return round(sum(values) / len(values), 1) if values else None

    return {
        "per_job": sorted(per_job, key=lambda r: r["avg_days"], reverse=True),
        "overall_avg": mean(all_durations),
        "total_hires": len(all_durations),
        "recent_avg": mean(recent),
        "previous_avg": mean(previous),
    }


# ---------------------------------------------------------------------------
# Conversion funnel
# ---------------------------------------------------------------------------

def _furthest_stage_reached(cand: dict, transitions_by_cand: dict) -> Optional[int]:
    """How far a candidate actually got, not merely where they sit now.

    Someone currently marked Rejected may have reached Interview Done first —
    counting only their current stage would understate the funnel.
    """
    best = FUNNEL_INDEX.get(cand.get("stage"))
    for t in transitions_by_cand.get(cand["id"], []):
        for stage in (t.get("from_stage"), t.get("to_stage")):
            idx = FUNNEL_INDEX.get(stage)
            if idx is not None and (best is None or idx > best):
                best = idx
    # Every candidate has at least applied.
    return 0 if best is None else best


def _funnel(all_cands: list, transitions_by_cand: dict) -> list:
    reached = Counter()
    for cand in all_cands:
        furthest = _furthest_stage_reached(cand, transitions_by_cand)
        for i in range(furthest + 1):
            reached[i] += 1

    total = len(all_cands)
    rows, previous_count = [], None
    for i, stage in enumerate(FUNNEL_STAGES):
        count = reached.get(i, 0)
        rows.append({
            "stage": stage,
            "count": count,
            "pct_of_total": _pct(count, total),
            # Share of the previous stage that made it here.
            "conversion_from_previous": _pct(count, previous_count) if previous_count else None,
            "drop_off": (previous_count - count) if previous_count is not None else 0,
            "drop_off_pct": _pct(previous_count - count, previous_count) if previous_count else 0.0,
        })
        previous_count = count
    return rows


def _biggest_drop_off(funnel: list) -> Optional[dict]:
    """The stage transition losing the most candidates, ignoring the entry step."""
    candidates_for_drop = [
        r for r in funnel[1:] if r["drop_off"] > 0 and r["conversion_from_previous"] is not None
    ]
    if not candidates_for_drop:
        return None
    worst = max(candidates_for_drop, key=lambda r: r["drop_off"])
    idx = funnel.index(worst)
    return {
        "from_stage": funnel[idx - 1]["stage"],
        "to_stage": worst["stage"],
        "lost": worst["drop_off"],
        "drop_off_pct": worst["drop_off_pct"],
    }


# ---------------------------------------------------------------------------
# Source effectiveness
# ---------------------------------------------------------------------------

def _source_effectiveness(all_cands: list) -> list:
    grouped = defaultdict(list)
    for cand in all_cands:
        grouped[(cand.get("source") or UNKNOWN_SOURCE).strip() or UNKNOWN_SOURCE].append(cand)

    rows = []
    for source, cands in grouped.items():
        hired = sum(1 for c in cands if c.get("stage") == HIRED_STAGE)
        scored = [c["ai_score"] for c in cands if c.get("ai_score") is not None]
        rows.append({
            "source": source,
            "candidates": len(cands),
            "hired": hired,
            "hire_rate": _pct(hired, len(cands)),
            "avg_score": round(sum(scored) / len(scored)) if scored else None,
        })
    return sorted(rows, key=lambda r: (r["hired"], r["candidates"]), reverse=True)


# ---------------------------------------------------------------------------
# Postings: status over time, and which ones have stalled
# ---------------------------------------------------------------------------

def _postings_over_time(user_jobs: list, weeks: int = 12) -> list:
    today = datetime.now(timezone.utc).date()
    start_of_week = today - timedelta(days=today.weekday())
    buckets = [start_of_week - timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]

    parsed = [
        (_parse(j.get("created_at")), j.get("status"), _parse(j.get("updated_at")))
        for j in user_jobs
    ]
    rows = []
    for week_start in buckets:
        week_end = week_start + timedelta(days=7)
        opened = sum(1 for c, _s, _u in parsed if c and c.date() < week_end)
        closed = sum(
            1 for c, s, u in parsed
            if c and c.date() < week_end and s != "active" and u and u.date() < week_end
        )
        rows.append({
            "week": week_start.isoformat(),
            "open": max(opened - closed, 0),
            "closed": closed,
        })
    return rows


def _aging_postings(user_jobs: list, cands_by_job: dict, last_activity: dict) -> list:
    """Open postings with no candidate movement recently — the actionable list."""
    now = datetime.now(timezone.utc)
    rows = []
    for job in user_jobs:
        if job.get("status") != "active":
            continue
        cands = cands_by_job.get(job["id"], [])
        hired = sum(1 for c in cands if c.get("stage") == HIRED_STAGE)
        needed = job.get("openings_needed", 1)
        if hired >= needed:
            continue

        moved_at = last_activity.get(job["id"]) or _parse(job.get("created_at"))
        idle_days = _days_between(moved_at, now)
        if idle_days is None or idle_days < STALE_DAYS:
            continue

        rows.append({
            "job": job["title"],
            "job_id": job["id"],
            "days_since_activity": idle_days,
            "days_open": _days_between(_parse(job.get("created_at")), now),
            "candidates": len(cands),
            "hired": hired,
            "needed": needed,
            "no_candidates": len(cands) == 0,
        })
    return sorted(rows, key=lambda r: r["days_since_activity"], reverse=True)


def _quota_tracker(user_jobs: list, cands_by_job: dict) -> list:
    rows = []
    for job in user_jobs:
        cands = cands_by_job.get(job["id"], [])
        hired = sum(1 for c in cands if c.get("stage") == HIRED_STAGE)
        active = sum(
            1 for c in cands if c.get("stage") not in (HIRED_STAGE, REJECTED_STAGE)
        )
        needed = job.get("openings_needed", 1)
        rows.append({
            "job": job["title"],
            "needed": needed,
            "hired": hired,
            "in_pipeline": active,
            "remaining": max(needed - hired, 0),
            "complete": hired >= needed,
            "status": job.get("status"),
        })
    return rows


# ---------------------------------------------------------------------------
# Plain-language insights
# ---------------------------------------------------------------------------

def _insights(tth: dict, funnel: list, aging: list, sources: list, quota: list,
              total_candidates: int, unanalyzed: int) -> list:
    """Deterministic, rule-based observations.

    Rule-based rather than an AI call: this renders on every page load, so it
    must be instant, free and identical for identical data. The on-demand AI
    pipeline-health report remains available separately for narrative analysis.

    Every claim below is derived from a real count. Each has a `tone` the UI
    uses for colour: positive / attention / neutral.
    """
    out = []

    if tth["overall_avg"] is not None:
        line = (
            f"Your average time-to-hire is {tth['overall_avg']:.0f} days "
            f"across {tth['total_hires']} hire{'s' if tth['total_hires'] != 1 else ''}."
        )
        tone = "neutral"
        if tth["recent_avg"] is not None and tth["previous_avg"] is not None:
            delta = tth["recent_avg"] - tth["previous_avg"]
            if abs(delta) >= 1:
                direction = "down" if delta < 0 else "up"
                tone = "positive" if delta < 0 else "attention"
                line += (
                    f" That's {direction} from {tth['previous_avg']:.0f} days"
                    f" before the last {TREND_WINDOW_DAYS} days."
                )
        out.append({"tone": tone, "text": line})

    worst = _biggest_drop_off(funnel)
    if worst and total_candidates >= MIN_SAMPLE_FOR_INSIGHT:
        out.append({
            "tone": "attention",
            "text": (
                f"Most candidates are lost between {worst['from_stage']} and "
                f"{worst['to_stage']} — {worst['lost']} "
                f"({worst['drop_off_pct']:.0f}%) don't get past it."
            ),
        })

    stalled = [a for a in aging if not a["no_candidates"]]
    empty = [a for a in aging if a["no_candidates"]]
    if stalled:
        longest = stalled[0]
        out.append({
            "tone": "attention",
            "text": (
                f"{len(stalled)} open posting{'s have' if len(stalled) != 1 else ' has'} had no "
                f"candidate movement in over {STALE_DAYS} days — "
                f"the longest is \"{longest['job']}\" at {longest['days_since_activity']} days."
            ),
        })
    if empty:
        out.append({
            "tone": "attention",
            "text": (
                f"{len(empty)} open posting{'s have' if len(empty) != 1 else ' has'} no "
                f"candidates at all. They may need promoting or closing."
            ),
        })

    real_sources = [s for s in sources if s["source"] != UNKNOWN_SOURCE]
    qualified = [s for s in real_sources if s["candidates"] >= MIN_SAMPLE_FOR_INSIGHT]
    if len(qualified) >= 2:
        best = max(qualified, key=lambda s: s["hire_rate"])
        if best["hire_rate"] > 0:
            out.append({
                "tone": "positive",
                "text": (
                    f"{best['source']} is converting best — {best['hire_rate']:.0f}% of its "
                    f"{best['candidates']} candidates were hired."
                ),
            })

    if unanalyzed:
        out.append({
            "tone": "attention",
            "text": (
                f"{unanalyzed} candidate{'s have' if unanalyzed != 1 else ' has'} not been "
                f"AI-ranked yet, so they're missing from score-based comparisons."
            ),
        })

    complete = [q for q in quota if q["complete"]]
    if complete:
        out.append({
            "tone": "positive",
            "text": (
                f"{len(complete)} posting{'s have' if len(complete) != 1 else ' has'} met "
                f"the full hiring target."
            ),
        })

    return out


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("")
async def reports(user: dict = Depends(get_current_user)) -> dict:
    user_jobs = await jobs.find({"user_id": user["id"]}, {"_id": 0}).to_list(1000)
    job_ids = [j["id"] for j in user_jobs]
    all_cands = await candidates.find(
        {"job_id": {"$in": job_ids}}, {"_id": 0, "resume_text": 0}
    ).to_list(50000)

    cands_by_job = defaultdict(list)
    for cand in all_cands:
        cands_by_job[cand["job_id"]].append(cand)

    # One query for every transition, instead of one per hired candidate.
    cand_ids = [c["id"] for c in all_cands]
    transitions = await stage_transitions.find(
        {"candidate_id": {"$in": cand_ids}}, {"_id": 0}
    ).to_list(200000)

    transitions_by_cand = defaultdict(list)
    for t in transitions:
        transitions_by_cand[t["candidate_id"]].append(t)

    # Latest move into Selected per candidate, for time-to-hire.
    hire_events: dict = {}
    for t in transitions:
        if t.get("to_stage") != HIRED_STAGE:
            continue
        moved = _parse(t.get("moved_at"))
        if moved and (t["candidate_id"] not in hire_events or moved > hire_events[t["candidate_id"]]):
            hire_events[t["candidate_id"]] = moved

    # Most recent activity per posting, for the stalled list.
    job_of_cand = {c["id"]: c["job_id"] for c in all_cands}
    last_activity: dict = {}
    for t in transitions:
        job_id = job_of_cand.get(t["candidate_id"])
        moved = _parse(t.get("moved_at"))
        if job_id and moved and (job_id not in last_activity or moved > last_activity[job_id]):
            last_activity[job_id] = moved
    for cand in all_cands:
        uploaded = _parse(cand.get("uploaded_at"))
        job_id = cand["job_id"]
        if uploaded and (job_id not in last_activity or uploaded > last_activity[job_id]):
            last_activity[job_id] = uploaded

    tth = _time_to_hire(user_jobs, cands_by_job, hire_events)
    funnel = _funnel(all_cands, transitions_by_cand)
    sources = _source_effectiveness(all_cands)
    aging = _aging_postings(user_jobs, cands_by_job, last_activity)
    quota = _quota_tracker(user_jobs, cands_by_job)
    unanalyzed = sum(1 for c in all_cands if not c.get("analyzed_at"))

    return {
        "time_to_hire": tth,
        "funnel": funnel,
        "biggest_drop_off": _biggest_drop_off(funnel),
        "sources": sources,
        "has_source_data": any(s["source"] != UNKNOWN_SOURCE for s in sources),
        "postings_over_time": _postings_over_time(user_jobs),
        "aging_postings": aging,
        "quota_tracker": quota,
        "insights": _insights(
            tth, funnel, aging, sources, quota, len(all_cands), unanalyzed
        ),
        "totals": {
            "jobs": len(user_jobs),
            "open_jobs": sum(1 for j in user_jobs if j.get("status") == "active"),
            "candidates": len(all_cands),
            "hired": sum(1 for c in all_cands if c.get("stage") == HIRED_STAGE),
            "unanalyzed": unanalyzed,
        },
    }
