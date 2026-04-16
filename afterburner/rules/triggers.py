"""Trigger rules (BLOT_006)."""

from __future__ import annotations

from afterburner.models.findings import ReportFinding, Severity
from afterburner.models.mission import Mission
from afterburner.rules.base import Rule, register


@register
class ContinuousTriggers(Rule):
    rule_id = "BLOT_006"
    title = "Continuous triggers"
    severity = Severity.WARNING
    description = (
        "Counts triggers with logic type MORE (continuous) rather than ONCE. "
        "Fires a warning above 40. "
        "Continuous triggers are evaluated every simulation frame for the entire "
        "mission — they never stop running even after their condition is met. "
        "A high count is a steady per-frame CPU cost that grows with mission length."
    )
    fix = (
        "Replace continuous triggers with ONCE triggers where the condition only "
        "needs to fire once, or move repeating logic into a Lua script using "
        "MIST or MOOSE timers which are far cheaper than trigger evaluation."
    )
    category = "bloat"

    def check(self, mission: Mission) -> list[ReportFinding]:
        continuous = [t for t in mission.triggers_detail if t.logic_type == "MORE"]
        n = len(continuous)
        if n > 40:
            return [
                ReportFinding(
                    rule_id=self.rule_id,
                    severity=Severity.WARNING,
                    title="High continuous trigger count",
                    detail=(
                        f"{n} continuous (MORE) triggers found (threshold: 40). "
                        "These evaluate every frame for the life of the mission."
                    ),
                    fix=self.fix,
                )
            ]
        return []
