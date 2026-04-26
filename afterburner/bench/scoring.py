"""
Mission performance scorer.

Accepts the dict returned by DCSBenchmarkHarness.run_benchmark() or the
'summary' sub-dict returned by aggregate_passes().
"""

import statistics
from typing import Optional

# All numeric keys emitted by DCSBenchmarkHarness.run_benchmark()
_NUMERIC_KEYS = (
    "avg_fps",
    "low_1pct_fps",
    "low_01pct_fps",
    "avg_frametime_ms",
    "frametime_stdev_ms",
    "load_and_run_time",
    "sample_count",
)


class MissionScorer:
    def __init__(self):
        # Weights from the mission validation issue
        self.weights = {
            "frametime_stability": 0.35,
            "fps_avg": 0.20,
            "fps_1_low": 0.20,
            "load_time": 0.10,
            "resource_efficiency": 0.10,
            "stability": 0.05,
        }

    # ------------------------------------------------------------------
    # Multi-pass aggregation
    # ------------------------------------------------------------------

    def aggregate_passes(self, results: list[dict]) -> dict:
        """
        Collapse 3–5 run_benchmark() dicts into a single stats dict.

        Returns:
            per_metric  — mean / median / stdev for each numeric field
            summary     — flat dict of mean values; pass directly to calculate_score()
            confidence  — "HIGH" / "MEDIUM" / "LOW" based on pass count and spread
        """
        if not results:
            raise ValueError("aggregate_passes requires at least one result")

        per_metric: dict[str, dict] = {}
        for key in _NUMERIC_KEYS:
            values = [r[key] for r in results if r.get(key) is not None]
            n = len(values)
            if not values:
                per_metric[key] = {
                    "mean": None,
                    "median": None,
                    "stdev": None,
                    "passes": 0,
                }
                continue
            per_metric[key] = {
                "mean": round(statistics.mean(values), 3),
                "median": round(statistics.median(values), 3),
                "stdev": round(statistics.stdev(values) if n > 1 else 0.0, 3),
                "passes": n,
            }

        # Flat summary uses mean values so calculate_score() can accept it directly
        summary: dict = {k: per_metric[k]["mean"] for k in _NUMERIC_KEYS}
        summary["mission"] = results[0].get("mission", "")
        summary["pass_count"] = len(results)

        return {
            "per_metric": per_metric,
            "summary": summary,
            "confidence": self._confidence_rating(
                pass_count=len(results),
                per_metric=per_metric,
            ),
        }

    def _confidence_rating(self, pass_count: int, per_metric: dict) -> str:
        """
        HIGH   — 5+ passes, avg_fps CV < 5 %
        MEDIUM — 3+ passes, avg_fps CV < 10 %
        LOW    — otherwise
        """
        fps_stats = per_metric.get("avg_fps", {})
        mean = fps_stats.get("mean") or 0
        stdev = fps_stats.get("stdev") or 0
        cv = (stdev / mean * 100) if mean > 0 else 100

        if pass_count >= 5 and cv < 5:
            return "HIGH"
        if pass_count >= 3 and cv < 10:
            return "MEDIUM"
        return "LOW"

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def calculate_score(self, metrics: dict) -> dict:
        """
        Calculate a 0–100 score from a single run_benchmark() result or an
        aggregate_passes()['summary'] dict.

        Key alignment with harness output:
          avg_fps           → fps component
          low_1pct_fps      → 1% low component
          frametime_stdev_ms → stability component
          load_time_s        → load component (optional; harness does not yet
                               emit this separately — scored neutrally until added)
        """
        # --- Frametime stability (lower stdev = better) ---
        # DCS realistic range:
        #   < 2 ms  → buttery smooth
        #   5–8 ms  → noticeable micro-stutter
        #   >= 20ms → unplayable (heavy dynamic war missions)
        # Linear scale: 0 ms → 100, 20 ms → 0
        stdev_ms = metrics.get("frametime_stdev_ms") or 20.0
        stability_score = max(0.0, 100.0 - (stdev_ms / 20.0 * 100.0))

        # --- Average FPS (60 fps target = 100%) ---
        avg_fps = metrics.get("avg_fps") or 0.0
        fps_score = min(100.0, (avg_fps / 60.0) * 100.0)

        # --- 1% Low FPS (45 fps target = 100%) ---
        low_fps = metrics.get("low_1pct_fps") or 0.0
        low_score = min(100.0, (low_fps / 45.0) * 100.0)

        # --- Load time ---
        # load_time_s is a future dedicated field (pure mission-load duration).
        # load_and_run_time is the full benchmark window and is NOT scored here
        # because it includes the fixed benchmark sleep duration.
        # DCS cold loads range from ~60 s (small SP) to ~300 s (large MP maps).
        # Scale: <= 60 s → 100, 300 s → 0
        load_time_s: Optional[float] = metrics.get("load_time_s")
        if load_time_s is not None:
            load_score = max(0.0, 100.0 - ((load_time_s - 60.0) / 2.4))
        else:
            load_score = 100.0  # neutral placeholder until harness emits load_time_s

        # --- Weighted final ---
        final_score = (
            stability_score * self.weights["frametime_stability"]
            + fps_score * self.weights["fps_avg"]
            + low_score * self.weights["fps_1_low"]
            + load_score * self.weights["load_time"]
            + 90.0
            * self.weights["resource_efficiency"]  # placeholder: no CPU/GPU hooks yet
            + 100.0 * self.weights["stability"]  # assume stable if no crash
        )

        return {
            "score": round(final_score, 2),
            "band": self.get_score_band(final_score),
            "breakdown": {
                "stability": round(stability_score, 1),
                "fps": round(fps_score, 1),
                "1_percent_low": round(low_score, 1),
                "load": round(load_score, 1),
            },
        }

    def score_aggregated(self, aggregate: dict) -> dict:
        """Convenience wrapper: score the mean values from aggregate_passes()."""
        result = self.calculate_score(aggregate["summary"])
        result["confidence"] = aggregate["confidence"]
        result["pass_count"] = aggregate["summary"].get("pass_count", 0)
        return result

    # ------------------------------------------------------------------
    # Band classification
    # ------------------------------------------------------------------

    def get_score_band(self, score: float) -> str:
        """Consistent with report.py risk_label() thresholds."""
        if score >= 92:
            return "LOW RISK"
        if score >= 75:
            return "MODERATE"
        if score >= 50:
            return "HIGH"
        return "CRITICAL"
