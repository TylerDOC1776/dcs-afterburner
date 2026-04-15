"""Mission size / bloat rules (BLOT_*)."""

from __future__ import annotations

from afterburner.models.findings import ReportFinding, Severity
from afterburner.models.mission import Mission
from afterburner.rules.base import Rule, register


@register
class ActiveUnitCount(Rule):
    rule_id = "BLOT_001"

    def check(self, mission: Mission) -> list[ReportFinding]:
        n = mission.summary.active_units
        if n > 1000:
            return [
                ReportFinding(
                    rule_id=self.rule_id,
                    severity=Severity.CRITICAL,
                    title="Excessive active units",
                    detail=f"{n} units active at mission start (threshold: 1000). "
                    "Expect severe FPS impact on entry-level servers.",
                    fix="Move non-essential groups to late activation or delete them.",
                )
            ]
        if n > 600:
            return [
                ReportFinding(
                    rule_id=self.rule_id,
                    severity=Severity.WARNING,
                    title="High active unit count",
                    detail=f"{n} units active at mission start (threshold: 600). "
                    "May cause performance issues on lower-end servers.",
                    fix="Consider late-activating groups that spawn later in the mission.",
                )
            ]
        return []


@register
class TotalUnitCount(Rule):
    rule_id = "BLOT_008"

    def check(self, mission: Mission) -> list[ReportFinding]:
        n = mission.summary.total_units
        if n > 1200:
            return [
                ReportFinding(
                    rule_id=self.rule_id,
                    severity=Severity.WARNING,
                    title="Very high total unit count",
                    detail=f"{n} total units in mission (threshold: 1200). "
                    "Even late-activated units consume memory.",
                    fix="Audit late-activation groups and remove units not used by the mission flow.",
                )
            ]
        return []


@register
class StaticObjectCount(Rule):
    rule_id = "BLOT_002"

    def check(self, mission: Mission) -> list[ReportFinding]:
        n = mission.summary.total_statics
        if n > 800:
            return [
                ReportFinding(
                    rule_id=self.rule_id,
                    severity=Severity.CRITICAL,
                    title="Excessive static objects",
                    detail=f"{n} static objects (threshold: 800). "
                    "Statics are always active and are a major FPS cost.",
                    fix="Remove decorative statics or replace dense clusters with scenery objects.",
                )
            ]
        if n > 500:
            return [
                ReportFinding(
                    rule_id=self.rule_id,
                    severity=Severity.WARNING,
                    title="High static object count",
                    detail=f"{n} static objects (threshold: 500).",
                    fix="Review statics for decorative items that can be removed.",
                )
            ]
        return []


@register
class TriggerCount(Rule):
    rule_id = "BLOT_003"

    def check(self, mission: Mission) -> list[ReportFinding]:
        n = mission.summary.trigger_count
        if n > 150:
            return [
                ReportFinding(
                    rule_id=self.rule_id,
                    severity=Severity.WARNING,
                    title="High trigger count",
                    detail=f"{n} triggers (threshold: 150). "
                    "Each trigger is evaluated every frame until it fires.",
                    fix="Consolidate triggers or move logic to a Lua script using event handlers.",
                )
            ]
        return []


@register
class ZoneCount(Rule):
    rule_id = "BLOT_004"

    def check(self, mission: Mission) -> list[ReportFinding]:
        n = mission.summary.zone_count
        if n > 100:
            return [
                ReportFinding(
                    rule_id=self.rule_id,
                    severity=Severity.WARNING,
                    title="High trigger zone count",
                    detail=f"{n} trigger zones (threshold: 100). "
                    "Zones used in triggers are evaluated every frame.",
                    fix="Remove unused zones or merge overlapping zones.",
                )
            ]
        return []


@register
class PlayerSlotCount(Rule):
    rule_id = "BLOT_005"

    def check(self, mission: Mission) -> list[ReportFinding]:
        n = mission.summary.player_slots
        if n > 80:
            return [
                ReportFinding(
                    rule_id=self.rule_id,
                    severity=Severity.WARNING,
                    title="Very high player slot count",
                    detail=f"{n} player slots (threshold: 80). "
                    "Excess slots waste group slots and can confuse server browsers.",
                    fix="Remove unused player slots, especially duplicate airframes at the same base.",
                )
            ]
        return []
