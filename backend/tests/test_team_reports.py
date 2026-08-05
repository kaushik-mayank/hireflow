"""Tests for the manager team-report computations (team_reports.py).

Pure functions on plain dicts — no DB, no network. Follows the Cycle-1 report
discipline: every metric gets a zero-data, single-item, divide-by-zero,
naive-vs-aware-timestamp, and candidate-predating-the-field case.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import team_reports as tr  # noqa: E402

NOW = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)


def iso(days_from_now):
    return (NOW + timedelta(days=days_from_now)).isoformat()


def cand(cid, rid, job="job-1", stage="Applied"):
    return {"id": cid, "sourced_by": rid, "job_id": job, "stage": stage, "uploaded_at": iso(-10)}


def assignment(rid, job="job-1", targets=None, deadline=None, assigned=-10, aid=None):
    return {
        "id": aid or f"as-{rid}-{job}", "org_id": "org-A", "job_id": job, "user_id": rid,
        "status": "active", "targets": targets or {}, "deadline": deadline, "assigned_at": iso(assigned),
    }


# ---------------------------------------------------------------------------
# _pct / helpers
# ---------------------------------------------------------------------------

def test_pct_suppressed_below_sample_and_divide_by_zero():
    assert tr._pct(3, 4) is None          # sample < 5
    assert tr._pct(0, 0) is None          # divide-by-zero never raises
    assert tr._pct(3, 10) == 30.0


def test_parse_handles_naive_and_aware():
    naive = "2026-08-01T00:00:00"          # no tz
    aware = "2026-08-01T00:00:00+00:00"
    assert tr._parse(naive).tzinfo is not None
    assert tr._parse(naive) == tr._parse(aware)
    assert tr._parse(None) is None
    assert tr._parse("not-a-date") is None


def test_furthest_index_uses_history_not_just_current():
    c = cand("c1", "r1", stage="Rejected")
    transitions = {"c1": [{"from_stage": "Shortlisted", "to_stage": "Interview Scheduled"}]}
    # Currently Rejected (not on the funnel) but reached Interview Scheduled.
    assert tr.furthest_index(c, transitions) == tr.INTERVIEW_IDX


# ---------------------------------------------------------------------------
# throughput_by_recruiter
# ---------------------------------------------------------------------------

def test_throughput_zero_data():
    assert tr.throughput_by_recruiter([], [], {}) == []
    rows = tr.throughput_by_recruiter(["r1"], [], {})
    assert rows == [{"user_id": "r1", "sourced": 0, "shortlisted": 0,
                     "interviewed": 0, "hired": 0, "shortlist_rate": None, "hire_rate": None}]


def test_throughput_single_item_no_rate():
    rows = tr.throughput_by_recruiter(["r1"], [cand("c1", "r1", stage="Selected")], {})
    r = rows[0]
    assert r["sourced"] == 1 and r["hired"] == 1
    assert r["hire_rate"] is None  # 1 < MIN_SAMPLE, no percentage claim


def test_throughput_rates_appear_at_sample_threshold():
    cands = [cand(f"c{i}", "r1", stage="Selected" if i < 2 else "Applied") for i in range(5)]
    rows = tr.throughput_by_recruiter(["r1"], cands, {})
    assert rows[0]["sourced"] == 5
    assert rows[0]["hire_rate"] == 40.0  # 2/5, now above the sample floor


def test_throughput_ignores_unattributed_candidates():
    # A candidate predating sourced_by (None) is attributed to no one.
    cands = [cand("c1", None), cand("c2", "r1")]
    rows = tr.throughput_by_recruiter(["r1"], cands, {})
    assert rows[0]["sourced"] == 1


# ---------------------------------------------------------------------------
# target_attainment
# ---------------------------------------------------------------------------

def test_attainment_null_target_is_hidden():
    a = assignment("r1", targets={"sourced_target": None, "shortlist_target": None})
    rows = tr.target_attainment([a], [cand("c1", "r1")], {}, NOW)
    assert rows == []  # nothing to show, not a row of zeros


def test_attainment_met():
    a = assignment("r1", targets={"sourced_target": 2}, deadline=iso(5))
    cands = [cand("c1", "r1"), cand("c2", "r1")]
    rows = tr.target_attainment([a], cands, {}, NOW)
    m = rows[0]["metrics"][0]
    assert m["kind"] == "sourced" and m["actual"] == 2 and m["status"] == "met"


def test_attainment_missed_when_past_deadline():
    a = assignment("r1", targets={"sourced_target": 10}, deadline=iso(-1))
    rows = tr.target_attainment([a], [cand("c1", "r1")], {}, NOW)
    assert rows[0]["metrics"][0]["status"] == "missed"


def test_attainment_no_deadline():
    a = assignment("r1", targets={"sourced_target": 10}, deadline=None)
    rows = tr.target_attainment([a], [cand("c1", "r1")], {}, NOW)
    assert rows[0]["metrics"][0]["status"] == "no_deadline"


def test_attainment_on_track_vs_at_risk():
    # Assigned 10 days ago, 5 days left. sourced_target 20.
    # on_track: 15 sourced so far (rate 1.5/day) vs required (20-15)/5 = 1.0/day.
    on = assignment("r1", targets={"sourced_target": 20}, deadline=iso(5), assigned=-10, aid="on")
    on_cands = [cand(f"c{i}", "r1") for i in range(15)]
    assert tr.target_attainment([on], on_cands, {}, NOW)[0]["metrics"][0]["status"] == "on_track"
    # at_risk: only 2 sourced (rate 0.2/day) vs required (20-2)/5 = 3.6/day.
    ar = assignment("r2", targets={"sourced_target": 20}, deadline=iso(5), assigned=-10, aid="ar")
    ar_cands = [cand(f"d{i}", "r2") for i in range(2)]
    assert tr.target_attainment([ar], ar_cands, {}, NOW)[0]["metrics"][0]["status"] == "at_risk"


def test_attainment_naive_deadline_does_not_crash():
    a = assignment("r1", targets={"sourced_target": 5})
    a["deadline"] = "2026-09-01T00:00:00"  # naive, no tz
    a["assigned_at"] = "2026-08-01T00:00:00"
    rows = tr.target_attainment([a], [cand("c1", "r1")], {}, NOW)
    assert rows[0]["metrics"][0]["status"] in ("on_track", "at_risk")


# ---------------------------------------------------------------------------
# deadline_health
# ---------------------------------------------------------------------------

def test_deadline_health_orders_overdue_first_and_skips_no_deadline():
    a1 = assignment("r1", deadline=iso(3), aid="future")
    a2 = assignment("r2", deadline=iso(-5), aid="overdue")
    a3 = assignment("r3", deadline=None, aid="none")
    rows = tr.deadline_health([a1, a2, a3], NOW)
    assert [r["assignment_id"] for r in rows] == ["overdue", "future"]  # most overdue first, no-deadline excluded
    assert rows[0]["overdue"] is True and rows[1]["overdue"] is False


def test_deadline_health_zero_data():
    assert tr.deadline_health([], NOW) == []


# ---------------------------------------------------------------------------
# workload_balance
# ---------------------------------------------------------------------------

def test_workload_counts_open_and_active_only():
    assignments = [assignment("r1", job="j1", aid="a1"), assignment("r1", job="j2", aid="a2")]
    cands = [cand("c1", "r1", stage="Applied"), cand("c2", "r1", stage="Selected"),
             cand("c3", "r1", stage="Rejected")]
    rows = tr.workload_balance(["r1", "r2"], assignments, cands)
    r1 = next(r for r in rows if r["user_id"] == "r1")
    r2 = next(r for r in rows if r["user_id"] == "r2")
    assert r1["open_assignments"] == 2 and r1["active_candidates"] == 1  # hired+rejected excluded
    assert r2["open_assignments"] == 0 and r2["active_candidates"] == 0  # idle recruiter shown


# ---------------------------------------------------------------------------
# insights
# ---------------------------------------------------------------------------

def test_insights_flag_overdue_and_hires():
    throughput = [{"user_id": "r1", "sourced": 5, "hired": 2}]
    deadlines = [{"assignment_id": "a", "overdue": True}]
    lines = tr.insights(throughput, [], deadlines, NOW)
    text = " ".join(x["text"] for x in lines)
    assert "past its deadline" in text and "2 hire" in text


def test_insights_empty_on_no_data():
    assert tr.insights([], [], [], NOW) == []


# ---------------------------------------------------------------------------
# quality_of_sourcing
# ---------------------------------------------------------------------------

def test_quality_zero_data():
    rows = tr.quality_of_sourcing(["r1"], [], {})
    assert rows[0]["sourced"] == 0 and rows[0]["shortlist_rate"] is None


def test_quality_reject_after_screen():
    # 6 sourced, all shortlisted (via history); 3 later Rejected.
    cands, trans = [], {}
    for i in range(6):
        cid = f"c{i}"
        cands.append(cand(cid, "r1", stage="Rejected" if i < 3 else "Shortlisted"))
        trans[cid] = [{"from_stage": "AI Ranked", "to_stage": "Shortlisted"}]
    rows = tr.quality_of_sourcing(["r1"], cands, trans)
    assert rows[0]["shortlist_rate"] == 100.0
    assert rows[0]["reject_after_screen_rate"] == 50.0  # 3 of 6 shortlisted rejected


# ---------------------------------------------------------------------------
# roles_needing_attention
# ---------------------------------------------------------------------------

def test_roles_flags_unassigned_and_stale_skips_filled():
    jobs = [
        {"id": "j1", "status": "active", "openings_needed": 1, "created_at": iso(-40)},   # stale + unassigned + no cands
        {"id": "j2", "status": "active", "openings_needed": 1, "created_at": iso(-40)},   # filled -> excluded
        {"id": "j3", "status": "closed", "openings_needed": 1, "created_at": iso(-40)},   # not active -> excluded
    ]
    cands_by_job = {"j2": [cand("c1", "r1", job="j2", stage="Selected")]}
    rows = tr.roles_needing_attention(jobs, {}, cands_by_job, {}, NOW)
    ids = {r["job_id"] for r in rows}
    assert ids == {"j1"}
    assert "unassigned" in rows[0]["reasons"] and "no candidates" in rows[0]["reasons"]


def test_roles_past_deadline():
    jobs = [{"id": "j1", "status": "active", "openings_needed": 1, "created_at": iso(-1)}]
    assignments_by_job = {"j1": [assignment("r1", job="j1", deadline=iso(-3))]}
    cands_by_job = {"j1": [cand("c1", "r1", job="j1")]}
    last_activity = {"j1": tr._parse(iso(-1))}
    rows = tr.roles_needing_attention(jobs, assignments_by_job, cands_by_job, last_activity, NOW)
    assert "past deadline" in rows[0]["reasons"]


# ---------------------------------------------------------------------------
# activity_summary
# ---------------------------------------------------------------------------

def test_activity_summary_window_and_last_active():
    events = [
        {"actor_id": "r1", "created_at": iso(-2)},
        {"actor_id": "r1", "created_at": iso(-40)},   # outside 30d window
        {"actor_id": "other", "created_at": iso(-1)}, # not a tracked recruiter
    ]
    rows = tr.activity_summary(["r1"], events, NOW, window_days=30)
    r1 = rows[0]
    assert r1["events"] == 1                       # only the in-window one counts
    assert r1["last_active"] == iso(-2)            # most recent overall
