# Oneo

Oneo indexes one or more Open Knowledge Format (OKF) repositories —
**corpuses** — into a single shared Neo4j database and uses the
resulting graph for hybrid and graph-enhanced retrieval, one corpus at a
time. Each corpus is a named OKF bundle rooted at its own directory,
registered in `corpuses.toml`. The filesystem remains the canonical
source of truth for each corpus; Neo4j is a derived index, fully
reproducible from the filesystem at any time, per corpus.

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

`.env` configures the corpus registry, Neo4j connection, and retrieval
tuning parameters (see `src/oneo/config.py` for the full list of
`ONEO_*` settings). Corpuses are registered in `corpuses.toml`:

```bash
cp corpuses.toml.example corpuses.toml
```

```toml
# corpuses.toml
[corpuses.billing]
root = "./corpuses/billing"

[corpuses.engineering]
root = "./corpuses/engineering"
```

`ONEO_DEFAULT_CORPUS` selects which corpus is used when `--corpus` is
omitted; every corpus-scoped command otherwise requires an explicit
`--corpus <name>`.

## Usage

```bash
# Check Neo4j connectivity
uv run oneo health

# List registered corpuses and their filesystem roots
uv run oneo corpus list

# List discovered OKF source files for a corpus
uv run oneo files --corpus billing

# Parse a corpus into a normalized JSON representation
uv run oneo parse --corpus billing --output build/billing.json

# Validate a corpus (add --strict to fail on unresolved links/anchors)
uv run oneo validate --corpus billing --strict

# Reset the Neo4j data owned by this index for one corpus
uv run oneo reset --corpus billing

# Index a corpus into Neo4j: schema, documents, sections, links, embeddings
uv run oneo index --corpus billing --rebuild

# Compare a corpus's filesystem against its graph index
uv run oneo verify --corpus billing

# Raw vector-similarity search over one corpus's indexed sections
uv run oneo vector-search "How are customers billed?" --corpus billing

# Hybrid retrieval (vector + full-text, rank-fused) for one corpus,
# optionally with one-hop graph expansion via --mode graph-hybrid
uv run oneo retrieve "How are customers billed?" --mode hybrid --corpus billing --explain

# Grounded, cited answer generation for one corpus (defaults to
# graph-hybrid retrieval)
uv run oneo query "How are customers billed?" --corpus billing --show-sources --show-paths
```

A `Makefile` wraps the common commands (`make up`, `make validate`,
`make index`, `make retrieve QUERY="..."`, `make query QUERY="..."`,
`make test`, `make demo`, `make publish BUMP=patch|minor|major`; run
`make help` for the full list).

## Agent interface (`oneo mcp`)

```bash
# Run the MCP server over stdio (default; agent-spawned, no network listener)
uv run oneo mcp

# Or over a loopback-only HTTP endpoint
uv run oneo mcp --transport streamable-http --port 8765
```

Requires the optional `mcp` dependency group: `uv pip install 'oneo[mcp]'`.
Exposes exactly two tools to an MCP host (e.g. Claude Desktop, opencode):
`oneo_ask` (a grounded answer plus citations for one corpus) and
`oneo_list_corpuses` (discovery of registered corpuses). Write operations
(`index`, `reset`) stay CLI-only. `streamable-http` binds `127.0.0.1` by
default; no authentication is provided, so exposing it beyond loopback is
the caller's explicit responsibility.

## Releasing

```bash
make publish BUMP=patch   # or BUMP=minor / BUMP=major
```

Requires a clean working tree and the [GitHub CLI](https://cli.github.com/)
authenticated (`gh auth login`). Runs the test suite, bumps the version via
`uv version --bump`, builds the package, commits and tags the release, pushes
both, and creates a GitHub release with auto-generated notes.

## Demo

```bash
./scripts/demo.sh
```

Runs the complete pipeline end to end from a clean checkout — starting
Neo4j, then for each registered demo corpus (`billing`, `engineering`):
validating the corpus, indexing it, running hybrid retrieval, graph
expansion, and grounded query generation — and finally proves corpus
isolation before printing a pass/fail summary.

## Tests

```bash
uv run pytest
```

- `tests/unit` — no external dependencies required.
- `tests/integration` — require a reachable Neo4j instance
  (`docker compose up -d neo4j`); skipped otherwise.
- `tests/e2e` — full filesystem-to-graph round trips, including
  cross-corpus isolation, against a live Neo4j instance.

## Limitations

Oneo is a small, deliberately scoped multi-corpus index, not a
general-purpose retrieval framework. Notably out of scope: general
document conversion (PDF/DOCX/PPTX), a second vector database or
datastore, filesystem watching or incremental ingestion, remote URL
ingestion, a general web interface, RDF projection,
cross-corpus/federated retrieval, and production authentication/
authorization. See `AGENTS.md` for the full list of goals, non-goals,
and constraints.
