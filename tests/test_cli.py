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
