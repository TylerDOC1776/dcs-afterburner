# DCS-Afterburner — Project Planning

## Vision

DCS-Afterburner is a mission linting, diagnostics, and safe optimization toolkit for DCS World `.miz` files. The goal is to become the standard pre-deployment quality gate used by mission makers, server operators, and community pipelines.

A `.miz` file is a ZIP archive containing Lua-based mission tables and embedded assets. The tool unpacks it, parses the contents, runs heuristic checks, and produces actionable reports. Optionally, it can apply low-risk automatic optimizations and repack the archive.

DCS server log files (`dcs.log`) can be supplied alongside a mission to provide real-world runtime evidence — correlating static analysis findings with actual errors, scheduler spam, and event handler failures observed during live operation.

The tool is **heuristic-based, not simulation-based**. It identifies known bad patterns rather than attempting to model DCS engine behavior directly.

---

## Target Users

| User | Primary need |
|------|-------------|
| Mission makers | Catch design problems before release |
| Server admins | Validate missions before hosting and diagnose live issues via logs |
| Community CI pipelines | Automated quality gates on pull requests |
| Campaign builders | Compare mission weight across versions |

---

## Architecture

### Pipeline overview

```
.miz file          dcs.log (optional)
    │                   │
    ▼                   ▼
Input Layer          validate paths, extract .miz ZIP to temp workspace,
                     stream-parse log file if provided
    │                   │
    ▼                   ▼
Parsing Layer        parse Lua tables → Python models
                     parse log → LogEvent list (errors, warnings, scheduler hits)
    │                   │
    └─────────┬─────────┘
              ▼
Rule Engine          run checks against mission models + optional log events
                     log findings cross-reference static analysis with runtime evidence
              │
              ▼
Optimization Engine  (optional) apply safe transforms, log changes
              │
              ▼
Output Layer         console / markdown / JSON / HTML
```

### Module layout

```
dcs-afterburner/
├── afterburner/
│   ├── cli.py                  entry point (typer)
│   ├── config.py               threshold and rule config
│   ├── models/
│   │   ├── mission.py          Mission, Coalition, Country, Group, Unit, Route
│   │   ├── findings.py         ReportFinding, Severity enum
│   │   └── report.py           Report, MissionSummary
│   ├── parsers/
│   │   ├── miz.py              ZIP extraction and repack
│   │   ├── mission_parser.py   parse main mission table
│   │   ├── trigger_parser.py   parse trigger and condition tables
│   │   └── script_parser.py    extract and inspect embedded Lua
│   ├── rules/
│   │   ├── base.py             Rule base class and registry
│   │   ├── mission_size.py     unit/static/zone count thresholds
│   │   ├── performance.py      AI density, route complexity
│   │   ├── triggers.py         polling triggers, duplicate actions
│   │   ├── scripting.py        framework detection, timer patterns
│   │   └── ai.py               spawn risk, uncontrolled aircraft
│   ├── optimize/
│   │   ├── engine.py           orchestrate backup + transforms + changelog
│   │   ├── safe_fixes.py       individual safe transform functions
│   │   └── rewrite.py          rebuild and repack .miz
│   ├── reporters/
│   │   ├── console.py          rich terminal summary
│   │   ├── markdown.py         markdown report
│   │   ├── json_report.py      machine-readable JSON
│   │   └── html.py             HTML report (Phase 4+)
│   ├── log_analysis/
│   │   ├── parser.py           stream-parse dcs.log into LogEvent list
│   │   ├── patterns.py         regex patterns for known error signatures
│   │   └── correlator.py       match log events to mission findings
│   └── utils/
│       ├── files.py            temp workspace management
│       ├── hashes.py           file deduplication helpers
│       └── tempdir.py          context manager for temp extraction
├── tests/
│   ├── fixtures/               .miz files used as test inputs
│   ├── test_miz_unpack.py
│   ├── test_rules.py
│   └── test_optimize.py
├── docs/
├── .github/
│   └── workflows/
│       └── mission-lint.yml
├── README.md
├── pyproject.toml
└── .gitignore
```

