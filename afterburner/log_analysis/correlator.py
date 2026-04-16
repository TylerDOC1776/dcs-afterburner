"""Correlate parsed log events against known patterns and produce findings.

Usage::

    from afterburner.log_analysis.parser import parse_log
    from afterburner.log_analysis.correlator import correlate

    events = parse_log(Path("dcs.log"))
    findings = correlate(events)

The correlator:
- Scans all events against each pattern in ALL_PATTERNS
- Aggregates occurrences (one ReportFinding per matched pattern)
- Handles LOG_001 specially: both "Severe precision loss" and
  "Failed assert fabsf" must appear in the event stream to emit the finding
- Optionally boosts the confidence of existing rule findings via
  ``boost_findings()`` (e.g. LOG_001 raises BLOT_001 confidence)
"""

from __future__ import annotations

from afterburner.log_analysis.parser import LogEvent
from afterburner.log_analysis.patterns import (
    ALL_PATTERNS,
    LOG_001,
    _LOG_001_ASSERT,
    LogPattern,
)
from afterburner.models.findings import ReportFinding, Severity

# Maps log rule_id → rule_ids whose confidence should be boosted when the log
# pattern fires.  Extend as correlations are discovered.
_CONFIDENCE_BOOST: dict[str, list[str]] = {
    "LOG_001": ["BLOT_001"],
}
_BOOST_AMOUNT = 0.15


def correlate(events: list[LogEvent]) -> list[ReportFinding]:
    """Match events against all known patterns and return findings.

    One finding is emitted per matched pattern (occurrence count in detail).
    """
    findings: list[ReportFinding] = []

    # LOG_001 — two-line pair check
    has_precision = any(LOG_001.matches(e.full_message) for e in events)
    has_assert = any(_LOG_001_ASSERT.matches(e.full_message) for e in events)
    if has_precision and has_assert:
        count = sum(1 for e in events if LOG_001.matches(e.full_message))
        findings.append(_make_finding(LOG_001, count))

    # All other patterns
    for pattern in ALL_PATTERNS:
        matched = [e for e in events if pattern.matches(e.full_message)]
        if matched:
            findings.append(_make_finding(pattern, len(matched)))

    return findings


def boost_findings(
    rule_findings: list[ReportFinding],
    log_findings: list[ReportFinding],
) -> list[ReportFinding]:
    """Return a copy of rule_findings with confidence boosted where applicable.

    For each log finding, looks up which rule IDs should be boosted and
    increases their confidence by _BOOST_AMOUNT (capped at 1.0).
    """
    log_ids = {f.rule_id for f in log_findings}
    boosted_rule_ids: set[str] = set()
    for log_id in log_ids:
        boosted_rule_ids.update(_CONFIDENCE_BOOST.get(log_id, []))

    result: list[ReportFinding] = []
    for f in rule_findings:
        if f.rule_id in boosted_rule_ids:
            new_confidence = min(1.0, f.confidence + _BOOST_AMOUNT)
            result.append(
                ReportFinding(
                    rule_id=f.rule_id,
                    severity=f.severity,
                    title=f.title,
                    detail=f.detail,
                    fix=f.fix,
                    confidence=new_confidence,
                )
            )
        else:
            result.append(f)
    return result


def _make_finding(pattern: LogPattern, count: int) -> ReportFinding:
    return ReportFinding(
        rule_id=pattern.rule_id,
        severity=pattern.severity,
        title=pattern.title,
        detail=pattern.detail_template.format(count=count),
        fix=pattern.fix,
        confidence=1.0,
    )
