"""Maintainability rules (MAINT_*)."""

from __future__ import annotations

from afterburner.models.findings import ReportFinding, Severity
from afterburner.models.mission import Mission
from afterburner.rules.base import Rule, register

_DEFAULT_PREFIXES = ("New ", "Static Object", "Vehicle", "Airplane", "Helicopter")


@register
class UnnamedGroups(Rule):
    rule_id = "MAINT_001"

    def check(self, mission: Mission) -> list[ReportFinding]:
        all_groups = mission.groups + mission.statics
        if not all_groups:
            return []
        unnamed = [
            g
            for g in all_groups
            if not g.name or any(g.name.startswith(p) for p in _DEFAULT_PREFIXES)
        ]
        pct = len(unnamed) / len(all_groups)
        if pct > 0.05:
            return [
                ReportFinding(
                    rule_id=self.rule_id,
                    severity=Severity.INFO,
                    title="Many groups with default names",
                    detail=f"{len(unnamed)} of {len(all_groups)} groups ({pct:.0%}) appear to use "
                    "default DCS-generated names. This makes trigger/script maintenance harder.",
                    fix="Rename groups to reflect their tactical purpose.",
                )
            ]
        return []


@register
class DuplicateGroupNames(Rule):
    rule_id = "MAINT_002"

    def check(self, mission: Mission) -> list[ReportFinding]:
        all_groups = mission.groups + mission.statics
        seen: dict[str, int] = {}
        for g in all_groups:
            if g.name:
                seen[g.name] = seen.get(g.name, 0) + 1
        dupes = {name: count for name, count in seen.items() if count > 1}
        if dupes:
            examples = ", ".join(list(dupes)[:5])
            return [
                ReportFinding(
                    rule_id=self.rule_id,
                    severity=Severity.WARNING,
                    title="Duplicate group names",
                    detail=f"{len(dupes)} group names appear more than once (e.g. {examples}). "
                    "DCS trigger conditions that match by name will fire on all groups with that name.",
                    fix="Ensure every group has a unique name.",
                )
            ]
        return []
