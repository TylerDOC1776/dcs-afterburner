"""SQLite persistence for benchmark runs."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from afterburner.models.findings import ReportFinding

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY,
    mission     TEXT    NOT NULL,
    started_at  TEXT    NOT NULL,
    ended_at    TEXT,
    duration_s  INTEGER,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS bench_timeseries (
    run_id    INTEGER NOT NULL REFERENCES runs(id),
    elapsed_s REAL    NOT NULL,
    drift_s   REAL    NOT NULL,
    groups    INTEGER NOT NULL,
    units     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cpu_timeseries (
    run_id    INTEGER NOT NULL REFERENCES runs(id),
    elapsed_s REAL    NOT NULL,
    cpu_pct   REAL    NOT NULL,
    mem_mb    REAL    NOT NULL,
    threads   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
    run_id   INTEGER NOT NULL REFERENCES runs(id),
    rule_id  TEXT    NOT NULL,
    severity TEXT    NOT NULL,
    detail   TEXT
);

CREATE INDEX IF NOT EXISTS idx_bench_run    ON bench_timeseries(run_id);
CREATE INDEX IF NOT EXISTS idx_cpu_run      ON cpu_timeseries(run_id);
CREATE INDEX IF NOT EXISTS idx_findings_run ON findings(run_id);
"""


@dataclass
class BenchRow:
    elapsed_s: float
    drift_s: float
    groups: int
    units: int


@dataclass
class CpuRow:
    elapsed_s: float
    cpu_pct: float
    mem_mb: float
    threads: int


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    return conn


def create_run(
    conn: sqlite3.Connection,
    mission: str,
    started_at: str,
    notes: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO runs (mission, started_at, notes) VALUES (?, ?, ?)",
        (mission, started_at, notes),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    ended_at: str,
    duration_s: int,
) -> None:
    conn.execute(
        "UPDATE runs SET ended_at=?, duration_s=? WHERE id=?",
        (ended_at, duration_s, run_id),
    )
    conn.commit()


def insert_bench_rows(
    conn: sqlite3.Connection,
    run_id: int,
    rows: list[BenchRow],
) -> None:
    conn.executemany(
        "INSERT INTO bench_timeseries VALUES (?,?,?,?,?)",
        [(run_id, r.elapsed_s, r.drift_s, r.groups, r.units) for r in rows],
    )
    conn.commit()


def insert_cpu_rows(
    conn: sqlite3.Connection,
    run_id: int,
    rows: list[CpuRow],
) -> None:
    conn.executemany(
        "INSERT INTO cpu_timeseries VALUES (?,?,?,?,?)",
        [(run_id, r.elapsed_s, r.cpu_pct, r.mem_mb, r.threads) for r in rows],
    )
    conn.commit()


def insert_findings(
    conn: sqlite3.Connection,
    run_id: int,
    findings: list[ReportFinding],
) -> None:
    conn.executemany(
        "INSERT INTO findings VALUES (?,?,?,?)",
        [(run_id, f.rule_id, f.severity.value, f.detail) for f in findings],
    )
    conn.commit()


def get_run(conn: sqlite3.Connection, run_id: int) -> dict | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    return dict(row) if row else None


def latest_run_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("SELECT id FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    return row[0] if row else None


def get_bench_rows(conn: sqlite3.Connection, run_id: int) -> list[BenchRow]:
    rows = conn.execute(
        "SELECT elapsed_s, drift_s, groups, units FROM bench_timeseries WHERE run_id=? ORDER BY elapsed_s",
        (run_id,),
    ).fetchall()
    return [
        BenchRow(elapsed_s=r[0], drift_s=r[1], groups=r[2], units=r[3]) for r in rows
    ]


def get_cpu_rows(conn: sqlite3.Connection, run_id: int) -> list[CpuRow]:
    rows = conn.execute(
        "SELECT elapsed_s, cpu_pct, mem_mb, threads FROM cpu_timeseries WHERE run_id=? ORDER BY elapsed_s",
        (run_id,),
    ).fetchall()
    return [
        CpuRow(elapsed_s=r[0], cpu_pct=r[1], mem_mb=r[2], threads=r[3]) for r in rows
    ]


def get_finding_rows(conn: sqlite3.Connection, run_id: int) -> list[dict]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT rule_id, severity, detail FROM findings WHERE run_id=?",
        (run_id,),
    ).fetchall()
    return [dict(r) for r in rows]
