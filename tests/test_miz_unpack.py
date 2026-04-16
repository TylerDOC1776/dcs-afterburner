"""Tests for .miz extract and repack."""

import shutil
import zipfile
from pathlib import Path

import pytest

from afterburner.utils.miz import MizEditor, extract, repack

_MISSION = b"mission =\n{\n}\n"
_OPTIONS = b"options =\n{\n}\n"


def _make_miz(path: Path) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mission", _MISSION.decode())
        zf.writestr("options", _OPTIONS.decode())
        zf.writestr("l10n/DEFAULT/dictionary", "dictionary =\n{\n}\n")


# ------------------------------------------------------------------
# extract
# ------------------------------------------------------------------


def test_extract_to_specified_dir(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    dest = extract(miz, tmp_path / "out")
    assert (dest / "mission").exists()
    assert (dest / "options").exists()
    assert (dest / "l10n" / "DEFAULT" / "dictionary").exists()


def test_extract_to_temp_dir(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    dest = extract(miz)
    try:
        assert dest.is_dir()
        assert (dest / "mission").read_bytes() == _MISSION
    finally:
        shutil.rmtree(dest)


def test_extract_file_contents(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    dest = extract(miz, tmp_path / "out")
    assert (dest / "mission").read_bytes() == _MISSION
    assert (dest / "options").read_bytes() == _OPTIONS


# ------------------------------------------------------------------
# repack
# ------------------------------------------------------------------


def test_repack_roundtrip(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    work = extract(miz, tmp_path / "work")
    out = tmp_path / "repacked.miz"
    repack(work, out, original_miz=miz)

    assert out.exists()
    with zipfile.ZipFile(out) as zf:
        assert zf.read("mission") == _MISSION
        assert zf.read("options") == _OPTIONS


def test_repack_mission_is_first_entry(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    work = extract(miz, tmp_path / "work")
    out = tmp_path / "out.miz"
    repack(work, out)
    with zipfile.ZipFile(out) as zf:
        assert zf.namelist()[0] == "mission"


def test_repack_refuses_overwrite(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    work = extract(miz, tmp_path / "work")
    with pytest.raises(FileExistsError):
        repack(work, miz)


def test_repack_uses_deflate(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    work = extract(miz, tmp_path / "work")
    out = tmp_path / "out.miz"
    repack(work, out)
    with zipfile.ZipFile(out) as zf:
        for info in zf.infolist():
            assert info.compress_type == zipfile.ZIP_DEFLATED


# ------------------------------------------------------------------
# MizEditor context manager
# ------------------------------------------------------------------


def test_miz_editor_modifies_and_repacks(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    out = tmp_path / "edited.miz"

    with MizEditor(miz, out) as work_dir:
        mission_file = work_dir / "mission"
        mission_file.write_text('mission =\n{\n["edited"] =\ntrue,\n}\n')

    with zipfile.ZipFile(out) as zf:
        content = zf.read("mission").decode()
    assert "edited" in content


def test_miz_editor_cleans_up_on_success(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    out = tmp_path / "edited.miz"

    captured_work_dir = None
    with MizEditor(miz, out) as work_dir:
        captured_work_dir = work_dir

    assert not captured_work_dir.exists()


def test_extract_rejects_path_traversal(tmp_path):
    miz = tmp_path / "evil.miz"
    with zipfile.ZipFile(miz, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mission", _MISSION.decode())
        zf.writestr("../../escape.txt", "pwned")
    dest = tmp_path / "out"
    with pytest.raises(ValueError, match="Path traversal"):
        extract(miz, dest)


def test_miz_editor_cleans_up_on_exception(tmp_path):
    miz = tmp_path / "test.miz"
    _make_miz(miz)
    out = tmp_path / "edited.miz"

    captured_work_dir = None
    with pytest.raises(RuntimeError):
        with MizEditor(miz, out) as work_dir:
            captured_work_dir = work_dir
            raise RuntimeError("simulated failure")

    assert not captured_work_dir.exists()
    assert not out.exists()  # partial output not written on exception
