"""Typer-based command-line interface for Oneo.

Command handlers are thin: they parse CLI input, invoke the ``Oneo``
coordinator, render results, and map failures to exit codes. They must
not contain discovery, validation, persistence, retrieval, or
answer-generation logic.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from oneo.answering import ExtractiveChatModel
from oneo.config import load_settings
from oneo.corpus import CorpusConfigError, CorpusRegistry
from oneo.okf_loader import corpus_to_dict
from oneo.pipeline import Oneo
from oneo.security import PathSecurityError

app = typer.Typer(help="Oneo: OKF-to-Neo4j multi-corpus graph retrieval.")
corpus_app = typer.Typer(help="Inspect the configured corpus registry.")
app.add_typer(corpus_app, name="corpus")


def _build_registry() -> CorpusRegistry:
    settings = load_settings()
    return CorpusRegistry.load(settings.corpus_config, settings.default_corpus)


def _build_coordinator(with_chat_model: bool = False) -> Oneo:
    chat_model = ExtractiveChatModel() if with_chat_model else None
    return Oneo(load_settings(), chat_model=chat_model)


@corpus_app.command("list")
def corpus_list() -> None:
    """List every configured corpus and its filesystem root."""

    try:
        registry = _build_registry()
    except CorpusConfigError as exc:
        typer.echo(f"corpus configuration error: {exc}")
        raise typer.Exit(code=1) from exc

    for name in registry.names():
        corpus = registry.get(name)
        typer.echo(f"{corpus.name} {corpus.root}")


@corpus_app.command("info")
def corpus_info(name: str = typer.Argument(..., help="Corpus name.")) -> None:
    """Print one corpus's name, resolved root, and whether it exists."""

    try:
        registry = _build_registry()
        corpus = registry.get(name)
    except CorpusConfigError as exc:
        typer.echo(f"corpus configuration error: {exc}")
        raise typer.Exit(code=1) from exc

    root_path = Path(corpus.root).expanduser().resolve()
    typer.echo(f"name={corpus.name} root={corpus.root} exists={root_path.exists()}")


@app.command()
def health() -> None:
    """Check connectivity to the configured Neo4j database."""

    coordinator = _build_coordinator()
    status = coordinator.health()
    if status.connected:
        typer.echo(
            f"connected to database {status.database!r} "
            f"(server: {status.server_agent})"
        )
        raise typer.Exit(code=0)

    typer.echo(f"failed to connect to database {status.database!r}: {status.detail}")
    raise typer.Exit(code=1)


@app.command()
def files(
    input_path: str = typer.Argument(
        None, help="Directory to scan. Defaults to the selected corpus's root."
    ),
    corpus: str = typer.Option(
        None, "--corpus", help="Corpus to select. Defaults to the configured default corpus."
    ),
) -> None:
    """List supported OKF source files under INPUT_PATH."""

    coordinator = _build_coordinator()
    try:
        discovered = coordinator.discover(input_path, corpus=corpus)
    except (PathSecurityError, CorpusConfigError) as exc:
        typer.echo(f"rejected: {exc}")
        raise typer.Exit(code=1) from exc

    for path in discovered:
        typer.echo(path)


@app.command()
def parse(
    input_path: str = typer.Argument(
        None, help="Directory to parse. Defaults to the selected corpus's root."
    ),
    output: str = typer.Option(
        ..., "--output", help="Path to write the normalized corpus JSON."
    ),
    corpus: str = typer.Option(
        None, "--corpus", help="Corpus to select. Defaults to the configured default corpus."
    ),
) -> None:
    """Parse OKF documents under INPUT_PATH into a normalized corpus JSON file."""

    coordinator = _build_coordinator()
    try:
        documents = coordinator.parse(input_path, corpus=corpus)
    except (PathSecurityError, CorpusConfigError) as exc:
        typer.echo(f"rejected: {exc}")
        raise typer.Exit(code=1) from exc

    corpus = corpus_to_dict(documents)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(corpus, indent=2, sort_keys=True) + "\n")
    typer.echo(f"wrote {len(documents)} document(s) to {output}")


@app.command()
def validate(
    input_path: str = typer.Argument(
        None, help="Directory to validate. Defaults to the selected corpus's root."
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Fail on unresolved links/anchors and duplicate IDs."
    ),
    corpus: str = typer.Option(
        None, "--corpus", help="Corpus to select. Defaults to the configured default corpus."
    ),
) -> None:
    """Validate the OKF corpus under INPUT_PATH without writing to Neo4j."""

    coordinator = _build_coordinator()
    try:
        result = coordinator.validate(input_path, strict=strict, corpus=corpus)
    except (PathSecurityError, CorpusConfigError) as exc:
        typer.echo(f"rejected: {exc}")
        raise typer.Exit(code=1) from exc

    for diagnostic in result.diagnostics:
        parts = [
            f"[{diagnostic.severity}]",
            diagnostic.code,
            diagnostic.source_path,
        ]
        if diagnostic.source_section:
            parts.append(diagnostic.source_section)
        if diagnostic.line is not None:
            parts.append(f"line={diagnostic.line}")
        if diagnostic.raw_target:
            parts.append(f"raw_target={diagnostic.raw_target}")
        parts.append(diagnostic.message)
        typer.echo(" ".join(parts))

    typer.echo(f"{len(result.diagnostics)} diagnostic(s)")
    if not result.ok:
        raise typer.Exit(code=1)


