"""Unit tests for ``Neo4jStore._run_scoped``'s corpus guard.

These tests require no live Neo4j instance: they construct a
``Neo4jStore`` without calling ``__init__`` (avoiding a real driver
connection) and stub out ``_run`` to detect whether a query would have
been executed.
"""

from __future__ import annotations

import pytest

from oneo.neo4j_store import Neo4jStore


def _store_with_stub_run() -> tuple[Neo4jStore, list[object]]:
    store = Neo4jStore.__new__(Neo4jStore)
    calls: list[object] = []

    def _stub_run(query: str, **parameters: object) -> object:
        calls.append((query, parameters))
        return []

    store._run = _stub_run  # type: ignore[method-assign]
    return store, calls


def test_run_scoped_raises_for_empty_corpus():
    store, calls = _store_with_stub_run()

    with pytest.raises(ValueError, match="corpus is required"):
        store._run_scoped("RETURN 1", corpus="")

    assert calls == []


def test_run_scoped_raises_for_none_corpus():
    store, calls = _store_with_stub_run()

    with pytest.raises(ValueError, match="corpus is required"):
        store._run_scoped("RETURN 1", corpus=None)  # type: ignore[arg-type]

    assert calls == []


def test_run_scoped_runs_query_for_valid_corpus():
    store, calls = _store_with_stub_run()

    store._run_scoped("RETURN 1", corpus="test-corpus", owner="oneo")

    assert calls == [("RETURN 1", {"corpus": "test-corpus", "owner": "oneo"})]
