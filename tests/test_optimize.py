"""Tests for the safe optimization engine."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from afterburner.optimize.engine import run_safe_optimizations
from afterburner.optimize.rewrite import repack_optimized
from afterburner.optimize.safe_fixes import is_junk, normalize_path

_MISSION_LUA = """\
mission =
{
["theatre"] =
"Caucasus",
["sortie"] =
"Optimize Test",
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


def _make_miz(path: Path, extra_entries: dict[str, bytes] | None = None) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mission", _MISSION_LUA)
        zf.writestr("options", "options =\n{\n}\n")
        zf.writestr("dictionary", "dictionary =\n{\n}\n")
        zf.writestr("l10n/DEFAULT/dictionary", "dictionary =\n{\n}\n")
        if extra_entries:
            for name, data in extra_entries.items():
                zf.writestr(name, data)


# ------------------------------------------------------------------
# safe_fixes unit tests
# ------------------------------------------------------------------


def test_is_junk_ds_store():
    assert is_junk(".DS_Store")


def test_is_junk_macosx():
    assert is_junk("__MACOSX/mission")


def test_is_junk_nested_ds_store():
    assert is_junk("Scripts/.DS_Store")


def test_is_junk_thumbs():
    assert is_junk("Thumbs.db")


def test_is_junk_desktop_ini():
    assert is_junk("desktop.ini")


def test_is_junk_tmp():
    assert is_junk("~temp.tmp")


def test_not_junk_mission():
    assert not is_junk("mission")


def test_not_junk_lua():
    assert not is_junk("l10n/DEFAULT/dictionary")


def test_normalize_path_backslash():
    assert normalize_path("Scripts\\myscript.lua") == "Scripts/myscript.lua"


def test_normalize_path_no_change():
    assert normalize_path("Scripts/myscript.lua") == "Scripts/myscript.lua"


# ------------------------------------------------------------------
# repack_optimized
# ------------------------------------------------------------------


def test_repack_produces_valid_zip(tmp_path):
    src = tmp_path / "source.miz"
    dest = tmp_path / "dest.miz"
    _make_miz(src)
    repack_optimized(src, dest)
    assert dest.exists()
    assert zipfile.is_zipfile(dest)


def test_repack_mission_entry_first(tmp_path):
    src = tmp_path / "source.miz"
    dest = tmp_path / "dest.miz"
    _make_miz(src)
    repack_optimized(src, dest)
    with zipfile.ZipFile(dest, "r") as zf:
        assert zf.namelist()[0] == "mission"


def test_repack_round_trip_parse(tmp_path):
    """Output must be parseable by the mission parser."""
    from afterburner.parsers.mission_parser import parse

    src = tmp_path / "source.miz"
    dest = tmp_path / "dest.miz"
    _make_miz(src)
    repack_optimized(src, dest)
    m = parse(dest)
    assert m.theatre == "Caucasus"


def test_repack_removes_junk(tmp_path):
    src = tmp_path / "source.miz"
    dest = tmp_path / "dest.miz"
    _make_miz(
        src,
        extra_entries={
            ".DS_Store": b"junk",
            "__MACOSX/mission": b"junk",
        },
    )
    changes = repack_optimized(src, dest)
    applied_ids = [c.transform_id for c in changes if c.status == "applied"]
    assert "SAFE_001" in applied_ids

    with zipfile.ZipFile(dest, "r") as zf:
        names = zf.namelist()
    assert ".DS_Store" not in names
    assert "__MACOSX/mission" not in names


def test_repack_normalizes_backslash_paths(tmp_path):
    src = tmp_path / "source.miz"
    dest = tmp_path / "dest.miz"

    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("mission", _MISSION_LUA)
        zf.writestr("Scripts\\myscript.lua", "-- script")

    changes = repack_optimized(src, dest)
    applied_ids = [c.transform_id for c in changes if c.status == "applied"]
    assert "SAFE_002" in applied_ids

    with zipfile.ZipFile(dest, "r") as zf:
        names = zf.namelist()
    assert "Scripts/myscript.lua" in names
    assert "Scripts\\myscript.lua" not in names


def test_repack_no_partial_on_failure(tmp_path):
    """If output path is a directory, repack raises and leaves no partial file."""
    src = tmp_path / "source.miz"
    dest = tmp_path / "dest.miz"
    dest.mkdir()  # make dest a directory so ZipFile write fails

    _make_miz(src)
    with pytest.raises(Exception):
        repack_optimized(src, dest)


# ------------------------------------------------------------------
# run_safe_optimizations (engine)
# ------------------------------------------------------------------


def test_engine_creates_output(tmp_path):
    src = tmp_path / "mission.miz"
    _make_miz(src)
    result = run_safe_optimizations(src)
    assert result.output.exists()
    assert result.output.name == "mission.optimized.miz"


def test_engine_creates_backup(tmp_path):
    src = tmp_path / "mission.miz"
    _make_miz(src)
    result = run_safe_optimizations(src)
    assert result.backup.exists()
    assert result.backup.name == "mission.miz.bak"


def test_engine_backup_matches_original(tmp_path):
    src = tmp_path / "mission.miz"
    _make_miz(src)
    original_bytes = src.read_bytes()
    result = run_safe_optimizations(src)
    assert result.backup.read_bytes() == original_bytes


def test_engine_output_is_valid_miz(tmp_path):
    src = tmp_path / "mission.miz"
    _make_miz(src)
    result = run_safe_optimizations(src)
    assert zipfile.is_zipfile(result.output)


def test_engine_output_round_trips(tmp_path):
    from afterburner.parsers.mission_parser import parse

    src = tmp_path / "mission.miz"
    _make_miz(src)
    result = run_safe_optimizations(src)
    m = parse(result.output)
    assert m.name == "Optimize Test"


def test_engine_custom_output_path(tmp_path):
    src = tmp_path / "mission.miz"
    out = tmp_path / "custom_output.miz"
    _make_miz(src)
    result = run_safe_optimizations(src, output=out)
    assert result.output == out.resolve()


def test_engine_rejects_same_path(tmp_path):
    src = tmp_path / "mission.miz"
    _make_miz(src)
    with pytest.raises(ValueError, match="same as input"):
        run_safe_optimizations(src, output=src)


def test_engine_rejects_existing_output(tmp_path):
    src = tmp_path / "mission.miz"
    out = tmp_path / "existing.miz"
    _make_miz(src)
    out.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        run_safe_optimizations(src, output=out)


def test_engine_removes_junk_entries(tmp_path):
    src = tmp_path / "mission.miz"
    _make_miz(src, extra_entries={".DS_Store": b"x", "Thumbs.db": b"y"})
    result = run_safe_optimizations(src)
    safe001 = [c for c in result.changes if c.transform_id == "SAFE_001"]
    assert len(safe001) == 2


def test_engine_bytes_before_after(tmp_path):
    src = tmp_path / "mission.miz"
    _make_miz(src)
    result = run_safe_optimizations(src)
    assert result.bytes_before > 0
    assert result.bytes_after > 0
    assert result.bytes_before == src.stat().st_size


# ------------------------------------------------------------------
# CLI integration
# ------------------------------------------------------------------


def test_cli_optimize_requires_safe(tmp_path):
    from typer.testing import CliRunner

    from afterburner.cli import app

    src = tmp_path / "mission.miz"
    _make_miz(src)
    result = CliRunner().invoke(app, ["optimize", str(src)])
    assert result.exit_code == 2


def test_cli_optimize_safe_flag(tmp_path):
    from typer.testing import CliRunner

    from afterburner.cli import app

    src = tmp_path / "mission.miz"
    _make_miz(src)
    result = CliRunner().invoke(app, ["optimize", str(src), "--safe"])
    assert result.exit_code == 0
    assert (tmp_path / "mission.optimized.miz").exists()


def test_cli_optimize_json_output(tmp_path):
    import json

    from typer.testing import CliRunner

    from afterburner.cli import app

    src = tmp_path / "mission.miz"
    _make_miz(src)
    result = CliRunner().invoke(app, ["optimize", str(src), "--safe", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    for key in ("source", "output", "backup", "bytes_before", "bytes_after", "changes"):
        assert key in data


def test_engine_rejects_existing_backup(tmp_path):
    src = tmp_path / "mission.miz"
    _make_miz(src)
    backup = tmp_path / "mission.miz.bak"
    backup.write_bytes(b"old backup")
    with pytest.raises(FileExistsError, match="Backup already exists"):
        run_safe_optimizations(src)


def test_cli_optimize_missing_file(tmp_path):
    from typer.testing import CliRunner

    from afterburner.cli import app

    result = CliRunner().invoke(app, ["optimize", str(tmp_path / "nope.miz"), "--safe"])
    assert result.exit_code != 0