@app.command()
def index(
    input_path: str = typer.Argument(
        None, help="Directory to index. Defaults to the selected corpus's root."
    ),
    no_embeddings: bool = typer.Option(
        False,
        "--no-embeddings",
        help="Skip embedding generation (required until embeddings are implemented).",
    ),
    rebuild: bool = typer.Option(
        True,
        "--rebuild/--no-rebuild",
        help="Reset the owned graph index before writing.",
    ),
    corpus: str = typer.Option(
        None, "--corpus", help="Corpus to select. Defaults to the configured default corpus."
    ),
) -> None:
    """Index the OKF corpus under INPUT_PATH into Neo4j."""

    coordinator = _build_coordinator()
    try:
        summary = coordinator.index(
            input_path, rebuild=rebuild, embeddings=not no_embeddings, corpus=corpus
        )
    except (PathSecurityError, CorpusConfigError) as exc:
        typer.echo(f"rejected: {exc}")
        raise typer.Exit(code=1) from exc
    except NotImplementedError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    typer.echo(
        f"indexed {summary.documents} document(s), {summary.sections} "
        f"section(s), {summary.links} link(s)"
    )


@app.command("vector-search")
def vector_search(
    query: str = typer.Argument(..., help="Natural-language query to embed and search."),
    top_k: int = typer.Option(5, "--top-k", help="Number of results to return."),
    corpus: str = typer.Option(
        None, "--corpus", help="Corpus to select. Defaults to the configured default corpus."
    ),
) -> None:
    """Run a raw vector-similarity search over indexed OKF sections."""

    coordinator = _build_coordinator()
    try:
        matches = coordinator.vector_search(query, top_k=top_k, corpus=corpus)
    except (PathSecurityError, CorpusConfigError) as exc:
        typer.echo(f"rejected: {exc}")
        raise typer.Exit(code=1) from exc

    for match in matches:
        typer.echo(
            f"document_id={match.document_id} section_id={match.section_id} "
            f"heading={match.heading!r} score={match.score:.4f} "
            f"source_path={match.source_path}"
        )
    typer.echo(f"{len(matches)} result(s)")


@app.command()
def retrieve(
    query: str = typer.Argument(..., help="Natural-language query."),
    mode: str = typer.Option(
        "hybrid",
        "--mode",
        help="Retrieval mode: 'hybrid' or 'graph-hybrid' (adds one-hop graph expansion).",
    ),
    top_k: int = typer.Option(5, "--top-k", help="Number of fused results to return."),
    explain: bool = typer.Option(
        False, "--explain", help="Print per-hit ranking diagnostics."
    ),
    corpus: str = typer.Option(
        None, "--corpus", help="Corpus to select. Defaults to the configured default corpus."
    ),
) -> None:
    """Run hybrid retrieval (vector + full-text with rank fusion), optionally
    followed by one-hop graph expansion."""

    if mode not in ("hybrid", "graph-hybrid"):
        typer.echo(
            f"unsupported mode: {mode!r} (only 'hybrid' and 'graph-hybrid' are implemented)"
        )
        raise typer.Exit(code=1)

    coordinator = _build_coordinator()
    try:
        result = coordinator.retrieve(
            query, top_k=top_k, expand=mode == "graph-hybrid", corpus=corpus
        )
    except (PathSecurityError, CorpusConfigError) as exc:
        typer.echo(f"rejected: {exc}")
        raise typer.Exit(code=1) from exc

    for hit in result.hits:
        line = (
            f"[seed] document_id={hit.document_id} section_id={hit.section_id} "
            f"heading={hit.heading!r} fused_score={hit.fused_score:.6f} "
            f"origin={hit.retrieval_origin} source_path={hit.source_path}"
        )
        if explain:
            line += (
                f" vector_rank={hit.vector_rank} vector_score={hit.vector_score} "
                f"lexical_rank={hit.lexical_rank} lexical_score={hit.lexical_score}"
            )
        typer.echo(line)
    typer.echo(f"{len(result.hits)} seed result(s)")

    if mode == "graph-hybrid":
        for expanded in result.expanded_hits:
            line = (
                f"[expanded] document_id={expanded.document_id} "
                f"section_id={expanded.section_id} heading={expanded.heading!r} "
                f"expansion_score={expanded.expansion_score:.6f} "
                f"strategy={expanded.selection_strategy} "
                f"source_path={expanded.source_path}"
            )
            if explain:
                line += f" graph_path={' -> '.join(expanded.graph_path)}"
            typer.echo(line)
        typer.echo(f"{len(result.expanded_hits)} expanded result(s)")


