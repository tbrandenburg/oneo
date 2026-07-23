"""MCP server exposing Oneo's grounded retrieval as agent tools.

Hosts one warm ``Oneo`` coordinator for the server's lifetime so the
one-time ``sentence_transformers``/torch import cost (see
``SectionEmbedder``) is amortized across every tool call in an agent
session, instead of paid once per CLI invocation. The embedder itself
is never touched here -- ``Oneo._embedder`` stays lazy and is
constructed on first real ``oneo_ask`` call, so server startup and the
MCP ``initialize``/``tools/list`` handshake remain near-instant.

Only two tools are exposed, per "curate ruthlessly": ``oneo_ask`` (the
single outcome-oriented tool) and ``oneo_list_corpuses`` (discovery).
Write operations (``index``, ``reset``) are deliberately excluded and
remain CLI-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from oneo.answering import ExtractiveChatModel
from oneo.config import Settings, load_settings
from oneo.corpus import CorpusConfigError, CorpusRegistry
from oneo.pipeline import Oneo
from oneo.security import PathSecurityError


@dataclass(frozen=True)
class _ServerContext:
    coordinator: Oneo
    registry: CorpusRegistry


def _build_context(settings: Settings | None = None) -> _ServerContext:
    resolved_settings = settings if settings is not None else load_settings()
    coordinator = Oneo(resolved_settings, chat_model=ExtractiveChatModel())
    registry = CorpusRegistry.load(
        resolved_settings.corpus_config, resolved_settings.default_corpus
    )
    return _ServerContext(coordinator=coordinator, registry=registry)


def build_server(
    context: _ServerContext | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> FastMCP:
    """Build (but do not run) the Oneo MCP server.

    ``context`` is injectable for testing (see
    ``tests/unit/test_mcp_server.py``); production callers omit it and
    get a real coordinator built from environment settings. ``host``
    and ``port`` only take effect for the ``streamable-http``
    transport; the FastMCP SDK accepts them as constructor arguments,
    not ``run()`` arguments.
    """

    ctx = context if context is not None else _build_context()
    mcp = FastMCP("oneo", host=host, port=port)

    @mcp.tool(name="oneo_list_corpuses")
    def oneo_list_corpuses() -> list[dict[str, object]]:
        """List every registered OKF corpus available to oneo_ask.

        Call this only when the desired corpus name is not already
        obvious; the common case needs no discovery call.
        """

        return [
            {
                "name": name,
                "root": ctx.registry.get(name).root,
                "exists": Path(ctx.registry.get(name).root)
                .expanduser()
                .resolve()
                .exists(),
            }
            for name in ctx.registry.names()
        ]

    @mcp.tool(name="oneo_ask")
    def oneo_ask(
        question: str,
        corpus: str | None = None,
        expand_graph: bool = True,
        limit: int = 5,
    ) -> dict[str, object]:
        """Answer a question grounded in one indexed OKF corpus.

        Returns a synthesized answer plus the underlying citations, so
        the caller can use the answer directly or reason over the
        evidence itself. Call oneo_list_corpuses first if the correct
        corpus name is unclear.
        """

        try:
            result = ctx.coordinator.query(
                question, top_k=limit, expand=expand_graph, corpus=corpus
            )
        except (CorpusConfigError, PathSecurityError) as exc:
            return {
                "answer": f"error: {exc}",
                "insufficient_evidence": True,
                "citations": [],
                "corpus": corpus,
            }

        return {
            "answer": result.answer,
            "insufficient_evidence": result.insufficient_evidence,
            "citations": [
                {
                    "label": citation.label,
                    "heading": citation.heading,
                    "source_path": citation.source_path,
                    "document_id": citation.document_id,
                    "section_id": citation.section_id,
                }
                for citation in result.citations
            ],
            "corpus": corpus if corpus is not None else ctx.registry.default_name(),
        }

    return mcp


def run_mcp_server(transport: str = "stdio", **kwargs: object) -> None:
    """Build and run the Oneo MCP server.

    ``host``/``port`` (streamable-http only) are forwarded to
    ``build_server`` since FastMCP takes them as constructor
    arguments; ``run()`` itself only accepts ``transport``.
    """

    host = kwargs.pop("host", "127.0.0.1")
    port = kwargs.pop("port", 8765)
    server = build_server(host=host, port=port)  # type: ignore[arg-type]
    server.run(transport=transport, **kwargs)
