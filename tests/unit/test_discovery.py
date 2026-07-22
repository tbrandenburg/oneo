from __future__ import annotations

from oneo.discovery import discover_files
from oneo.security import PathSecurityError

import pytest


def _make_corpus(root):
    (root / "topics").mkdir()
    (root / ".git").mkdir()
    (root / "overview.md").write_text("# Overview\n")
    (root / "topics" / "example.markdown").write_text("# Example\n")
    (root / "topics" / "notes.txt").write_text("not markdown\n")
    (root / ".git" / "excluded.md").write_text("excluded\n")


def test_discovers_only_supported_markdown_files(tmp_path):
    _make_corpus(tmp_path)

    discovered = discover_files(
        input_path=str(tmp_path),
        knowledge_root=str(tmp_path),
        exclude_patterns=(".git",),
    )

    assert discovered == ["overview.md", "topics/example.markdown"]


def test_discovery_is_deterministic(tmp_path):
    _make_corpus(tmp_path)

    first = discover_files(input_path=str(tmp_path), knowledge_root=str(tmp_path))
    second = discover_files(input_path=str(tmp_path), knowledge_root=str(tmp_path))

    assert first == second
    assert first == sorted(first)


def test_missing_directory_returns_empty_list(tmp_path):
    discovered = discover_files(
        input_path=str(tmp_path / "missing"), knowledge_root=str(tmp_path)
    )

    assert discovered == []


def test_rejects_parent_traversal(tmp_path):
    _make_corpus(tmp_path)

    with pytest.raises(PathSecurityError):
        discover_files(input_path=str(tmp_path.parent), knowledge_root=str(tmp_path))
