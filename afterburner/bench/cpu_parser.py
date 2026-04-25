"""Parse bench_monitor.py CSV output into CpuRow objects."""

from __future__ import annotations

import csv
from pathlib import Path

from afterburner.bench.db import CpuRow

_REQUIRED_COLUMNS = {"elapsed_s", "cpu_pct", "mem_mb", "threads"}


def parse_cpu_csv(source: str | Path) -> list[CpuRow]:
    """Parse bench_cpu.csv text or a file path.

    Extra columns are ignored. Blank rows are skipped. Missing required columns
    or invalid numeric values raise ValueError with row context.
    """
    text = (
        source.read_text(encoding="utf-8", errors="replace")
        if isinstance(source, Path)
        else source
    )
    if not text.strip():
        return []

    reader = csv.DictReader(text.splitlines())
    missing = _REQUIRED_COLUMNS - set(reader.fieldnames or [])
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ValueError(f"CPU CSV missing required column(s): {missing_str}")

    rows: list[CpuRow] = []
    for line_num, raw in enumerate(reader, start=2):
        if _is_blank_row(raw):
            continue
        try:
            rows.append(
                CpuRow(
                    elapsed_s=float(_required(raw, "elapsed_s")),
                    cpu_pct=float(_required(raw, "cpu_pct")),
                    mem_mb=float(_required(raw, "mem_mb")),
                    threads=int(float(_required(raw, "threads"))),
                )
            )
        except ValueError as exc:
            raise ValueError(f"Invalid CPU CSV row {line_num}: {exc}") from exc
    return rows


def _required(row: dict[str, str | None], key: str) -> str:
    value = row.get(key)
    if value is None or value == "":
        raise ValueError(f"{key} is required")
    return value


def _is_blank_row(row: dict[str, str | None]) -> bool:
    return all(value in (None, "") for value in row.values())
