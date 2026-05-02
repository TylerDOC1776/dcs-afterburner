"""Log pattern definitions for known DCS World error signatures.

Each LogPattern describes a known log signature, its severity, and the
finding metadata to emit when it matches.

LOG_001 is special: it requires TWO distinct lines to both appear (precision
loss assertion).  The correlator handles the two-line check by looking for
both substrings across all events rather than per-event.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from afterburner.models.findings import Severity


@dataclass(frozen=True)
class LogPattern:
    rule_id: str
    severity: Severity
    title: str
    detail_template: str  # may contain {count} placeholder
    fix: str | None
    # substring match — if set, event.full_message must contain this
    contains: str | None = None
    # regex match — if set, compiled and matched against event.full_message
    pattern: str | None = None
    # If True, the correlator skips lines matching this pattern
    suppress: bool = False

    def matches(self, message: str) -> bool:
        if self.contains is not None and self.contains not in message:
            return False
        if self.pattern is not None and not re.search(self.pattern, message):
            return False
        return True


# ---------------------------------------------------------------------------
# Pattern registry
# ---------------------------------------------------------------------------

LOG_001 = LogPattern(
    rule_id="LOG_001",
    severity=Severity.CRITICAL,
    title="Half-float precision loss assertion failure",
    detail_template=(
        "DCS EDCORE raised a half-float precision loss assertion "
        "({count} occurrence(s)). This fires when a physics value exceeds "
        "±1024 in half-float compression and typically causes client stutters "
        "or crashes at the moment of the assertion."
    ),
    fix="Reduce unit density or object counts near the triggering area. "
    "Check for units placed at extreme coordinates.",
    # Both substrings must appear — checked in correlator via two-pass scan
    contains="Severe precision loss",
)

# Second line of the LOG_001 pair — used by the correlator to confirm the event
_LOG_001_ASSERT = LogPattern(
    rule_id="LOG_001",
    severity=Severity.CRITICAL,
    title="Half-float precision loss assertion failure",
    detail_template="",
    fix=None,
    contains="Failed assert fabsf",
)

LOG_002 = LogPattern(
    rule_id="LOG_002",
    severity=Severity.WARNING,
    title="Radio storage overflow (>300 radio pairs)",
    detail_template=(
        "Radio storage filled with more than 300 radio pairs "
        "({count} occurrence(s)). Likely caused by CTLD registering too many "
        "frequencies. Self-resolves in 1–2 min but adds startup latency."
    ),
    fix="Reduce the number of CTLD-registered radio frequencies or defer "
    "radio setup until after players connect.",
    contains="Radio storage is filled with more than 300 radio pairs",
)

LOG_003 = LogPattern(
    rule_id="LOG_003",
    severity=Severity.INFO,
    title="Missing wreckage shape (mod asset not found)",
    detail_template=(
        "ShapeTable could not find a destroyed-state model "
        "({count} occurrence(s)). Usually indicates a mod asset pack is "
        "installed on clients but not on the server."
    ),
    fix="Install the matching asset mod on the server, or remove the unit "
    "type from the mission if the mod is not available server-side.",
    pattern=r"ShapeTable shape not found",
)

LOG_004 = LogPattern(
    rule_id="LOG_004",
    severity=Severity.INFO,
    title="Corrupt damage model (known DCS engine bug)",
    detail_template=(
        "DCS engine reported a corrupt damage model "
        "({count} occurrence(s)). This is a known engine bug that fires each "
        "time certain unit types spawn. It is not a crash risk."
    ),
    fix=None,
    pattern=r"Corrupt damage model",
    suppress=True,
)

LOG_005 = LogPattern(
    rule_id="LOG_005",
    severity=Severity.INFO,
    title="bhHook.lua TCP nil-index on disconnect",
    detail_template=(
        "bhHook.lua attempted to index a nil TCP connection "
        "({count} occurrence(s)). Fires on every player disconnect when the "
        "TCP connection is already closed. Non-fatal."
    ),
    fix=None,
    contains="attempt to index upvalue 'tcp' (a nil value)",
    suppress=True,
)

# Ordered list used by the correlator (LOG_001 handled separately)
ALL_PATTERNS: list[LogPattern] = [LOG_002, LOG_003, LOG_004, LOG_005]

# Confirmed-harmless engine errors that are suppressed to reduce noise.
# Suppressed patterns produce no findings and are not counted.
SUPPRESSED_PATTERNS: list[LogPattern] = [p for p in ALL_PATTERNS if p.suppress]
