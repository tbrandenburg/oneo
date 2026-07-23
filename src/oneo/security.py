"""Filesystem boundary enforcement for Oneo.

All ingest paths must be validated against a configured corpus root
before they are opened, listed, or parsed. This module isolates that
security-sensitive normalization and containment logic.
"""

from __future__ import annotations

from pathlib import Path


class PathSecurityError(ValueError):
    """Raised when a requested path violates the corpus-root boundary."""


def _looks_like_remote_url(raw_path: str) -> bool:
    """Return True if ``raw_path`` looks like a remote URL rather than a
    local filesystem path."""

    return "://" in raw_path


def resolve_within_root(raw_path: str, corpus_root: str) -> Path:
    """Resolve ``raw_path`` and verify it stays inside ``corpus_root``.

    Args:
        raw_path: The user-supplied path, relative (to the current
            working directory) or absolute.
        corpus_root: The configured canonical root directory.

    Returns:
        The resolved, absolute path, guaranteed to be inside
        ``corpus_root``.

    Raises:
        PathSecurityError: If ``raw_path`` is a remote URL, escapes the
            corpus root via parent traversal, or is an unrelated
            absolute path outside the corpus root.
    """

    if _looks_like_remote_url(raw_path):
        raise PathSecurityError(f"remote URLs are not allowed: {raw_path!r}")

    root = Path(corpus_root).expanduser().resolve()
    candidate = Path(raw_path).expanduser()
    resolved = candidate.resolve()

    if resolved != root and root not in resolved.parents:
        raise PathSecurityError(
            f"path {raw_path!r} resolves outside the corpus root "
            f"{corpus_root!r}"
        )

    return resolved
