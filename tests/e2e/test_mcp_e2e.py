"""End-to-end proof that the MCP agent interface (``oneo mcp``) answers
real questions against a real, self-contained corpus.

Uses the in-memory ``create_connected_server_and_client_session`` MCP
transport (the same pattern already used by
``tests/unit/test_mcp_server.py`` and
``tests/integration/test_mcp_server_integration.py``; the installed
``mcp`` SDK version in this repo does not expose ``mcp.Client``) so no
subprocess or network port is ever opened. The test indexes and removes
only its own corpus in real Neo4j; it does not load operator corpus
configuration or depend on demo data.
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


async def _call_tool(server, name, arguments):
    from mcp.shared.memory import create_connected_server_and_client_session

    async with create_connected_server_and_client_session(server) as session:
        return await session.call_tool(name, arguments)


def _write_corpus(root) -> None:
    root.mkdir()
    (root / "billing.md").write_text(
        "---\ntitle: Billing\ntype: concept\n---\n\n"
        "# Billing\n\nCustomers are billed monthly after invoices are issued.\n"
    )


@requires_neo4j
@pytest.mark.anyio
async def test_mcp_agent_interface_against_real_self_contained_corpus(tmp_path):
    corpus_name = "mcp-e2e"
    root = tmp_path / corpus_name
    _write_corpus(root)
    settings = Settings(
        corpus_config=str(tmp_path / "corpuses.toml"),
        default_corpus=corpus_name,
        neo4j_uri=NEO4J_URI,
        neo4j_username=NEO4J_USERNAME,
        neo4j_password=NEO4J_PASSWORD,
        neo4j_database=NEO4J_DATABASE,
    )
    registry = CorpusRegistry(
        {corpus_name: Corpus(name=corpus_name, root=str(root))}, corpus_name
    )
    coordinator = Oneo(settings, registry=registry, chat_model=ExtractiveChatModel())

    try:
        coordinator.index(str(root), rebuild=True, embeddings=True, corpus=corpus_name)
        ctx = _ServerContext(coordinator=coordinator, registry=registry)
        server = build_server(ctx)

        corpuses_result = await _call_tool(server, "oneo_list_corpuses", {})
        assert corpuses_result.structuredContent["result"] == [
            {"name": corpus_name, "root": str(root), "exists": True}
        ]

        ask_result = await _call_tool(
            server,
            "oneo_ask",
            {"question": "How are customers billed?", "corpus": corpus_name},
        )

        assert ask_result.structuredContent["insufficient_evidence"] is False
        assert ask_result.structuredContent["citations"]
    finally:
        coordinator.reset(corpus=corpus_name)
