from __future__ import annotations

import pytest

from afterburner.bench.cpu_parser import parse_cpu_csv
from afterburner.bench.db import CpuRow


def test_parse_cpu_csv_valid_rows():
    text = """timestamp_utc,elapsed_s,cpu_pct,cpu_pct_raw,mem_mb,threads,child_cpu_pct,child_mem_mb
2026-04-24T12:00:05+00:00,5.0,20.0,80.0,512.0,42,5.0,128.0
2026-04-24T12:00:10+00:00,10.0,22.5,90.0,520.5,43,,
"""

    assert parse_cpu_csv(text) == [
        CpuRow(elapsed_s=5.0, cpu_pct=20.0, mem_mb=512.0, threads=42),
        CpuRow(elapsed_s=10.0, cpu_pct=22.5, mem_mb=520.5, threads=43),
    ]


def test_parse_cpu_csv_from_path(tmp_path):
    path = tmp_path / "bench_cpu.csv"
    path.write_text(
        "elapsed_s,cpu_pct,mem_mb,threads\n5.0,20.0,512.0,42\n",
        encoding="utf-8",
    )

    assert parse_cpu_csv(path) == [
        CpuRow(elapsed_s=5.0, cpu_pct=20.0, mem_mb=512.0, threads=42)
    ]


def test_parse_cpu_csv_empty_text():
    assert parse_cpu_csv("") == []


def test_parse_cpu_csv_header_only():
    assert parse_cpu_csv("elapsed_s,cpu_pct,mem_mb,threads\n") == []


def test_parse_cpu_csv_ignores_extra_columns():
    text = "elapsed_s,cpu_pct,mem_mb,threads,extra\n5,20,512,42,ignored\n"

    assert parse_cpu_csv(text) == [
        CpuRow(elapsed_s=5.0, cpu_pct=20.0, mem_mb=512.0, threads=42)
    ]


def test_parse_cpu_csv_skips_blank_rows():
    text = "elapsed_s,cpu_pct,mem_mb,threads\n5,20,512,42\n,,,\n10,25,600,44\n"

    assert parse_cpu_csv(text) == [
        CpuRow(elapsed_s=5.0, cpu_pct=20.0, mem_mb=512.0, threads=42),
        CpuRow(elapsed_s=10.0, cpu_pct=25.0, mem_mb=600.0, threads=44),
    ]


def test_parse_cpu_csv_missing_required_column():
    with pytest.raises(ValueError, match="missing required column"):
        parse_cpu_csv("elapsed_s,cpu_pct,threads\n5,20,42\n")


def test_parse_cpu_csv_missing_required_value():
    with pytest.raises(ValueError, match="Invalid CPU CSV row 2: mem_mb is required"):
        parse_cpu_csv("elapsed_s,cpu_pct,mem_mb,threads\n5,20,,42\n")


def test_parse_cpu_csv_invalid_numeric_value():
    with pytest.raises(ValueError, match="Invalid CPU CSV row 2"):
        parse_cpu_csv("elapsed_s,cpu_pct,mem_mb,threads\n5,nope,512,42\n")


def test_parse_cpu_csv_threads_accepts_float_string():
    text = "elapsed_s,cpu_pct,mem_mb,threads\n5,20,512,42.0\n"

    assert parse_cpu_csv(text) == [
        CpuRow(elapsed_s=5.0, cpu_pct=20.0, mem_mb=512.0, threads=42)
    ]
