"""
Utility for opening, modifying, and repacking DCS .miz files.

A .miz is a ZIP archive using DEFLATE compression. Rules DCS requires:
  - No directory entries (files only, paths with / separators are fine)
  - DEFLATE compression (compress_type=8) on all entries
  - `mission` file must be the first entry
  - Never overwrite the original
"""

import shutil
import tempfile
import zipfile
from pathlib import Path


def extract(miz_path: str | Path, dest_dir: str | Path | None = None) -> Path:
    """
    Extract a .miz to a directory.

    If dest_dir is None, creates a temp directory (caller must clean up).
    Returns the path to the extraction directory.
    """
    miz_path = Path(miz_path)
    if dest_dir is None:
        dest = Path(tempfile.mkdtemp(prefix="miz_"))
    else:
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(miz_path, "r") as zf:
        for entry in zf.infolist():
            # Skip any directory entries (shouldn't exist but be safe)
            if entry.filename.endswith("/"):
                continue
            out_path = dest / entry.filename
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(zf.read(entry.filename))

    return dest


def repack(
    source_dir: str | Path,
    output_miz: str | Path,
    original_miz: str | Path | None = None,
) -> Path:
    """
    Repack a directory into a .miz file.

    source_dir    -- directory containing the unpacked mission files
    output_miz    -- path for the new .miz (must not be the original)
    original_miz  -- if provided, preserves the original file order for any
                     files that exist in both; new/modified files append after

    Returns the output path.
    """
    source_dir = Path(source_dir)
    output_miz = Path(output_miz)

    if output_miz.exists():
        raise FileExistsError(f"Output already exists: {output_miz}")

    # Collect all files relative to source_dir
    all_files = sorted(
        p.relative_to(source_dir).as_posix()
        for p in source_dir.rglob("*")
        if p.is_file()
    )

    # Build ordered list: `mission` first, then follow original order if given,
    # then anything remaining
    ordered = _build_order(all_files, original_miz)

    with zipfile.ZipFile(output_miz, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel_path in ordered:
            abs_path = source_dir / rel_path
            if abs_path.exists():
                zf.write(abs_path, arcname=rel_path)

    return output_miz


def _build_order(files: list[str], original_miz: str | Path | None) -> list[str]:
    remaining = set(files)
    ordered = []

    # mission always goes first
    if "mission" in remaining:
        ordered.append("mission")
        remaining.discard("mission")

    # follow original order for anything else
    if original_miz is not None:
        with zipfile.ZipFile(original_miz, "r") as zf:
            for entry in zf.infolist():
                name = entry.filename
                if name in remaining:
                    ordered.append(name)
                    remaining.discard(name)

    # append anything new (not in original)
    ordered.extend(sorted(remaining))
    return ordered


def edit_miz(miz_path: str | Path, output_miz: str | Path) -> Path:
    """
    Context manager-style helper: extracts to temp dir, returns it.
    Caller modifies files, then calls repack manually. For simple scripts
    prefer using extract() + repack() directly.

    Example:
        work_dir = extract("mission.miz")
        # edit files in work_dir
        repack(work_dir, "mission_v2.miz", original_miz="mission.miz")
        shutil.rmtree(work_dir)
    """
    return extract(miz_path)


class MizEditor:
    """
    Context manager that extracts on enter and repacks on exit.

    Usage:
        with MizEditor("Vietguam3C.miz", "Vietguam3C_edited.miz") as work_dir:
            lua_file = work_dir / "l10n/DEFAULT/CSARVG2.lua"
            text = lua_file.read_text(encoding="utf-8")
            lua_file.write_text(text.replace("old", "new"), encoding="utf-8")
    """

    def __init__(self, source_miz: str | Path, output_miz: str | Path):
        self.source_miz = Path(source_miz)
        self.output_miz = Path(output_miz)
        self._work_dir: Path | None = None

    def __enter__(self) -> Path:
        self._work_dir = extract(self.source_miz)
        return self._work_dir

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and self._work_dir is not None:
            repack(self._work_dir, self.output_miz, original_miz=self.source_miz)
        if self._work_dir is not None:
            shutil.rmtree(self._work_dir, ignore_errors=True)
        return False  # don't suppress exceptions
