import csv
import json
import os
import statistics
import subprocess
import time
from datetime import datetime

_PRESENTMON_CANDIDATES = [
    r"C:\Program Files\PresentMon\PresentMon.exe",
    r"C:\Program Files (x86)\PresentMon\PresentMon.exe",
    r"C:\Tools\PresentMon\PresentMon.exe",
    r"C:\PresentMon\PresentMon.exe",
    "PresentMon.exe",  # on PATH
    "PresentMon64.exe",
]

# Column names across PresentMon 1.x / 2.x releases
_FRAMETIME_COLS = ("msBetweenPresents", "FrameTime_ms", "MsBetweenPresents")


class DCSBenchmarkHarness:
    def __init__(self, dcs_path, output_dir="bench_results", presentmon_path=None):
        self.dcs_path = dcs_path
        self.output_dir = output_dir
        self.presentmon_path = presentmon_path or self._find_presentmon()
        os.makedirs(self.output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # PresentMon helpers
    # ------------------------------------------------------------------

    def _find_presentmon(self):
        for path in _PRESENTMON_CANDIDATES:
            if os.path.isfile(path):
                return path
        return None

    def _start_presentmon(self, output_csv: str) -> subprocess.Popen:
        if not self.presentmon_path:
            raise FileNotFoundError(
                "PresentMon not found. Install it or pass presentmon_path= to the harness. "
                "Download: https://github.com/GameTechDev/PresentMon/releases"
            )
        cmd = [
            self.presentmon_path,
            "-process_name",
            "DCS.exe",
            "-output_file",
            output_csv,
            "-stop_existing_session",
            "-no_top",
        ]
        return subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    def _stop_process(self, proc: subprocess.Popen, timeout: int = 5) -> None:
        proc.terminate()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()

    # ------------------------------------------------------------------
    # CSV parsing
    # ------------------------------------------------------------------

    def _parse_frametimes(self, csv_path: str) -> list[float]:
        """Return a list of per-frame durations (ms) from a PresentMon CSV."""
        if not os.path.isfile(csv_path):
            return []

        frametimes: list[float] = []
        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                # PresentMon 1.x prepends comment lines starting with "//"
                lines = [ln for ln in f if not ln.startswith("//")]

            reader = csv.DictReader(lines)
            col = next(
                (c for c in _FRAMETIME_COLS if c in (reader.fieldnames or [])),
                None,
            )
            if col is None:
                print(
                    f"[harness] WARNING: no frametime column found in {csv_path}. "
                    f"Available columns: {reader.fieldnames}"
                )
                return []

            for row in reader:
                raw = row.get(col, "").strip()
                if not raw:
                    continue
                try:
                    ft = float(raw)
                    if ft > 0:
                        frametimes.append(ft)
                except ValueError:
                    continue

        except OSError as exc:
            print(f"[harness] WARNING: could not read PresentMon CSV: {exc}")

        return frametimes

    # ------------------------------------------------------------------
    # FPS statistics
    # ------------------------------------------------------------------

    def _compute_fps_stats(self, frametimes_ms: list[float]) -> dict:
        if not frametimes_ms:
            return {
                "avg_fps": None,
                "low_1pct_fps": None,
                "low_01pct_fps": None,
                "avg_frametime_ms": None,
                "frametime_stdev_ms": None,
                "sample_count": 0,
            }

        fps = [1000.0 / ft for ft in frametimes_ms]
        fps_asc = sorted(fps)
        n = len(fps_asc)

        # 1% low: mean of the worst 1% of frames (lowest FPS = longest frametimes)
        cut_1pct = max(1, int(n * 0.01))
        cut_01pct = max(1, int(n * 0.001))

        return {
            "avg_fps": round(statistics.mean(fps), 2),
            "low_1pct_fps": round(statistics.mean(fps_asc[:cut_1pct]), 2),
            "low_01pct_fps": round(statistics.mean(fps_asc[:cut_01pct]), 2),
            "avg_frametime_ms": round(statistics.mean(frametimes_ms), 3),
            "frametime_stdev_ms": round(
                statistics.stdev(frametimes_ms) if n > 1 else 0.0, 3
            ),
            "sample_count": n,
        }

    # ------------------------------------------------------------------
    # Core benchmark
    # ------------------------------------------------------------------

    def run_benchmark(self, mission_path: str, duration: int = 60) -> dict:
        """
        Launch DCS with `mission_path`, collect PresentMon frame data for
        `duration` seconds, then return FPS and timing metrics.

        PresentMon requires Administrator privileges. If unavailable, the
        harness still runs but fps_stats will be None/0.
        """
        mission_name = os.path.basename(mission_path)
        print(f"--- Starting Benchmark: {mission_name} ---")

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(self.output_dir, f"presentmon_{ts}.csv")

        cmd = [self.dcs_path, "--mission", mission_path]
        start_time = time.time()
        dcs_proc = subprocess.Popen(cmd)

        pm_proc = None
        if self.presentmon_path:
            # Let DCS register with the OS before PresentMon attaches
            time.sleep(5)
            pm_proc = self._start_presentmon(csv_path)
            print(f"[harness] PresentMon capturing to {csv_path}")
        else:
            print(
                "[harness] WARNING: PresentMon not found — FPS metrics will be empty."
            )

        time.sleep(duration)

        if pm_proc is not None:
            self._stop_process(pm_proc)

        self._stop_process(dcs_proc)
        end_time = time.time()

        fps_stats = self._compute_fps_stats(self._parse_frametimes(csv_path))

        return {
            "mission": mission_path,
            "load_and_run_time": round(end_time - start_time, 2),
            "timestamp": datetime.now().isoformat(),
            "presentmon_csv": csv_path if pm_proc is not None else None,
            **fps_stats,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_results(self, data: dict, filename: str) -> None:
        with open(os.path.join(self.output_dir, filename), "w") as f:
            json.dump(data, f, indent=4)
