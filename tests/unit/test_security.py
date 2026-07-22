from __future__ import annotations

import pytest

from oneo.security import PathSecurityError, resolve_within_root


def test_resolves_relative_path_inside_root(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    monkeypatch.chdir(tmp_path)

    resolved = resolve_within_root("docs", str(tmp_path))

    assert resolved == (tmp_path / "docs").resolve()


def test_resolves_absolute_path_inside_root(tmp_path):
    nested = tmp_path / "docs"
    nested.mkdir()

    resolved = resolve_within_root(str(nested), str(tmp_path))

    assert resolved == nested.resolve()


def test_rejects_parent_traversal_outside_root(tmp_path):
    with pytest.raises(PathSecurityError):
        resolve_within_root("../outside", str(tmp_path))


def test_rejects_unrelated_absolute_path(tmp_path, tmp_path_factory):
    other_root = tmp_path_factory.mktemp("other")

    with pytest.raises(PathSecurityError):
        resolve_within_root(str(other_root), str(tmp_path))


def test_rejects_remote_urls(tmp_path):
    with pytest.raises(PathSecurityError):
        resolve_within_root("https://example.com/doc.md", str(tmp_path))
