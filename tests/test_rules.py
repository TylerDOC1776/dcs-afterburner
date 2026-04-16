"""Tests for the rule engine — builds Mission objects directly."""

from __future__ import annotations

import afterburner.rules  # noqa: F401 — register all rules
from afterburner.models.findings import Severity
from afterburner.models.mission import (
    Category,
    Group,
    Mission,
    MissionSummary,
    Unit,
)
from afterburner.models.report import Report


def _make_summary(**kwargs) -> MissionSummary:
    defaults = dict(
        theatre="Caucasus",
        total_units=0,
        active_units=0,
        late_units=0,
        player_slots=0,
        total_groups=0,
        active_groups=0,
        total_statics=0,
        trigger_count=0,
        zone_count=0,
    )
    defaults.update(kwargs)
    return MissionSummary(**defaults)


def _make_mission(summary: MissionSummary | None = None, **kwargs) -> Mission:
    return Mission(
        name="Test",
        source_file="test.miz",
        sha256="sha256:abc",
        theatre="Caucasus",
        summary=summary or _make_summary(),
        **kwargs,
    )


def _unit(uid: int = 1, name: str = "Unit1", skill: str = "High") -> Unit:
    return Unit(
        id=uid,
        name=name,
        type="F-16C_50",
        skill=skill,
        late_activation=False,
        x=0.0,
        y=0.0,
        is_player_slot=skill in ("Client", "Player"),
    )


def _group(
    gid: int = 1,
    name: str = "Group1",
    category: Category = Category.PLANE,
    coalition: str = "blue",
    units: list[Unit] | None = None,
    late_activation: bool = False,
    uncontrolled: bool = False,
) -> Group:
    return Group(
        id=gid,
        name=name,
        category=category,
        coalition=coalition,
        units=units or [_unit()],
        late_activation=late_activation,
        uncontrolled=uncontrolled,
    )


# ------------------------------------------------------------------
# Report / risk scoring
# ------------------------------------------------------------------


def test_risk_score_no_findings():
    report = Report(mission=_make_mission())
    assert report.risk_score() == 100
    assert report.risk_label() == "LOW"


def test_risk_score_critical():
    from afterburner.models.findings import ReportFinding

    report = Report(
        mission=_make_mission(),
        findings=[ReportFinding("X", Severity.CRITICAL, "t", "d")],
    )
    assert report.risk_score() == 85
    assert report.risk_label() == "MODERATE"


def test_risk_score_clamps_to_zero():
    from afterburner.models.findings import ReportFinding

    findings = [ReportFinding("X", Severity.CRITICAL, "t", "d")] * 10
    report = Report(mission=_make_mission(), findings=findings)
    assert report.risk_score() == 0
    assert report.risk_label() == "CRITICAL"


def test_risk_label_moderate():
    from afterburner.models.findings import ReportFinding

    findings = [ReportFinding("X", Severity.WARNING, "t", "d")] * 3
    report = Report(mission=_make_mission(), findings=findings)
    # 100 - (3 × 8) = 76 → MODERATE (≥75, <92)
    assert report.risk_score() == 76
    assert report.risk_label() == "MODERATE"


# ------------------------------------------------------------------
# BLOT_001 — active units
# ------------------------------------------------------------------


def test_blot001_no_finding_below_threshold():
    from afterburner.rules.mission_size import ActiveUnitCount

    m = _make_mission(_make_summary(active_units=300))
    assert ActiveUnitCount().check(m) == []


def test_blot001_warning_above_350():
    from afterburner.rules.mission_size import ActiveUnitCount

    m = _make_mission(_make_summary(active_units=400))
    findings = ActiveUnitCount().check(m)
    assert len(findings) == 1
    assert findings[0].severity == Severity.WARNING
    assert findings[0].rule_id == "BLOT_001"


def test_blot001_critical_above_600():
    from afterburner.rules.mission_size import ActiveUnitCount

    m = _make_mission(_make_summary(active_units=700))
    findings = ActiveUnitCount().check(m)
    assert findings[0].severity == Severity.CRITICAL


# ------------------------------------------------------------------
# BLOT_002 — statics
# ------------------------------------------------------------------


def test_blot002_warning_above_500():
    from afterburner.rules.mission_size import StaticObjectCount

    m = _make_mission(_make_summary(total_statics=600))
    findings = StaticObjectCount().check(m)
    assert len(findings) == 1
    assert findings[0].severity == Severity.WARNING


def test_blot002_critical_above_800():
    from afterburner.rules.mission_size import StaticObjectCount

    m = _make_mission(_make_summary(total_statics=900))
    assert StaticObjectCount().check(m)[0].severity == Severity.CRITICAL


