"""Tests for the log_analysis module."""

from __future__ import annotations

from afterburner.log_analysis.correlator import boost_findings, correlate
from afterburner.log_analysis.parser import LogEvent, parse_log
from afterburner.models.findings import ReportFinding, Severity

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PRECISION_LINE = "  123.456 ERROR   EDCORE (Main): Severe precision loss! Half-float has 10-bit mantissa"
_ASSERT_LINE = "  123.457 ERROR   EDCORE (Main): Failed assert fabsf(f) < 1024 at some_file.cpp:99"
_RADIO_LINE = "    3.100 WARNING SCRIPTING (Main): Radio storage is filled with more than 300 radio pairs"
_SHAPE_LINE = "   45.000 WARNING EDCORE (Main): ShapeTable shape not found TYPE_88_75MM_AA_DESTROYED"
_DAMAGE_LINE = "   10.000 INFO    SCRIPTING (Main): Error: Unit [MiG-21Bis]: Corrupt damage model"
_TCP_LINE = "  200.000 ERROR   SCRIPTING (Main): attempt to index upvalue 'tcp' (a nil value)"

_UNRELATED_LINE = "    0.001 INFO    EDCORE (Main): DCS/ (x86_64; Windows NT 10.0.19041)"


def _events(*lines: str) -> list[LogEvent]:
    return parse_log("\n".join(lines))


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def test_parse_empty():
    assert parse_log("") == []


def test_parse_single_line():
    events = parse_log(_PRECISION_LINE)
    assert len(events) == 1
    assert events[0].level == "ERROR"
    assert "Severe precision loss" in events[0].message


def test_parse_timestamp():
    events = parse_log(_PRECISION_LINE)
    assert "123.456" in events[0].timestamp


def test_parse_continuation_line():
    text = _PRECISION_LINE + "\n    stack traceback: ...\n    (more trace)"
    events = parse_log(text)
    assert len(events) == 1
    assert len(events[0].extra) == 2
    assert "stack traceback" in events[0].extra[0]


def test_parse_full_message_includes_extra():
    text = _PRECISION_LINE + "\n    extra line"
    events = parse_log(text)
    assert "extra line" in events[0].full_message


def test_parse_multiple_events():
    events = parse_log("\n".join([_PRECISION_LINE, _RADIO_LINE, _SHAPE_LINE]))
    assert len(events) == 3


def test_parse_unrelated_line_ignored():
    events = _events(_UNRELATED_LINE)
    assert len(events) == 1
    assert events[0].level == "INFO"


def test_parse_datetime_format():
    line = "2026-04-12 23:55:01.939 INFO    EDCORE (Main): some message"
    events = parse_log(line)
    assert len(events) == 1
    assert events[0].timestamp == "2026-04-12 23:55:01.939"
    assert events[0].level == "INFO"
    assert "some message" in events[0].message


def test_parse_from_path(tmp_path):
    log_file = tmp_path / "dcs.log"
    log_file.write_text(_RADIO_LINE + "\n" + _SHAPE_LINE)
    events = parse_log(log_file)
    assert len(events) == 2


# ---------------------------------------------------------------------------
# LOG_001 — two-line pair
# ---------------------------------------------------------------------------


def test_log001_fires_when_both_lines_present():
    findings = correlate(_events(_PRECISION_LINE, _ASSERT_LINE))
    ids = [f.rule_id for f in findings]
    assert "LOG_001" in ids


def test_log001_severity_is_critical():
    findings = correlate(_events(_PRECISION_LINE, _ASSERT_LINE))
    f = next(f for f in findings if f.rule_id == "LOG_001")
    assert f.severity == Severity.CRITICAL


def test_log001_suppressed_when_only_precision_line():
    findings = correlate(_events(_PRECISION_LINE))
    assert not any(f.rule_id == "LOG_001" for f in findings)


def test_log001_suppressed_when_only_assert_line():
    findings = correlate(_events(_ASSERT_LINE))
    assert not any(f.rule_id == "LOG_001" for f in findings)


def test_log001_count_in_detail():
    # Two precision lines + one assert — count reflects precision matches
    text = "\n".join([_PRECISION_LINE, _PRECISION_LINE, _ASSERT_LINE])
    findings = correlate(parse_log(text))
    f = next(f for f in findings if f.rule_id == "LOG_001")
    assert "2" in f.detail


# ---------------------------------------------------------------------------
# LOG_002
# ---------------------------------------------------------------------------


def test_log002_fires():
    findings = correlate(_events(_RADIO_LINE))
    assert any(f.rule_id == "LOG_002" for f in findings)


def test_log002_severity_is_warning():
    findings = correlate(_events(_RADIO_LINE))
    f = next(f for f in findings if f.rule_id == "LOG_002")
    assert f.severity == Severity.WARNING


