"""DCS Afterburner CLI entry point."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

import afterburner.rules  # noqa: F401 — triggers rule registration
from afterburner.models.report import Report
from afterburner.parsers.mission_parser import parse
from afterburner.reporters.console import print_summary
from afterburner.reporters.json_report import to_json
from afterburner.reporters.markdown import to_markdown
from afterburner.rules.base import get_registry, run_all

app = typer.Typer(name="afterburner", add_completion=False, no_args_is_help=True)
_rules_app = typer.Typer(name="rules", no_args_is_help=True)
_bench_app = typer.Typer(name="bench", no_args_is_help=True)
app.add_typer(_rules_app, name="rules", help="List and explain lint rules.")
app.add_typer(_bench_app, name="bench", help="Benchmark mission tooling.")
_err = Console(stderr=True)


@app.callback()
def _root() -> None:
    """DCS Afterburner — mission linting and diagnostics for DCS World .miz files."""


@app.command()
def analyze(
    mission: Path = typer.Argument(..., help="Path to .miz file"),
    log_file: Path = typer.Option(
        None,
        "--log",
        help="Path to DCS log file (dcs.log) to correlate with mission findings",
    ),
    as_json: bool = typer.Option(False, "--json", help="Output machine-readable JSON"),
    fail_on: str = typer.Option(
        "none",
        "--fail-on",
        help="Exit non-zero if any finding at this severity or above exists (critical|warning|info|none)",
    ),
) -> None:
    """Analyze a DCS .miz mission file and print a summary."""
    if not mission.exists():
        _err.print(f"[red]Error:[/red] File not found: {mission}")
        raise typer.Exit(2)
    if mission.suffix.lower() != ".miz":
        _err.print(f"[red]Error:[/red] Expected a .miz file, got: {mission}")
        raise typer.Exit(2)

    try:
        parsed = parse(mission)
    except Exception as exc:
        _err.print(f"[red]Error parsing mission:[/red] {exc}")
        raise typer.Exit(2)

    rule_findings = run_all(parsed)
    log_findings = []
    log_meta: dict | None = None

    if log_file is not None:
        if not log_file.exists():
            _err.print(f"[red]Error:[/red] Log file not found: {log_file}")
            raise typer.Exit(2)
        from afterburner.log_analysis.correlator import boost_findings, correlate
        from afterburner.log_analysis.parser import parse_log

        try:
            events = parse_log(log_file)
        except Exception as exc:
            _err.print(f"[red]Error reading log:[/red] {exc}")
            raise typer.Exit(2)

        log_findings = correlate(events)
        rule_findings = boost_findings(rule_findings, log_findings)
        log_meta = {"source": str(log_file), "events_parsed": len(events)}

    report = Report(mission=parsed, findings=rule_findings + log_findings)

    if as_json:
        data = to_json(report)
        if log_meta:
            data["log_source"] = log_meta["source"]
            data["log_events_parsed"] = log_meta["events_parsed"]
        print(json.dumps(data, indent=2))
    else:
        print_summary(report, log_meta=log_meta)

    _check_fail_on(report, fail_on)


@app.command()
def report(
    mission: Path = typer.Argument(..., help="Path to .miz file"),
    fmt: str = typer.Option("md", "--format", help="Output format: md"),
) -> None:
    """Generate a full mission report."""
    if not mission.exists():
        _err.print(f"[red]Error:[/red] File not found: {mission}")
        raise typer.Exit(2)
    if mission.suffix.lower() != ".miz":
        _err.print(f"[red]Error:[/red] Expected a .miz file, got: {mission}")
        raise typer.Exit(2)

    try:
        parsed = parse(mission)
    except Exception as exc:
        _err.print(f"[red]Error parsing mission:[/red] {exc}")
        raise typer.Exit(2)

    findings = run_all(parsed)
    rep = Report(mission=parsed, findings=findings)

    if fmt == "md":
        print(to_markdown(rep))
    else:
        _err.print(f"[red]Error:[/red] Unknown format: {fmt!r}. Supported: md")
        raise typer.Exit(2)


@app.command()
def optimize(
    mission: Path = typer.Argument(..., help="Path to .miz file"),
    safe: bool = typer.Option(
        False, "--safe", help="Apply safe, zero-risk optimizations"
    ),
    output: Path = typer.Option(
        None, "--output", help="Output path (default: <stem>.optimized.miz)"
    ),
    as_json: bool = typer.Option(False, "--json", help="Output change log as JSON"),
) -> None:
    """Apply safe optimizations to a .miz file."""
    if not safe:
        _err.print(
            "[red]Error:[/red] --safe flag is required. "
            "Run with --safe to apply zero-risk optimizations."
        )
        raise typer.Exit(2)
    if not mission.exists():
        _err.print(f"[red]Error:[/red] File not found: {mission}")
        raise typer.Exit(2)
    if mission.suffix.lower() != ".miz":
        _err.print(f"[red]Error:[/red] Expected a .miz file, got: {mission}")
        raise typer.Exit(2)

    from afterburner.optimize.engine import run_safe_optimizations

    try:
        result = run_safe_optimizations(mission, output)
    except FileExistsError as exc:
        _err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2)
    except ValueError as exc:
        _err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2)
    except Exception as exc:
        _err.print(f"[red]Error during optimization:[/red] {exc}")
        raise typer.Exit(2)

    if as_json:
        import json

        print(
            json.dumps(
                {
                    "source": str(result.source),
                    "output": str(result.output),
                    "backup": str(result.backup),
                    "bytes_before": result.bytes_before,
                    "bytes_after": result.bytes_after,
                    "bytes_saved": result.bytes_saved,
                    "changes": [
                        {
                            "transform_id": c.transform_id,
                            "status": c.status,
                            "detail": c.detail,
                            "bytes_saved": c.bytes_saved,
                        }
                        for c in result.changes
                    ],
                },
                indent=2,
            )
        )
    else:
        from rich import box
        from rich.console import Console
        from rich.table import Table

        con = Console()
        con.print()
        con.print(
            f"[bold cyan]DCS Afterburner — Optimize[/bold cyan]  [dim]{mission.name}[/dim]"
        )
        con.print()

        applied = [c for c in result.changes if c.status == "applied"]
        skipped = [c for c in result.changes if c.status == "skipped"]

        if applied or skipped:
            table = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
            table.add_column("Status", min_width=9)
            table.add_column("ID", min_width=9, style="bold")
            table.add_column("Detail")
            table.add_column("Saved", justify="right")

            for c in result.changes:
                status_style = "green" if c.status == "applied" else "dim"
                saved_str = (
                    f"-{c.bytes_saved / 1024:.1f} KB" if c.bytes_saved > 0 else ""
                )
                table.add_row(
                    f"[{status_style}]{c.status.upper()}[/{status_style}]",
                    c.transform_id,
                    c.detail,
                    saved_str,
                )
            con.print(table)

        pct = result.pct_saved * 100
        size_str = (
            f"{result.bytes_before / 1_048_576:.1f} MB → "
            f"{result.bytes_after / 1_048_576:.1f} MB, "
            f"-{result.bytes_saved / 1024:.0f} KB / -{pct:.1f}%"
        )
        con.print(f"Backup:  [dim]{result.backup.name}[/dim]")
        con.print(f"Output:  [green]{result.output.name}[/green]  ({size_str})")
        con.print()


@app.command()
def logs(
    log_file: Path = typer.Argument(..., help="Path to DCS log file (dcs.log)"),
    as_json: bool = typer.Option(False, "--json", help="Output machine-readable JSON"),
    fail_on: str = typer.Option(
        "none",
        "--fail-on",
        help="Exit non-zero if any finding at this severity or above exists (critical|warning|info|none)",
    ),
) -> None:
    """Analyze a DCS log file for known error patterns."""
    if not log_file.exists():
        _err.print(f"[red]Error:[/red] File not found: {log_file}")
        raise typer.Exit(2)

    from afterburner.log_analysis.correlator import correlate
    from afterburner.log_analysis.parser import parse_log
    from afterburner.models.findings import Severity

    try:
        events = parse_log(log_file)
    except Exception as exc:
        _err.print(f"[red]Error reading log:[/red] {exc}")
        raise typer.Exit(2)

    findings = correlate(events)

    if as_json:
        print(
            json.dumps(
                {
                    "source_file": str(log_file),
                    "events_parsed": len(events),
                    "findings": [
                        {
                            "rule_id": f.rule_id,
                            "severity": f.severity.value,
                            "title": f.title,
                            "detail": f.detail,
                            "fix": f.fix,
                            "confidence": f.confidence,
                        }
                        for f in findings
                    ],
                },
                indent=2,
            )
        )
    else:
        from rich.console import Console

        _SEVERITY_STYLE = {
            Severity.CRITICAL: "red",
            Severity.WARNING: "yellow",
            Severity.INFO: "cyan",
        }
        con = Console()
        con.print()
        con.print(
            f"[bold cyan]DCS Afterburner — Logs[/bold cyan]  [dim]{log_file.name}[/dim]"
        )
        con.print(f"Events parsed: [dim]{len(events)}[/dim]")
        con.print()
        if findings:
            for f in findings:
                style = _SEVERITY_STYLE.get(f.severity, "white")
                con.print(
                    f"  [{style}]{f.severity.value.upper():8}[/{style}]  "
                    f"[bold]{f.rule_id}[/bold]  {f.title}"
                )
                con.print(f"           {f.detail}")
                if f.fix:
                    con.print(f"           [dim]Fix: {f.fix}[/dim]")
        else:
            con.print("[green]No findings.[/green]")
        con.print()

    _check_fail_on_findings(findings, fail_on)


@app.command()
def diff(
    old_mission: Path = typer.Argument(..., metavar="OLD", help="Baseline .miz file"),
    new_mission: Path = typer.Argument(..., metavar="NEW", help="Updated .miz file"),
    as_json: bool = typer.Option(False, "--json", help="Output machine-readable JSON"),
) -> None:
    """Compare two DCS .miz mission files and show what changed."""
    for path in (old_mission, new_mission):
        if not path.exists():
            _err.print(f"[red]Error:[/red] File not found: {path}")
            raise typer.Exit(2)
        if path.suffix.lower() != ".miz":
            _err.print(f"[red]Error:[/red] Expected a .miz file, got: {path}")
            raise typer.Exit(2)

    try:
        old_parsed = parse(old_mission)
    except Exception as exc:
        _err.print(f"[red]Error parsing {old_mission.name}:[/red] {exc}")
        raise typer.Exit(2)

    try:
        new_parsed = parse(new_mission)
    except Exception as exc:
        _err.print(f"[red]Error parsing {new_mission.name}:[/red] {exc}")
        raise typer.Exit(2)

    from afterburner.diff import compute, print_diff
    from afterburner.diff import to_json as diff_to_json

    result = compute(old_parsed, new_parsed)

    if as_json:
        print(json.dumps(diff_to_json(result), indent=2))
    else:
        print_diff(result)


# ---------------------------------------------------------------------------
# bench subcommands
# ---------------------------------------------------------------------------


@_bench_app.callback()
def _bench_root() -> None:
    """Benchmark mission tooling."""


@_bench_app.command("inject")
def bench_inject(
    mission: Path = typer.Argument(..., help="Path to source .miz file"),
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Output path for the instrumented benchmark .miz",
    ),
) -> None:
    """Inject the GM_BENCH timer into a .miz file."""
    if not mission.exists():
        _err.print(f"[red]Error:[/red] File not found: {mission}")
        raise typer.Exit(2)
    if mission.suffix.lower() != ".miz":
        _err.print(f"[red]Error:[/red] Expected a .miz file, got: {mission}")
        raise typer.Exit(2)

    mission_resolved = mission.resolve()
    output_resolved = output.resolve()
    if output_resolved == mission_resolved:
        _err.print(
            f"[red]Error:[/red] Output path is the same as input: {mission}. "
            "Use a different --output path."
        )
        raise typer.Exit(2)
    if output.exists():
        _err.print(f"[red]Error:[/red] Output already exists: {output}")
        raise typer.Exit(2)

    from afterburner.bench.inject import inject

    try:
        inject(mission_resolved, output_resolved)
    except FileExistsError as exc:
        _err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2)
    except RuntimeError as exc:
        _err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2)
    except Exception as exc:
        _err.print(f"[red]Error injecting benchmark script:[/red] {exc}")
        raise typer.Exit(2)

    con = Console()
    con.print(f"[green]Injected GM_BENCH:[/green] {output_resolved}")


@_bench_app.command("record")
def bench_record(
    mission: Path = typer.Argument(..., help="Path to .miz file"),
    log_file: Path = typer.Option(
        ..., "--log", help="DCS log file containing GM_BENCH lines"
    ),
    cpu_csv: Path = typer.Option(
        None, "--cpu", help="bench_monitor CSV output (bench_cpu.csv)"
    ),
    db_path: Path = typer.Option(
        Path.home() / ".afterburner" / "bench.db",
        "--db",
        help="SQLite DB path (created if absent)",
    ),
    notes: str = typer.Option(None, "--notes", help="Free-text notes for this run"),
) -> None:
    """Import a GM_BENCH run into the SQLite database."""
    from datetime import datetime, timezone

    from afterburner.bench.cpu_parser import parse_cpu_csv
    from afterburner.bench.db import (
        create_run,
        finish_run,
        insert_bench_rows,
        insert_cpu_rows,
        insert_findings,
        open_db,
    )
    from afterburner.bench.log_parser import parse_bench_log

    for label, path in [("Mission", mission), ("Log", log_file)]:
        if not path.exists():
            _err.print(f"[red]Error:[/red] {label} file not found: {path}")
            raise typer.Exit(2)
    if mission.suffix.lower() != ".miz":
        _err.print(f"[red]Error:[/red] Expected a .miz file, got: {mission}")
        raise typer.Exit(2)
    if cpu_csv is not None and not cpu_csv.exists():
        _err.print(f"[red]Error:[/red] CPU CSV not found: {cpu_csv}")
        raise typer.Exit(2)

    bench_rows = parse_bench_log(log_file)
    if not bench_rows:
        _err.print(
            "[yellow]Warning:[/yellow] No GM_BENCH lines found in log — is gm_bench.lua injected?"
        )

    cpu_rows = []
    if cpu_csv is not None:
        try:
            cpu_rows = parse_cpu_csv(cpu_csv)
        except ValueError as exc:
            _err.print(f"[red]Error parsing CPU CSV:[/red] {exc}")
            raise typer.Exit(2)

    try:
        parsed = parse(mission)
    except Exception as exc:
        _err.print(f"[red]Error parsing mission:[/red] {exc}")
        raise typer.Exit(2)

    findings = run_all(parsed)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = open_db(db_path)

    now = datetime.now(timezone.utc).isoformat()
    run_id = create_run(conn, mission.stem, now, notes)

    if bench_rows:
        insert_bench_rows(conn, run_id, bench_rows)
    if cpu_rows:
        insert_cpu_rows(conn, run_id, cpu_rows)
    if findings:
        insert_findings(conn, run_id, findings)

    duration_s = int(max((r.elapsed_s for r in bench_rows), default=0))
    finish_run(conn, run_id, now, duration_s)
    conn.close()

    con = Console()
    con.print(
        f"[green]Recorded run #{run_id}:[/green] {mission.stem}  "
        f"[dim]{len(bench_rows)} bench samples, {len(cpu_rows)} CPU samples, "
        f"{len(findings)} findings, {duration_s}s[/dim]"
    )
    con.print(f"[dim]DB: {db_path}[/dim]")


@_bench_app.command("push")
def bench_push(
    url: str = typer.Argument(
        ..., help="Orchestrator base URL (e.g. https://example.com)"
    ),
    host_id: str = typer.Option(
        ..., "--host-id", help="Agent host ID (from orchestrator registration)"
    ),
    key: str = typer.Option(..., "--key", help="Agent API key"),
    run_id: int = typer.Option(
        None, "--run-id", help="Run ID to push (default: latest)"
    ),
    db_path: Path = typer.Option(
        Path.home() / ".afterburner" / "bench.db",
        "--db",
        help="SQLite DB path",
    ),
) -> None:
    """Push a recorded bench run to the orchestrator."""
    import httpx

    from afterburner.bench.db import (
        get_bench_rows,
        get_cpu_rows,
        get_finding_rows,
        get_run,
        latest_run_id,
        open_db,
    )

    if not db_path.exists():
        _err.print(f"[red]Error:[/red] DB not found: {db_path}")
        raise typer.Exit(2)

    conn = open_db(db_path)

    resolved_id = run_id if run_id is not None else latest_run_id(conn)
    if resolved_id is None:
        _err.print("[red]Error:[/red] No runs in DB.")
        raise typer.Exit(2)

    run = get_run(conn, resolved_id)
    if run is None:
        _err.print(f"[red]Error:[/red] Run #{resolved_id} not found.")
        raise typer.Exit(2)

    bench_rows = get_bench_rows(conn, resolved_id)
    cpu_rows = get_cpu_rows(conn, resolved_id)
    finding_rows = get_finding_rows(conn, resolved_id)
    conn.close()

    payload = {
        "mission": run["mission"],
        "started_at": run["started_at"],
        "ended_at": run.get("ended_at"),
        "duration_s": run.get("duration_s"),
        "notes": run.get("notes"),
        "bench_timeseries": [
            {
                "elapsed_s": r.elapsed_s,
                "drift_s": r.drift_s,
                "groups": r.groups,
                "units": r.units,
            }
            for r in bench_rows
        ],
        "cpu_timeseries": [
            {
                "elapsed_s": r.elapsed_s,
                "cpu_pct": r.cpu_pct,
                "mem_mb": r.mem_mb,
                "threads": r.threads,
            }
            for r in cpu_rows
        ],
        "findings": finding_rows,
    }

    endpoint = url.rstrip("/") + "/api/v1/bench/runs"
    try:
        resp = httpx.post(
            endpoint,
            json=payload,
            headers={"X-Host-Id": host_id, "X-Agent-Key": key},
            timeout=30,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        _err.print(
            f"[red]Error:[/red] Orchestrator returned {exc.response.status_code}: {exc.response.text}"
        )
        raise typer.Exit(1)
    except httpx.RequestError as exc:
        _err.print(f"[red]Error:[/red] Request failed: {exc}")
        raise typer.Exit(1)

    remote_id = resp.json().get("id", "?")
    con = Console()
    con.print(
        f"[green]Pushed run #{resolved_id}[/green] → orchestrator run [bold]{remote_id}[/bold]  "
        f"[dim]{len(bench_rows)} bench, {len(cpu_rows)} CPU, {len(finding_rows)} findings[/dim]"
    )


def _check_fail_on(report: Report, fail_on: str) -> None:
    _check_fail_on_findings(report.findings, fail_on)


def _check_fail_on_findings(findings: list, fail_on: str) -> None:
    from afterburner.models.findings import Severity

    levels = {
        "critical": {Severity.CRITICAL},
        "warning": {Severity.CRITICAL, Severity.WARNING},
        "info": {Severity.CRITICAL, Severity.WARNING, Severity.INFO},
        "none": set(),
    }
    threshold = levels.get(fail_on.lower(), set())
    if threshold and any(f.severity in threshold for f in findings):
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# rules subcommands
# ---------------------------------------------------------------------------

_SEVERITY_COLOR = {
    "critical": "red",
    "warning": "yellow",
    "info": "cyan",
}


@_rules_app.callback()
def _rules_root() -> None:
    """List and explain mission lint rules."""


@_rules_app.command("list")
def rules_list() -> None:
    """List all registered lint rules."""
    from rich import box
    from rich.console import Console
    from rich.table import Table

    con = Console()
    registry = get_registry()

    table = Table(box=box.SIMPLE, show_header=True, pad_edge=False)
    table.add_column("Rule ID", style="bold", min_width=10)
    table.add_column("Severity", min_width=10)
    table.add_column("Category", min_width=16)
    table.add_column("Title")

    for rule_cls in registry:
        sev = rule_cls.severity.value
        color = _SEVERITY_COLOR.get(sev, "white")
        table.add_row(
            rule_cls.rule_id,
            f"[{color}]{sev}[/{color}]",
            rule_cls.category,
            rule_cls.title,
        )

    con.print()
    con.print(table)


@_rules_app.command("explain")
def rules_explain(
    rule_id: str = typer.Argument(..., help="Rule ID to explain (e.g. BLOT_001)"),
) -> None:
    """Show full detail for a specific rule."""
    from rich.console import Console

    con = Console()
    registry = get_registry()
    match = next((r for r in registry if r.rule_id.upper() == rule_id.upper()), None)

    if match is None:
        _err.print(f"[red]Error:[/red] Unknown rule ID: {rule_id!r}")
        valid = ", ".join(r.rule_id for r in registry)
        _err.print(f"Valid IDs: {valid}")
        raise typer.Exit(2)

    sev = match.severity.value
    color = _SEVERITY_COLOR.get(sev, "white")

    con.print()
    con.print(f"[bold]{match.rule_id}[/bold] — {match.title}")
    con.print(f"Severity:  [{color}]{sev}[/{color}]")
    con.print(f"Category:  {match.category}")
    con.print()
    con.print(match.description)
    if match.fix:
        con.print()
        con.print(f"[dim]Fix: {match.fix}[/dim]")
    con.print()
