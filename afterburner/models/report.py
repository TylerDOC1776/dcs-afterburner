"""Report model: mission + findings + risk scoring."""

from __future__ import annotations

from dataclasses import dataclass, field

from afterburner.models.findings import ReportFinding, Severity
from afterburner.models.mission import Mission


@dataclass
class Report:
    mission: Mission
    findings: list[ReportFinding] = field(default_factory=list)

    def risk_score(self) -> int:
        """0–100 score. Higher is better. Clamped to 0."""
        penalty = sum(
            15
            if f.severity == Severity.CRITICAL
            else 5
            if f.severity == Severity.WARNING
            else 1
            for f in self.findings
        )
        return max(0, 100 - penalty)

    def risk_label(self) -> str:
        s = self.risk_score()
        if s >= 80:
            return "LOW"
        if s >= 50:
            return "MODERATE"
        if s >= 25:
            return "HIGH"
        return "CRITICAL"