---

## Data Models

### Core mission models

```python
@dataclass
class Unit:
    id: int
    name: str
    type: str
    skill: str
    late_activation: bool
    position: tuple[float, float]

@dataclass
class Group:
    id: int
    name: str
    category: str          # ground / air / ship / static
    units: list[Unit]
    route: Route | None
    late_activation: bool
    uncontrolled: bool

@dataclass
class Trigger:
    id: int
    name: str
    type: str              # ONCE / MULTI / COND etc.
    conditions: list[TriggerCondition]
    actions: list[TriggerAction]

@dataclass
class ReportFinding:
    rule_id: str
    severity: Severity     # CRITICAL / WARNING / INFO
    title: str
    detail: str
    fix: str | None
    confidence: float      # 0.0–1.0
```

### JSON output schema

```json
{
  "mission_name": "operation_iron_rain",
  "source_file": "mission.miz",
  "hash": "sha256:...",
  "summary": {
    "total_units": 1240,
    "active_units": 620,
    "statics": 820,
    "triggers": 210,
    "continuous_triggers": 97,
    "script_payload_kb": 9400,
    "risk_score": 38,
    "risk_label": "HIGH"
  },
  "findings": [
    {
      "rule_id": "PERF_001",
      "severity": "critical",
      "title": "Excessive active ground units at mission start",
      "detail": "426 active ground units detected across 4 high-density clusters.",
      "fix": "Convert non-essential groups to late activation."
    }
  ],
  "metrics": {},
  "optimizations_applied": [],
  "output_file": null
}
```

---

## Rule Catalog

### Naming convention

Rule IDs follow the pattern `CATEGORY_NNN`:

| Prefix | Category |
|--------|----------|
| `PERF` | Performance / AI load |
| `TRIG` | Trigger system |
| `SCRP` | Scripting and Lua |
| `BLOT` | Mission size and bloat |
| `MULT` | Multiplayer / server health |
| `MAINT` | Maintainability and hygiene |

### Default thresholds (all configurable)

| Rule ID | Check | Default threshold |
|---------|-------|-------------------|
| `BLOT_001` | Total units | > 1200 |
| `BLOT_002` | Active units at start | > 600 |
| `BLOT_003` | Static objects | > 800 |
| `BLOT_004` | Trigger count | > 150 |
| `BLOT_005` | Zone count | > 100 |
| `BLOT_006` | Embedded script payload | > 1 MB |
| `BLOT_007` | Archive size | > 100 MB |
| `BLOT_008` | Player slots | > 80 |
| `TRIG_001` | Continuous / polling triggers | > 40 |
| `TRIG_002` | Duplicate trigger actions | any |
| `TRIG_003` | Unnamed triggers | > 10 |
| `SCRP_001` | Duplicate script frameworks | any |
| `SCRP_002` | Suspicious timer intervals | < 0.1s schedule |
| `SCRP_003` | Unfiltered world.searchObjects | any |
| `PERF_001` | Active AI group density (per km²) | configurable |
| `PERF_002` | Route waypoint count | > 50 per group |
| `PERF_003` | Uncontrolled aircraft not delayed | > 10 |
| `MAINT_001` | Unnamed groups | > 5% of total |
| `MAINT_002` | Duplicate group names | any |
| `MAINT_003` | Missing mission metadata block | — |
| `MULT_001` | Radio menu item count | > 40 |
| `MULT_002` | Spawn area object density | configurable |

---

## Log Analysis

### Purpose

`dcs.log` provides real-world runtime evidence that static mission analysis cannot. Log analysis is optional but significantly increases finding confidence when available.

Where static analysis says "this pattern is risky," log correlation can say "this pattern caused 847 errors during the last session."

### What gets extracted from dcs.log

