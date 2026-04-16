"""Optimization orchestrator: backup, transform, report."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from afterburner.optimize.rewrite import ChangeEntry, repack_optimized


@dataclass
class OptimizeResult:
    source: Path
    output: Path
    backup: Path
    changes: list[ChangeEntry] = field(default_factory=list)
    bytes_before: int = 0
    bytes_after: int = 0

    @property
    def bytes_saved(self) -> int:
        return self.bytes_before - self.bytes_after

    @property
    def pct_saved(self) -> float:
        if self.bytes_before == 0:
            return 0.0
        return self.bytes_saved / self.bytes_before


def run_safe_optimizations(
    miz_path: Path,
    output: Path | None = None,
) -> OptimizeResult:
    """
    Apply all safe, zero-risk optimizations to *miz_path*.

    *output* defaults to ``<stem>.optimized.miz`` in the same directory.
    Refuses to overwrite *miz_path* — caller must pass a different path.

    Always writes a ``.bak`` copy of the original before producing output.
    """
    miz_path = miz_path.resolve()

    if output is None:
        output = miz_path.with_name(miz_path.stem + ".optimized.miz")
    else:
        output = output.resolve()

    if output == miz_path:
        raise ValueError(
            f"Output path is the same as input: {miz_path}. "
            "Use a different --output path."
        )

    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")

    # Create backup before touching anything
    backup = miz_path.with_suffix(".miz.bak")
    if backup.exists():
        raise FileExistsError(
            f"Backup already exists: {backup}. Remove it before optimizing again."
        )
    shutil.copy2(miz_path, backup)

    bytes_before = miz_path.stat().st_size

    try:
        changes = repack_optimized(miz_path, output)
    except Exception:
        # If optimization fails, remove the half-written output if it exists
        output.unlink(missing_ok=True)
        raise

    bytes_after = output.stat().st_size

    return OptimizeResult(
        source=miz_path,
        output=output,
        backup=backup,
        changes=changes,
        bytes_before=bytes_before,
        bytes_after=bytes_after,
    )
