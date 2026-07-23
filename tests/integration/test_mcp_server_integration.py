"""Integration test for the ``oneo mcp`` server against a live Neo4j.

Mirrors ``tests/unit/test_mcp_server.py``'s in-memory ``Client``
pattern, but wires ``_ServerContext`` to a real ``Oneo`` coordinator
and a real, indexed corpus instead of a fake coordinator.
"""

from __future__ import annotations

import pytest

from oneo.answering import ExtractiveChatModel
from oneo.config import Settings
from oneo.corpus import Corpus, CorpusRegistry
from oneo.mcp_server import _ServerContext, build_server
from oneo.neo4j_store import Neo4jStore
from oneo.pipeline import Oneo

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "password"
NEO4J_DATABASE = "neo4j"


def _neo4j_available() -> bool:
    try:
        with Neo4jStore(
            uri=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            database=NEO4J_DATABASE,
        ) as store:
            return store.health().connected
    except Exception:
        return False


requires_neo4j = pytest.mark.skipif(
    not _neo4j_available(),
    reason="Neo4j is not reachable at bolt://localhost:7687; run `docker compose up -d`",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _make_corpus(root):
    (root / "topics").mkdir()
    (root / "overview.md").write_text(
        "---\ntitle: Overview\ntype: concept\n---\n\n"
        "# Overview\n\nInvoices are due net-30 after issue.\n"
    )


async def _call_tool(server, name, arguments):
    from mcp.shared.memory import create_connected_server_and_client_session

    async with create_connected_server_and_client_session(server) as session:
        return await session.call_tool(name, arguments)


@requires_neo4j
@pytest.mark.anyio
async def test_oneo_ask_delegates_to_real_coordinator(tmp_path):
    root = tmp_path
    _make_corpus(root)
    settings = Settings()
    registry = CorpusRegistry({"test": Corpus(name="test", root=str(root))}, "test")
    coordinator = Oneo(settings, registry=registry, chat_model=ExtractiveChatModel())

    try:
        coordinator.index(str(root), rebuild=True, embeddings=True)

        ctx = _ServerContext(coordinator=coordinator, registry=registry)
        server = build_server(ctx)

        result = await _call_tool(
            server,
            "oneo_ask",
            {"question": "When are invoices due?", "corpus": "test"},
        )

        assert result.structuredContent["corpus"] == "test"
        assert isinstance(result.structuredContent["citations"], list)
    finally:
        coordinator.reset()


@requires_neo4j
@pytest.mark.anyio
async def test_oneo_list_corpuses_delegates_to_real_registry(tmp_path):
    root = tmp_path
    _make_corpus(root)
    settings = Settings()
    registry = CorpusRegistry({"test": Corpus(name="test", root=str(root))}, "test")
    coordinator = Oneo(settings, registry=registry, chat_model=ExtractiveChatModel())

    ctx = _ServerContext(coordinator=coordinator, registry=registry)
    server = build_server(ctx)

    result = await _call_tool(server, "oneo_list_corpuses", {})

    assert result.structuredContent["result"] == [
        {"name": "test", "root": str(root), "exists": True}
    ]
