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
    """Read-only lookup of configured corpuses.

    Exposes only :meth:`names`, :meth:`get`, and :meth:`default_name`.
    """

    def __init__(self, corpuses: dict[str, Corpus], default_name: str | None) -> None:
        self._corpuses = corpuses
        self._default_name = default_name

    @classmethod
    def load(cls, config_path: str, default_name: str | None = None) -> "CorpusRegistry":
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
