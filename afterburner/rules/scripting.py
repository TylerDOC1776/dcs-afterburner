"""Scripting rules (PERF_001, PERF_002, SCPT_001)."""

from __future__ import annotations

from afterburner.models.findings import ReportFinding, Severity
from afterburner.models.mission import Mission
from afterburner.rules.base import Rule, register

_CTLD_NAMES = {"ctld"}
_CSAR_NAMES = {"csar"}

# Known large frameworks that are routinely shipped unstripped — exclude from
# the SCPT_001 LOC threshold so it only catches mission-specific script bloat.
_FRAMEWORK_NAMES = {
    "moose",
    "mist",
    "ctld",
    "csar",
    "splash_damage",
    "zonecommander",
    "aien",
}

_SCPT_WARN = 5_000
_SCPT_CRIT = 15_000


def _is_framework(filename: str) -> bool:
    name = filename.lower()
    return any(kw in name for kw in _FRAMEWORK_NAMES)


def _matches(script_files: list[str], keywords: set[str]) -> bool:
    return any(any(kw in f.lower() for kw in keywords) for f in script_files)


@register
class CtldDetected(Rule):
    rule_id = "PERF_001"
    title = "CTLD script detected"
    severity = Severity.WARNING
    description = (
        "Detected a CTLD (Combined Arms Transport and Logistics Deployment) script "
        "loaded via a DO SCRIPT FILE trigger action. "
        "CTLD runs two polling loops: checkHoverStatus (every 1s) and checkAIStatus "
        "(every 2s), both of which iterate over all registered transport pilots. "
        "On missions with many transport slots this is a steady background CPU cost "
        "that is independent of player count and cannot be reduced without modifying "
        "the script."
    )
    fix = (
        "Reduce the number of CTLD-registered transport pilot names, or consider "
        "switching to a version of CTLD with event-driven hooks instead of polling."
    )
    category = "performance"

    def check(self, mission: Mission) -> list[ReportFinding]:
        if not _matches(mission.script_files, _CTLD_NAMES):
            return []
        return [
            ReportFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                title=self.title,
                detail=(
                    "CTLD detected in mission scripts. "
                    "checkHoverStatus and checkAIStatus poll every 1–2s over all "
                    "registered transport pilots — a steady CPU cost at scale."
                ),
                fix=self.fix,
            )
        ]


@register
class CsarDetected(Rule):
    rule_id = "PERF_002"
    title = "CSAR script detected"
    severity = Severity.INFO
    description = (
        "Detected a CSAR (Combat Search and Rescue) script loaded via a DO SCRIPT "
        "FILE trigger action. "
        "CSAR accumulates scheduler timers as a function of active rescue helicopters "
        "and wounded groups (N helis × M wounded). On long sessions with many "
        "rescues, the timer count can grow large enough to cause noticeable overhead. "
        "Not a problem in short sessions or low-rescue missions."
    )
    fix = (
        "Monitor timer count on long sessions. If issues arise, restart the mission "
        "periodically or use a CSAR version that cleans up completed timers."
    )
    category = "performance"

    def check(self, mission: Mission) -> list[ReportFinding]:
        if not _matches(mission.script_files, _CSAR_NAMES):
            return []
        return [
            ReportFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                title=self.title,
                detail=(
                    "CSAR detected in mission scripts. "
                    "Timer accumulation (N helis × M wounded groups) can grow on "
                    "long sessions with many active rescues."
                ),
                fix=self.fix,
            )
        ]


@register
class ScriptLinesOfCode(Rule):
    rule_id = "SCPT_001"
    title = "High script line count"
    severity = Severity.WARNING
    description = (
        "The total non-blank lines of Lua code across all DO SCRIPT FILE scripts "
        "loaded by this mission exceeds the warning threshold. "
        "All script files are parsed and executed synchronously on the DCS main thread "
        "at mission load. Large scripts increase load time and can cause a noticeable "
        "stutter or timeout for connecting clients."
    )
    fix = (
        "Audit script files for dead code, commented-out blocks, or redundant copies "
        "of frameworks. Consider stripping/minifying large libraries before packing "
        "into the .miz. Remove scripts that are loaded but not used."
    )
    category = "performance"

    def check(self, mission: Mission) -> list[ReportFinding]:
        mission_scripts = {
            name: loc
            for name, loc in mission.script_loc.items()
            if not _is_framework(name)
        }
        total = sum(mission_scripts.values())
        if total < _SCPT_WARN:
            return []
        severity = Severity.CRITICAL if total >= _SCPT_CRIT else Severity.WARNING
        file_summary = ", ".join(
            f"{n} ({c:,})"
            for n, c in sorted(mission_scripts.items(), key=lambda x: -x[1])
        )
        return [
            ReportFinding(
                rule_id=self.rule_id,
                severity=severity,
                title=self.title,
                detail=(
                    f"{total:,} non-blank lines of mission-specific Lua "
                    f"(frameworks excluded): {file_summary}. "
                    f"Threshold: warning >{_SCPT_WARN:,}, critical >{_SCPT_CRIT:,}."
                ),
                fix=self.fix,
            )
        ]
