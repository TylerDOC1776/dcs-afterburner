"""Rich terminal output for mission analysis."""

from __future__ import annotations

from rich import box
from rich.console import Console
from rich.table import Table

from afterburner.models.findings import Severity
from afterburner.models.report import Report

_console = Console()

# Thresholds matching PLANNING.md defaults
_THRESHOLDS = {
    "active_units": 600,
    "total_statics": 800,
    "trigger_count": 150,
    "zone_count": 100,
    "player_slots": 80,
}

_SEVERITY_STYLE = {
    Severity.CRITICAL: "red",
    Severity.WARNING: "yellow",
    Severity.INFO: "cyan",
}


def print_summary(report: Report) -> None:
    mission = report.mission
    s = mission.summary

    _console.print()
    _console.print(
        f"[bold cyan]DCS Afterburner[/bold cyan]  [dim]{mission.source_file}[/dim]"
    )
    _console.print(
        f"Theatre: [yellow]{s.theatre}[/yellow]   "
        f"Mission: [yellow]{mission.name}[/yellow]"
    )
    _console.print()

    table = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    table.add_column("Metric", style="dim", min_width=28)
    table.add_column("Value", justify="right")

    table.add_row("Total units", str(s.total_units))
    table.add_row(
        "  Active at start", _flag(s.active_units, _THRESHOLDS["active_units"])
    )
    table.add_row("  Late activation", str(s.late_units))
    table.add_row("Player slots", _flag(s.player_slots, _THRESHOLDS["player_slots"]))
    table.add_row("Groups (total)", str(s.total_groups))
    table.add_row("  Active groups", str(s.active_groups))
    table.add_row(
        "Static objects", _flag(s.total_statics, _THRESHOLDS["total_statics"])
    )
    table.add_row("Triggers", _flag(s.trigger_count, _THRESHOLDS["trigger_count"]))
    table.add_row("Trigger zones", _flag(s.zone_count, _THRESHOLDS["zone_count"]))

    _console.print(table)

    # Risk score
    score = report.risk_score()
    label = report.risk_label()
    score_style = "green" if score >= 80 else "yellow" if score >= 50 else "red"
    _console.print(f"Risk score: [{score_style}]{score}/100 ({label})[/{score_style}]")

    if report.findings:
        _console.print()
        _console.print("[bold]Findings:[/bold]")
        for f in report.findings:
            style = _SEVERITY_STYLE.get(f.severity, "white")
            _console.print(
                f"  [{style}]{f.severity.value.upper():8}[/{style}]  "
                f"[bold]{f.rule_id}[/bold]  {f.title}"
            )
            _console.print(f"           {f.detail}")
            if f.fix:
                _console.print(f"           [dim]Fix: {f.fix}[/dim]")

    _console.print()


def _flag(value: int, threshold: int) -> str:
    if value > threshold:
        return f"[red]{value}[/red]"
    if value > int(threshold * 0.75):
        return f"[yellow]{value}[/yellow]"
    return str(value)