def test_log002_count():
    text = "\n".join([_RADIO_LINE, _RADIO_LINE, _RADIO_LINE])
    findings = correlate(parse_log(text))
    f = next(f for f in findings if f.rule_id == "LOG_002")
    assert "3" in f.detail


# ---------------------------------------------------------------------------
# LOG_003
# ---------------------------------------------------------------------------


def test_log003_fires():
    findings = correlate(_events(_SHAPE_LINE))
    assert any(f.rule_id == "LOG_003" for f in findings)


def test_log003_severity_is_info():
    findings = correlate(_events(_SHAPE_LINE))
    f = next(f for f in findings if f.rule_id == "LOG_003")
    assert f.severity == Severity.INFO


def test_log003_different_shape_name():
    line = "   45.000 WARNING EDCORE (Main): ShapeTable shape not found SOME_OTHER_SHAPE"
    findings = correlate(_events(line))
    assert any(f.rule_id == "LOG_003" for f in findings)


# ---------------------------------------------------------------------------
# LOG_004 — Suppressed
# ---------------------------------------------------------------------------


def test_log004_is_suppressed():
    findings = correlate(_events(_DAMAGE_LINE))
    assert not any(f.rule_id == "LOG_004" for f in findings)


def test_log004_different_unit_type_is_suppressed():
    line = "   10.000 INFO    SCRIPTING (Main): Error: Unit [Su-27]: Corrupt damage model"
    findings = correlate(_events(line))
    assert not any(f.rule_id == "LOG_004" for f in findings)


# ---------------------------------------------------------------------------
# LOG_005 — Suppressed
# ---------------------------------------------------------------------------


def test_log005_is_suppressed():
    findings = correlate(_events(_TCP_LINE))
    assert not any(f.rule_id == "LOG_005" for f in findings)


# ---------------------------------------------------------------------------
# No matches
# ---------------------------------------------------------------------------


def test_no_findings_for_clean_log():
    findings = correlate(_events(_UNRELATED_LINE))
    assert findings == []


def test_suppressed_patterns_produce_no_findings():
    # Mixed log with suppressed and non-suppressed errors
    text = "\n".join([_RADIO_LINE, _DAMAGE_LINE, _TCP_LINE])
    findings = correlate(parse_log(text))
    ids = [f.rule_id for f in findings]

    assert "LOG_002" in ids
    assert "LOG_004" not in ids
    assert "LOG_005" not in ids
    assert len(findings) == 1


def test_no_findings_empty():
    assert correlate([]) == []


# ---------------------------------------------------------------------------
# One finding per pattern (deduplication)
# ---------------------------------------------------------------------------


def test_one_finding_per_pattern_regardless_of_count():
    text = "\n".join([_RADIO_LINE] * 10)
    findings = correlate(parse_log(text))
    log002_findings = [f for f in findings if f.rule_id == "LOG_002"]
    assert len(log002_findings) == 1


# ---------------------------------------------------------------------------
# boost_findings
# ---------------------------------------------------------------------------


def _make_rule_finding(rule_id: str, confidence: float = 0.8) -> ReportFinding:
    return ReportFinding(
        rule_id=rule_id,
        severity=Severity.WARNING,
        title="Test",
        detail="Test detail",
        confidence=confidence,
    )


def test_boost_raises_confidence_for_log001():
    rule_findings = [_make_rule_finding("BLOT_001", confidence=0.8)]
    log_findings = correlate(_events(_PRECISION_LINE, _ASSERT_LINE))
    boosted = boost_findings(rule_findings, log_findings)
    assert boosted[0].confidence > 0.8


def test_boost_caps_at_1():
    rule_findings = [_make_rule_finding("BLOT_001", confidence=0.95)]
    log_findings = correlate(_events(_PRECISION_LINE, _ASSERT_LINE))
    boosted = boost_findings(rule_findings, log_findings)
    assert boosted[0].confidence <= 1.0


def test_boost_does_not_affect_unrelated_rules():
    rule_findings = [_make_rule_finding("PERF_001", confidence=0.5)]
    log_findings = correlate(_events(_PRECISION_LINE, _ASSERT_LINE))
    boosted = boost_findings(rule_findings, log_findings)
    assert boosted[0].confidence == 0.5


def test_boost_no_log_findings_unchanged():
    rule_findings = [_make_rule_finding("BLOT_001", confidence=0.8)]
    boosted = boost_findings(rule_findings, [])
    assert boosted[0].confidence == 0.8


def test_boost_preserves_other_fields():
    rule_findings = [_make_rule_finding("BLOT_001", confidence=0.8)]
    log_findings = correlate(_events(_PRECISION_LINE, _ASSERT_LINE))
    boosted = boost_findings(rule_findings, log_findings)
    assert boosted[0].rule_id == "BLOT_001"
    assert boosted[0].title == "Test"
