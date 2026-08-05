"""Manager team-report computations — pure, side-effect-free, offline-testable.

These are the per-recruiter numbers a manager acts on, so — exactly like the
Cycle-1 reports — every figure is derived from real records, rates are withheld
below a 5-item sample, and a null target hides its panel rather than showing 0.

KPI formulas (see PROJECT_PLAN_CYCLE2.md §8.3):
    shortlist_rate    = shortlisted / sourced           (min sample 5)
    target_attainment = actual / target                 (null target -> hidden)
    deadline burn-down: on_track when the pace achieved so far already meets the
        pace still required to finish by the deadline; at_risk otherwise; missed
        once the deadline has passed and the target isn't met.

The DB layer (routes_reports) fetches records and enriches these rows with names
and job titles; nothing here touches Mongo, so it is trivially unit-tested.
"""

from datetime import datetime, timezone
from typing import Optional

# Progression path only (Rejected / On Hold are outcomes, not steps). Mirrors the
# Cycle-1 funnel so "furthest stage reached" means the same thing everywhere.
FUNNEL_STAGES = [
    "Applied", "AI Ranked", "Shortlisted", "Contact Pending", "Contacted",
    "Interview Scheduled", "Interview Done", "Selected",
]
FUNNEL_INDEX = {s: i for i, s in enumerate(FUNNEL_STAGES)}

SHORTLISTED_IDX = FUNNEL_INDEX["Shortlisted"]
INTERVIEW_IDX = FUNNEL_INDEX["Interview Scheduled"]
HIRED_STAGE = "Selected"
REJECTED_STAGE = "Rejected"

# Below this a percentage is too noisy to present as a rate.
MIN_SAMPLE = 5


def _parse(dt: Optional[str]) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(dt) if isinstance(dt, str) else dt
    except (ValueError, TypeError):
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:  # older/naive rows -> treat as UTC so maths never explodes
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _days_between(start: Optional[datetime], end: Optional[datetime]) -> Optional[int]:
    if not start or not end:
        return None
    return (end - start).days


def _pct(part: int, whole: int) -> Optional[float]:
    """Rate as a %, or None when the sample is too small to be meaningful."""
    if whole < MIN_SAMPLE:
        return None
    return round((part / whole) * 100, 1)


def furthest_index(cand: dict, transitions_by_cand: dict) -> int:
    """How far a candidate actually got — the max funnel index across their
    current stage and every stage in their transition history. Someone now
    Rejected may have reached Interview Done first."""
    best = FUNNEL_INDEX.get(cand.get("stage"))
    for t in transitions_by_cand.get(cand["id"], []):
        for stage in (t.get("from_stage"), t.get("to_stage")):
            idx = FUNNEL_INDEX.get(stage)
            if idx is not None and (best is None or idx > best):
                best = idx
    return 0 if best is None else best  # everyone has at least applied


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------

def throughput_by_recruiter(recruiter_ids, candidates, transitions_by_cand) -> list:
    """Candidates sourced / shortlisted / interviewed / hired per recruiter."""
    by_rec = {rid: [] for rid in recruiter_ids}
    for c in candidates:
        rid = c.get("sourced_by")
        if rid in by_rec:
            by_rec[rid].append(c)

    rows = []
    for rid, cands in by_rec.items():
        sourced = len(cands)
        shortlisted = sum(1 for c in cands if furthest_index(c, transitions_by_cand) >= SHORTLISTED_IDX)
        interviewed = sum(1 for c in cands if furthest_index(c, transitions_by_cand) >= INTERVIEW_IDX)
        hired = sum(1 for c in cands if c.get("stage") == HIRED_STAGE)
        rows.append({
            "user_id": rid,
            "sourced": sourced,
            "shortlisted": shortlisted,
            "interviewed": interviewed,
            "hired": hired,
            "shortlist_rate": _pct(shortlisted, sourced),
            "hire_rate": _pct(hired, sourced),
        })
    return sorted(rows, key=lambda r: (r["hired"], r["sourced"]), reverse=True)


