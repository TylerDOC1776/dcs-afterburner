"""Parse native DCS ``Scripting event:`` log lines."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_EVENT_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) "
    r".*?\bScripting \(Main\): event:(?P<payload>.*)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NativeEvent:
    timestamp: datetime
    type: str
    fields: dict[str, str]

    @property
    def player(self) -> str | None:
        return self.fields.get("initiatorPilotName") or self.fields.get(
            "targetPilotName"
        )

    @property
    def elapsed_s(self) -> float | None:
        value = self.fields.get("t")
        if value is None or value == "":
            return None
        try:
            return float(value)
        except ValueError:
            return None


def parse_native_events(source: str | Path) -> list[NativeEvent]:
    """Parse DCS native scripting event lines from text or a log path."""
    text = (
        source.read_text(encoding="utf-8", errors="replace")
        if isinstance(source, Path)
        else source
    )

    events: list[NativeEvent] = []
    for line in text.splitlines():
        match = _EVENT_RE.search(line)
        if not match:
            continue

        fields = _parse_fields(match.group("payload"))
        event_type = fields.get("type", "")
        if not event_type:
            continue

        events.append(
            NativeEvent(
                timestamp=datetime.strptime(
                    match.group("timestamp"), "%Y-%m-%d %H:%M:%S.%f"
                ),
                type=event_type,
                fields=fields,
            )
        )
    return events


def _parse_fields(payload: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in payload.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        if key:
            fields[key] = value.strip()
    return fields
