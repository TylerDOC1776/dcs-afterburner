from __future__ import annotations

import csv
import json
import subprocess

import pytest

from afterburner.bench.harness import DCSBenchmarkHarness, _PRESENTMON_CANDIDATES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_harness(tmp_path, presentmon_path="fake_presentmon.exe"):
    return DCSBenchmarkHarness(
        dcs_path="DCS.exe",
        output_dir=str(tmp_path),
        presentmon_path=presentmon_path,
    )


def _write_pm_csv(path, col_name, values):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[col_name])
        writer.writeheader()
        for v in values:
            writer.writerow({col_name: v})


class _FakeProc:
    def __init__(self):
        self.terminated = False
        self.killed = False

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        pass

    def kill(self):
        self.killed = True


class _TimeoutProc(_FakeProc):
    def wait(self, timeout=None):
        raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout)


# ---------------------------------------------------------------------------
# __init__ / output_dir creation
# ---------------------------------------------------------------------------

def test_init_creates_output_dir(tmp_path):
    out = tmp_path / "nested" / "bench"
    DCSBenchmarkHarness(dcs_path="DCS.exe", output_dir=str(out), presentmon_path="x.exe")
    assert out.is_dir()


# ---------------------------------------------------------------------------
# _find_presentmon
# ---------------------------------------------------------------------------

def test_find_presentmon_returns_first_existing(monkeypatch, tmp_path):
    real = tmp_path / "PresentMon.exe"
    real.write_text("")
    monkeypatch.setattr(
        "afterburner.bench.harness._PRESENTMON_CANDIDATES",
        [str(tmp_path / "missing.exe"), str(real)],
    )
    h = DCSBenchmarkHarness(dcs_path="DCS.exe", output_dir=str(tmp_path), presentmon_path=None)
    assert h.presentmon_path == str(real)


def test_find_presentmon_returns_none_when_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "afterburner.bench.harness._PRESENTMON_CANDIDATES",
        [str(tmp_path / "nope1.exe"), str(tmp_path / "nope2.exe")],
    )
    h = DCSBenchmarkHarness(dcs_path="DCS.exe", output_dir=str(tmp_path), presentmon_path=None)
    assert h.presentmon_path is None


def test_find_presentmon_explicit_path_bypasses_search(monkeypatch, tmp_path):
    monkeypatch.setattr("afterburner.bench.harness._PRESENTMON_CANDIDATES", [])
    h = DCSBenchmarkHarness(
        dcs_path="DCS.exe", output_dir=str(tmp_path), presentmon_path="custom.exe"
    )
    assert h.presentmon_path == "custom.exe"


# ---------------------------------------------------------------------------
# _stop_process
# ---------------------------------------------------------------------------

def test_stop_process_terminates_normally(tmp_path):
    h = _make_harness(tmp_path)
    proc = _FakeProc()
    h._stop_process(proc, timeout=1)
    assert proc.terminated
    assert not proc.killed


def test_stop_process_kills_on_timeout(tmp_path):
    h = _make_harness(tmp_path)
    proc = _TimeoutProc()
    h._stop_process(proc, timeout=1)
    assert proc.killed


# ---------------------------------------------------------------------------
# _parse_frametimes
# ---------------------------------------------------------------------------

def test_parse_frametimes_missing_file(tmp_path):
    h = _make_harness(tmp_path)
    assert h._parse_frametimes(str(tmp_path / "no_such.csv")) == []


def test_parse_frametimes_msbetweenpresents(tmp_path):
    p = str(tmp_path / "pm.csv")
    _write_pm_csv(p, "msBetweenPresents", ["16.67", "16.50", "17.00"])
    h = _make_harness(tmp_path)
    assert h._parse_frametimes(p) == pytest.approx([16.67, 16.50, 17.00])


def test_parse_frametimes_frametime_ms_column(tmp_path):
    p = str(tmp_path / "pm.csv")
    _write_pm_csv(p, "FrameTime_ms", ["8.33", "8.50"])
    h = _make_harness(tmp_path)
    assert h._parse_frametimes(p) == pytest.approx([8.33, 8.50])


