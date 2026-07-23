"""Unit tests for :mod:`oneo.corpus`."""

from __future__ import annotations

import pytest

from oneo.corpus import Corpus, CorpusConfigError, CorpusRegistry


def _write_config(tmp_path, text: str):
    config_path = tmp_path / "corpuses.toml"
    config_path.write_text(text)
    return str(config_path)


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(CorpusConfigError, match="not found"):
        CorpusRegistry.load(str(tmp_path / "missing.toml"))


def test_load_empty_config_raises(tmp_path):
    config_path = _write_config(tmp_path, "")

    with pytest.raises(CorpusConfigError, match="no corpuses"):
        CorpusRegistry.load(config_path)


def test_load_returns_registered_corpuses(tmp_path):
    config_path = _write_config(
        tmp_path,
        """
        [corpuses.billing]
        root = "./corpuses/billing"

        [corpuses.engineering]
        root = "./corpuses/engineering"
        """,
    )

    registry = CorpusRegistry.load(config_path)

    assert registry.names() == ["billing", "engineering"]
    assert registry.get("billing") == Corpus(name="billing", root="./corpuses/billing")
    assert registry.get("engineering") == Corpus(
        name="engineering", root="./corpuses/engineering"
    )


def test_get_unknown_name_raises(tmp_path):
    config_path = _write_config(
        tmp_path, '[corpuses.billing]\nroot = "./corpuses/billing"\n'
    )
    registry = CorpusRegistry.load(config_path)

    with pytest.raises(CorpusConfigError, match="unknown corpus"):
        registry.get("nonexistent")


def test_invalid_corpus_name_raises(tmp_path):
    config_path = _write_config(
        tmp_path, '[corpuses."Bad Name"]\nroot = "./corpuses/bad"\n'
    )

    with pytest.raises(CorpusConfigError, match="invalid corpus name"):
        CorpusRegistry.load(config_path)


def test_empty_root_raises(tmp_path):
    config_path = _write_config(tmp_path, '[corpuses.billing]\nroot = ""\n')

    with pytest.raises(CorpusConfigError, match="no non-empty 'root'"):
        CorpusRegistry.load(config_path)


def test_default_name_resolves(tmp_path):
    config_path = _write_config(
        tmp_path, '[corpuses.billing]\nroot = "./corpuses/billing"\n'
    )
    registry = CorpusRegistry.load(config_path, default_name="billing")

    assert registry.default_name() == "billing"


def test_default_name_missing_raises(tmp_path):
    config_path = _write_config(
        tmp_path, '[corpuses.billing]\nroot = "./corpuses/billing"\n'
    )
    registry = CorpusRegistry.load(config_path)

    with pytest.raises(CorpusConfigError, match="no default corpus configured"):
        registry.default_name()


def test_default_name_unregistered_raises(tmp_path):
    config_path = _write_config(
        tmp_path, '[corpuses.billing]\nroot = "./corpuses/billing"\n'
    )
    registry = CorpusRegistry.load(config_path, default_name="unknown")

    with pytest.raises(CorpusConfigError, match="not registered"):
        registry.default_name()
