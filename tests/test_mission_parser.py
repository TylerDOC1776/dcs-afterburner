"""Tests for the mission parser — uses synthetic .miz fixtures."""

import zipfile
from pathlib import Path

import pytest

from afterburner.parsers.mission_parser import parse

# A minimal but structurally complete DCS mission table.
# Uses DCS's actual formatting style (key on one line, = newline, value on next).
_MISSION_LUA = """\
mission =
{
["theatre"] =
"Caucasus",
["sortie"] =
"Test Op",
["coalition"] =
{
["blue"] =
{
["country"] =
{
[1] =
{
["id"] =
2,
["name"] =
"USA",
["plane"] =
{
["group"] =
{
[1] =
{
["groupId"] =
100,
["name"] =
"Dodge1",
["lateActivation"] =
false,
["uncontrolled"] =
false,
["units"] =
{
[1] =
{
["unitId"] =
1,
["name"] =
"Dodge1-1",
["type"] =
"F-16C_50",
["skill"] =
"High",
["x"] =
-100000.0,
["y"] =
200000.0,
},
[2] =
{
["unitId"] =
2,
["name"] =
"Dodge1-2",
["type"] =
"F-16C_50",
["skill"] =
"Client",
["x"] =
-100001.0,
["y"] =
200001.0,
},
},
},
[2] =
{
["groupId"] =
101,
["name"] =
"Viper1",
["lateActivation"] =
true,
["uncontrolled"] =
false,
["units"] =
{
[1] =
{
["unitId"] =
3,
["name"] =
"Viper1-1",
["type"] =
"F-16C_50",
["skill"] =
"High",
["x"] =
0.0,
["y"] =
0.0,
},
},
},
},
},
["vehicle"] =
{
["group"] =
{
[1] =
{
["groupId"] =
200,
["name"] =
"Ground1",
["lateActivation"] =
false,
["uncontrolled"] =
false,
["units"] =
{
[1] =
{
["unitId"] =
10,
["name"] =
"Ground1-1",
["type"] =
"M1A2",
["skill"] =
"High",
["x"] =
0.0,
["y"] =
0.0,
},
},
},
},
},
["static"] =
{
["group"] =
{
[1] =
{
["groupId"] =
300,
["name"] =
"Static1",
["lateActivation"] =
false,
["uncontrolled"] =
false,
["units"] =
{
[1] =
{
["unitId"] =
20,
["name"] =
"Static1-1",
["type"] =
"FARP",
["skill"] =
"Excellent",
["x"] =
0.0,
["y"] =
0.0,
},
},
},
},
},
},
},
},
["red"] =
{
["country"] =
{
},
},
},
["triggers"] =
{
["zones"] =
{
[1] =
{
["zoneId"] =
1,
["name"] =
"Zone Alpha",
["radius"] =
5000.0,
["x"] =
1000.0,
["y"] =
2000.0,
},
[2] =
{
["zoneId"] =
2,
["name"] =
"Zone Bravo",
["radius"] =
3000.0,
["x"] =
0.0,
["y"] =
0.0,
},
},
},
["trig"] =
{
["conditions"] =
{
[1] =
"return(true)",
[2] =
"return(false)",
[3] =
"return(false)",
},
["actions"] =
{
[1] =
"action_message()",
[2] =
"action_script()",
[3] =
"action_flag()",
},
},
}
"""


def _make_miz(path: Path, mission_lua: str = _MISSION_LUA) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mission", mission_lua)
        zf.writestr("options", "options =\n{\n}\n")
        zf.writestr("dictionary", "dictionary =\n{\n}\n")
        zf.writestr("l10n/DEFAULT/dictionary", "dictionary =\n{\n}\n")


@pytest.fixture
def sample_miz(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    return miz


# ------------------------------------------------------------------
# Basic parse
# ------------------------------------------------------------------


def test_parse_returns_mission(sample_miz):
    mission = parse(sample_miz)
    assert mission is not None


def test_theatre(sample_miz):
    assert parse(sample_miz).theatre == "Caucasus"


def test_sortie_name(sample_miz):
    assert parse(sample_miz).name == "Test Op"


def test_source_file(sample_miz):
    assert parse(sample_miz).source_file == "test.miz"


def test_sha256_prefix(sample_miz):
    assert parse(sample_miz).sha256.startswith("sha256:")


# ------------------------------------------------------------------
# Unit and group counts
# ------------------------------------------------------------------


def test_total_groups(sample_miz):
    # 2 plane groups + 1 vehicle group = 3 (statics are separate)
    assert parse(sample_miz).summary.total_groups == 3


def test_total_units(sample_miz):
    # Dodge1 (2 units) + Viper1 (1 late) + Ground1 (1) = 4
    assert parse(sample_miz).summary.total_units == 4


def test_active_units(sample_miz):
    # Viper1 is late activation → 3 active
    assert parse(sample_miz).summary.active_units == 3


def test_late_units(sample_miz):
    assert parse(sample_miz).summary.late_units == 1


def test_player_slots(sample_miz):
    # Dodge1-2 has skill=Client
    assert parse(sample_miz).summary.player_slots == 1


def test_total_statics(sample_miz):
    assert parse(sample_miz).summary.total_statics == 1


# ------------------------------------------------------------------
# Triggers and zones
# ------------------------------------------------------------------


def test_trigger_count(sample_miz):
    assert parse(sample_miz).summary.trigger_count == 3


def test_zone_count(sample_miz):
    assert parse(sample_miz).summary.zone_count == 2


def test_zone_fields(sample_miz):
    zones = parse(sample_miz).zones
    alpha = next(z for z in zones if z.name == "Zone Alpha")
    assert alpha.radius == pytest.approx(5000.0)
    assert alpha.x == pytest.approx(1000.0)


# ------------------------------------------------------------------
# JSON output schema
# ------------------------------------------------------------------


def test_json_schema_shape(sample_miz):
    from afterburner.models.report import Report
    from afterburner.reporters.json_report import to_json

    data = to_json(Report(mission=parse(sample_miz)))
    assert "mission_name" in data
    assert "source_file" in data
    assert "hash" in data
    assert "summary" in data
    assert "findings" in data
    assert "metrics" in data
    assert "optimizations_applied" in data
    assert "output_file" in data


def test_json_summary_fields(sample_miz):
    from afterburner.models.report import Report
    from afterburner.reporters.json_report import to_json

    summary = to_json(Report(mission=parse(sample_miz)))["summary"]
    for key in (
        "total_units",
        "active_units",
        "trigger_count",
        "zone_count",
        "risk_label",
    ):
        assert key in summary


def test_json_findings_empty_no_rules(sample_miz):
    from afterburner.models.report import Report
    from afterburner.reporters.json_report import to_json

    # A report with no findings explicitly added has an empty findings list
    assert to_json(Report(mission=parse(sample_miz)))["findings"] == []


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------


def test_empty_coalitions(tmp_path):
    lua = """\
mission =
{
["theatre"] =
"PersianGulf",
["sortie"] =
"Empty",
["coalition"] =
{
},
["triggers"] =
{
},
["trig"] =
{
},
}
"""
    miz = tmp_path / "empty.miz"
    _make_miz(miz, lua)
    m = parse(miz)
    assert m.summary.total_units == 0
    assert m.summary.trigger_count == 0
    assert m.summary.zone_count == 0
