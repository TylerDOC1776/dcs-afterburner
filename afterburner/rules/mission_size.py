"""Mission size / bloat rules (BLOT_*)."""

from __future__ import annotations

from afterburner.models.findings import ReportFinding, Severity
from afterburner.models.mission import Mission
from afterburner.rules.base import Rule, register


@register
class ActiveUnitCount(Rule):
    rule_id = "BLOT_001"
    title = "Active unit count"
    severity = Severity.CRITICAL
    description = (
        "Counts units that are active (not late-activated) at mission start. "
        "Fires a warning above 350 units and a critical above 600. "
        "Active units all run AI pathfinding immediately on load — the more there are, "
        "the harder the server's CPU is hit from the first second of the mission."
    )
    fix = "Move non-essential groups to late activation or delete them."
    category = "bloat"

    def check(self, mission: Mission) -> list[ReportFinding]:
        n = mission.summary.active_units
        if n > 600:
            return [
                ReportFinding(
                    rule_id=self.rule_id,
                    severity=Severity.CRITICAL,
                    title="Excessive active units",
                    detail=f"{n} units active at mission start (threshold: 600). "
                    "Expect severe FPS impact on entry-level servers.",
                    fix="Move non-essential groups to late activation or delete them.",
                )
            ]
        if n > 350:
            return [
                ReportFinding(
                    rule_id=self.rule_id,
                    severity=Severity.WARNING,
                    title="High active unit count",
                    detail=f"{n} units active at mission start (threshold: 350). "
                    "May cause performance issues on lower-end servers.",
                    fix="Consider late-activating groups that spawn later in the mission.",
                )
            ]
        return []


@register
class TotalUnitCount(Rule):
    rule_id = "BLOT_008"
    title = "Total unit count"
    severity = Severity.WARNING
    description = (
        "Counts all units in the mission including late-activated ones. "
        "Fires a warning above 1200. Even late-activated units occupy memory "
        "and add to load time — a very high total count is a sign the mission "
        "has grown beyond a manageable size."
    )
    fix = "Audit late-activation groups and remove units not used by the mission flow."
    category = "bloat"

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
    title = "Static object count"
    severity = Severity.CRITICAL
    description = (
        "Counts all static objects in the mission. "
        "Fires a warning above 500 and a critical above 800. "
        "Unlike dynamic groups, statics are always active — they cannot be "
        "late-activated. Dense static decoration is one of the most common "
        "causes of server FPS problems."
    )
    fix = "Remove decorative statics or replace dense clusters with scenery objects."
    category = "bloat"

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
    title = "Trigger count"
    severity = Severity.WARNING
    description = (
        "Counts all triggers in the mission. Fires a warning above 150. "
        "Each trigger is evaluated every frame until it fires. "
        "Large trigger counts are often a sign that mission logic should be "
        "moved into Lua scripts using event handlers instead."
    )
    fix = "Consolidate triggers or move logic to a Lua script using event handlers."
    category = "bloat"

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
    title = "Trigger zone count"
    severity = Severity.WARNING
    description = (
        "Counts all trigger zones in the mission. Fires a warning above 90. "
        "Zones used in trigger conditions are checked every frame. "
        "A high zone count combined with many triggers multiplies the per-frame cost."
    )
    fix = "Remove unused zones or merge overlapping zones."
    category = "bloat"

    def check(self, mission: Mission) -> list[ReportFinding]:
        n = mission.summary.zone_count
        if n > 90:
            return [
                ReportFinding(
                    rule_id=self.rule_id,
                    severity=Severity.WARNING,
                    title="High trigger zone count",
                    detail=f"{n} trigger zones (threshold: 90). "
                    "Zones used in triggers are evaluated every frame.",
                    fix="Remove unused zones or merge overlapping zones.",
                )
            ]
        return []


@register
class PlayerSlotCount(Rule):
    rule_id = "BLOT_005"
    title = "Player slot count"
    severity = Severity.WARNING
    description = (
        "Counts all player-flyable slots in the mission. Fires a warning above 80. "
        "Excess slots waste group slots and can make the server browser entry "
        "appear to have far more capacity than realistic player numbers support."
    )
    fix = "Remove unused player slots, especially duplicate airframes at the same base."
    category = "bloat"

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