| Log event type | What it indicates |
|---------------|-------------------|
| Lua errors with stack traces | Broken script logic, nil references |
| Scheduler spam (repeated calls < 0.1s) | Timer abuse, high-frequency polling |
| Event handler errors | Unfiltered or fragile event logic |
| `world.searchObjects` repeated calls | Expensive world scanning in a loop |
| Mission scripting load errors | Broken embedded scripts or frameworks |
| Performance warnings | Engine-side frame time or unit count warnings |
| Repeated identical errors (> N times) | Runaway loops, unfixed nil dereferences |

### CLI usage

```bash
# Analyze mission with a log file for correlation
afterburner analyze mission.miz --log dcs.log

# Log-only mode: inspect a log without a .miz
afterburner log dcs.log

# Log + mission report
afterburner report mission.miz --log dcs.log --format md
```

### How correlation works

The correlator maps log evidence back to mission findings:

1. Parse log into `LogEvent` objects (timestamp, level, source, message, count)
2. Group events by type and deduplicate repeated entries
3. For each static rule finding, check if matching log events exist
4. If log evidence confirms a finding → raise confidence, add log excerpt to detail
5. If log evidence is present but no static finding exists → generate a log-only finding

Example enriched finding:

```
[SCRP_002] High-frequency timer detected
Confidence: HIGH (confirmed by log)
Detail: timer.scheduleFunction called with 0.05s interval.
        Log evidence: 1,247 scheduler callbacks in 45 minutes (dcs.log line 8842)
Fix: Increase interval to >= 1s or restructure to event-driven logic.
```

### Log-only findings

Some issues only appear at runtime and have no static signal:

- Nil dereference errors in triggered scripts
- Framework version conflicts at load time
- Errors generated by late-activation group scripts
- Network sync errors in multiplayer sessions

These are surfaced as `LOG_NNN` findings.

### Log data model

```python
@dataclass
class LogEvent:
    timestamp: datetime | None
    level: str           # ERROR / WARNING / INFO
    source: str          # module or script path
    message: str
    count: int           # how many times this line repeats
    line_number: int
```

---

## Risk Scoring

A mission risk score (0–100) is computed from weighted findings. The score is always shown alongside the reasons that drove it down — a number without explanation is not output.

| Score | Label |
|-------|-------|
| 90–100 | Clean |
| 75–89 | Acceptable |
| 50–74 | Caution |
| < 50 | High risk |

Score weights (draft):

- Active AI load: 25%
- Trigger complexity: 20%
- Scripting weight: 20%
- Archive size / bloat: 15%
- Naming and hygiene: 10%
- Spawn area density: 10%

---

## Safe Optimization Rules

### What may be auto-applied with `--safe`

- Remove exact-duplicate embedded assets (same hash, multiple copies)
- Strip orphaned and temporary generated files from the archive
- Normalize archive internal structure (consistent path separators, no junk entries)
- Optionally rename unnamed groups/triggers using a safe prefix (`UNNAMED_GRP_001`)

### What requires manual action (suggestions only)

- Converting active groups to late activation
- Consolidating duplicate trigger logic
- Reducing route waypoint counts
- Splitting overloaded script blocks

### What is never auto-applied

- AI route changes
- Group or unit deletion
- Trigger condition or action rewriting
- Mission balance, tasking, or gameplay behavior

### Backup and change log

Every optimize run:
1. Creates `<name>.miz.bak` before any changes
2. Writes a change log to stdout and optionally to a JSON sidecar
3. Records each transform as `applied`, `skipped`, or `unsafe`
4. Aborts cleanly if any step fails — never produces a partial output

---

## Configuration

Config is loaded in this order (later entries override earlier):

1. Built-in defaults
2. `afterburner.yaml` in the working directory
3. `--config` flag on the CLI
4. Individual `--set key=value` overrides

Example `afterburner.yaml`:

