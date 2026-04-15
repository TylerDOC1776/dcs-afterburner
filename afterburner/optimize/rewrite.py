"""ZIP-level repack with safe transforms applied."""

from __future__ import annotations

import os
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from afterburner.optimize.safe_fixes import is_junk, normalize_path


@dataclass
class ChangeEntry:
    transform_id: str
    status: str  # "applied" | "skipped" | "unsafe"
    detail: str
    bytes_saved: int = field(default=0)


def repack_optimized(source: Path, dest: Path) -> list[ChangeEntry]:
    """
    Repack *source* .miz into *dest* with all safe transforms applied.

    Writes to a temp file then atomically renames to *dest* — if anything
    fails mid-write no partial file is left behind.  *dest* must not already
    exist when this function is called.
    """
    changes: list[ChangeEntry] = []

    with zipfile.ZipFile(source, "r") as src_zf:
        raw_entries = src_zf.infolist()
        kept: list[
            tuple[str, bytes, int]
        ] = []  # (arc_name, data, original_compress_size)

        for entry in raw_entries:
            if entry.filename.endswith("/"):
                continue  # directory entries — DCS doesn't use them

            name = entry.filename

            # SAFE_001: strip junk
            if is_junk(name):
                changes.append(
                    ChangeEntry(
                        transform_id="SAFE_001",
                        status="applied",
                        detail=f"Removed junk entry: {name}",
                        bytes_saved=entry.compress_size,
                    )
                )
                continue

            # SAFE_002: normalize path separators
            normalized = normalize_path(name)
            if normalized != name:
                changes.append(
                    ChangeEntry(
                        transform_id="SAFE_002",
                        status="applied",
                        detail=f"Normalized path: {name!r} → {normalized!r}",
                    )
                )

            kept.append((normalized, src_zf.read(entry.filename), entry.compress_size))

    # Ensure `mission` is first entry (DCS requirement)
    kept.sort(key=lambda t: (0 if t[0] == "mission" else 1, t[0]))

    # Write to a temp file in the same directory (ensures atomic rename works
    # across filesystems that require same-device moves)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path_str = tempfile.mkstemp(dir=dest.parent, suffix=".miz.tmp")
    tmp_path = Path(tmp_path_str)
    try:
        os.close(tmp_fd)
        with zipfile.ZipFile(
            tmp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as out_zf:
            for arc_name, data, _ in kept:
                out_zf.writestr(arc_name, data)

        bytes_before = source.stat().st_size
        bytes_after = tmp_path.stat().st_size
        saved = bytes_before - bytes_after

        # SAFE_003: report max-compression result
        if saved > 0:
            changes.append(
                ChangeEntry(
                    transform_id="SAFE_003",
                    status="applied",
                    detail="Repacked with maximum compression",
                    bytes_saved=saved,
                )
            )
        else:
            changes.append(
                ChangeEntry(
                    transform_id="SAFE_003",
                    status="skipped",
                    detail="Maximum compression did not reduce archive size",
                )
            )

        os.replace(tmp_path, dest)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    return changes