@app.command()
def query(
    query: str = typer.Argument(..., help="Natural-language question."),
    mode: str = typer.Option(
        "graph-hybrid",
        "--mode",
        help="Retrieval mode: 'hybrid' or 'graph-hybrid' (adds one-hop graph expansion).",
    ),
    top_k: int = typer.Option(5, "--top-k", help="Number of fused seed hits to retrieve."),
    show_sources: bool = typer.Option(
        False, "--show-sources", help="Print every retrieved source used as evidence."
    ),
    show_paths: bool = typer.Option(
        False, "--show-paths", help="Print graph paths for cited graph-expanded sections."
    ),
    corpus: str = typer.Option(
        None, "--corpus", help="Corpus to select. Defaults to the configured default corpus."
    ),
) -> None:
    """Generate a grounded answer with citations from hybrid (optionally
    graph-expanded) retrieval."""

    if mode not in ("hybrid", "graph-hybrid"):
        typer.echo(
            f"unsupported mode: {mode!r} (only 'hybrid' and 'graph-hybrid' are implemented)"
        )
        raise typer.Exit(code=1)

    coordinator = _build_coordinator(with_chat_model=True)
    try:
        result = coordinator.query(
            query, top_k=top_k, expand=mode == "graph-hybrid", corpus=corpus
        )
    except (PathSecurityError, CorpusConfigError) as exc:
        typer.echo(f"rejected: {exc}")
        raise typer.Exit(code=1) from exc

    typer.echo(f"answer: {result.answer}")
    typer.echo(f"insufficient_evidence: {result.insufficient_evidence}")
    for citation in result.citations:
        typer.echo(
            f"[citation {citation.label}] document_id={citation.document_id} "
            f"section_id={citation.section_id} heading={citation.heading!r} "
            f"source_path={citation.source_path} origin={citation.retrieval_origin}"
        )

    if show_sources:
        for hit in result.retrieval.hits:
            typer.echo(
                f"[source] document_id={hit.document_id} section_id={hit.section_id} "
                f"source_path={hit.source_path}"
            )
        for hit in result.retrieval.expanded_hits:
            typer.echo(
                f"[source-expanded] document_id={hit.document_id} "
                f"section_id={hit.section_id} source_path={hit.source_path}"
            )

    if show_paths:
        for graph_path in result.graph_paths:
            typer.echo(f"[graph_path] {' -> '.join(graph_path)}")


@app.command()
def reset(
    corpus: str = typer.Option(
        None, "--corpus", help="Corpus to select. Defaults to the configured default corpus."
    ),
) -> None:
    """Delete only the Neo4j data owned by this index."""

    coordinator = _build_coordinator()
    try:
        coordinator.reset(corpus=corpus)
    except CorpusConfigError as exc:
        typer.echo(f"rejected: {exc}")
        raise typer.Exit(code=1) from exc
    typer.echo("reset complete")


@app.command()
def verify(
    input_path: str = typer.Argument(
        None, help="Directory to verify. Defaults to the selected corpus's root."
    ),
    corpus: str = typer.Option(
        None, "--corpus", help="Corpus to select. Defaults to the configured default corpus."
    ),
) -> None:
    """Compare the filesystem corpus against the graph index."""

    coordinator = _build_coordinator()
    try:
        result = coordinator.verify(input_path, corpus=corpus)
    except (PathSecurityError, CorpusConfigError) as exc:
        typer.echo(f"rejected: {exc}")
        raise typer.Exit(code=1) from exc

    for issue in result.issues:
        typer.echo(f"[issue] {issue}")
    typer.echo(
        f"documents={result.documents} sections={result.sections} "
        f"links={result.links}"
    )
    if not result.ok:
        raise typer.Exit(code=1)


@app.command()
def mcp(
    transport: str = typer.Option(
        "stdio",
        "--transport",
        help="Transport: 'stdio' (default, agent-spawned) or 'streamable-http'.",
    ),
    host: str = typer.Option(
        "127.0.0.1", "--host", help="Bind host (streamable-http only)."
    ),
    port: int = typer.Option(8765, "--port", help="Bind port (streamable-http only)."),
) -> None:
    """Run the Oneo MCP server (agent interface)."""

    if transport not in ("stdio", "streamable-http"):
        typer.echo(
            f"unsupported transport: {transport!r} (only 'stdio' and "
            "'streamable-http' are implemented)"
        )
        raise typer.Exit(code=1)

    try:
        from oneo.mcp_server import run_mcp_server
    except ModuleNotFoundError as exc:
        typer.echo(
            "the 'mcp' package is required for this command; install "
            "with: uv pip install 'oneo[mcp]'"
        )
        raise typer.Exit(code=1) from exc

    kwargs = {"host": host, "port": port} if transport == "streamable-http" else {}
    run_mcp_server(transport=transport, **kwargs)


def main() -> None:
    """Entry point for the ``oneo`` console script."""

    app()


if __name__ == "__main__":
    main()
