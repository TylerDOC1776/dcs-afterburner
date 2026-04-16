"""Tests for the CLI commands."""

import json
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from afterburner.cli import app

runner = CliRunner()

_MISSION_LUA = """\
mission =
{
["theatre"] =
"Caucasus",
["sortie"] =
"CLI Test",
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
1,
["name"] =
"Alpha1",
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
"Alpha1-1",
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
},
},
},
},
["triggers"] =
{
},
["trig"] =
{
},
}
"""


def _make_miz(path: Path) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mission", _MISSION_LUA)
        zf.writestr("options", "options =\n{\n}\n")
        zf.writestr("dictionary", "dictionary =\n{\n}\n")
        zf.writestr("l10n/DEFAULT/dictionary", "dictionary =\n{\n}\n")


def test_analyze_console_output(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    result = runner.invoke(app, ["analyze", str(miz)])
    assert result.exit_code == 0
    assert "Caucasus" in result.output
    assert "CLI Test" in result.output


def test_analyze_with_clean_log(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    log = tmp_path / "dcs.log"
    log.write_text("2026-04-12 23:55:01.939 INFO    EDCORE (Main): DCS started\n")
    result = runner.invoke(app, ["analyze", str(miz), "--log", str(log)])
    assert result.exit_code == 0
    assert "events scanned" in result.output
    assert "Log Findings" not in result.output


def test_analyze_with_finding_log(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    log = tmp_path / "dcs.log"
    log.write_text(
        "2026-04-12 23:55:01.939 WARNING EDCORE (Main): Severe precision loss\n"
        "2026-04-12 23:55:02.000 ERROR   EDCORE (Main): Failed assert fabsf\n"
    )
    result = runner.invoke(app, ["analyze", str(miz), "--log", str(log)])
    assert result.exit_code == 0
    assert "Log Findings" in result.output
    assert "LOG_001" in result.output


def test_analyze_with_log_json(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    log = tmp_path / "dcs.log"
    log.write_text(
        "2026-04-12 23:55:01.939 WARNING EDCORE (Main): Severe precision loss\n"
        "2026-04-12 23:55:02.000 ERROR   EDCORE (Main): Failed assert fabsf\n"
    )
    result = runner.invoke(app, ["analyze", str(miz), "--log", str(log), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "log_source" in data
    assert "log_events_parsed" in data
    assert any(f["rule_id"] == "LOG_001" for f in data["findings"])


def test_analyze_log_missing_file(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    result = runner.invoke(app, ["analyze", str(miz), "--log", str(tmp_path / "nope.log")])
    assert result.exit_code == 2


def test_analyze_json_output(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    result = runner.invoke(app, ["analyze", str(miz), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["summary"]["theatre"] == "Caucasus"
    assert data["mission_name"] == "CLI Test"
    assert data["findings"] == []


def test_analyze_json_schema_complete(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    result = runner.invoke(app, ["analyze", str(miz), "--json"])
    data = json.loads(result.output)
    for key in (
        "mission_name",
        "source_file",
        "hash",
        "summary",
        "findings",
        "metrics",
        "output_file",
    ):
        assert key in data


def test_analyze_missing_file(tmp_path):
    result = runner.invoke(app, ["analyze", str(tmp_path / "nope.miz")])
    assert result.exit_code != 0


def test_analyze_wrong_extension(tmp_path):
    f = tmp_path / "mission.txt"
    f.write_text("not a miz")
    result = runner.invoke(app, ["analyze", str(f)])
    assert result.exit_code == 2


def test_no_args_shows_help():
    result = runner.invoke(app, [])
    # no_args_is_help=True — shows usage/help regardless of exit code
    assert "analyze" in result.output


def test_analyze_corrupt_miz(tmp_path):
    miz = tmp_path / "bad.miz"
    miz.write_bytes(b"this is not a zip file")
    result = runner.invoke(app, ["analyze", str(miz)])
    assert result.exit_code == 2


def test_analyze_fail_on_warning_exits_nonzero(tmp_path):
    """--fail-on warning should exit 1 when a critical-level finding is present."""
    import zipfile

    # Build a mission with enough active units to trigger BLOT_001 warning (>600)
    mission_lua = """\
mission =
{
["theatre"] =
"Caucasus",
["sortie"] =
"Big Mission",
["coalition"] =
{
["blue"] =
{
["country"] =
{
[1] =
{
["id"] = 2,
["name"] = "USA",
["plane"] =
{
["group"] =
{
"""
    # Add 650 units across groups to exceed the active unit critical threshold (>600)
    for i in range(1, 66):
        units = ""
        for j in range(1, 11):
            uid = (i - 1) * 10 + j
            units += f"""
[{j}] =
{{
["unitId"] = {uid},
["name"] = "Unit{uid}",
["type"] = "F-16C_50",
["skill"] = "High",
["x"] = {float(uid)},
["y"] = {float(uid)},
}},
"""
        mission_lua += f"""
[{i}] =
{{
["groupId"] = {i},
["name"] = "Group{i}",
["lateActivation"] = false,
["uncontrolled"] = false,
["units"] =
{{
{units}
}},
}},
"""
    mission_lua += """
},
},
},
},
},
},
["triggers"] = {},
["trig"] = {},
}
"""
    miz = tmp_path / "big.miz"
    with zipfile.ZipFile(miz, "w") as zf:
        zf.writestr("mission", mission_lua)
        zf.writestr("options", "options =\n{\n}\n")
        zf.writestr("dictionary", "dictionary =\n{\n}\n")
        zf.writestr("l10n/DEFAULT/dictionary", "dictionary =\n{\n}\n")

    result = runner.invoke(app, ["analyze", str(miz), "--fail-on", "warning"])
    assert result.exit_code == 1


def test_analyze_fail_on_none_always_zero(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    result = runner.invoke(app, ["analyze", str(miz), "--fail-on", "none"])
    assert result.exit_code == 0


# ------------------------------------------------------------------
# report command
# ------------------------------------------------------------------


def test_report_missing_file(tmp_path):
    result = runner.invoke(app, ["report", str(tmp_path / "nope.miz")])
    assert result.exit_code == 2


def test_report_wrong_extension(tmp_path):
    f = tmp_path / "mission.txt"
    f.write_text("not a miz")
    result = runner.invoke(app, ["report", str(f)])
    assert result.exit_code == 2


def test_report_markdown_output(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    result = runner.invoke(app, ["report", str(miz), "--format", "md"])
    assert result.exit_code == 0
    assert "# DCS Afterburner Report" in result.output
    assert "## Mission Summary" in result.output


def test_report_unknown_format(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    result = runner.invoke(app, ["report", str(miz), "--format", "html"])
    assert result.exit_code == 2


def test_report_corrupt_miz(tmp_path):
    miz = tmp_path / "bad.miz"
    miz.write_bytes(b"not a zip")
    result = runner.invoke(app, ["report", str(miz)])
    assert result.exit_code == 2


# ------------------------------------------------------------------
# optimize error paths
# ------------------------------------------------------------------


def test_optimize_missing_file(tmp_path):
    result = runner.invoke(
        app, ["optimize", str(tmp_path / "nope.miz"), "--safe"]
    )
    assert result.exit_code == 2


def test_optimize_wrong_extension(tmp_path):
    f = tmp_path / "mission.txt"
    f.write_text("not a miz")
    result = runner.invoke(app, ["optimize", str(f), "--safe"])
    assert result.exit_code == 2


def test_optimize_output_already_exists(tmp_path):
    miz = tmp_path / "mission.miz"
    _make_miz(miz)
    out = tmp_path / "mission.optimized.miz"
    out.write_bytes(b"already here")
    result = runner.invoke(app, ["optimize", str(miz), "--safe"])
    assert result.exit_code == 2


def test_optimize_rejects_same_output_path(tmp_path):
    miz = tmp_path / "mission.miz"
    _make_miz(miz)
    result = runner.invoke(
        app, ["optimize", str(miz), "--safe", "--output", str(miz)]
    )
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# logs command
# ---------------------------------------------------------------------------

_CLEAN_LOG = "2026-04-12 23:55:01.939 INFO    EDCORE (Main): DCS started\n"

_FINDING_LOG = (
    "2026-04-12 23:55:01.939 WARNING EDCORE (Main): Severe precision loss\n"
    "2026-04-12 23:55:02.000 ERROR   EDCORE (Main): Failed assert fabsf\n"
)


def test_logs_missing_file(tmp_path):
    result = runner.invoke(app, ["logs", str(tmp_path / "nope.log")])
    assert result.exit_code == 2


def test_logs_clean_console_output(tmp_path):
    log = tmp_path / "dcs.log"
    log.write_text(_CLEAN_LOG)
    result = runner.invoke(app, ["logs", str(log)])
    assert result.exit_code == 0
    assert "No findings" in result.output


def test_logs_finding_console_output(tmp_path):
    log = tmp_path / "dcs.log"
    log.write_text(_FINDING_LOG)
    result = runner.invoke(app, ["logs", str(log)])
    assert result.exit_code == 0
    assert "LOG_001" in result.output
    assert "precision loss" in result.output.lower()


def test_logs_json_output(tmp_path):
    log = tmp_path / "dcs.log"
    log.write_text(_FINDING_LOG)
    result = runner.invoke(app, ["logs", str(log), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "findings" in data
    assert "events_parsed" in data
    assert any(f["rule_id"] == "LOG_001" for f in data["findings"])


def test_logs_json_clean(tmp_path):
    log = tmp_path / "dcs.log"
    log.write_text(_CLEAN_LOG)
    result = runner.invoke(app, ["logs", str(log), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["findings"] == []


def test_logs_fail_on_critical_exits_nonzero(tmp_path):
    log = tmp_path / "dcs.log"
    log.write_text(_FINDING_LOG)
    result = runner.invoke(app, ["logs", str(log), "--fail-on", "critical"])
    assert result.exit_code == 1


def test_logs_fail_on_none_always_zero(tmp_path):
    log = tmp_path / "dcs.log"
    log.write_text(_FINDING_LOG)
    result = runner.invoke(app, ["logs", str(log), "--fail-on", "none"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# rules subcommands
# ---------------------------------------------------------------------------


def test_rules_list_output():
    result = runner.invoke(app, ["rules", "list"])
    assert result.exit_code == 0
    # spot-check a rule from each category
    assert "BLOT_001" in result.output
    assert "PERF_003" in result.output
    assert "MAINT_001" in result.output
    assert "MAINT_002" in result.output


def test_rules_list_columns():
    result = runner.invoke(app, ["rules", "list"])
    assert result.exit_code == 0
    assert "bloat" in result.output
    assert "performance" in result.output
    assert "maintainability" in result.output


def test_rules_explain_known_rule():
    result = runner.invoke(app, ["rules", "explain", "BLOT_001"])
    assert result.exit_code == 0
    assert "BLOT_001" in result.output
    assert "critical" in result.output
    assert "bloat" in result.output


def test_rules_explain_case_insensitive():
    result = runner.invoke(app, ["rules", "explain", "blot_001"])
    assert result.exit_code == 0
    assert "BLOT_001" in result.output


def test_rules_explain_unknown_rule():
    result = runner.invoke(app, ["rules", "explain", "FAKE_999"])
    assert result.exit_code == 2