def _attainment_status(actual: int, target: int, assigned_at, deadline, now: datetime) -> str:
    """met / on_track / at_risk / missed / no_deadline via a simple burn-down."""
    if actual >= target:
        return "met"
    deadline_dt = _parse(deadline)
    if deadline_dt is None:
        return "no_deadline"
    if now > deadline_dt:
        return "missed"
    remaining = target - actual
    days_left = max(_days_between(now, deadline_dt) or 0, 1)
    days_elapsed = max(_days_between(_parse(assigned_at), now) or 0, 1)
    observed_rate = actual / days_elapsed          # per day achieved so far
    required_rate = remaining / days_left          # per day still needed
    return "on_track" if observed_rate >= required_rate else "at_risk"


def target_attainment(assignments, candidates, transitions_by_cand, now: datetime) -> list:
    """Per assignment: actual-vs-target for each target that was set. A target
    left null is omitted (its panel is hidden), never shown as 0."""
    # Pre-bucket candidates by (job, recruiter) once.
    by_job_rec: dict = {}
    for c in candidates:
        by_job_rec.setdefault((c.get("job_id"), c.get("sourced_by")), []).append(c)

    rows = []
    for a in assignments:
        targets = a.get("targets") or {}
        key = (a.get("job_id"), a.get("user_id"))
        cands = by_job_rec.get(key, [])
        sourced_actual = len(cands)
        shortlist_actual = sum(1 for c in cands if furthest_index(c, transitions_by_cand) >= SHORTLISTED_IDX)

        metrics = []
        for kind, actual, target in (
            ("sourced", sourced_actual, targets.get("sourced_target")),
            ("shortlist", shortlist_actual, targets.get("shortlist_target")),
        ):
            if target is None:
                continue  # null target -> hidden, not zero
            metrics.append({
                "kind": kind,
                "actual": actual,
                "target": target,
                "pct": round((actual / target) * 100, 1) if target else None,
                "status": _attainment_status(actual, target, a.get("assigned_at"), a.get("deadline"), now),
            })
        if metrics:
            rows.append({
                "assignment_id": a.get("id"),
                "job_id": a.get("job_id"),
                "user_id": a.get("user_id"),
                "deadline": a.get("deadline"),
                "metrics": metrics,
            })
    return rows


def deadline_health(assignments, now: datetime) -> list:
    """Assignments that carry a deadline, most-overdue first."""
    rows = []
    for a in assignments:
        deadline_dt = _parse(a.get("deadline"))
        if deadline_dt is None:
            continue
        days_remaining = _days_between(now, deadline_dt)
        rows.append({
            "assignment_id": a.get("id"),
            "job_id": a.get("job_id"),
            "user_id": a.get("user_id"),
            "deadline": a.get("deadline"),
            "days_remaining": days_remaining,
            "overdue": days_remaining is not None and days_remaining < 0,
        })
    # Most overdue (smallest / most negative days_remaining) first.
    return sorted(rows, key=lambda r: (r["days_remaining"] if r["days_remaining"] is not None else 10 ** 9))


def workload_balance(recruiter_ids, assignments, candidates) -> list:
    """Open assignments and live candidate load per recruiter — surfaces both
    overload and idleness."""
    open_by_rec = {rid: 0 for rid in recruiter_ids}
    for a in assignments:
        rid = a.get("user_id")
        if rid in open_by_rec:
            open_by_rec[rid] += 1
    active_by_rec = {rid: 0 for rid in recruiter_ids}
    for c in candidates:
        rid = c.get("sourced_by")
        if rid in active_by_rec and c.get("stage") not in (HIRED_STAGE, REJECTED_STAGE):
            active_by_rec[rid] += 1
    return [
        {"user_id": rid, "open_assignments": open_by_rec[rid], "active_candidates": active_by_rec[rid]}
        for rid in recruiter_ids
    ]


def insights(throughput, attainment, deadlines, now: datetime) -> list:
    """Deterministic, rule-based lines (instant, free, identical for identical
    data). Each has a tone the UI colours: positive / attention / neutral."""
    out = []

    overdue = [d for d in deadlines if d["overdue"]]
    if overdue:
        out.append({
            "tone": "attention",
            "text": f"{len(overdue)} assignment{'s are' if len(overdue) != 1 else ' is'} past its deadline.",
        })

    at_risk = [r for r in attainment for m in r["metrics"] if m["status"] == "at_risk"]
    if at_risk:
        out.append({
            "tone": "attention",
            "text": f"{len(at_risk)} target{'s are' if len(at_risk) != 1 else ' is'} at risk of being missed by the deadline.",
        })

    hires = sum(r["hired"] for r in throughput)
    if hires:
        out.append({
            "tone": "positive",
            "text": f"Your team has made {hires} hire{'s' if hires != 1 else ''} in this range.",
        })

    idle = [w for w in throughput if w["sourced"] == 0]
    if idle and len(idle) != len(throughput):
        out.append({
            "tone": "attention",
            "text": f"{len(idle)} recruiter{'s have' if len(idle) != 1 else ' has'} sourced no candidates in this range.",
        })

    return out


