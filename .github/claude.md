# DCS-Afterburner Project Rules

## Tech Stack & Constraints
- **Language:** Python (Base only, no external heavy libraries like pandas)
- **Focus:** DCS World `.miz` (ZIP/Lua) analysis and benchmarking.
- **CLI Framework:** Built-in Python argparse/cli structure in `afterburner/cli.py`.

## Project Structure
- `afterburner/bench/`: Automated benchmark harness (Current Focus).
- `afterburner/models/`: Data structures for missions and scores.
- `afterburner/parsers/`: Logic for reading `.miz` and `dcs.log`.

## Development Standards
- Use `pytest` for testing in the `tests/` directory.
- Maintain compatibility with standard Windows environments (DCS host).
- Output should be Markdown or machine-readable JSON.

## Current Objective
- Build the **Automated Client-Side Mission Benchmark Harness**.
- Capture metrics: FPS, 1% Lows, Frametime Variance, and Load Times.
- Implement the 0–100 Weighted Scoring Model.