from __future__ import annotations

from afterburner.bench.log_issues import parse_log_issues


def test_parse_log_issues_always_reports_hard_stop():
    log = """\
2026-04-27 08:09:02.503 ERROR   SCRIPTING (Main): Mission script error: [string "assert(loadfile(lfs.writedir().."ColdWar/Core/loader.lua"))()"]:1: no file 'C:\\Users\\DCS\\ColdWar/Core/loader.lua'
stack traceback:
\t[C]: ?
\t[C]: in function 'assert'
"""

    issues = parse_log_issues(log, repeated_threshold=10)

    assert len(issues) == 1
    assert issues[0].issue_type == "hard_stop"
    assert "Mission script error:" in issues[0].signature
    assert "stack traceback" in (issues[0].detail or "")


def test_parse_log_issues_reports_repeated_scripting_errors_only_above_threshold():
    line = (
        "2026-04-27 08:09:02.503 ERROR   SCRIPTING (Main): "
        '[string "l10n/DEFAULT/foo.lua"]:12: attempt to index local x\n'
    )
    low = (
        "2026-04-27 08:09:03.503 ERROR   SCRIPTING (Main): "
        '[string "l10n/DEFAULT/low.lua"]:1: one off\n'
    )

    issues = parse_log_issues(line * 10 + low, repeated_threshold=10)

    repeated = [i for i in issues if i.issue_type == "repeated_scripting"]
    assert len(repeated) == 1
    assert repeated[0].count == 10
    assert "foo.lua" in repeated[0].signature
