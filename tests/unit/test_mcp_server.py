"""Unit tests for the ``oneo mcp`` server (in-memory transport, no Neo4j)."""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

from oneo.corpus import Corpus, CorpusConfigError, CorpusRegistry
from oneo.mcp_server import _ServerContext, build_server


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _FakeCoordinator:
    def __init__(self, query_result=None, query_error=None):
        self._query_result = query_result
        self._query_error = query_error

    def query(self, question, top_k=5, expand=True, corpus=None):
        if self._query_error is not None:
            raise self._query_error
        return self._query_result


class _FakeAnswerResult:
    def __init__(self, answer, insufficient_evidence=False, citations=()):
        self.answer = answer
        self.insufficient_evidence = insufficient_evidence
        self.citations = citations


class _FakeCitation:
    def __init__(self, label, heading, source_path, document_id, section_id):
        self.label = label
        self.heading = heading
        self.source_path = source_path
        self.document_id = document_id
        self.section_id = section_id


def _fake_registry() -> CorpusRegistry:
    return CorpusRegistry(
        {"billing": Corpus(name="billing", root="/tmp/billing")}, "billing"
    )


async def _call_tool(server, name, arguments):
    from mcp.shared.memory import create_connected_server_and_client_session

    async with create_connected_server_and_client_session(server) as session:
        return await session.call_tool(name, arguments)


async def _list_tools(server):
    from mcp.shared.memory import create_connected_server_and_client_session

    async with create_connected_server_and_client_session(server) as session:
        return await session.list_tools()


@pytest.mark.anyio
async def test_oneo_list_corpuses_returns_registered_corpuses():
    ctx = _ServerContext(coordinator=_FakeCoordinator(), registry=_fake_registry())
    server = build_server(ctx)

    result = await _call_tool(server, "oneo_list_corpuses", {})

    assert result.structuredContent["result"] == [
        {"name": "billing", "root": "/tmp/billing", "exists": False}
    ]


@pytest.mark.anyio
async def test_oneo_ask_returns_answer_and_citations():
    query_result = _FakeAnswerResult(
        answer="Invoices are due net-30.",
        citations=(
            _FakeCitation(
                "S1", "Payment Terms", "billing/terms.md", "terms", "terms#0"
            ),
        ),
    )
    ctx = _ServerContext(
        coordinator=_FakeCoordinator(query_result=query_result),
        registry=_fake_registry(),
    )
    server = build_server(ctx)

    result = await _call_tool(
        server, "oneo_ask", {"question": "When are invoices due?", "corpus": "billing"}
    )

    assert result.structuredContent["answer"] == "Invoices are due net-30."
    assert result.structuredContent["insufficient_evidence"] is False
    assert result.structuredContent["citations"] == [
        {
            "label": "S1",
            "heading": "Payment Terms",
            "source_path": "billing/terms.md",
            "document_id": "terms",
            "section_id": "terms#0",
        }
    ]
    assert result.structuredContent["corpus"] == "billing"


@pytest.mark.anyio
async def test_oneo_ask_reports_unknown_corpus_as_actionable_string():
    ctx = _ServerContext(
        coordinator=_FakeCoordinator(
            query_error=CorpusConfigError("unknown corpus 'x'")
        ),
        registry=_fake_registry(),
    )
    server = build_server(ctx)

    result = await _call_tool(server, "oneo_ask", {"question": "q", "corpus": "x"})

    assert "unknown corpus" in result.structuredContent["answer"]
    assert result.structuredContent["insufficient_evidence"] is True
    assert result.structuredContent["citations"] == []


def test_startup_does_not_import_torch():
    script = textwrap.dedent(
        """
        import asyncio
        import sys

        from mcp.shared.memory import create_connected_server_and_client_session
        from oneo.corpus import Corpus, CorpusRegistry
        from oneo.mcp_server import _ServerContext, build_server


        async def main():
            context = _ServerContext(
                coordinator=object(),
                registry=CorpusRegistry(
                    {"billing": Corpus(name="billing", root="/tmp/billing")},
                    "billing",
                ),
            )
            server = build_server(context)
            async with create_connected_server_and_client_session(server) as session:
                await session.list_tools()


        asyncio.run(main())
        imported = {"torch", "sentence_transformers"} & sys.modules.keys()
        if imported:
            raise SystemExit(f"heavy modules imported during MCP startup: {imported}")
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.anyio
async def test_tool_surface_is_exactly_two_tools():
    ctx = _ServerContext(coordinator=_FakeCoordinator(), registry=_fake_registry())
    server = build_server(ctx)

    result = await _list_tools(server)

    assert sorted(tool.name for tool in result.tools) == [
        "oneo_ask",
        "oneo_list_corpuses",
    ]
