"""Parse GM_BENCH lines from a DCS log file into BenchRow objects."""

from __future__ import annotations

import re
from pathlib import Path

from afterburner.bench.db import BenchRow

_GM_BENCH_RE = re.compile(
    r"GM_BENCH drift=(-?[\d.]+)s groups=(\d+) units=(\d+) elapsed=([\d.]+)"
)


def parse_bench_log(source: str | Path) -> list[BenchRow]:
    if isinstance(source, Path):
        text = source.read_text(encoding="utf-8", errors="replace")
    else:
        text = source

    rows: list[BenchRow] = []
    for line in text.splitlines():
        m = _GM_BENCH_RE.search(line)
        if m:
            rows.append(
                BenchRow(
                    elapsed_s=float(m.group(4)),
                    drift_s=float(m.group(1)),
                    groups=int(m.group(2)),
                    units=int(m.group(3)),
                )
            )
    return rows
