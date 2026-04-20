"""
DCS server CPU/memory benchmark monitor.

Finds DCS.exe instances by their child process names (MemphisBBQ, SouthernBBQ, etc.)
and samples performance metrics every N seconds into a CSV file.

Usage:
    python bench_monitor.py --list
    python bench_monitor.py --server MemphisBBQ --out bench_cpu.csv
    python bench_monitor.py --server MemphisBBQ --interval 2 --out bench_cpu.csv

Requirements:
    pip install psutil
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime, timezone
from typing import NamedTuple

try:
    import psutil
except ImportError:
    sys.exit("psutil not found — run: pip install psutil")


class DcsInstance(NamedTuple):
    server_name: str
    parent_pid: int
    child_pid: int | None


def find_dcs_instances() -> list[DcsInstance]:
    """Return all running DCS.exe instances, identified by their named child process."""
    instances: list[DcsInstance] = []

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["name"] and "DCS" in proc.info["name"] and proc.info["name"].endswith(".exe"):
                children = proc.children()
                if children:
                    for child in children:
                        try:
                            child_name = child.name().replace(".exe", "")
                            # Skip generic Windows sub-processes
                            if child_name not in ("conhost", "WerFault", "DCS"):
                                instances.append(DcsInstance(
                                    server_name=child_name,
                                    parent_pid=proc.pid,
                                    child_pid=child.pid,
                                ))
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                else:
                    # No named child — list as unnamed
                    instances.append(DcsInstance(
                        server_name=f"DCS_{proc.pid}",
                        parent_pid=proc.pid,
                        child_pid=None,
                    ))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return instances


def monitor(instance: DcsInstance, interval: float, out_path: str) -> None:
    try:
        parent = psutil.Process(instance.parent_pid)
    except psutil.NoSuchProcess:
        sys.exit(f"DCS process {instance.parent_pid} not found")

    # Prime cpu_percent — first call always returns 0.0
    parent.cpu_percent(interval=None)
    child_proc = None
    if instance.child_pid:
        try:
            child_proc = psutil.Process(instance.child_pid)
            child_proc.cpu_percent(interval=None)
        except psutil.NoSuchProcess:
            child_proc = None

    cpu_count = psutil.cpu_count(logical=True) or 1

    print(f"Monitoring: {instance.server_name}  (PID {instance.parent_pid})")
    print(f"Output:     {out_path}")
    print(f"Interval:   {interval}s")
    print(f"CPUs:       {cpu_count} logical")
    print("Press Ctrl+C to stop.\n")

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp_utc",
            "elapsed_s",
            "cpu_pct",           # DCS parent process, normalised to 0-100%
            "cpu_pct_raw",       # raw psutil value (can exceed 100 on multi-core)
            "mem_mb",
            "threads",
            "child_cpu_pct",     # child process if present, else blank
            "child_mem_mb",
        ])
        f.flush()

        start = time.monotonic()

        try:
            while True:
                time.sleep(interval)
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

                child_cpu = ""
                child_mem = ""
                if child_proc:
                    try:
                        child_cpu = round(child_proc.cpu_percent(interval=None) / cpu_count, 2)
                        child_mem = round(child_proc.memory_info().rss / 1_048_576, 1)
                    except psutil.NoSuchProcess:
                        child_proc = None

                writer.writerow([now_utc, elapsed, norm_cpu, raw_cpu, mem_mb, threads, child_cpu, child_mem])
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
    print(f"{'Server':<25} {'Parent PID':>10} {'Child PID':>10}")
    print("-" * 48)
    for inst in instances:
        print(f"{inst.server_name:<25} {inst.parent_pid:>10} {inst.child_pid or '—':>10}")


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
        sys.exit(f"Multiple DCS instances found — specify one with --server. Running: {names}")

    monitor(instance, interval=args.interval, out_path=args.out)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bench_monitor",
        description="Monitor DCS server CPU/memory during a benchmark soak run.",
    )
    parser.add_argument("--list", action="store_true", help="List running DCS instances and exit")
    parser.add_argument("--server", default=None, help="Server name to monitor (e.g. MemphisBBQ)")
    parser.add_argument("--interval", type=float, default=1.0, help="Sample interval in seconds (default: 1)")
    parser.add_argument("--out", default="bench_cpu.csv", help="Output CSV path (default: bench_cpu.csv)")
    args = parser.parse_args()

    if args.list:
        cmd_list()
    else:
        cmd_monitor(args)


if __name__ == "__main__":
    main()
