"""Extract benchmark-relevant scripting issues from DCS logs."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LogIssue:
    issue_type: str
    signature: str
    count: int
    first_line: str | None = None
    last_line: str | None = None
    detail: str | None = None


_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\s+")
_MISSION_SCRIPT_ERROR_RE = re.compile(r"Mission script error:\s*(.*)")
_SCRIPTING_ERROR_RE = re.compile(r"\b(?:SCRIPTING|Scripting) \([^)]*\):\s*(.*)")


def parse_log_issues(
    source: str | Path,
    *,
    repeated_threshold: int = 10,
    ignored_signatures: set[str] | None = None,
) -> list[LogIssue]:
    """Return hard-stop and repeated scripting issues from a DCS log.

    Hard-stop mission script errors are always returned, even when seen once.
    Other scripting errors are returned only when the normalized signature count
    reaches repeated_threshold.
    """
    if isinstance(source, Path):
        text = source.read_text(encoding="utf-8", errors="replace")
    else:
        text = source

    ignored = ignored_signatures or set()
    lines = text.splitlines()
    issues: list[LogIssue] = []
    counter: Counter[str] = Counter()
    first_line: dict[str, str] = {}
    last_line: dict[str, str] = {}

    for i, line in enumerate(lines):
        if "Mission script error:" in line:
            signature = _normalize_mission_script_error(line)
            if signature not in ignored:
                issues.append(
                    LogIssue(
                        issue_type="hard_stop",
                        signature=signature,
                        count=1,
                        first_line=line,
                        last_line=line,
                        detail=_stack_block(lines, i),
                    )
                )

        if "ERROR" not in line or not _is_scripting_line(line):
            continue

        signature = _normalize_scripting_error(line)
        if not signature or signature in ignored:
            continue
        counter[signature] += 1
        first_line.setdefault(signature, line)
        last_line[signature] = line

    for signature, count in counter.most_common():
        if count < repeated_threshold:
            continue
        issues.append(
            LogIssue(
                issue_type="repeated_scripting",
                signature=signature,
                count=count,
                first_line=first_line.get(signature),
                last_line=last_line.get(signature),
            )
        )

    return issues


def _is_scripting_line(line: str) -> bool:
    return " SCRIPTING " in line or " Scripting " in line


def _normalize_mission_script_error(line: str) -> str:
    match = _MISSION_SCRIPT_ERROR_RE.search(line)
    if match:
        return "Mission script error: " + match.group(1).strip()
    return _strip_timestamp(line).strip()


def _normalize_scripting_error(line: str) -> str:
    stripped = _strip_timestamp(line).strip()
    match = _SCRIPTING_ERROR_RE.search(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def _strip_timestamp(line: str) -> str:
    return _TS_RE.sub("", line)


def _stack_block(lines: list[str], start: int) -> str:
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if line.startswith("\t") or line.startswith("stack traceback:"):
            block.append(line)
            continue
        break
    return "\n".join(block)
