"""Safe, zero-risk transform predicates for .miz archive entries."""

from __future__ import annotations

import fnmatch

# Entries matching any of these patterns are junk — safe to remove
_JUNK_PATTERNS = (
    "__MACOSX/*",
    ".DS_Store",
    "*/.DS_Store",
    "Thumbs.db",
    "*/Thumbs.db",
    "desktop.ini",
    "*/desktop.ini",
    "~*.tmp",
    "*~*.tmp",
    "*.bak",
)


def is_junk(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in _JUNK_PATTERNS)


def normalize_path(name: str) -> str:
    """Normalize backslash separators to forward slashes."""
    return name.replace("\\", "/")
