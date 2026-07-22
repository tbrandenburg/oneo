"""Filesystem boundary enforcement for Oneo.

All ingest paths must be validated against a configured knowledge root
before they are opened, listed, or parsed. This module isolates that
security-sensitive normalization and containment logic.
"""

from __future__ import annotations

from pathlib import Path


class PathSecurityError(ValueError):
    """Raised when a requested path violates the knowledge-root boundary."""


def _looks_like_remote_url(raw_path: str) -> bool:
    """Return True if ``raw_path`` looks like a remote URL rather than a
    local filesystem path."""

    return "://" in raw_path


def resolve_within_root(raw_path: str, knowledge_root: str) -> Path:
    """Resolve ``raw_path`` and verify it stays inside ``knowledge_root``.

    Args:
        raw_path: The user-supplied path, relative (to the current
            working directory) or absolute.
        knowledge_root: The configured canonical root directory.

    Returns:
        The resolved, absolute path, guaranteed to be inside
        ``knowledge_root``.

    Raises:
        PathSecurityError: If ``raw_path`` is a remote URL, escapes the
            knowledge root via parent traversal, or is an unrelated
            absolute path outside the knowledge root.
    """

    if _looks_like_remote_url(raw_path):
        raise PathSecurityError(f"remote URLs are not allowed: {raw_path!r}")

    root = Path(knowledge_root).expanduser().resolve()
    candidate = Path(raw_path).expanduser()
    resolved = candidate.resolve()

    if resolved != root and root not in resolved.parents:
        raise PathSecurityError(
            f"path {raw_path!r} resolves outside the knowledge root "
            f"{knowledge_root!r}"
        )

    return resolved
