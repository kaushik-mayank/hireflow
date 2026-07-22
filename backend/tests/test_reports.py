"""Tests for the hiring analytics computations.

These are the numbers an HR user makes decisions on, so the arithmetic needs to
be right and the edge cases (no data, one candidate, everyone rejected) must
not produce nonsense or crash.

Pure functions only — no database, no network.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="module")
def rp():
    """Import routes_reports with no FastAPI, database or network available.

    The analytics are pure functions on plain dicts; only the module-level
    router declaration needs FastAPI, so a minimal stub is enough. This keeps
    the suite runnable on a machine with no backend dependencies installed.
    """
    import types

    class _APIRouter:
        def __init__(self, **kwargs):
            pass

        def _decorator(self, *args, **kwargs):
            return lambda fn: fn

        get = post = put = delete = _decorator

    # Merge into any stub another test module already installed rather than
    # skipping when the name exists — otherwise whichever suite runs first
    # decides which attributes are available to the rest.
    def stub(name, **attrs):
        module = sys.modules.get(name) or types.ModuleType(name)
        for key, value in attrs.items():
            if not hasattr(module, key):
                setattr(module, key, value)
        sys.modules[name] = module

    stub("fastapi", APIRouter=_APIRouter, Depends=lambda dependency=None: None)
    stub("database", jobs=None, candidates=None, stage_transitions=None)
    stub("auth", get_current_user=None)

    import routes_reports
    return routes_reports


NOW = datetime.now(timezone.utc)


def iso(days_ago):
    return (NOW - timedelta(days=days_ago)).isoformat()


def cand(cid, job="j1", stage="Applied", uploaded=10, score=None, source=None, analyzed=True):
    return {
        "id": cid, "job_id": job, "stage": stage, "uploaded_at": iso(uploaded),
        "ai_score": score, "source": source,
        "analyzed_at": iso(uploaded - 1) if analyzed else None,
    }


def job(jid="j1", title="Some Role", status="active", needed=1, created=60, updated=5):
    return {
        "id": jid, "title": title, "status": status, "openings_needed": needed,
        "created_at": iso(created), "updated_at": iso(updated),
    }


# ---------------------------------------------------------------------------
# Empty and low-data states must not break
# ---------------------------------------------------------------------------

def test_all_computations_survive_no_data(rp):
    tth = rp._time_to_hire([], {}, {})
    assert tth["overall_avg"] is None and tth["total_hires"] == 0

    funnel = rp._funnel([], {})
    assert len(funnel) == len(rp.FUNNEL_STAGES)
    assert all(row["count"] == 0 for row in funnel)

    assert rp._biggest_drop_off(funnel) is None
    assert rp._source_effectiveness([]) == []
    assert rp._aging_postings([], {}, {}) == []
    assert rp._quota_tracker([], {}) == []
    assert rp._insights(tth, funnel, [], [], [], 0, 0) == []


def test_percentages_never_divide_by_zero(rp):
    assert rp._pct(0, 0) == 0.0
    assert rp._pct(5, 0) == 0.0
    assert rp._pct(1, 3) == 33.3


def test_naive_timestamps_do_not_crash_comparisons(rp):
    """Older rows may lack timezone info; mixing them would raise TypeError."""
    naive = rp._parse("2026-01-01T00:00:00")
    assert naive is not None and naive.tzinfo is not None
    assert rp._days_between(naive, NOW) >= 0


@pytest.mark.parametrize("bad", [None, "", "not-a-date", 12345])
def test_unparseable_dates_return_none(rp, bad):
    assert rp._parse(bad) is None


# ---------------------------------------------------------------------------
# Time to hire
# ---------------------------------------------------------------------------

def test_time_to_hire_measures_upload_to_selected(rp):
    jobs = [job("j1", "Role A", needed=2)]
    cands = {"j1": [cand("c1", stage="Selected", uploaded=30),
                    cand("c2", stage="Selected", uploaded=20)]}
    hires = {"c1": NOW - timedelta(days=10), "c2": NOW - timedelta(days=5)}

    tth = rp._time_to_hire(jobs, cands, hires)
    # c1: 30 -> 10 = 20 days. c2: 20 -> 5 = 15 days. Mean 17.5.
    assert tth["per_job"][0]["avg_days"] == 17.5
    assert tth["per_job"][0]["hires"] == 2
    assert tth["overall_avg"] == 17.5
    assert tth["total_hires"] == 2


def test_time_to_hire_ignores_candidates_who_were_not_hired(rp):
    jobs = [job("j1")]
    cands = {"j1": [cand("c1", stage="Rejected"), cand("c2", stage="Interview Done")]}
    tth = rp._time_to_hire(jobs, cands, {})
    assert tth["per_job"] == [] and tth["overall_avg"] is None


def test_time_to_hire_skips_hires_with_no_recorded_transition(rp):
    """A Selected candidate with no transition row cannot be timed honestly."""
    jobs = [job("j1")]
    cands = {"j1": [cand("c1", stage="Selected", uploaded=30)]}
    tth = rp._time_to_hire(jobs, cands, {})  # no hire event
    assert tth["total_hires"] == 0


def test_time_to_hire_splits_recent_from_previous_for_trend(rp):
    jobs = [job("j1")]
    cands = {"j1": [cand("c1", stage="Selected", uploaded=90),
                    cand("c2", stage="Selected", uploaded=20)]}
    hires = {
        "c1": NOW - timedelta(days=60),   # older than the 30-day window
        "c2": NOW - timedelta(days=5),    # inside it
    }
    tth = rp._time_to_hire(jobs, cands, hires)
    assert tth["recent_avg"] == 15.0     # 20 -> 5
    assert tth["previous_avg"] == 30.0   # 90 -> 60


# ---------------------------------------------------------------------------
# Funnel
# ---------------------------------------------------------------------------

def test_funnel_counts_furthest_stage_reached_not_current(rp):
    """A rejected candidate who got to interview still counts at every earlier
    stage — otherwise the funnel understates how far people actually got."""
    rejected_late = cand("c1", stage="Rejected")
    transitions = {"c1": [{"from_stage": "Shortlisted", "to_stage": "Interview Done"}]}

    funnel = rp._funnel([rejected_late], transitions)
    by_stage = {r["stage"]: r["count"] for r in funnel}
    assert by_stage["Applied"] == 1
    assert by_stage["Interview Done"] == 1
    assert by_stage["Selected"] == 0


def test_funnel_is_monotonically_non_increasing(rp):
    cands = [cand("c1", stage="Selected"), cand("c2", stage="Shortlisted"),
             cand("c3", stage="Applied"), cand("c4", stage="Interview Scheduled")]
    funnel = rp._funnel(cands, {})
    counts = [r["count"] for r in funnel]
    assert counts == sorted(counts, reverse=True), "a funnel cannot widen"
    assert counts[0] == 4


def test_funnel_reports_drop_off_between_stages(rp):
    cands = [cand("c1", stage="Applied"), cand("c2", stage="Applied"),
             cand("c3", stage="Shortlisted")]
    funnel = rp._funnel(cands, {})
    by_stage = {r["stage"]: r for r in funnel}
    assert by_stage["Applied"]["count"] == 3
    assert by_stage["AI Ranked"]["count"] == 1
    assert by_stage["AI Ranked"]["drop_off"] == 2
    assert by_stage["AI Ranked"]["drop_off_pct"] == pytest.approx(66.7, abs=0.1)
    assert by_stage["Applied"]["conversion_from_previous"] is None


def test_biggest_drop_off_identifies_the_worst_transition(rp):
    cands = ([cand(f"a{i}", stage="AI Ranked") for i in range(10)]
             + [cand("b1", stage="Shortlisted")])
    worst = rp._biggest_drop_off(rp._funnel(cands, {}))
    assert worst["from_stage"] == "AI Ranked"
    assert worst["to_stage"] == "Shortlisted"
    assert worst["lost"] == 10


def test_on_hold_and_rejected_are_not_funnel_steps(rp):
    """They are outcomes, not stages candidates progress through."""
    assert "Rejected" not in rp.FUNNEL_STAGES
    assert "On Hold" not in rp.FUNNEL_STAGES
    assert rp.FUNNEL_STAGES[-1] == "Selected"


# ---------------------------------------------------------------------------
# Source effectiveness
# ---------------------------------------------------------------------------

def test_source_effectiveness_computes_hire_rate_per_channel(rp):
    cands = [
        cand("c1", stage="Selected", source="Referral", score=90),
        cand("c2", stage="Rejected", source="Referral", score=50),
        cand("c3", stage="Rejected", source="Job board", score=40),
        cand("c4", stage="Rejected", source="Job board", score=30),
    ]
    rows = {r["source"]: r for r in rp._source_effectiveness(cands)}
    assert rows["Referral"]["hire_rate"] == 50.0
    assert rows["Referral"]["avg_score"] == 70
    assert rows["Job board"]["hire_rate"] == 0.0


@pytest.mark.parametrize("missing", [None, "", "   "])
def test_candidates_without_a_source_group_under_unknown(rp, missing):
    """Existing records predate the source field and must not be dropped."""
    rows = rp._source_effectiveness([cand("c1", source=missing)])
    assert rows[0]["source"] == rp.UNKNOWN_SOURCE
    assert rows[0]["candidates"] == 1


def test_avg_score_is_none_when_nothing_is_ranked_yet(rp):
    rows = rp._source_effectiveness([cand("c1", source="Referral", score=None)])
    assert rows[0]["avg_score"] is None


# ---------------------------------------------------------------------------
# Aging postings
# ---------------------------------------------------------------------------

def test_aging_flags_only_stale_open_unfilled_postings(rp):
    jobs = [
        job("stale", "Stale Role", needed=1, created=90),
        job("fresh", "Fresh Role", needed=1, created=90),
        job("closed", "Closed Role", status="closed", created=90),
        job("filled", "Filled Role", needed=1, created=90),
    ]
    cands_by_job = {
        "stale": [cand("c1", job="stale")],
        "fresh": [cand("c2", job="fresh")],
        "closed": [],
        "filled": [cand("c3", job="filled", stage="Selected")],
    }
    last_activity = {
        "stale": NOW - timedelta(days=40),
        "fresh": NOW - timedelta(days=2),
        "filled": NOW - timedelta(days=40),
    }
    flagged = {r["job_id"] for r in rp._aging_postings(jobs, cands_by_job, last_activity)}
    assert flagged == {"stale"}, "only open, unfilled, inactive postings should flag"


def test_aging_marks_postings_with_no_candidates(rp):
    jobs = [job("empty", "Empty Role", created=60)]
    rows = rp._aging_postings(jobs, {"empty": []}, {})
    assert rows[0]["no_candidates"] is True
    assert rows[0]["candidates"] == 0


def test_aging_sorted_by_longest_idle_first(rp):
    jobs = [job("a", "A", created=90), job("b", "B", created=90)]
    cands_by_job = {"a": [cand("c1", job="a")], "b": [cand("c2", job="b")]}
    last_activity = {"a": NOW - timedelta(days=20), "b": NOW - timedelta(days=50)}
    rows = rp._aging_postings(jobs, cands_by_job, last_activity)
    assert [r["job_id"] for r in rows] == ["b", "a"]


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

def test_insight_reports_time_to_hire_direction(rp):
    tth = {"overall_avg": 18.0, "total_hires": 4, "recent_avg": 18.0,
           "previous_avg": 24.0, "per_job": []}
    text = rp._insights(tth, rp._funnel([], {}), [], [], [], 0, 0)[0]
    assert "18 days" in text["text"] and "down from 24 days" in text["text"]
    assert text["tone"] == "positive"


def test_rising_time_to_hire_is_flagged_for_attention(rp):
    tth = {"overall_avg": 30.0, "total_hires": 4, "recent_avg": 30.0,
           "previous_avg": 20.0, "per_job": []}
    assert rp._insights(tth, rp._funnel([], {}), [], [], [], 0, 0)[0]["tone"] == "attention"


def test_source_insight_suppressed_on_a_tiny_sample(rp):
    """One hire from one candidate is not a 100% conversion rate worth reporting."""
    tth = {"overall_avg": None, "total_hires": 0, "recent_avg": None,
           "previous_avg": None, "per_job": []}
    tiny = rp._source_effectiveness([cand("c1", stage="Selected", source="Referral")])
    texts = [i["text"] for i in rp._insights(tth, rp._funnel([], {}), [], tiny, [], 1, 0)]
    assert not any("converting best" in t for t in texts)


def test_every_insight_has_a_known_tone(rp):
    cands = [cand(f"c{i}", stage="AI Ranked") for i in range(10)]
    funnel = rp._funnel(cands, {})
    tth = {"overall_avg": 20.0, "total_hires": 3, "recent_avg": 20.0,
           "previous_avg": 25.0, "per_job": []}
    aging = [{"job": "X", "days_since_activity": 30, "no_candidates": False}]
    quota = [{"complete": True}]
    for insight in rp._insights(tth, funnel, aging, [], quota, len(cands), 4):
        assert insight["tone"] in {"positive", "attention", "neutral"}
        assert insight["text"].strip()


# ---------------------------------------------------------------------------
# Quota
# ---------------------------------------------------------------------------

def test_quota_tracker_counts_hired_and_active_pipeline(rp):
    jobs = [job("j1", "Role", needed=3)]
    cands_by_job = {"j1": [
        cand("c1", stage="Selected"), cand("c2", stage="Rejected"),
        cand("c3", stage="Shortlisted"),
    ]}
    row = rp._quota_tracker(jobs, cands_by_job)[0]
    assert row["hired"] == 1
    assert row["in_pipeline"] == 1      # Rejected excluded
    assert row["remaining"] == 2
    assert row["complete"] is False


def test_quota_marks_complete_when_target_met(rp):
    jobs = [job("j1", "Role", needed=1)]
    row = rp._quota_tracker(jobs, {"j1": [cand("c1", stage="Selected")]})[0]
    assert row["complete"] is True and row["remaining"] == 0


def test_no_fabricated_completion_estimate_is_returned(rp):
    """The old tracker invented `est_completion` as now + 14 days per remaining
    hire. It was the only fake number on the page and is gone."""
    row = rp._quota_tracker([job("j1", needed=5)], {"j1": []})[0]
    assert "est_completion" not in row
