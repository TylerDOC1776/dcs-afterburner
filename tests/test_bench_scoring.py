from __future__ import annotations

import pytest

from afterburner.bench.scoring import MissionScorer


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _result(**overrides) -> dict:
    base = {
        "avg_fps": 60.0,
        "low_1pct_fps": 45.0,
        "low_01pct_fps": 40.0,
        "avg_frametime_ms": 16.67,
        "frametime_stdev_ms": 1.0,
        "load_and_run_time": 120.0,
        "sample_count": 1000,
        "mission": "test.miz",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# get_score_band
# ---------------------------------------------------------------------------

def test_band_low_risk_at_92():
    assert MissionScorer().get_score_band(92.0) == "LOW RISK"


def test_band_low_risk_at_100():
    assert MissionScorer().get_score_band(100.0) == "LOW RISK"


def test_band_moderate():
    s = MissionScorer()
    assert s.get_score_band(75.0) == "MODERATE"
    assert s.get_score_band(91.9) == "MODERATE"


def test_band_high():
    s = MissionScorer()
    assert s.get_score_band(50.0) == "HIGH"
    assert s.get_score_band(74.9) == "HIGH"


def test_band_critical():
    s = MissionScorer()
    assert s.get_score_band(0.0) == "CRITICAL"
    assert s.get_score_band(49.9) == "CRITICAL"


# ---------------------------------------------------------------------------
# calculate_score — structure
# ---------------------------------------------------------------------------

def test_calculate_score_returns_required_keys():
    result = MissionScorer().calculate_score(_result())
    assert "score" in result
    assert "band" in result
    assert set(result["breakdown"]) >= {"stability", "fps", "1_percent_low", "load"}


def test_calculate_score_band_matches_score():
    s = MissionScorer()
    r = s.calculate_score(_result())
    assert r["band"] == s.get_score_band(r["score"])


# ---------------------------------------------------------------------------
# calculate_score — sensitivity
# ---------------------------------------------------------------------------

def test_higher_fps_raises_score():
    s = MissionScorer()
    assert s.calculate_score(_result(avg_fps=60.0))["score"] > \
           s.calculate_score(_result(avg_fps=20.0))["score"]


def test_lower_stdev_raises_score():
    s = MissionScorer()
    assert s.calculate_score(_result(frametime_stdev_ms=1.0))["score"] > \
           s.calculate_score(_result(frametime_stdev_ms=18.0))["score"]


def test_higher_low_1pct_raises_score():
    s = MissionScorer()
    assert s.calculate_score(_result(low_1pct_fps=45.0))["score"] > \
           s.calculate_score(_result(low_1pct_fps=5.0))["score"]


def test_shorter_load_time_raises_score():
    s = MissionScorer()
    assert s.calculate_score(_result(load_time_s=60.0))["score"] > \
           s.calculate_score(_result(load_time_s=290.0))["score"]


def test_missing_load_time_s_uses_neutral_placeholder():
    s = MissionScorer()
    # load_time_s=60 is defined as the 100-point neutral baseline
    with_load    = s.calculate_score(_result(load_time_s=60.0))
    without_load = s.calculate_score(_result())  # no load_time_s key
    assert with_load["breakdown"]["load"] == without_load["breakdown"]["load"]


def test_none_fps_fields_give_zero_fps_component():
    s = MissionScorer()
    result = s.calculate_score({"avg_fps": None, "low_1pct_fps": None, "frametime_stdev_ms": None})
    assert result["breakdown"]["fps"] == 0.0
    assert result["breakdown"]["1_percent_low"] == 0.0


def test_score_capped_at_100():
    s = MissionScorer()
    r = s.calculate_score(_result(avg_fps=999.0, low_1pct_fps=999.0, frametime_stdev_ms=0.0))
    assert r["score"] <= 100.0


def test_score_non_negative():
    s = MissionScorer()
    r = s.calculate_score(_result(avg_fps=0.0, low_1pct_fps=0.0, frametime_stdev_ms=20.0))
    assert r["score"] >= 0.0


# ---------------------------------------------------------------------------
# aggregate_passes
# ---------------------------------------------------------------------------

def test_aggregate_passes_empty_raises():
    with pytest.raises(ValueError, match="at least one result"):
        MissionScorer().aggregate_passes([])


def test_aggregate_passes_single_pass():
    s = MissionScorer()
    agg = s.aggregate_passes([_result()])
    assert agg["summary"]["avg_fps"] == pytest.approx(60.0)
    assert agg["summary"]["pass_count"] == 1
    assert "per_metric" in agg
    assert "confidence" in agg


def test_aggregate_passes_mean_of_two():
    s = MissionScorer()
    agg = s.aggregate_passes([_result(avg_fps=50.0), _result(avg_fps=70.0)])
    assert agg["summary"]["avg_fps"] == pytest.approx(60.0)


def test_aggregate_passes_none_values_excluded_from_stats():
    s = MissionScorer()
    agg = s.aggregate_passes([_result(avg_fps=None), _result(avg_fps=60.0)])
    assert agg["per_metric"]["avg_fps"]["passes"] == 1
    assert agg["summary"]["avg_fps"] == pytest.approx(60.0)


def test_aggregate_passes_all_none_for_key():
    s = MissionScorer()
    agg = s.aggregate_passes([_result(avg_fps=None)])
    assert agg["per_metric"]["avg_fps"]["mean"] is None
    assert agg["summary"]["avg_fps"] is None


def test_aggregate_passes_preserves_mission_from_first():
    s = MissionScorer()
    agg = s.aggregate_passes([_result(mission="first.miz"), _result(mission="second.miz")])
    assert agg["summary"]["mission"] == "first.miz"


# ---------------------------------------------------------------------------
# _confidence_rating
# ---------------------------------------------------------------------------

def test_confidence_high_five_passes_low_cv():
    s = MissionScorer()
    pm = {"avg_fps": {"mean": 60.0, "stdev": 0.5}}  # CV ~0.8 %
    assert s._confidence_rating(5, pm) == "HIGH"


def test_confidence_medium_three_passes_moderate_cv():
    s = MissionScorer()
    pm = {"avg_fps": {"mean": 60.0, "stdev": 3.0}}  # CV = 5 %
    assert s._confidence_rating(3, pm) == "MEDIUM"


def test_confidence_low_too_few_passes():
    s = MissionScorer()
    pm = {"avg_fps": {"mean": 60.0, "stdev": 0.1}}
    assert s._confidence_rating(2, pm) == "LOW"


def test_confidence_low_high_variance():
    s = MissionScorer()
    pm = {"avg_fps": {"mean": 60.0, "stdev": 15.0}}  # CV = 25 %
    assert s._confidence_rating(5, pm) == "LOW"


def test_confidence_zero_mean_returns_low():
    s = MissionScorer()
    pm = {"avg_fps": {"mean": 0, "stdev": 0}}
    assert s._confidence_rating(5, pm) == "LOW"


def test_confidence_missing_avg_fps_returns_low():
    s = MissionScorer()
    assert s._confidence_rating(5, {}) == "LOW"


# ---------------------------------------------------------------------------
# score_aggregated
# ---------------------------------------------------------------------------

def test_score_aggregated_attaches_confidence_and_pass_count():
    s = MissionScorer()
    agg = s.aggregate_passes([_result()] * 3)
    scored = s.score_aggregated(agg)
    assert "confidence" in scored
    assert scored["pass_count"] == 3
    assert "score" in scored
    assert "band" in scored


def test_score_aggregated_uses_mean_values():
    s = MissionScorer()
    single = s.calculate_score(_result())
    agg    = s.aggregate_passes([_result()] * 3)
    scored = s.score_aggregated(agg)
    assert scored["score"] == pytest.approx(single["score"], rel=1e-3)
