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


def test_initialize_creates_empty_valid_registry(tmp_path):
    config_path = tmp_path / "config" / "corpuses.toml"

    CorpusRegistry.initialize(str(config_path))

    assert config_path.read_text() == "[corpuses]\n"
    with pytest.raises(CorpusConfigError, match="no corpuses"):
        CorpusRegistry.load(str(config_path))


def test_initialize_never_overwrites_existing_registry(tmp_path):
    config_path = tmp_path / "corpuses.toml"
    original = '[corpuses.billing]\nroot = "/billing"\n'
    config_path.write_text(original)

    with pytest.raises(CorpusConfigError, match="already exists"):
        CorpusRegistry.initialize(str(config_path))

    assert config_path.read_text() == original


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


def test_register_adds_first_canonical_root_after_initialization(tmp_path):
    root = tmp_path / "billing"
    root.mkdir()
    config_path = tmp_path / "config" / "corpuses.toml"
    CorpusRegistry.initialize(str(config_path))

    corpus = CorpusRegistry.register(str(config_path), "billing", str(root))

    assert corpus == Corpus(name="billing", root=str(root.resolve()))
    assert CorpusRegistry.load(str(config_path)).names() == ["billing"]


def test_register_adds_canonical_root_without_changing_existing_entries(tmp_path):
    billing_root = tmp_path / "billing"
    billing_root.mkdir()
    engineering_root = tmp_path / "engineering"
    engineering_root.mkdir()
    config_path = _write_config(
        tmp_path,
        f'title = "My registry"\n\n[corpuses.billing]\nroot = "{billing_root}"\n',
    )

    corpus = CorpusRegistry.register(config_path, "engineering", str(engineering_root))

    assert corpus == Corpus(name="engineering", root=str(engineering_root.resolve()))
    assert CorpusRegistry.load(config_path).names() == ["billing", "engineering"]
    content = (tmp_path / "corpuses.toml").read_text()
    assert (
        f'title = "My registry"\n\n[corpuses.billing]\nroot = "{billing_root}"\n'
        in content
    )
    assert f'root = "{engineering_root.resolve()}"' in content


def test_register_rejects_missing_registry_duplicate_name_and_invalid_root(tmp_path):
    root = tmp_path / "billing"
    root.mkdir()
    missing_path = str(tmp_path / "missing.toml")

    with pytest.raises(CorpusConfigError, match="Run 'oneo init'"):
        CorpusRegistry.register(missing_path, "billing", str(root))

    config_path = _write_config(tmp_path, f'[corpuses.billing]\nroot = "{root}"\n')
    original = (tmp_path / "corpuses.toml").read_text()

    with pytest.raises(CorpusConfigError, match="duplicate corpus name"):
        CorpusRegistry.register(config_path, "billing", str(root))
    with pytest.raises(CorpusConfigError, match="not an existing directory"):
        CorpusRegistry.register(config_path, "engineering", str(tmp_path / "missing"))

    assert (tmp_path / "corpuses.toml").read_text() == original


def test_register_rejects_invalid_name(tmp_path):
    root = tmp_path / "billing"
    root.mkdir()
    config_path = _write_config(tmp_path, f'[corpuses.billing]\nroot = "{root}"\n')

    with pytest.raises(CorpusConfigError, match="invalid corpus name"):
        CorpusRegistry.register(config_path, "Bad Name", str(root))


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
