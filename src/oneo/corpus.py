"""Corpus registry: configuration-only mapping of named OKF bundles to
their filesystem roots.

The registry is a small, read-only object loaded once from a required
TOML file (``corpuses.toml`` by default, overridable via
``ONEO_CORPUS_CONFIG``). It holds no connections and performs no I/O
beyond reading that one file. It must not grow connection handling,
indexing state, or per-corpus runtime objects -- see
``doc/plan/plan.md`` §9.
"""

from __future__ import annotations

import re
import json
import os
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class CorpusConfigError(ValueError):
    """Raised when ``corpuses.toml`` is missing, empty, or invalid."""


@dataclass(frozen=True)
class Corpus:
    """A single named OKF bundle and its filesystem root."""

    name: str
    root: str


class CorpusRegistry:
    """Lookup and explicit maintenance of configured corpuses."""

    def __init__(self, corpuses: dict[str, Corpus], default_name: str | None) -> None:
        self._corpuses = corpuses
        self._default_name = default_name

    @classmethod
    def initialize(cls, config_path: str) -> None:
        """Create an empty registry without overwriting an existing file."""

        cls._create_file(Path(config_path), "[corpuses]\n")

    @classmethod
    def register(cls, config_path: str, name: str, root: str) -> Corpus:
        """Atomically add a corpus with a canonical existing directory root."""

        cls._validate_name(name)
        canonical_root = cls._canonical_root(root)
        path = Path(config_path)
        if not path.is_file():
            raise CorpusConfigError(
                f"corpus configuration file not found: {config_path!r}. "
                "Run 'oneo init' before adding a corpus."
            )
        content = path.read_text()
        try:
            raw = tomllib.loads(content)
        except tomllib.TOMLDecodeError as exc:
            raise CorpusConfigError(
                f"failed to parse corpus configuration {config_path!r}: {exc}"
            ) from exc
        raw_corpuses = raw.get("corpuses")
        if not isinstance(raw_corpuses, dict):
            raise CorpusConfigError(
                f"corpus configuration {config_path!r} defines no corpuses. "
                "Run 'oneo init' before adding a corpus."
            )
        if raw_corpuses:
            registry = cls.load(config_path)
            if name in registry._corpuses:
                raise CorpusConfigError(f"duplicate corpus name: {name!r}")

        separator = "" if content.endswith("\n\n") else "\n"
        if not content.endswith("\n"):
            separator = "\n\n"
        updated = (
            f"{content}{separator}[corpuses.{name}]\n"
            f"root = {json.dumps(canonical_root)}\n"
        )
        cls._replace_file(path, updated)
        return Corpus(name=name, root=canonical_root)

    @classmethod
    def load(
        cls, config_path: str, default_name: str | None = None
    ) -> "CorpusRegistry":
        """Load and validate the corpus registry from ``config_path``.

        Args:
            config_path: Path to the ``corpuses.toml`` file.
            default_name: Optional configured default corpus name
                (``ONEO_DEFAULT_CORPUS``).

        Raises:
            CorpusConfigError: If the file is missing, empty, defines no
                corpuses, has an invalid corpus name, an empty root, or
                a duplicate corpus name.
        """

        path = Path(config_path)
        if not path.is_file():
            raise CorpusConfigError(
                f"corpus configuration file not found: {config_path!r}. "
                "At least one corpus must be defined in corpuses.toml "
                "(see corpuses.toml.example); there is no corpus_root "
                "fallback."
            )

        try:
            raw = tomllib.loads(path.read_text())
        except tomllib.TOMLDecodeError as exc:
            raise CorpusConfigError(
                f"failed to parse corpus configuration {config_path!r}: {exc}"
            ) from exc

        raw_corpuses = raw.get("corpuses")
        if not raw_corpuses or not isinstance(raw_corpuses, dict):
            raise CorpusConfigError(
                f"corpus configuration {config_path!r} defines no corpuses. "
                "At least one [corpuses.<name>] table with a 'root' is required."
            )

        corpuses: dict[str, Corpus] = {}
        for name, table in raw_corpuses.items():
            if not _NAME_PATTERN.match(name):
                raise CorpusConfigError(
                    f"invalid corpus name {name!r}: names must match "
                    f"{_NAME_PATTERN.pattern!r}"
                )
            if name in corpuses:
                raise CorpusConfigError(f"duplicate corpus name: {name!r}")

            root = table.get("root") if isinstance(table, dict) else None
            if not root or not isinstance(root, str):
                raise CorpusConfigError(
                    f"corpus {name!r} has no non-empty 'root' configured"
                )

            corpuses[name] = Corpus(name=name, root=root)

        return cls(corpuses, default_name)

    @staticmethod
    def _validate_name(name: str) -> None:
        if not _NAME_PATTERN.match(name):
            raise CorpusConfigError(
                f"invalid corpus name {name!r}: names must match "
                f"{_NAME_PATTERN.pattern!r}"
            )

    @staticmethod
    def _canonical_root(root: str) -> str:
        path = Path(root).expanduser().resolve()
        if not path.is_dir():
            raise CorpusConfigError(
                f"corpus root {root!r} is not an existing directory"
            )
        return str(path)

    @staticmethod
    def _create_file(path: Path, content: str) -> None:
        """Atomically publish a new file while refusing to replace one."""

        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() or path.is_symlink():
            raise CorpusConfigError(
                f"corpus configuration file already exists: {str(path)!r}; "
                "refusing to overwrite it"
            )
        descriptor, temporary_path = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", text=True
        )
        try:
            with os.fdopen(descriptor, "w") as temporary_file:
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            try:
                os.link(temporary_path, path)
            except FileExistsError as exc:
                raise CorpusConfigError(
                    f"corpus configuration file already exists: {str(path)!r}; "
                    "refusing to overwrite it"
                ) from exc
        finally:
            Path(temporary_path).unlink(missing_ok=True)

    @staticmethod
    def _replace_file(path: Path, content: str) -> None:
        """Atomically replace ``path`` with fully written registry content."""

        descriptor, temporary_path = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", text=True
        )
        try:
            with os.fdopen(descriptor, "w") as temporary_file:
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, path)
        finally:
            Path(temporary_path).unlink(missing_ok=True)

    def names(self) -> list[str]:
        """Return every configured corpus name, sorted for determinism."""

        return sorted(self._corpuses)

    def get(self, name: str) -> Corpus:
        """Return the configured corpus named ``name``.

        Raises:
            CorpusConfigError: If no corpus is registered under ``name``.
        """

        try:
            return self._corpuses[name]
        except KeyError as exc:
            raise CorpusConfigError(
                f"unknown corpus {name!r}. Configured corpuses: {self.names()}"
            ) from exc

    def default_name(self) -> str:
        """Return the configured default corpus name.

        Raises:
            CorpusConfigError: If no default is configured, or the
                configured default does not match a registered corpus.
        """

        if self._default_name is None:
            raise CorpusConfigError(
                "no default corpus configured (set ONEO_DEFAULT_CORPUS); "
                "an explicit corpus name is required"
            )
        if self._default_name not in self._corpuses:
            raise CorpusConfigError(
                f"configured default corpus {self._default_name!r} is not "
                f"registered. Configured corpuses: {self.names()}"
            )
        return self._default_name
