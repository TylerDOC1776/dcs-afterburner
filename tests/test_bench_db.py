"""Tests for bench SQLite persistence and the bench record/push CLI commands."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from afterburner.bench.db import (
    BenchRow,
    CpuRow,
    create_run,
    finish_run,
    get_log_issue_rows,
    insert_bench_rows,
    insert_cpu_rows,
    open_db,
)
from afterburner.cli import app

runner = CliRunner()

_MISSION_LUA = """\
mission =
{
["theatre"] =
"Caucasus",
["sortie"] =
"Bench Test",
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

_BENCH_LOG = """\
2026-04-25 10:00:00.000 INFO GM_BENCH drift=0.012s groups=20 units=140 elapsed=5.0
2026-04-25 10:00:05.000 INFO GM_BENCH drift=0.015s groups=21 units=145 elapsed=10.0
2026-04-25 10:00:10.000 INFO GM_BENCH drift=0.010s groups=22 units=150 elapsed=15.0
"""

_CPU_CSV = "elapsed_s,cpu_pct,mem_mb,threads\n5.0,35.0,1024.0,20\n10.0,40.0,1050.0,21\n"


def _make_miz(path: Path) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mission", _MISSION_LUA)
        zf.writestr("options", "options =\n{\n}\n")
        zf.writestr("dictionary", "dictionary =\n{\n}\n")
        zf.writestr("l10n/DEFAULT/dictionary", "dictionary =\n{\n}\n")


# ---------------------------------------------------------------------------
# db unit tests
# ---------------------------------------------------------------------------


def test_open_db_creates_schema(tmp_path):
    conn = open_db(tmp_path / "bench.db")
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {
        "runs",
        "bench_timeseries",
        "cpu_timeseries",
        "findings",
        "log_issues",
    } <= tables
    conn.close()


def test_create_and_finish_run(tmp_path):
    conn = open_db(tmp_path / "bench.db")
    run_id = create_run(conn, "TestMission", "2026-04-25T10:00:00+00:00")
    assert isinstance(run_id, int)

    finish_run(
        conn,
        run_id,
        "2026-04-25T11:00:00+00:00",
        3600,
        intended_duration_s=1800,
        bench_elapsed_s=15,
        run_quality="ok",
        injection_status="injected",
    )
    row = conn.execute(
        "SELECT mission, duration_s, intended_duration_s, bench_elapsed_s, run_quality, injection_status FROM runs WHERE id=?",
        (run_id,),
    ).fetchone()
    assert row == ("TestMission", 3600, 1800, 15, "ok", "injected")
    conn.close()


def test_insert_bench_rows(tmp_path):
    conn = open_db(tmp_path / "bench.db")
    run_id = create_run(conn, "M", "2026-04-25T10:00:00+00:00")
    rows = [BenchRow(5.0, 0.01, 20, 140), BenchRow(10.0, 0.02, 21, 145)]
    insert_bench_rows(conn, run_id, rows)

    stored = conn.execute(
        "SELECT elapsed_s, groups, units FROM bench_timeseries WHERE run_id=? ORDER BY elapsed_s",
        (run_id,),
    ).fetchall()
    assert stored == [(5.0, 20, 140), (10.0, 21, 145)]
    conn.close()


def test_insert_cpu_rows(tmp_path):
    conn = open_db(tmp_path / "bench.db")
    run_id = create_run(conn, "M", "2026-04-25T10:00:00+00:00")
    rows = [CpuRow(5.0, 35.0, 1024.0, 20)]
    insert_cpu_rows(conn, run_id, rows)

    stored = conn.execute(
        "SELECT cpu_pct, mem_mb FROM cpu_timeseries WHERE run_id=?", (run_id,)
    ).fetchone()
    assert stored == (35.0, 1024.0)
    conn.close()


# ---------------------------------------------------------------------------
# bench record CLI tests
# ---------------------------------------------------------------------------


def test_bench_record_basic(tmp_path):
    miz = tmp_path / "GoonFront.miz"
    _make_miz(miz)
    log = tmp_path / "dcs.log"
    log.write_text(_BENCH_LOG, encoding="utf-8")
    db = tmp_path / "bench.db"

    result = runner.invoke(
        app, ["bench", "record", str(miz), "--log", str(log), "--db", str(db)]
    )
    assert result.exit_code == 0, result.output
    assert "Recorded run #1" in result.output
    assert "3 bench samples" in result.output

    conn = open_db(db)
    count = conn.execute("SELECT COUNT(*) FROM bench_timeseries").fetchone()[0]
    assert count == 3
    conn.close()


def test_bench_record_with_cpu_csv(tmp_path):
    miz = tmp_path / "GoonFront.miz"
    _make_miz(miz)
    log = tmp_path / "dcs.log"
    log.write_text(_BENCH_LOG, encoding="utf-8")
    cpu = tmp_path / "bench_cpu.csv"
    cpu.write_text(_CPU_CSV, encoding="utf-8")
    db = tmp_path / "bench.db"

    result = runner.invoke(
        app,
        [
            "bench",
            "record",
            str(miz),
            "--log",
            str(log),
            "--cpu",
            str(cpu),
            "--db",
            str(db),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "2 CPU samples" in result.output

    conn = open_db(db)
    count = conn.execute("SELECT COUNT(*) FROM cpu_timeseries").fetchone()[0]
    assert count == 2
    conn.close()


def test_bench_record_no_bench_lines_warns(tmp_path):
    miz = tmp_path / "GoonFront.miz"
    _make_miz(miz)
    log = tmp_path / "dcs.log"
    log.write_text(
        "2026-04-25 10:00:00.000 INFO EDCORE: DCS started\n", encoding="utf-8"
    )
    db = tmp_path / "bench.db"

    result = runner.invoke(
        app, ["bench", "record", str(miz), "--log", str(log), "--db", str(db)]
    )
    assert result.exit_code == 0
    assert "Warning" in result.output

    conn = open_db(db)
    count = conn.execute("SELECT COUNT(*) FROM bench_timeseries").fetchone()[0]
    quality = conn.execute("SELECT run_quality FROM runs WHERE id=1").fetchone()[0]
    assert count == 0
    assert quality == "no_bench_rows"
    conn.close()


def test_bench_record_missing_log(tmp_path):
    miz = tmp_path / "GoonFront.miz"
    _make_miz(miz)
    db = tmp_path / "bench.db"

    result = runner.invoke(
        app,
        [
            "bench",
            "record",
            str(miz),
            "--log",
            str(tmp_path / "missing.log"),
            "--db",
            str(db),
        ],
    )
    assert result.exit_code == 2


def test_bench_record_duration_tracks_intended_and_bench_elapsed(tmp_path):
    miz = tmp_path / "GoonFront.miz"
    _make_miz(miz)
    log = tmp_path / "dcs.log"
    log.write_text(_BENCH_LOG, encoding="utf-8")
    db = tmp_path / "bench.db"

    runner.invoke(
        app,
        [
            "bench",
            "record",
            str(miz),
            "--log",
            str(log),
            "--intended-duration",
            "1800",
            "--injection-status",
            "injected",
            "--db",
            str(db),
        ],
    )

    conn = open_db(db)
    duration, intended, elapsed, quality, injection = conn.execute(
        "SELECT duration_s, intended_duration_s, bench_elapsed_s, run_quality, injection_status FROM runs WHERE id=1"
    ).fetchone()
    assert duration == 1800
    assert intended == 1800
    assert elapsed == 15
    assert quality == "partial_bench_rows"
    assert injection == "injected"
    conn.close()


def test_bench_record_stores_hard_stop_log_issue(tmp_path):
    miz = tmp_path / "GoonFront.miz"
    _make_miz(miz)
    log = tmp_path / "dcs.log"
    log.write_text(
        '2026-04-27 08:09:02.503 ERROR   SCRIPTING (Main): Mission script error: [string "assert(loadfile(\\"C:/Scripts/Moose.lua\\"))()"]:1: no file \'C:/Scripts/Moose.lua\'\n',
        encoding="utf-8",
    )
    db = tmp_path / "bench.db"

    result = runner.invoke(
        app, ["bench", "record", str(miz), "--log", str(log), "--db", str(db)]
    )
    assert result.exit_code == 0, result.output

    conn = open_db(db)
    quality, hard_stop = conn.execute(
        "SELECT run_quality, hard_stop_error FROM runs WHERE id=1"
    ).fetchone()
    issues = get_log_issue_rows(conn, 1)
    assert quality == "mission_script_hard_stop"
    assert "Moose.lua" in hard_stop
    assert issues[0]["issue_type"] == "hard_stop"
    conn.close()


# ---------------------------------------------------------------------------
# bench push CLI tests
# ---------------------------------------------------------------------------


def _seed_db(db: Path) -> None:
    """Create a DB with one fully-populated run."""
    miz = db.parent / "GoonFront.miz"
    _make_miz(miz)
    log = db.parent / "dcs.log"
    log.write_text(_BENCH_LOG, encoding="utf-8")
    cpu = db.parent / "bench_cpu.csv"
    cpu.write_text(_CPU_CSV, encoding="utf-8")
    runner.invoke(
        app,
        [
            "bench",
            "record",
            str(miz),
            "--log",
            str(log),
            "--cpu",
            str(cpu),
            "--db",
            str(db),
        ],
    )


def _mock_post(status_code: int = 201, body: dict | None = None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body or {"id": "brun_abc123"}
    resp.text = json.dumps(body or {"id": "brun_abc123"})
    if status_code >= 400:
        import httpx

        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def test_bench_push_latest_run(tmp_path):
    db = tmp_path / "bench.db"
    _seed_db(db)

    with patch("httpx.post", return_value=_mock_post()) as mock_post:
        result = runner.invoke(
            app,
            [
                "bench",
                "push",
                "https://example.com",
                "--host-id",
                "host_abc",
                "--key",
                "secret",
                "--db",
                str(db),
            ],
        )

    assert result.exit_code == 0, result.output
    assert "brun_abc123" in result.output

    call_kwargs = mock_post.call_args
    sent = call_kwargs.kwargs["json"]
    assert sent["mission"] == "GoonFront"
    assert sent["run_quality"] == "ok"
    assert "log_issues" in sent
    assert len(sent["bench_timeseries"]) == 3
    assert len(sent["cpu_timeseries"]) == 2
    assert call_kwargs.kwargs["headers"] == {
        "X-Host-Id": "host_abc",
        "X-Agent-Key": "secret",
    }


def test_bench_push_specific_run_id(tmp_path):
    db = tmp_path / "bench.db"
    _seed_db(db)

    with patch("httpx.post", return_value=_mock_post()) as mock_post:
        result = runner.invoke(
            app,
            [
                "bench",
                "push",
                "https://example.com",
                "--host-id",
                "host_abc",
                "--key",
                "secret",
                "--run-id",
                "1",
                "--db",
                str(db),
            ],
        )

    assert result.exit_code == 0, result.output
    assert mock_post.called


def test_bench_push_missing_db(tmp_path):
    result = runner.invoke(
        app,
        [
            "bench",
            "push",
            "https://example.com",
            "--host-id",
            "host_abc",
            "--key",
            "secret",
            "--db",
            str(tmp_path / "missing.db"),
        ],
    )
    assert result.exit_code == 2


def test_bench_push_http_error(tmp_path):
    db = tmp_path / "bench.db"
    _seed_db(db)

    with patch(
        "httpx.post",
        return_value=_mock_post(status_code=401, body={"detail": "Unauthorized"}),
    ):
        result = runner.invoke(
            app,
            [
                "bench",
                "push",
                "https://example.com",
                "--host-id",
                "host_abc",
                "--key",
                "wrong",
                "--db",
                str(db),
            ],
        )

    assert result.exit_code == 1
