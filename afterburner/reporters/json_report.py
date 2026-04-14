"""Machine-readable JSON output."""

from __future__ import annotations

from afterburner.models.report import Report


def to_json(report: Report) -> dict:
    mission = report.mission
    s = mission.summary
    return {
        "mission_name": mission.name,
        "source_file": mission.source_file,
        "hash": mission.sha256,
        "summary": {
            "theatre": s.theatre,
            "total_units": s.total_units,
            "active_units": s.active_units,
            "late_units": s.late_units,
            "player_slots": s.player_slots,
            "total_groups": s.total_groups,
            "active_groups": s.active_groups,
            "total_statics": s.total_statics,
            "trigger_count": s.trigger_count,
            "zone_count": s.zone_count,
            "risk_score": report.risk_score(),
            "risk_label": report.risk_label(),
        },
        "findings": [
            {
                "rule_id": f.rule_id,
                "severity": f.severity.value,
                "title": f.title,
                "detail": f.detail,
                "fix": f.fix,
                "confidence": f.confidence,
            }
            for f in report.findings
        ],
        "metrics": {},
        "optimizations_applied": [],
        "output_file": None,
    }