def test_parse_frametimes_msbetweenpresents_capital(tmp_path):
    p = str(tmp_path / "pm.csv")
    _write_pm_csv(p, "MsBetweenPresents", ["10.0", "12.0"])
    h = _make_harness(tmp_path)
    assert h._parse_frametimes(p) == pytest.approx([10.0, 12.0])


def test_parse_frametimes_skips_non_positive(tmp_path):
    p = str(tmp_path / "pm.csv")
    _write_pm_csv(p, "msBetweenPresents", ["16.0", "0", "-1.0", "8.0"])
    h = _make_harness(tmp_path)
    assert h._parse_frametimes(p) == pytest.approx([16.0, 8.0])


def test_parse_frametimes_skips_bad_values(tmp_path):
    p = str(tmp_path / "pm.csv")
    _write_pm_csv(p, "msBetweenPresents", ["16.0", "bad", "", "8.0"])
    h = _make_harness(tmp_path)
    assert h._parse_frametimes(p) == pytest.approx([16.0, 8.0])


def test_parse_frametimes_strips_comment_lines(tmp_path):
    p = str(tmp_path / "pm.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        f.write("// PresentMon v1.x header\n")
        f.write("msBetweenPresents\n")
        f.write("16.67\n")
    h = _make_harness(tmp_path)
    assert h._parse_frametimes(p) == pytest.approx([16.67])


def test_parse_frametimes_unknown_column_returns_empty(tmp_path):
    p = str(tmp_path / "pm.csv")
    _write_pm_csv(p, "UnknownColumn", ["16.67"])
    h = _make_harness(tmp_path)
    assert h._parse_frametimes(p) == []


# ---------------------------------------------------------------------------
# _compute_fps_stats
# ---------------------------------------------------------------------------

def test_compute_fps_stats_empty(tmp_path):
    h = _make_harness(tmp_path)
    stats = h._compute_fps_stats([])
    assert stats["avg_fps"] is None
    assert stats["low_1pct_fps"] is None
    assert stats["low_01pct_fps"] is None
    assert stats["avg_frametime_ms"] is None
    assert stats["frametime_stdev_ms"] is None
    assert stats["sample_count"] == 0


def test_compute_fps_stats_single_frame(tmp_path):
    h = _make_harness(tmp_path)
    stats = h._compute_fps_stats([16.67])
    assert stats["sample_count"] == 1
    assert stats["avg_fps"] == pytest.approx(1000 / 16.67, rel=1e-3)
    assert stats["frametime_stdev_ms"] == 0.0


def test_compute_fps_stats_steady_60fps(tmp_path):
    h = _make_harness(tmp_path)
    frametimes = [16.67] * 300
    stats = h._compute_fps_stats(frametimes)
    assert stats["avg_fps"] == pytest.approx(59.99, rel=1e-2)
    assert stats["sample_count"] == 300
    assert stats["low_1pct_fps"] is not None
    assert stats["low_01pct_fps"] is not None


def test_compute_fps_stats_lows_below_average(tmp_path):
    h = _make_harness(tmp_path)
    # 990 fast frames + 10 very slow frames (100 ms → 10 fps)
    frametimes = [8.33] * 990 + [100.0] * 10
    stats = h._compute_fps_stats(frametimes)
    assert stats["low_1pct_fps"] < stats["avg_fps"]


def test_compute_fps_stats_stdev_nonzero_for_mixed(tmp_path):
    h = _make_harness(tmp_path)
    stats = h._compute_fps_stats([10.0, 20.0, 30.0])
    assert stats["frametime_stdev_ms"] > 0


# ---------------------------------------------------------------------------
# save_results
# ---------------------------------------------------------------------------

def test_save_results_writes_valid_json(tmp_path):
    h = _make_harness(tmp_path)
    data = {"score": 88.5, "mission": "test.miz", "sample_count": 500}
    h.save_results(data, "out.json")
    loaded = json.loads((tmp_path / "out.json").read_text())
    assert loaded == data


def test_save_results_overwrites_existing(tmp_path):
    h = _make_harness(tmp_path)
    h.save_results({"v": 1}, "out.json")
    h.save_results({"v": 2}, "out.json")
    loaded = json.loads((tmp_path / "out.json").read_text())
    assert loaded == {"v": 2}
