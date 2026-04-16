<img src="https://raw.githubusercontent.com/wiki/TylerDOC1776/dcs-afterburner/dcs-afterburnerlogo.png" alt="DCS Afterburner" width="150">

# DCS-Afterburner

![Pre-release](https://img.shields.io/badge/status-pre--release-orange)

A mission linting, diagnostics, and safe optimization toolkit for DCS World `.miz` files.

**[Browser-based mission analyzer →](https://tylerdoc1776.github.io/dcs-afterburner/)** — drop a `.miz` (and optional `dcs.log`) directly in your browser. No install required, nothing uploaded.

Analyze missions before deployment, catch common performance killers, compare versions over time, and optionally apply low-risk automatic optimizations. Optionally load a `dcs.log` file alongside any mission to correlate static findings with real runtime errors.

---

## What it does

DCS `.miz` files are ZIP archives containing Lua-based mission configuration. Afterburner unpacks them, inspects the contents, and runs heuristic checks against known performance and stability patterns.

```
Mission: operation_iron_rain.miz
Severity: 3 critical  8 warnings  11 info

Critical:
  - 426 active ground units at mission start in 4 dense clusters
  - 187 polling triggers detected
  - 9.4 MB embedded script payload

Warnings:
  - 74 unnamed groups
  - 33 duplicate sound assets
  - 18 high-complexity routes

Risk Score: HIGH
```

---

## Use cases

- **Pre-release validation** — scan a mission before putting it on the server
- **Live issue diagnosis** — load a `dcs.log` to find what broke during the last session
- **Legacy cleanup** — find obvious performance problems in old missions
- **Before/after comparison** — check if a new version got heavier or cleaner
- **Safe optimization** — apply low-risk cleanup automatically with a backup
- **CI gate** — fail a build if a mission exceeds thresholds or contains banned patterns

---

## Installation

```bash
pip install dcs-afterburner
```

Or from source:

```bash
git clone https://github.com/your-org/dcs-afterburner
cd dcs-afterburner
pip install -e .
```

---

## Usage

```bash
# Analyze a mission and print a summary
afterburner analyze mission.miz

# Output machine-readable JSON (for CI/CD or dashboards)
afterburner analyze mission.miz --json

# Generate a markdown report
afterburner report mission.miz --format md

# Apply safe optimizations (always creates a backup first)
afterburner optimize mission.miz --safe

# Compare two versions of a mission
afterburner diff old.miz new.miz

# Analyze with a DCS log file for runtime correlation
afterburner analyze mission.miz --log dcs.log

# Inspect a log file on its own
afterburner logs dcs.log

# List all available rules
afterburner rules list

# Explain a specific rule
afterburner rules explain PERF_001
```

---

## What gets checked

**Mission size and bloat**
- Excessive unit, static object, trigger, and zone counts
- Oversized embedded script blocks
- Large archive payload and duplicate assets

**Trigger system**
- Excessive continuous / polling triggers (`TIME MORE` patterns)
- Duplicate trigger actions
- Missing or non-descriptive trigger names

**AI and unit performance**
- High density of active AI groups at mission start
- Large ground formations in small areas
- Route complexity above threshold
- Excessive late-activation groups

**Scripts and Lua**
- Oversized embedded scripts
- Duplicate script frameworks (MOOSE, MIST, CTLD bundled multiple times)
- Timer-heavy and loop-heavy code patterns
- Heavy event handlers without filtering

**DCS log analysis** *(optional — supply a `dcs.log`)*
- Lua errors and stack traces from the last session
- Scheduler spam and high-frequency timer abuse
- Repeated errors indicating runaway loops
- Framework load failures and nil dereferences
- Runtime confirmation of static findings

**Multiplayer and server health**
- Too many active slots relative to mission complexity
- Excessive radio menu items
- High object density near spawn areas

**Maintainability**
- Unnamed or badly named groups
- Duplicate group names
- Missing mission metadata

---

## Configuration

Create an `afterburner.yaml` in your project to tune thresholds:

```yaml
rules:
  max_active_ground_units: 250
  max_trigger_count: 150
  max_script_size_kb: 1024
  warn_on_unnamed_groups: true

optimize:
  safe_mode_only: true
  create_backup: true

output:
  format: markdown
```

---

## Risk scoring

Each mission receives a score based on weighted findings:

| Score | Rating |
|-------|--------|
| 90–100 | Clean |
| 75–89 | Acceptable |
| 50–74 | Caution |
| < 50 | Performance / stability risk |

Scores are always accompanied by an explanation. A score without reasons is not output.

---

## Safe optimization

The `--safe` flag applies only low-risk, reversible transformations:

- Remove exact-duplicate embedded assets
- Strip orphaned or temporary files from the archive
- Optionally rename unnamed groups and triggers using a safe prefix scheme

The following are **never modified automatically**:
- AI routes
- Trigger logic
- Group or unit deletion
- Mission balance or tasking behavior

Every optimization run produces a change log listing each change as `applied`, `skipped`, or `unsafe`.

---

## GitHub Actions

```yaml
- name: Lint mission files
  run: |
    pip install dcs-afterburner
    afterburner analyze *.miz --json > report.json
    afterburner analyze *.miz --fail-on critical
```

---

## License

MIT
