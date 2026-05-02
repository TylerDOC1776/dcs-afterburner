"""
DCS server CPU/memory benchmark monitor.

Finds DCS_server.exe instances by their -w (saved games) argument and samples
performance metrics every N seconds into a CSV file.

Usage:
    python bench_monitor.py --list
    python bench_monitor.py --server MemphisBBQ --out bench_cpu.csv
    python bench_monitor.py --server MemphisBBQ --interval 2 --out bench_cpu.csv
    python bench_monitor.py --server MemphisBBQ --duration 3600 --out bench_cpu.csv

Requirements:
    pip install psutil
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

try:
    import psutil
except ImportError:
    sys.exit("psutil not found — run: pip install psutil")


class DcsInstance(NamedTuple):
    server_name: str
    parent_pid: int
    child_pid: int | None


_CSV_HEADER = [
    "timestamp_utc",
    "elapsed_s",
    "cpu_pct",
    "cpu_pct_raw",
    "mem_mb",
    "threads",
    "child_cpu_pct",
    "child_mem_mb",
]


def find_dcs_instances() -> list[DcsInstance]:
    """Return all running DCS_server.exe instances, identified by their -w argument."""
    instances: list[DcsInstance] = []

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = proc.info["name"] or ""
            if not _is_dcs_process_name(name):
                continue

            cmdline = proc.info["cmdline"] or []
            server_name = None
            if "-w" in cmdline:
                idx = cmdline.index("-w")
                if idx + 1 < len(cmdline):
                    server_name = cmdline[idx + 1]

            if server_name is None:
                server_name = f"DCS_{proc.pid}"

            instances.append(
                DcsInstance(
                    server_name=server_name,
                    parent_pid=proc.pid,
                    child_pid=None,
                )
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return instances


def _is_dcs_process_name(name: str) -> bool:
    normalized = name.lower()
    return normalized.endswith(".exe") and "dcs" in normalized


def monitor(
    instance: DcsInstance,
    interval: float,
    out_path: str | Path,
    duration: float | None = None,
) -> None:
    if interval <= 0:
        sys.exit("--interval must be greater than 0")
    if duration is not None and duration <= 0:
        sys.exit("--duration must be greater than 0")

    try:
        parent = psutil.Process(instance.parent_pid)
    except psutil.NoSuchProcess:
        sys.exit(f"DCS process {instance.parent_pid} not found")

    # Prime cpu_percent — first call always returns 0.0
    parent.cpu_percent(interval=None)

    cpu_count = psutil.cpu_count(logical=True) or 1
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Monitoring: {instance.server_name}  (PID {instance.parent_pid})")
    print(f"Output:     {out_path}")
    print(f"Interval:   {interval}s")
    if duration is not None:
        print(f"Duration:   {duration}s")
    print(f"CPUs:       {cpu_count} logical")
    print("Press Ctrl+C to stop.\n")

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(_CSV_HEADER)
        f.flush()

        start = time.monotonic()
        elapsed = 0.0

        try:
            while True:
                if duration is not None and elapsed >= duration:
                    print(f"\nCompleted {duration:.1f}s — saved to {out_path}")
                    break

                sleep_for = interval
                if duration is not None:
                    sleep_for = min(interval, max(0.0, duration - elapsed))
                time.sleep(sleep_for)

                now_utc = datetime.now(timezone.utc).isoformat()
                elapsed = round(time.monotonic() - start, 1)

                try:
                    raw_cpu = parent.cpu_percent(interval=None)
                    norm_cpu = round(raw_cpu / cpu_count, 2)
                    mem_mb = round(parent.memory_info().rss / 1_048_576, 1)
                    threads = parent.num_threads()
                except psutil.NoSuchProcess:
                    print(f"\n[{elapsed}s] DCS process exited.")
                    break

                writer.writerow(
                    [
                        now_utc,
                        elapsed,
                        norm_cpu,
                        raw_cpu,
                        mem_mb,
                        threads,
                        "",
                        "",
                    ]
                )
                f.flush()

                print(
                    f"  [{elapsed:>6.1f}s]  CPU {norm_cpu:>5.1f}%  "
                    f"MEM {mem_mb:>7.1f} MB  threads {threads}",
                    end="\r",
                )

        except KeyboardInterrupt:
            print(f"\n\nStopped at {elapsed:.1f}s — saved to {out_path}")


def cmd_list() -> None:
    instances = find_dcs_instances()
    if not instances:
        print("No DCS.exe instances found.")
        return
    print(f"{'Server':<25} {'Parent PID':>10}")
    print("-" * 38)
    for inst in instances:
        print(f"{inst.server_name:<25} {inst.parent_pid:>10}")


def cmd_monitor(args: argparse.Namespace) -> None:
    instances = find_dcs_instances()
    if not instances:
        sys.exit("No DCS.exe instances found.")

    if len(instances) == 1 and not args.server:
        instance = instances[0]
    elif args.server:
        matches = [i for i in instances if i.server_name.lower() == args.server.lower()]
        if not matches:
            names = ", ".join(i.server_name for i in instances)
            sys.exit(f"Server '{args.server}' not found. Running: {names}")
        instance = matches[0]
    else:
        names = ", ".join(i.server_name for i in instances)
        sys.exit(
            f"Multiple DCS instances found — specify one with --server. Running: {names}"
        )

    monitor(instance, interval=args.interval, out_path=args.out, duration=args.duration)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bench_monitor",
        description="Monitor DCS server CPU/memory during a benchmark soak run.",
    )
    parser.add_argument(
        "--list", action="store_true", help="List running DCS instances and exit"
    )
    parser.add_argument(
        "--server", default=None, help="Server name to monitor (e.g. MemphisBBQ)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Sample interval in seconds (default: 5)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Stop automatically after this many seconds",
    )
    parser.add_argument(
        "--out",
        default="bench_cpu.csv",
        help="Output CSV path (default: bench_cpu.csv)",
    )
    args = parser.parse_args()

    if args.list:
        cmd_list()
    else:
        cmd_monitor(args)


if __name__ == "__main__":
    main()
