# Oneo — Agent Guidelines

## Purpose

Oneo is a proof of concept that indexes an Open Knowledge Format (OKF)
repository into Neo4j and uses the resulting graph for hybrid and
graph-enhanced retrieval. The OKF filesystem is the canonical source of
truth; Neo4j is a derived index that must be fully reproducible from the
filesystem at any time. Oneo demonstrates the value of combining
OKF-aware parsing, explicit document relationships, Neo4j graph
projection, vector retrieval, full-text retrieval, rank fusion, graph
expansion, and grounded answer generation into one small, understandable
pipeline.

## Goals

- Index an OKF repository without manual preprocessing.
- Preserve document identities, headings, metadata, anchors, and links.
- Project OKF documents and sections into Neo4j as first-class nodes and
  relationships.
- Store section embeddings directly in Neo4j and support vector search.
- Support Neo4j full-text search alongside vector search.
- Combine vector and lexical retrieval using explicit, explainable rank
  fusion.
- Expand retrieval context through one-hop document relationships.
- Generate answers grounded only in retrieved OKF content, with citations
  that resolve to indexed sections.
- Fully rebuild the derived Neo4j index from the filesystem at any time.
- Provide a single executable demo script that runs the complete
  pipeline from a clean checkout.

## Non-Goals

- Building a general-purpose RAG or retrieval framework.
- General document conversion (PDF/DOCX/PPTX) in the normal OKF
  ingestion path.
- A second vector database or any additional derived datastore.
- LLM-based graph extraction.
- Filesystem watching, incremental ingestion, or remote URL ingestion.
- An in-memory, corpus-wide BM25 index.
- A web interface or MCP integration.
- RDF projection.
- Production authentication, authorization, or high-availability
  deployment.
- Distributed ingestion, automated retrieval tuning, or multi-tenant
  indexing.
- Generic plugin infrastructure or dynamic pipeline composition.
- Support for arbitrary document schemas beyond OKF.

## Constraints

- Filesystem remains the only canonical source; Neo4j must be safely
  deletable and rebuildable without loss of canonical knowledge.
- Use `uv` as the standard interface for dependency resolution,
  environment management, command execution, locking, and reproducible
  setup — even as a proof of concept.
- Use Typer for the CLI; command handlers must be thin and delegate to
  the `Oneo` coordinator, never containing domain logic.
- Persistence is limited to Neo4j; no secondary database is permitted.
- Reuse mature open-source libraries (`markdown-it-py`, a frontmatter
  parser, the official Neo4j Python driver, Sentence Transformers)
  instead of rebuilding generic infrastructure.
- Keep public interfaces small, typed, and free of framework-specific
  objects.
- Target approximately 2,000–2,700 lines of production code; pause for
  architecture review beyond ~5,000 lines.
- Approximately 10–12 modules, ≤20 exported classes, ≤40 exported
  functions.
- All ingest paths must be validated against a configured knowledge root;
  reject path traversal, unrelated absolute paths, and remote URLs.
