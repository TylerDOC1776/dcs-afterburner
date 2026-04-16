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
from afterburner.rules.base import run_all

app = typer.Typer(name="afterburner", add_completion=False, no_args_is_help=True)
_err = Console(stderr=True)


@app.callback()
def _root() -> None:
    """DCS Afterburner — mission linting and diagnostics for DCS World .miz files."""


@app.command()
def analyze(
    mission: Path = typer.Argument(..., help="Path to .miz file"),
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

    findings = run_all(parsed)
    report = Report(mission=parsed, findings=findings)

    if as_json:
        print(json.dumps(to_json(report), indent=2))
    else:
        print_summary(report)

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
