"""Supported-file discovery for OKF repositories.

Discovery is restricted to ``.md`` and ``.markdown`` files, applies
exclusion patterns, and returns deterministic, normalized, root-relative
source paths. Path-security validation is delegated to
:mod:`oneo.security`.
"""

from __future__ import annotations

from collections.abc import Sequence
from fnmatch import fnmatch
from pathlib import Path

from oneo.security import resolve_within_root

SUPPORTED_SUFFIXES = (".md", ".markdown")


def _is_excluded(relative_path: Path, exclude_patterns: Sequence[str]) -> bool:
    """Return True if any path segment or the full relative path matches an
    exclusion pattern."""

    parts = relative_path.parts
    return any(
        fnmatch(part, pattern) or fnmatch(str(relative_path), pattern)
        for pattern in exclude_patterns
        for part in parts
    )


def discover_files(
    input_path: str,
    knowledge_root: str,
    exclude_patterns: Sequence[str] = (),
) -> list[str]:
    """Recursively discover supported OKF source files.

    Args:
        input_path: Directory to scan, relative to or inside
            ``knowledge_root``.
        knowledge_root: The configured canonical root directory.
        exclude_patterns: Glob patterns; matching path segments are
            excluded.

    Returns:
        A sorted list of root-relative, normalized POSIX-style source
        paths for every discovered ``.md``/``.markdown`` file.

    Raises:
        oneo.security.PathSecurityError: If ``input_path`` violates the
            knowledge-root boundary.
    """

    root = Path(knowledge_root).expanduser().resolve()
    scan_root = resolve_within_root(input_path, knowledge_root)

    if not scan_root.exists():
        return []

    discovered: list[str] = []
    for candidate in scan_root.rglob("*"):
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue

        relative = candidate.relative_to(root)
        if _is_excluded(relative, exclude_patterns):
            continue

        discovered.append(relative.as_posix())

    return sorted(discovered)