- The embedding model is fixed to
  `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, cosine
  similarity) and must not be made configurable.
- Document ID = bundle-relative file path with the Markdown suffix
  removed; section ID = document ID + normalized heading path + section
  ordinal. Content hashes are never used as identities.
- Key pitfall: when validating an ingest path against the knowledge root,
  resolve relative paths against the current working directory (not
  against the knowledge root itself) before checking containment —
  otherwise a CLI argument that already equals the knowledge root (e.g.
  `oneo files ./knowledge` when `ONEO_KNOWLEDGE_ROOT=./knowledge`) gets
  incorrectly double-joined and fails to resolve.
- Typer command handlers can be unit-tested without a live Neo4j instance by
  monkeypatching the module-level `_build_coordinator` seam in `cli.py` to
  return a fake coordinator; use `typer.testing.CliRunner` to invoke commands
  and assert on `result.exit_code` / `result.output`.
- Key pitfall: `discover_files()` returns paths relative to the knowledge
  root, but `resolve_within_root()` resolves its `raw_path` argument
  against the current working directory, not the root. Callers that load a
  single discovered file (e.g. `OkfLoader.load`) must join the root onto
  the discovered relative path before calling `resolve_within_root`,
  otherwise a root-relative path like `overview.md` is wrongly resolved
  against the CWD and rejected as outside the root.
- Key pitfall: when computing Markdown heading section boundaries from
  `markdown-it-py` tokens, use each `heading_open` token's `map[0]`
  (the heading's own start line) as the boundary for the *previous*
  section's end / the preamble's end — not `map[1]` (the line where the
  heading's content starts). Using `map[1]` for the boundary check causes
  the heading line itself to leak into the preceding section's text.
- Key pitfall: OKF spec §9 requires a non-empty `type` frontmatter field for
  strict-mode conformance, but the bootstrap `knowledge/` sample documents
  only had `id`/`title`. Any demo/fixture corpus intended to pass
  `oneo validate --strict` must include `type` in frontmatter — permissive
  mode tolerates its absence (reported as a `missing-required-field`
  diagnostic), but strict mode fails on it. Local link/anchor resolution in
  the validator is directory-relative to the *linking* document's
  `document_id` (via `PurePosixPath(...).parent`), not the knowledge root,
  matching how relative Markdown links resolve on disk.
- Key pitfall: `python-frontmatter`'s `Post.content` strips the YAML
  frontmatter block before `markdown-it-py` tokenizes the body, so any
  `token.map`-derived line number (e.g. heading `start_line` in
  `okf_loader._extract_heading_blocks`) is relative to the stripped body,
  not the real file on disk. Any diagnostic/section/link `line` field
  meant to point a human at a real source line must add the frontmatter
  block's line count (delimiters + content + separator) back in before
  storing it — otherwise the reported line silently points at the wrong
  place (often into the frontmatter itself), and unit tests that assert
  `line == 1` against a body-relative offset will pass while still being
  wrong relative to the actual file.

## Architecture Decisions

- Pipeline flow: filesystem discovery and path validation → OKF-aware
  loader → documents/sections/anchors/links → corpus validation and link
  resolution → Neo4j graph, vector index, and full-text index → vector
  and lexical retrieval → rank fusion → one-hop graph expansion →
  grounded answer with citations and graph paths.
- Neo4j stores only derived data: document nodes, section nodes,
  relationships, full-text indexes, embedding vectors, vector indexes,
  and rebuild/index-owner metadata. All owned nodes are scoped with an
  index-owner marker so reset only removes data this index created.
- A narrow `OkfGraphStore` protocol isolates the Neo4j driver and Cypher
  from orchestration code; a narrow `SectionEmbedder` isolates the
  embedding model; a narrow `ChatModel` protocol isolates answer
  generation. None of these may grow into a registry, factory framework,
  or service locator.
- The `Oneo` coordinator exposes exactly: `validate`, `index`,
  `discover`, `retrieve`, `query`, `reset`.
- Rank fusion uses a small, explicit reciprocal-rank or weighted-rank
  fusion implementation, independently testable and diagnosable.
- Graph expansion is one-hop only across `LINKS_TO` relationships,
  applied after hybrid rank fusion.

## Design Principles

- Prefer composition and mature libraries over custom infrastructure;
  implement only behavior specific to OKF semantics or required
  orchestration.
- Avoid abstractions introduced only to anticipate future needs; a new
  abstraction is justified only when it removes demonstrated
  duplication, isolates a substantial dependency, enables meaningful
  testing, supports at least two concrete implementations, or provides a
  stable boundary around OKF-specific behavior.
- Prefer plain functions and small classes over inheritance hierarchies;
  prefer readable duplication over premature generalization.
- Optimize for readability over extensibility.
- Preserve source provenance throughout parsing, retrieval, graph
  expansion, and answer generation.
- Determinism first: given the same corpus, configuration, parser, and
  embedding model version, the pipeline must produce the same IDs,
  anchors, resolved links, graph structure, and normalized export.
- Permissive validation is the OKF-conformant default (broken cross-links
  are tolerated); strict mode is an explicit, project-specific opt-in.

## Main Features

- Secure, recursive filesystem discovery of `.md`/`.markdown` OKF files
  with exclusion patterns and knowledge-root enforcement.
- OKF-aware parsing of YAML frontmatter and Markdown structure into
  documents, sections, headings, anchors, and links, with a token-based
  fallback splitter for oversized sections.
- Structured corpus validation (strict and permissive modes) with
  link/anchor resolution before any graph writes occur.
- Idempotent Neo4j projection of documents, sections, and relationships
  with uniqueness constraints, ownership scoping, and full rebuild
  support.
- Deterministic section embedding generation and storage in a Neo4j
  vector index.
- Hybrid retrieval combining Neo4j vector search and full-text search via
  explicit rank fusion, with full retrieval diagnostics.
- One-hop graph expansion of retrieval results through document
  relationships, with deduplication and enforced limits.
- Grounded answer generation with stable, verifiable citations and
  insufficient-evidence handling.
- A single `./scripts/demo.sh` script that runs the entire pipeline
  end-to-end from a clean checkout and prints a pass/fail summary.

## Main Use Cases

- An engineer points Oneo at a local OKF knowledge repository and indexes
  it into Neo4j without any manual preprocessing.
- An engineer deletes and rebuilds the Neo4j database and confirms the
  resulting graph is identical to the original, proving the filesystem
  is the sole source of truth.
- A user issues a natural-language query and receives hybrid
  (vector + lexical) retrieval results with full ranking diagnostics.
- A user issues a query whose answer depends on a linked, non-seed
  document, and graph expansion surfaces the related section.
- A user asks a grounded question and receives an answer with citations
  that resolve to real indexed OKF sections and source paths.
- A user asks an unanswerable question and receives an explicit
  insufficient-evidence result instead of a fabricated answer.
- A reviewer runs `./scripts/demo.sh` from a clean checkout to verify the
  complete pipeline works end-to-end before merging a change.

## Lessons Learned

- Keep `factory_v2.sh` in repo gitignored
- Neo4j node/relationship properties cannot hold nested maps: `OkfDocument.metadata`
  (a `Mapping[str, object]`) must be serialized (e.g. `json.dumps(..., sort_keys=True)`)
  before being set as a property, or the write raises a type error.
- Step 00400's E2E validation requires an `oneo verify` CLI command, but the
  Architecture Decisions section above restricts the `Oneo` coordinator to
  exactly `validate`/`index`/`discover`/`retrieve`/`query`/`reset`. Resolved
  by adding a `verify()` read-only diagnostic method as a documented,
  narrow exception (it composes `parse()` + a Neo4j read, no new domain
  logic) rather than reinterpreting the fixed six-method surface.
- Neo4j `MERGE` on a relationship pattern that includes properties (e.g.
  `MERGE (a)-[r:LINKS_TO {source_section_id: ..., raw_target: ...}]->(b)`)
  is the correct way to keep `LINKS_TO` edges idempotent across repeated
  `oneo index` runs without a content-hash-based identity — the properties
  used in the `MERGE` pattern itself form the edge's dedup key.
- Setting a Neo4j relationship/node property to a Python `None` (e.g.
  `SET r.target_anchor = row.target_anchor` when `target_anchor` is
  `None`, as in `Neo4jStore.write_links`) does not create the property —
  Neo4j has no null property value, so the key is simply absent. Any
  later Cypher that references that property by name (e.g.
  `export_graph`'s `RETURN r.target_anchor`) then emits a
  "property key does not exist" driver warning on every run for rows
  where it was never set. Wrap such reads in `coalesce(r.prop, null)`
  or only `SET` the property conditionally to avoid persistent
  validation noise once anchor-less links exist in the corpus.
- Follow-up to the above: `coalesce(r.target_anchor, null)` and a
  conditional `SET` alone do *not* silence the warning when **no**
  relationship in the whole graph has ever had `target_anchor` set
  (e.g. the sample corpus's only link has no anchor) — Neo4j's
  "property key does not exist" notification is a schema/token-level
  check, not a per-row one: it fires whenever the property key has
  never been registered anywhere in the database, and reading it via
  `coalesce()` still references the key by name at parse time. The
  actual fix is to register the property key token unconditionally,
  e.g. `CREATE INDEX ... IF NOT EXISTS FOR ()-[r:LINKS_TO]-() ON
  (r.target_anchor)` in `apply_schema()` — this creates the token even
  with zero matching data, is idempotent, and (unlike a throwaway
  node) needs no cleanup since Neo4j property key tokens, once
  registered, are never removed even after `reset()` deletes the
  owned data.
- Neo4j `CREATE VECTOR INDEX ... IF NOT EXISTS` returns immediately, but
  the index itself starts in `POPULATING` state (via `SHOW VECTOR
  INDEXES YIELD state`) even for a corpus with only 1-2 sections — it
  is not synchronously `ONLINE` after the statement returns. Any code
  or E2E check that depends on the index being queryable (e.g.
  `db.index.vector.queryNodes` right after `oneo index`) must poll
  `SHOW VECTOR INDEXES` until `state = 'ONLINE'` (with a timeout) rather
  than assuming `CREATE VECTOR INDEX` is synchronous.
- `Neo4jStore._run(self, query: str, **parameters)` uses `query` as its
  own positional parameter name, so any Cypher call that also needs a
  `$query` parameter (e.g. `db.index.fulltext.queryNodes(indexName,
  $query, ...)` in a full-text search method) must bind it under a
  different keyword (e.g. `search_text`) when calling `_run(...,
  search_text=query, ...)` — passing `query=query` raises `TypeError:
  _run() got multiple values for argument 'query'` at call time, not
  import time, so it is easy to miss until the integration test
  actually runs against Neo4j.
- Grounded answer generation (Step 8) cannot use Neo4j full-text score or
  presence of a lexical match as a relevance gate for "insufficient
  evidence" detection: Lucene's full-text index still scores stopword-heavy,
  semantically unrelated queries (e.g. "What is the boiling point of
  mercury?") positively against unrelated sections through common-word
  overlap, sometimes higher than genuinely relevant matches on other
  queries. Only the MiniLM vector-search cosine similarity is a usable
  relevance signal for this gate (relevant hits on the sample corpus score
  ~0.7–0.85 vs. ~0.45–0.5 for unrelated queries); a seed hit with no vector
  score at all (lexical-only) must not be treated as relevant by default.
- `Neo4jStore.reset()` deletes all `index_owner="oneo"` data globally,
  regardless of which `knowledge_root`/`Settings` produced it. Integration
  tests that index a `tmp_path` fixture corpus and call
  `coordinator.reset()` in a `finally` block will also delete the real
  `./knowledge` demo index if it was indexed in the same Neo4j database —
  always re-run `oneo index ./knowledge` after running the test suite
  before manually validating `oneo query`/`oneo retrieve` against the demo
  corpus.

## Key Pitfalls

- `CREATE INDEX ... IF NOT EXISTS` and `CREATE VECTOR INDEX ... IF NOT
  EXISTS` share the same index namespace in Neo4j: if a regular (range)
  index is ever created under the same name intended for a vector index
  (e.g. both named after the property they cover, like
  `okf_section_embedding`), the later `CREATE VECTOR INDEX ... IF NOT
  EXISTS` silently no-ops because the name is already taken — it does
  not raise, and the vector index is simply never created, leaving
  `db.index.vector.queryNodes` broken. Any schema-registration index
  added purely to register a property key token that will later back a
  vector index (to avoid "property key does not exist" driver warnings)
  must use a distinct index name from the vector index it precedes.
- `SHOW VECTOR INDEXES YIELD state = 'ONLINE'` still does not guarantee
  `db.index.vector.queryNodes` will immediately return a just-written
  vector — under repeated reset/rebuild churn across a full test-suite
  run (as opposed to a single isolated test), two further races surface
  that don't show up in isolation: (1) `db.index.vector.queryNodes`
  raises `Neo.ClientError.Procedure.ProcedureCallFailed` ("no such
  vector schema index") if any caller queries it before the vector
  index has ever been created at all (e.g. graph-expansion code paths
  that may run before embeddings exist) — callers must treat that
  specific error as "no matches yet," not a hard failure; and (2) a
  just-`reset()`-deleted node's vector can remain visible to the ANN
  index for a moment alongside a fresh write with an identical/tied
  score, so a queryability probe that only checks `top_k=1` can flakily
  see the stale node ranked first and miss the real match — probing
  with a wider `top_k` (e.g. 10) while still requiring the exact known
  section ID to appear is necessary for the probe itself to be
  reliable under load, not just a longer timeout.