# ---------------------------------------------------------------------------
# Phase 14b panels
# ---------------------------------------------------------------------------

STALE_DAYS = 14


def quality_of_sourcing(recruiter_ids, candidates, transitions_by_cand) -> list:
    """Conversion quality per recruiter — the signal that matters more than raw
    volume. `reject_after_screen_rate` is share of shortlisted who ended Rejected."""
    by_rec = {rid: [] for rid in recruiter_ids}
    for c in candidates:
        if c.get("sourced_by") in by_rec:
            by_rec[c["sourced_by"]].append(c)

    rows = []
    for rid, cands in by_rec.items():
        sourced = len(cands)
        shortlisted = sum(1 for c in cands if furthest_index(c, transitions_by_cand) >= SHORTLISTED_IDX)
        interviewed = sum(1 for c in cands if furthest_index(c, transitions_by_cand) >= INTERVIEW_IDX)
        hired = sum(1 for c in cands if c.get("stage") == HIRED_STAGE)
        rejected_after_screen = sum(
            1 for c in cands
            if furthest_index(c, transitions_by_cand) >= SHORTLISTED_IDX and c.get("stage") == REJECTED_STAGE
        )
        rows.append({
            "user_id": rid,
            "sourced": sourced,
            "shortlist_rate": _pct(shortlisted, sourced),
            "interview_rate": _pct(interviewed, sourced),
            "hire_rate": _pct(hired, sourced),
            "reject_after_screen_rate": _pct(rejected_after_screen, shortlisted),
        })
    return sorted(rows, key=lambda r: r["sourced"], reverse=True)


def roles_needing_attention(jobs, assignments_by_job, cands_by_job, last_activity_by_job, now) -> list:
    """Open, unfilled roles that need a decision: unassigned, stalled 14+ days,
    past a deadline, or with no candidates. The manager's 'what to do next' list."""
    rows = []
    for job in jobs:
        if job.get("status") != "active":
            continue
        cands = cands_by_job.get(job["id"], [])
        hired = sum(1 for c in cands if c.get("stage") == HIRED_STAGE)
        needed = job.get("openings_needed") or 1
        if hired >= needed:
            continue  # filled

        assigns = assignments_by_job.get(job["id"], [])
        reasons = []
        if not assigns:
            reasons.append("unassigned")
        last = last_activity_by_job.get(job["id"]) or _parse(job.get("created_at"))
        idle = _days_between(last, now)
        if idle is not None and idle >= STALE_DAYS:
            reasons.append(f"no movement in {idle} days")
        if any((_parse(a.get("deadline")) and now > _parse(a.get("deadline"))) for a in assigns):
            reasons.append("past deadline")
        if not cands:
            reasons.append("no candidates")

        if reasons:
            rows.append({
                "job_id": job["id"], "reasons": reasons, "idle_days": idle,
                "hired": hired, "needed": needed,
            })
    return sorted(rows, key=lambda r: (r["idle_days"] if r["idle_days"] is not None else -1), reverse=True)


def activity_summary(recruiter_ids, activity_events, now, window_days=30) -> list:
    """Events per recruiter over the window, plus their last-active timestamp."""
    from datetime import timedelta
    cutoff = now - timedelta(days=window_days)
    counts = {rid: 0 for rid in recruiter_ids}
    last = {rid: None for rid in recruiter_ids}
    for e in activity_events:
        rid = e.get("actor_id")
        if rid not in counts:
            continue
        ts = _parse(e.get("created_at"))
        if ts is None:
            continue
        if ts >= cutoff:
            counts[rid] += 1
        prev = _parse(last[rid])
        if prev is None or ts > prev:
            last[rid] = e.get("created_at")
    return [{"user_id": rid, "events": counts[rid], "last_active": last[rid]} for rid in recruiter_ids]
