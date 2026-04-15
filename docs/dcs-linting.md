DCS Lua Linting & Benchmarking Pipeline
Overview

This project defines a GitHub Actions–based pipeline for validating and analyzing Lua scripts used in Digital Combat Simulator (DCS).

The goal is to move beyond generic Lua linting and implement:

A DCS-aware linter
A framework-aware analyzer (MOOSE, MIST, etc.)
A repeatable benchmarking system to track performance and regressions

DCS uses Lua 5.1, and its scripting environment introduces non-standard globals, timing constraints, and runtime behaviors that require specialized validation.

Core Objectives
1. Linting
Enforce correct Lua syntax
Detect DCS-specific scripting issues
Prevent common mission-breaking patterns
2. Static Analysis
Understand usage of:
DCS API
MOOSE
MIST
Validate function usage and patterns
3. Benchmarking
Measure performance of:
Linting pipeline
Parser and rule engine
Detect regressions over time
DCS Scripting Environment
Known Global Tables & Singletons

These are implicitly available in DCS and must be whitelisted:

world
coalition
timer
net
trigger
Unit
Weapon
StaticObject
Airbase
Access Patterns

DCS uses function-based access instead of direct variable access:

coalition.getPlayers()
Unit.getByName("unitName")
Object.inAir(unit)
Object.getVelocity(unit)
Important Constraints
Global Scope Behavior
Variables without local are global and persist across triggers
This can cause cross-script contamination
Timing Issues
Objects may not exist at script execution time
Late activation is common
Must use timer.scheduleFunction when needed
Performance Constraints
Blocking loops can freeze the simulation
All long-running logic must be scheduled
Linting Architecture
Base Linter

Use:

luacheck as the baseline static analyzer

Configuration:

Add DCS globals to avoid false positives
Enforce strict global usage rules
Custom DCS Rule Engine

A secondary linter layer will enforce domain-specific rules.

Rule Categories
1. Unsafe Global Writes
myVar = 5

Problem:

Creates persistent global state unintentionally

Rule:

Require explicit opt-in or enforce local
2. Unsafe Object Access
Unit.getByName("Aerial-1"):getPoint()

Problem:

Object may be nil

Correct Pattern:

local u = Unit.getByName("Aerial-1")
if u then
  u:getPoint()
end
3. Timing Violations

Flag:

Direct access to late-activated units
Immediate execution assumptions

Recommend:

Use timer.scheduleFunction
4. Blocking Execution
while true do

Problem:

Freezes DCS engine

Rule:

Require scheduled execution model
5. Event Handler Validation

Validate correct usage of:

world.addEventHandler(handler)

Ensure:

Proper event structure
Valid handler definitions
Framework Awareness
Supported Frameworks
MOOSE
MIST
CTLD (planned)
Skynet IADS (planned)
API Extraction System
Goal

Extract function signatures into JSON for:

Validation
Autocomplete
Static analysis
Example Output
{
  "MOOSE": {
    "SPAWN:New": ["string"],
    "SPAWN:Spawn": []
  },
  "mist": {
    "mist.scheduleFunction": ["function", "table", "number"]
  }
}
Implementation Strategy
Step 1: Parse Source Trees

Paths:

~/Documents/Projects/MOOSE
~/Documents/Projects/MissionScriptingTools

Extract:

Function names
Method chains
Basic argument patterns
Step 2: Normalize Output

Flatten into:

Callable names
Expected argument counts/types (best effort)
Step 3: Use in Linter

Validate:

Function existence
Basic usage patterns
Limitations
Cannot fully resolve:
Metatables
Dynamic inheritance
Must supplement with manual rules
Benchmarking System
Purpose

Track performance of:

Linter
Parser
Rule engine

Detect:

Regressions
Scaling issues
Benchmark Scope
1. Linter Performance

Measure:

Total runtime
Time per file
Time per corpus size
2. Parser Performance

Measure:

Time to process MOOSE
Time to process MIST
JSON generation cost
3. Rule Engine Cost

Measure:

Time per rule
Identify expensive checks
Benchmark Corpus
bench/
  corpus/
    small/
    medium/
    large/
Definitions
small: utility scripts
medium: typical mission scripts
large: full mission packages
Benchmark Tooling

Use:

hyperfine for repeatable benchmarking

Capabilities:

Warmup runs
Multiple iterations
Statistical output
Export formats (JSON, Markdown)
GitHub Actions Plan
Workflow 1: Linting (ci-lint.yml)

Triggers:

push
pull_request

Purpose:

Fast validation
Blocking errors
Jobs
1. LuaCheck
- run: luacheck .
2. DCS Linter
- run: ./tools/dcs-lint .
Workflow 2: Benchmarking (benchmark.yml)

Triggers:

manual (workflow_dispatch)
scheduled (weekly)
Job: Benchmark
name: benchmark

on:
  workflow_dispatch:
  schedule:
    - cron: '0 5 * * 1'

jobs:
  benchmark:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Install dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y hyperfine

      - name: Run benchmarks
        run: |
          mkdir -p bench-out

          hyperfine --warmup 3 --runs 10 \
            './tools/dcs-lint bench/corpus/small' \
            './tools/dcs-lint bench/corpus/medium' \
            './tools/dcs-lint bench/corpus/large' \
            --export-json bench-out/results.json \
            --export-markdown bench-out/results.md

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: benchmark-results
          path: bench-out/
Benchmark Policy
Do NOT fail builds for small regressions

Instead:

Track trends
Flag major regressions (>25–50%)
Runner Strategy
GitHub-hosted runners
Good for general benchmarking
Not reliable for micro-optimizations
Self-hosted runners (recommended later)
Stable environment
Better for long-term tracking
Future Enhancements
1. Pattern Cost Benchmarks

Test:

repeated Unit.getByName
table allocation
string concatenation
event dispatch patterns
2. Rule Severity Levels
Error (fail CI)
Warning
Info
3. Incremental Linting
Only analyze changed files
4. Cached Symbol Index
Avoid regenerating MOOSE/MIST index each run
Summary

This system provides:

A DCS-aware linting pipeline
A framework-aware validation layer
A repeatable benchmarking system

Key design decisions:

Separate linting and benchmarking
Focus on high-value DCS-specific rules
Use static extraction for framework awareness
Avoid over-reliance on runtime assumptions
