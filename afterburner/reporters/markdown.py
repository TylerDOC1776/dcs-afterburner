"""Markdown report output."""

from __future__ import annotations

from afterburner.models.findings import Severity
from afterburner.models.report import Report

_SEVERITY_EMOJI = {
    Severity.CRITICAL: "🔴",
    Severity.WARNING: "🟡",
    Severity.INFO: "🔵",
}


def to_markdown(report: Report) -> str:
    mission = report.mission
    s = mission.summary
    lines: list[str] = []

    lines.append(f"# DCS Afterburner Report: {mission.name}")
    lines.append("")
    lines.append(f"**Source:** `{mission.source_file}`  ")
    lines.append(f"**Hash:** `{mission.sha256}`  ")
    lines.append(f"**Theatre:** {s.theatre}  ")
    lines.append(f"**Risk:** {report.risk_score()}/100 — {report.risk_label()}")
    lines.append("")

    lines.append("## Mission Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total units | {s.total_units} |")
    lines.append(f"| Active at start | {s.active_units} |")
    lines.append(f"| Late activation | {s.late_units} |")
    lines.append(f"| Player slots | {s.player_slots} |")
    lines.append(f"| Groups (total) | {s.total_groups} |")
    lines.append(f"| Active groups | {s.active_groups} |")
    lines.append(f"| Static objects | {s.total_statics} |")
    lines.append(f"| Triggers | {s.trigger_count} |")
    lines.append(f"| Trigger zones | {s.zone_count} |")
    lines.append("")

    if report.findings:
        lines.append("## Findings")
        lines.append("")
        for f in report.findings:
            icon = _SEVERITY_EMOJI.get(f.severity, "")
            lines.append(f"### {icon} `{f.rule_id}` — {f.title}")
            lines.append("")
            lines.append(f"**Severity:** {f.severity.value}  ")
            lines.append(f"**Confidence:** {f.confidence:.0%}  ")
            lines.append("")
            lines.append(f.detail)
            if f.fix:
                lines.append("")
                lines.append(f"**Fix:** {f.fix}")
            lines.append("")
    else:
        lines.append("## Findings")
        lines.append("")
        lines.append("No findings.")
        lines.append("")

    return "\n".join(lines)
