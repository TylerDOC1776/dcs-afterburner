"""Parse DCS World log files into LogEvent objects.

DCS log line format (two variants seen in the wild):

  Elapsed-seconds (older / some server builds):
    123.456 INFO    EDCORE (Main): message

  Wall-clock datetime (DCS 2.9+):
    2026-04-12 23:55:01.939 INFO    EDCORE (Main): message

Continuation lines (e.g. Lua stack traces) start with whitespace or do not
match either timestamp prefix pattern.  They are appended to the previous
event's message separated by a newline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Elapsed-seconds variant: optional leading spaces, decimal number, level, rest
_ELAPSED_RE = re.compile(
    r"^\s*(\d+\.\d+)\s+(INFO|WARNING|ERROR|DEBUG|ALERT|CRITICAL)\s+(.*)"
)

# Wall-clock variant: YYYY-MM-DD HH:MM:SS.mmm  LEVEL  rest
_DATETIME_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)\s+(INFO|WARNING|ERROR|DEBUG|ALERT|CRITICAL)\s+(.*)"
)


@dataclass
class LogEvent:
    timestamp: str  # raw timestamp string from the log line
    level: str
    message: str
    # Continuation lines appended here (Lua stack traces, etc.)
    extra: list[str] = field(default_factory=list)

    @property
    def full_message(self) -> str:
        if self.extra:
            return self.message + "\n" + "\n".join(self.extra)
        return self.message


def parse_log(source: str | Path) -> list[LogEvent]:
    """Parse a DCS log file and return a list of LogEvent objects.

    Args:
        source: Path to the log file or raw log text as a string.
    """
    if isinstance(source, Path):
        text = source.read_text(encoding="utf-8", errors="replace")
    else:
        text = source

    events: list[LogEvent] = []
    current: LogEvent | None = None

    for raw_line in text.splitlines():
        m = _DATETIME_RE.match(raw_line) or _ELAPSED_RE.match(raw_line)
        if m:
            current = LogEvent(
                timestamp=m.group(1),
                level=m.group(2),
                message=m.group(3),
            )
            events.append(current)
        elif current is not None:
            # Continuation line — attach to the most recent event
            current.extra.append(raw_line)

    return events
