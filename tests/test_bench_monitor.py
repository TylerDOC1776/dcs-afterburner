from __future__ import annotations

import argparse
import csv

import pytest

from tools import bench_monitor


class _MemInfo:
    def __init__(self, rss: int):
        self.rss = rss


class _FakeProc:
    def __init__(
        self,
        pid: int,
        name: str,
        cmdline: list[str] | None = None,
    ):
        self.pid = pid
        self.info = {"pid": pid, "name": name, "cmdline": cmdline or []}


class _FakePsutilProcess:
    def __init__(self, cpu_pct: float, rss: int, threads: int):
        self._cpu_pct = cpu_pct
        self._rss = rss
        self._threads = threads

    def cpu_percent(self, interval=None) -> float:
        return self._cpu_pct

    def memory_info(self) -> _MemInfo:
        return _MemInfo(self._rss)

    def num_threads(self) -> int:
        return self._threads


def test_is_dcs_process_name_matches_dcs_server_exe():
    assert bench_monitor._is_dcs_process_name("DCS_server.exe")


def test_find_dcs_instances_uses_cmdline_w_arg(monkeypatch):
    monkeypatch.setattr(
        bench_monitor.psutil,
        "process_iter",
        lambda attrs: [
            _FakeProc(100, "notepad.exe"),
            _FakeProc(
                200,
                "DCS_server.exe",
                ["C:\\DCS\\bin\\DCS_server.exe", "-w", "MemphisBBQ"],
            ),
        ],
    )

    assert bench_monitor.find_dcs_instances() == [
        bench_monitor.DcsInstance("MemphisBBQ", 200, None)
    ]


def test_find_dcs_instances_falls_back_to_pid_name(monkeypatch):
    monkeypatch.setattr(
        bench_monitor.psutil,
        "process_iter",
        lambda attrs: [_FakeProc(200, "DCS.exe", ["C:\\DCS\\bin\\DCS.exe"])],
    )

    assert bench_monitor.find_dcs_instances() == [
        bench_monitor.DcsInstance("DCS_200", 200, None)
    ]


def test_cmd_monitor_selects_single_instance_without_server(monkeypatch, tmp_path):
    selected = {}
    out_path = tmp_path / "bench_cpu.csv"

    monkeypatch.setattr(
        bench_monitor,
        "find_dcs_instances",
        lambda: [bench_monitor.DcsInstance("MemphisBBQ", 200, None)],
    )
    monkeypatch.setattr(
        bench_monitor,
        "monitor",
        lambda instance, interval, out_path, duration: selected.update(
            {
                "instance": instance,
                "interval": interval,
                "out_path": out_path,
                "duration": duration,
            }
        ),
    )

    bench_monitor.cmd_monitor(
        argparse.Namespace(server=None, interval=5.0, out=str(out_path), duration=60.0)
    )

    assert selected == {
        "instance": bench_monitor.DcsInstance("MemphisBBQ", 200, None),
        "interval": 5.0,
        "out_path": str(out_path),
        "duration": 60.0,
    }


def test_cmd_monitor_requires_server_when_multiple(monkeypatch):
    monkeypatch.setattr(
        bench_monitor,
        "find_dcs_instances",
        lambda: [
            bench_monitor.DcsInstance("MemphisBBQ", 200, None),
            bench_monitor.DcsInstance("SouthernBBQ", 300, None),
        ],
    )

    with pytest.raises(SystemExit) as exc:
        bench_monitor.cmd_monitor(
            argparse.Namespace(server=None, interval=5.0, out="x.csv", duration=None)
        )

    assert "Multiple DCS instances" in str(exc.value)


def test_monitor_writes_csv_row(monkeypatch, tmp_path):
    processes = {
        200: _FakePsutilProcess(cpu_pct=80.0, rss=512 * 1_048_576, threads=42),
    }
    clock = {"now": 0.0}

    monkeypatch.setattr(
        bench_monitor.psutil,
        "Process",
        lambda pid: processes[pid],
    )
    monkeypatch.setattr(bench_monitor.psutil, "cpu_count", lambda logical=True: 4)
    monkeypatch.setattr(bench_monitor.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(
        bench_monitor.time,
        "sleep",
        lambda seconds: clock.update(now=clock["now"] + seconds),
    )

    out_path = tmp_path / "nested" / "bench_cpu.csv"
    bench_monitor.monitor(
        bench_monitor.DcsInstance("MemphisBBQ", 200, None),
        interval=5.0,
        out_path=out_path,
        duration=5.0,
    )

    with out_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert rows == [
        {
            "timestamp_utc": rows[0]["timestamp_utc"],
            "elapsed_s": "5.0",
            "cpu_pct": "20.0",
            "cpu_pct_raw": "80.0",
            "mem_mb": "512.0",
            "threads": "42",
            "child_cpu_pct": "",
            "child_mem_mb": "",
        }
    ]


def test_monitor_rejects_non_positive_interval(tmp_path):
    with pytest.raises(SystemExit) as exc:
        bench_monitor.monitor(
            bench_monitor.DcsInstance("MemphisBBQ", 200, None),
            interval=0,
            out_path=tmp_path / "bench_cpu.csv",
        )

    assert "--interval must be greater than 0" in str(exc.value)