# ------------------------------------------------------------------
# BLOT_003 — triggers
# ------------------------------------------------------------------


def test_blot003_warning_above_150():
    from afterburner.rules.mission_size import TriggerCount

    m = _make_mission(_make_summary(trigger_count=200))
    assert TriggerCount().check(m)[0].severity == Severity.WARNING


def test_blot003_no_finding_at_150():
    from afterburner.rules.mission_size import TriggerCount

    m = _make_mission(_make_summary(trigger_count=150))
    assert TriggerCount().check(m) == []


# ------------------------------------------------------------------
# BLOT_004 — zones
# ------------------------------------------------------------------


def test_blot004_warning_above_90():
    from afterburner.rules.mission_size import ZoneCount

    m = _make_mission(_make_summary(zone_count=91))
    assert ZoneCount().check(m)[0].severity == Severity.WARNING


# ------------------------------------------------------------------
# BLOT_005 — player slots
# ------------------------------------------------------------------


def test_blot005_warning_above_80():
    from afterburner.rules.mission_size import PlayerSlotCount

    m = _make_mission(_make_summary(player_slots=81))
    assert PlayerSlotCount().check(m)[0].severity == Severity.WARNING


# ------------------------------------------------------------------
# BLOT_008 — total units
# ------------------------------------------------------------------


def test_blot008_warning_above_1200():
    from afterburner.rules.mission_size import TotalUnitCount

    m = _make_mission(_make_summary(total_units=1300))
    assert TotalUnitCount().check(m)[0].severity == Severity.WARNING


# ------------------------------------------------------------------
# PERF_003 — uncontrolled aircraft
# ------------------------------------------------------------------


def test_perf003_no_finding_below_threshold():
    from afterburner.rules.performance import UncontrolledAircraft

    groups = [_group(gid=i, name=f"G{i}", uncontrolled=True) for i in range(10)]
    m = _make_mission(groups=groups)
    assert UncontrolledAircraft().check(m) == []


def test_perf003_warning_above_10():
    from afterburner.rules.performance import UncontrolledAircraft

    groups = [_group(gid=i, name=f"G{i}", uncontrolled=True) for i in range(11)]
    m = _make_mission(groups=groups)
    assert UncontrolledAircraft().check(m)[0].severity == Severity.WARNING


def test_perf003_ignores_late_activation():
    from afterburner.rules.performance import UncontrolledAircraft

    groups = [
        _group(gid=i, name=f"G{i}", uncontrolled=True, late_activation=True)
        for i in range(15)
    ]
    m = _make_mission(groups=groups)
    assert UncontrolledAircraft().check(m) == []


def test_perf003_ignores_ground_units():
    from afterburner.rules.performance import UncontrolledAircraft

    groups = [
        _group(gid=i, name=f"G{i}", category=Category.VEHICLE, uncontrolled=True)
        for i in range(15)
    ]
    m = _make_mission(groups=groups)
    assert UncontrolledAircraft().check(m) == []


# ------------------------------------------------------------------
# MAINT_001 — unnamed groups
# ------------------------------------------------------------------


def test_maint001_no_finding_small_pct():
    from afterburner.rules.maintainability import UnnamedGroups

    groups = [_group(gid=i, name=f"Named{i}") for i in range(20)]
    groups[0] = _group(gid=0, name="New untitled")  # 1/20 = 5%, not > 5%
    m = _make_mission(groups=groups)
    assert UnnamedGroups().check(m) == []


def test_maint001_info_when_many_default_names():
    from afterburner.rules.maintainability import UnnamedGroups

    named = [_group(gid=i, name=f"Named{i}") for i in range(10)]
    default_named = [_group(gid=100 + i, name="New untitled") for i in range(5)]
    m = _make_mission(groups=named + default_named)
    findings = UnnamedGroups().check(m)
    assert findings[0].severity == Severity.INFO


# ------------------------------------------------------------------
# MAINT_002 — duplicate group names
# ------------------------------------------------------------------


def test_maint002_no_finding_unique_names():
    from afterburner.rules.maintainability import DuplicateGroupNames

    groups = [_group(gid=i, name=f"Unique{i}") for i in range(5)]
    m = _make_mission(groups=groups)
    assert DuplicateGroupNames().check(m) == []


def test_maint002_warning_on_duplicates():
    from afterburner.rules.maintainability import DuplicateGroupNames

    groups = [
        _group(gid=1, name="Alpha"),
        _group(gid=2, name="Alpha"),
        _group(gid=3, name="Bravo"),
    ]
    m = _make_mission(groups=groups)
    findings = DuplicateGroupNames().check(m)
    assert findings[0].severity == Severity.WARNING
