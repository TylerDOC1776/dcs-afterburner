"""Tests for reporter modules — markdown and JSON."""

from __future__ import annotations

from afterburner.models.findings import ReportFinding, Severity
from afterburner.models.mission import Mission, MissionSummary
from afterburner.models.report import Report
from afterburner.reporters.markdown import to_markdown


def _make_summary(**kwargs) -> MissionSummary:
    defaults = dict(
        theatre="Caucasus",
        total_units=100,
        active_units=80,
        late_units=20,
        player_slots=8,
        total_groups=30,
        active_groups=25,
        total_statics=10,
        trigger_count=5,
        zone_count=4,
    )
    defaults.update(kwargs)
    return MissionSummary(**defaults)


def _make_mission(**kwargs) -> Mission:
    return Mission(
        name="Test Mission",
        source_file="test.miz",
        sha256="sha256:abc123",
        theatre="Caucasus",
        summary=_make_summary(),
        **kwargs,
    )


def _make_finding(
    rule_id: str = "BLOT_001",
    severity: Severity = Severity.WARNING,
    title: str = "A finding",
    detail: str = "Some detail.",
    fix: str | None = None,
) -> ReportFinding:
    return ReportFinding(
        rule_id=rule_id,
        severity=severity,
        title=title,
        detail=detail,
        fix=fix,
    )


# ------------------------------------------------------------------
# Structure
# ------------------------------------------------------------------


def test_markdown_contains_mission_name():
    md = to_markdown(Report(mission=_make_mission()))
    assert "Test Mission" in md


def test_markdown_contains_source_file():
    md = to_markdown(Report(mission=_make_mission()))
    assert "test.miz" in md


def test_markdown_contains_hash():
    md = to_markdown(Report(mission=_make_mission()))
    assert "sha256:abc123" in md


def test_markdown_contains_theatre():
    md = to_markdown(Report(mission=_make_mission()))
    assert "Caucasus" in md


def test_markdown_contains_risk_score():
    report = Report(mission=_make_mission())
    md = to_markdown(report)
    assert str(report.risk_score()) in md
    assert report.risk_label() in md


def test_markdown_contains_summary_section():
    md = to_markdown(Report(mission=_make_mission()))
    assert "## Mission Summary" in md


def test_markdown_contains_findings_section():
    md = to_markdown(Report(mission=_make_mission()))
    assert "## Findings" in md


def test_markdown_summary_table_has_metrics():
    md = to_markdown(Report(mission=_make_mission()))
    assert "Total units" in md
    assert "Player slots" in md
    assert "Triggers" in md


# ------------------------------------------------------------------
# No findings
# ------------------------------------------------------------------


def test_markdown_no_findings_message():
    md = to_markdown(Report(mission=_make_mission()))
    assert "No findings." in md


def test_markdown_no_findings_has_no_rule_ids():
    md = to_markdown(Report(mission=_make_mission()))
    assert "BLOT_" not in md
    assert "PERF_" not in md


# ------------------------------------------------------------------
# With findings
# ------------------------------------------------------------------


def test_markdown_finding_rule_id_present():
    findings = [_make_finding(rule_id="BLOT_001")]
    md = to_markdown(Report(mission=_make_mission(), findings=findings))
    assert "BLOT_001" in md


def test_markdown_finding_title_present():
    findings = [_make_finding(title="High active unit count")]
    md = to_markdown(Report(mission=_make_mission(), findings=findings))
    assert "High active unit count" in md


def test_markdown_finding_detail_present():
    findings = [_make_finding(detail="700 units active at mission start.")]
    md = to_markdown(Report(mission=_make_mission(), findings=findings))
    assert "700 units active at mission start." in md


def test_markdown_finding_fix_present_when_set():
    findings = [_make_finding(fix="Move groups to late activation.")]
    md = to_markdown(Report(mission=_make_mission(), findings=findings))
    assert "Move groups to late activation." in md


def test_markdown_finding_fix_absent_when_none():
    findings = [_make_finding(fix=None)]
    md = to_markdown(Report(mission=_make_mission(), findings=findings))
    assert "**Fix:**" not in md


def test_markdown_critical_severity_shown():
    findings = [_make_finding(severity=Severity.CRITICAL)]
    md = to_markdown(Report(mission=_make_mission(), findings=findings))
    assert "critical" in md.lower()


def test_markdown_warning_severity_shown():
    findings = [_make_finding(severity=Severity.WARNING)]
    md = to_markdown(Report(mission=_make_mission(), findings=findings))
    assert "warning" in md.lower()


def test_markdown_info_severity_shown():
    findings = [_make_finding(severity=Severity.INFO)]
    md = to_markdown(Report(mission=_make_mission(), findings=findings))
    assert "info" in md.lower()


def test_markdown_multiple_findings_all_shown():
    findings = [
        _make_finding(rule_id="BLOT_001", title="Finding one"),
        _make_finding(rule_id="BLOT_002", title="Finding two"),
        _make_finding(rule_id="PERF_003", title="Finding three"),
    ]
    md = to_markdown(Report(mission=_make_mission(), findings=findings))
    assert "BLOT_001" in md
    assert "BLOT_002" in md
    assert "PERF_003" in md


def test_markdown_no_findings_section_absent_when_findings_present():
    findings = [_make_finding()]
    md = to_markdown(Report(mission=_make_mission(), findings=findings))
    assert "No findings." not in md


def test_markdown_confidence_shown():
    findings = [_make_finding()]
    md = to_markdown(Report(mission=_make_mission(), findings=findings))
    assert "Confidence:" in md


# ------------------------------------------------------------------
# Return type
# ------------------------------------------------------------------


def test_markdown_returns_string():
    md = to_markdown(Report(mission=_make_mission()))
    assert isinstance(md, str)


def test_markdown_nonempty():
    md = to_markdown(Report(mission=_make_mission()))
    assert len(md) > 0
