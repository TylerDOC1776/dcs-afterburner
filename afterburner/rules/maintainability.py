"""Maintainability rules (MAINT_*)."""

from __future__ import annotations

from afterburner.models.findings import ReportFinding, Severity
from afterburner.models.mission import Mission
from afterburner.rules.base import Rule, register

_DEFAULT_PREFIXES = ("New ", "Static Object", "Vehicle", "Airplane", "Helicopter")


@register
class UnnamedGroups(Rule):
    rule_id = "MAINT_001"
    title = "Groups with default names"
    severity = Severity.INFO
    description = (
        "Checks what percentage of groups still have DCS-generated default names "
        "(e.g. 'New Group', 'Static Object #1'). Fires an info finding when more "
        "than 5% of groups are unnamed. Default names make trigger and script "
        "maintenance significantly harder — you can't tell what a group does "
        "without opening it in the editor."
    )
    fix = "Rename groups to reflect their tactical purpose."
    category = "maintainability"

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
    title = "Duplicate group names"
    severity = Severity.WARNING
    description = (
        "Checks for groups that share the same name. Fires a warning if any "
        "duplicates are found. DCS trigger conditions that match groups by name "
        "will fire on every group with that name — duplicate names cause "
        "silent, hard-to-debug trigger behavior."
    )
    fix = "Ensure every group has a unique name."
    category = "maintainability"

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
