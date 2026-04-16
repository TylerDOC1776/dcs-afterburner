"""Tests for the mission diff engine."""

from __future__ import annotations

from afterburner.diff import MissionDiff, compute
from afterburner.models.mission import (
    Category,
    Group,
    Mission,
    MissionSummary,
    Trigger,
    Unit,
    Zone,
)


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


def _make_mission(
    summary: MissionSummary | None = None,
    groups: list[Group] | None = None,
    zones: list[Zone] | None = None,
    script_files: list[str] | None = None,
    triggers_detail: list[Trigger] | None = None,
    source_file: str = "test.miz",
    theatre: str = "Caucasus",
) -> Mission:
    return Mission(
        name="Test",
        source_file=source_file,
        sha256="sha256:abc",
        theatre=theatre,
        summary=summary or _make_summary(theatre=theatre),
        groups=groups or [],
        zones=zones or [],
        script_files=script_files or [],
        triggers_detail=triggers_detail or [],
    )


def _unit() -> Unit:
    return Unit(
        id=1, name="U1", type="F-16C_50", skill="High",
        late_activation=False, x=0.0, y=0.0, is_player_slot=False,
    )


def _group(name: str, gid: int = 1) -> Group:
    return Group(
        id=gid, name=name, category=Category.PLANE,
        coalition="blue", units=[_unit()],
        late_activation=False, uncontrolled=False,
    )


def _zone(name: str, zid: int = 1) -> Zone:
    return Zone(id=zid, name=name, radius=1000.0, x=0.0, y=0.0)


# ------------------------------------------------------------------
# Identical missions
# ------------------------------------------------------------------


def test_identical_missions_is_identical():
    old = _make_mission()
    new = _make_mission()
    result = compute(old, new)
    assert result.is_identical


# ------------------------------------------------------------------
# Summary deltas
# ------------------------------------------------------------------


def test_active_units_delta():
    old = _make_mission(_make_summary(active_units=100))
    new = _make_mission(_make_summary(active_units=150))
    result = compute(old, new)
    assert len(result.summary_deltas) == 1
    d = result.summary_deltas[0]
    assert d.field == "active_units"
    assert d.old == 100
    assert d.new == 150
    assert d.delta == 50


def test_multiple_summary_fields_changed():
    old = _make_mission(_make_summary(active_units=100, trigger_count=50))
    new = _make_mission(_make_summary(active_units=80, trigger_count=60))
    result = compute(old, new)
    fields = {d.field for d in result.summary_deltas}
    assert "active_units" in fields
    assert "trigger_count" in fields


def test_delta_negative():
    old = _make_mission(_make_summary(total_statics=200))
    new = _make_mission(_make_summary(total_statics=150))
    result = compute(old, new)
    assert result.summary_deltas[0].delta == -50


def test_unchanged_fields_not_in_deltas():
    old = _make_mission(_make_summary(active_units=100, total_statics=50))
    new = _make_mission(_make_summary(active_units=100, total_statics=60))
    result = compute(old, new)
    assert all(d.field != "active_units" for d in result.summary_deltas)


# ------------------------------------------------------------------
# Theatre
# ------------------------------------------------------------------


def test_theatre_change_detected():
    old = _make_mission(theatre="Caucasus")
    new = _make_mission(theatre="Nevada")
    result = compute(old, new)
    assert result.theatre_changed
    assert result.old_theatre == "Caucasus"
    assert result.new_theatre == "Nevada"


def test_same_theatre_not_flagged():
    old = _make_mission(theatre="Caucasus")
    new = _make_mission(theatre="Caucasus")
    result = compute(old, new)
    assert not result.theatre_changed


# ------------------------------------------------------------------
# Groups
# ------------------------------------------------------------------


def test_group_added():
    old = _make_mission(groups=[_group("Alpha")])
    new = _make_mission(groups=[_group("Alpha"), _group("Bravo", gid=2)])
    result = compute(old, new)
    assert result.groups_added == ["Bravo"]
    assert result.groups_removed == []


def test_group_removed():
    old = _make_mission(groups=[_group("Alpha"), _group("Bravo", gid=2)])
    new = _make_mission(groups=[_group("Alpha")])
    result = compute(old, new)
    assert result.groups_removed == ["Bravo"]
    assert result.groups_added == []


def test_groups_added_sorted():
    old = _make_mission(groups=[])
    new = _make_mission(groups=[_group("Zulu", 3), _group("Alpha", 1), _group("Mike", 2)])
    result = compute(old, new)
    assert result.groups_added == ["Alpha", "Mike", "Zulu"]


def test_same_groups_no_change():
    old = _make_mission(groups=[_group("Alpha"), _group("Bravo", 2)])
    new = _make_mission(groups=[_group("Alpha"), _group("Bravo", 2)])
    result = compute(old, new)
    assert result.groups_added == []
    assert result.groups_removed == []


# ------------------------------------------------------------------
# Zones
# ------------------------------------------------------------------


def test_zone_added():
    old = _make_mission(zones=[_zone("LZ1")])
    new = _make_mission(zones=[_zone("LZ1"), _zone("LZ2", 2)])
    result = compute(old, new)
    assert result.zones_added == ["LZ2"]
    assert result.zones_removed == []


def test_zone_removed():
    old = _make_mission(zones=[_zone("LZ1"), _zone("LZ2", 2)])
    new = _make_mission(zones=[_zone("LZ1")])
    result = compute(old, new)
    assert result.zones_removed == ["LZ2"]


# ------------------------------------------------------------------
# Scripts
# ------------------------------------------------------------------


def test_script_added():
    old = _make_mission(script_files=["MIST.lua"])
    new = _make_mission(script_files=["MIST.lua", "CTLD.lua"])
    result = compute(old, new)
    assert result.scripts_added == ["CTLD.lua"]
    assert result.scripts_removed == []


def test_script_removed():
    old = _make_mission(script_files=["MIST.lua", "CTLD.lua"])
    new = _make_mission(script_files=["MIST.lua"])
    result = compute(old, new)
    assert result.scripts_removed == ["CTLD.lua"]


# ------------------------------------------------------------------
# JSON serialization
# ------------------------------------------------------------------


def test_to_json_keys():
    from afterburner.diff import to_json

    old = _make_mission(_make_summary(active_units=100), groups=[_group("Alpha")])
    new = _make_mission(_make_summary(active_units=120), groups=[_group("Alpha"), _group("Bravo", 2)])
    result = to_json(compute(old, new))
    assert "summary_deltas" in result
    assert "groups_added" in result
    assert "groups_removed" in result
    assert "is_identical" in result
    assert result["groups_added"] == ["Bravo"]


def test_to_json_identical():
    from afterburner.diff import to_json

    old = _make_mission()
    new = _make_mission()
    result = to_json(compute(old, new))
    assert result["is_identical"] is True
