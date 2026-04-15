"""Performance rules (PERF_*)."""

from __future__ import annotations

from afterburner.models.findings import ReportFinding, Severity
from afterburner.models.mission import Category, Mission
from afterburner.rules.base import Rule, register


@register
class UncontrolledAircraft(Rule):
    rule_id = "PERF_003"

    def check(self, mission: Mission) -> list[ReportFinding]:
        air_categories = {Category.PLANE, Category.HELICOPTER}
        uncontrolled = [
            g
            for g in mission.groups
            if g.category in air_categories and g.uncontrolled and not g.late_activation
        ]
        n = len(uncontrolled)
        if n > 10:
            return [
                ReportFinding(
                    rule_id=self.rule_id,
                    severity=Severity.WARNING,
                    title="Many uncontrolled active aircraft",
                    detail=f"{n} uncontrolled air groups are active at mission start. "
                    "Uncontrolled aircraft still load AI pathfinding and consume CPU.",
                    fix="Late-activate uncontrolled aircraft or remove groups not needed at start.",
                )
            ]
        return []
