# Oneo

Oneo is a proof of concept that indexes an Open Knowledge Format (OKF)
repository into Neo4j and uses the resulting graph for hybrid and
graph-enhanced retrieval. The filesystem remains the canonical source of
truth; Neo4j is a derived index, fully reproducible from the filesystem at
any time.

The pipeline covers the full flow end to end: filesystem discovery and
path-security validation, OKF-aware parsing (frontmatter, headings,
sections, anchors, links), corpus validation with link/anchor resolution,
idempotent projection into Neo4j (documents, sections, relationships),
section embedding generation and vector indexing, hybrid retrieval (vector
+ full-text with reciprocal-rank fusion), one-hop graph expansion, and
grounded answer generation with citations.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Docker.

```bash
uv sync
cp .env.example .env
docker compose up -d neo4j
```

`.env` configures the knowledge root, Neo4j connection, and retrieval
tuning parameters (see `src/oneo/config.py` for the full list of
`ONEO_*` settings).

## Usage

```bash
# Check Neo4j connectivity
uv run oneo health

# List discovered OKF source files under a directory
uv run oneo files ./knowledge

# Parse the corpus into a normalized JSON representation
uv run oneo parse ./knowledge --output build/corpus.json

# Validate the corpus (add --strict to fail on unresolved links/anchors)
uv run oneo validate ./knowledge --strict

# Reset the Neo4j index owned by this pipeline
uv run oneo reset

# Index the corpus into Neo4j: schema, documents, sections, links, embeddings
uv run oneo index ./knowledge --rebuild

# Compare the filesystem corpus against the graph index
uv run oneo verify ./knowledge

# Raw vector-similarity search over indexed sections
uv run oneo vector-search "How are customers billed?"

# Hybrid retrieval (vector + full-text, rank-fused), optionally with
# one-hop graph expansion via --mode graph-hybrid
uv run oneo retrieve "How are customers billed?" --mode hybrid --explain

# Grounded, cited answer generation (defaults to graph-hybrid retrieval)
uv run oneo query "How are customers billed?" --show-sources --show-paths
```

A `Makefile` wraps the common commands (`make up`, `make validate`,
`make index`, `make retrieve QUERY="..."`, `make query QUERY="..."`,
`make test`, `make demo`; run `make help` for the full list).

## Demo

```bash
./scripts/demo.sh
```

Runs the complete pipeline end to end from a clean checkout — starting
Neo4j, validating the corpus, indexing it, running hybrid retrieval, graph
expansion, and grounded query generation — and prints a pass/fail summary.

## Tests

```bash
uv run pytest
```

- `tests/unit` — no external dependencies required.
- `tests/integration` — require a reachable Neo4j instance
  (`docker compose up -d neo4j`); skipped otherwise.
- `tests/e2e` — full filesystem-to-graph round trip against a live Neo4j
  instance.

## Limitations

This is a proof of concept, not a production system. Notably out of
scope: general document conversion (PDF/DOCX/PPTX), a second vector
database or datastore, filesystem watching or incremental ingestion,
remote URL ingestion, a web interface or MCP integration, RDF projection,
and production authentication/authorization. See `AGENTS.md` for the full
list of goals, non-goals, and constraints.