```yaml
rules:
  max_active_ground_units: 250
  max_trigger_count: 150
  max_continuous_triggers: 30
  max_script_size_kb: 1024
  max_player_slots: 60
  warn_on_unnamed_groups: true
  warn_on_unnamed_triggers: true

optimize:
  safe_mode_only: true
  create_backup: true
  backup_suffix: .bak

output:
  format: markdown       # console | markdown | json | html
  color: true
  verbose: false
```

---

## CI Integration

### GitHub Actions example

```yaml
name: Mission lint

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install dcs-afterburner
      - run: afterburner analyze *.miz --fail-on critical
      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: mission-report
          path: "*.report.md"
```

Exit codes:
- `0` — no findings at or above the fail threshold
- `1` — findings found at or above the fail threshold
- `2` — tool error (bad input, parse failure)

---

## Bullseye Integration Path

DCS-Afterburner is designed to remain fully usable as a standalone tool. The Bullseye integration is additive:

```bash
# Standalone
afterburner analyze mission.miz

# Via Bullseye (future)
bullseye mission analyze mission.miz
bullseye deploy mission.miz --precheck afterburner
```

The JSON output is the integration surface. Bullseye can consume the report, display the risk score in the server UI, and optionally block deployment if thresholds are exceeded.

---

## Development Phases

### Phase 1 — Foundation
- Repo skeleton and CLI entry point
- `.miz` unpack and repack
- Parse core mission tables (groups, units, statics, triggers, zones)
- Basic console summary

**Deliverable:** `afterburner analyze mission.miz` works on a real mission

### Phase 2 — Rules Engine MVP
- `ReportFinding` model and severity levels
- Rule base class and registry
- First 10–15 rules implemented
- Markdown and JSON output

**Deliverable:** Useful analysis reports on real missions

### Phase 3 — Safe Optimization
- Backup handling
- Safe transform engine with change log
- First low-risk optimizations

**Deliverable:** `afterburner optimize mission.miz --safe` works safely

### Phase 4 — Diff and Comparison
- Parse two missions and diff their models
- Output metric deltas and regression highlights

**Deliverable:** `afterburner diff old.miz new.miz` works

### Phase 4b — Log Analysis and Correlation
- Stream-parse `dcs.log` into `LogEvent` list
- Detect error patterns, scheduler spam, repeated failures
- Correlate log events with static rule findings
- Surface log-only findings (`LOG_NNN`)
- `--log` flag on `analyze` and `report` commands

**Deliverable:** `afterburner analyze mission.miz --log dcs.log` enriches findings with runtime evidence

### Phase 5 — CI and Automation
- Stable exit codes
- Stable JSON schema
- GitHub Action example workflow
- Bullseye pre-deploy hook

**Deliverable:** Automated mission quality gates in CI

---

## Testing Strategy

### Fixture library

Maintain a set of `.miz` fixtures in `tests/fixtures/` covering:

| Fixture | Purpose |
|---------|---------|
| `clean_small.miz` | Baseline — should produce no findings |
| `bloated.miz` | Triggers BLOT rules |
| `trigger_heavy.miz` | Triggers TRIG rules |
| `script_heavy.miz` | Triggers SCRP rules |
| `multiplayer.miz` | Triggers MULT rules |
| `unnamed_groups.miz` | Triggers MAINT rules |

Every bug fix should add a corresponding fixture or assertion that would have caught it.

### Test structure

- `test_miz_unpack.py` — extract, inspect, repack round-trip
- `test_rules.py` — each rule fires on the correct fixture and is silent on clean missions
- `test_optimize.py` — safe transforms produce correct output and backups are created
- `test_cli.py` — CLI commands return correct exit codes and output shapes

---

## Longer-Term Ideas

- `afterburner watch <folder>` — monitor a folder and re-analyze on change
- `afterburner benchmark <folder>` — score all missions in a directory
- Visual object density heatmap
- Trigger dependency graph
- Lua script complexity scoring
- Linting profiles: PvE, PvP, training, campaign
- `dcs.log` correlation — match script errors to mission findings
- Web UI or VS Code extension
