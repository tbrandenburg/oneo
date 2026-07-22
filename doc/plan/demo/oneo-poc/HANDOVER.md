# Oneo — Handover Document

## a. Executive Summary

Oneo is a proof-of-concept knowledge retrieval system built to demonstrate
that a Git-managed, Markdown-based "Open Knowledge Format" (OKF) repository
can be fully and reproducibly indexed into a Neo4j graph database, and then
used to answer natural-language questions with citations that trace back to
real source files.

The core idea being proven: **the filesystem is the only permanent source of
truth**. Neo4j holds nothing that cannot be regenerated from the Markdown
files on disk. At any time the graph can be deleted and rebuilt from scratch,
and the result is identical — there is no hidden state, no manual database
editing, and no risk of the graph and the files silently drifting apart.

On top of that reproducible graph, Oneo demonstrates a complete retrieval
pipeline: semantic (vector) search, keyword (full-text) search, an explicit
and explainable fusion of the two, one-hop expansion across document links to
pull in related content, and finally a grounded natural-language answer whose
every claim is tied to a citation that resolves to a real, indexed file and
section.

This was built and verified end-to-end, with no mocking, stubbing, or test
doubles standing in for Neo4j, the embedding model, or the corpus — every
artefact in this folder was produced by running the real system against a
live Neo4j instance and the real sample knowledge repository.

## b. What Works

All items below were exercised live during this verification pass; each is
backed by a captured terminal transcript in this folder.

1. **Filesystem discovery & security** — recursively finds Markdown files
   under a configured knowledge root, rejecting path traversal and paths
   outside the root.
   Evidence: [`10-files-discovery.txt`](10-files-discovery.txt)

2. **OKF parsing** — YAML frontmatter, headings, sections, anchors, and
   Markdown links are parsed into structured documents with stable,
   deterministic IDs derived from file paths (not content hashes).

3. **Corpus validation** — both permissive and strict validation modes,
   including cross-document link/anchor resolution, run before anything is
   written to the graph.
   Evidence: [`04-validate-strict.txt`](04-validate-strict.txt) (0
   diagnostics on the sample corpus in `--strict` mode)

4. **Neo4j graph projection** — documents, sections, and their relationships
   (`HAS_SECTION`, `LINKS_TO`) are written idempotently, scoped to this
   index so a reset never touches unrelated data in the same database.
   Repeated indexing produces no duplicates, and the graph can be verified
   against the filesystem at any time.
   Evidence: [`05-verify-graph-vs-filesystem.txt`](05-verify-graph-vs-filesystem.txt)
   shows the graph document/section/link counts exactly matching the
   filesystem corpus (6 documents, 6 sections, 2 links).

5. **Filesystem-first rebuild semantics** — an automated end-to-end test
   proves that editing a section, adding a link, or deleting a file and then
   rebuilding produces the correct corresponding change in the graph
   (updated text/vectors, a new edge, or full removal of the node/edges/
   vectors), with no direct database mutation used to fake the result.
   Evidence: [`09-e2e-filesystem-source-of-truth-test.txt`](09-e2e-filesystem-source-of-truth-test.txt)

6. **Section embeddings** — every section is embedded with the fixed
   `sentence-transformers/all-MiniLM-L6-v2` model (384-dimensional, cosine
   similarity) and stored directly in a Neo4j vector index; re-indexing
   skips sections whose text hasn't changed.
   Evidence: [`01-demo-sh-full-pipeline.txt`](01-demo-sh-full-pipeline.txt)
   ("Vector index: ONLINE")

7. **Hybrid retrieval** — vector search and Neo4j full-text search are
   combined with an explicit, explainable reciprocal-rank fusion. Every
   result exposes its vector rank/score, lexical rank/score, fused score,
   and retrieval origin, so results are never a black box.
   Evidence: [`06-retrieve-graph-hybrid-explain.txt`](06-retrieve-graph-hybrid-explain.txt)

8. **Graph-based expansion** — after hybrid fusion, Oneo follows one hop
   across document links to surface relevant content the initial query
   didn't directly match, clearly labelled as "expanded" (vs. "seed") and
   annotated with the graph path taken.
   Evidence: [`06-retrieve-graph-hybrid-explain.txt`](06-retrieve-graph-hybrid-explain.txt)
   shows `topics/related` pulled in via `overview -> LINKS_TO -> topics/related`,
   a document that was not among the direct hybrid hits.

9. **Grounded answer generation with citations** — natural-language answers
   are generated strictly from retrieved evidence; every citation resolves
   to a real document ID, section ID, and source path from the retrieval
   context. Unanswerable questions are explicitly flagged as insufficient
   evidence rather than answered speculatively.
   Evidence: [`07-query-grounded-answer-with-citations.txt`](07-query-grounded-answer-with-citations.txt)
   (answer with 6 resolvable citations, including one from the
   graph-expanded document) and
   [`08-query-insufficient-evidence.txt`](08-query-insufficient-evidence.txt)
   (an off-topic question — "What is the boiling point of mercury?" — correctly
   returns `insufficient_evidence: True` instead of a fabricated answer).

10. **Single-command demo** — the entire pipeline (start Neo4j, health check,
    security validation, corpus validation, reset, schema, projection,
    embeddings, index verification, hybrid retrieval, graph expansion,
    grounded answer, citation verification) runs from one script and reports
    a single pass/fail summary.
    Evidence: [`01-demo-sh-full-pipeline.txt`](01-demo-sh-full-pipeline.txt)
    — ends with `PoC status: SUCCESS`.

11. **Full automated test suite** — 145 unit and integration tests pass
    against a live Neo4j instance (no mocks for the database).
    Evidence: [`02-pytest-full-suite-145-passed.txt`](02-pytest-full-suite-145-passed.txt)

## c. How to Build and Run

Prerequisites: Docker, and [`uv`](https://docs.astral.sh/uv/) installed.

1. Clone the repository and change into it.
2. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
3. Install dependencies:
   ```bash
   uv sync
   ```
4. Run the complete demo from a clean state:
   ```bash
   docker compose down -v
   ./scripts/demo.sh
   ```
5. Confirm the final line of output reads:
   ```text
   PoC status: SUCCESS
   ```

That single script starts Neo4j, waits for it to become ready, validates the
sample knowledge repository under `./knowledge`, indexes it (schema,
documents, sections, links, embeddings), verifies both the vector and
full-text indexes are online, runs hybrid retrieval, runs graph expansion,
generates one grounded answer, and verifies its citations — printing a
pass/fail line for every stage.

## d. How to Test

All commands below assume `docker compose up -d` has been run and `.env` is
configured (steps 2–3 above), and that the corpus has been indexed at least
once (`./scripts/demo.sh` or `uv run oneo index ./knowledge --rebuild`).

| # | Action | Expected Result |
|---|--------|------------------|
| 1 | `uv run oneo validate ./knowledge --strict` | Reports `0 diagnostic(s)` — the sample corpus is fully OKF-conformant. |
| 2 | `uv run oneo verify` | Reports matching document/section/link counts between the filesystem and the graph (e.g. `documents=6 sections=6 links=2`), with no diff issues. |
| 3 | `uv run oneo retrieve "How are customers billed?" --mode graph-hybrid --explain` | Returns 5 seed results with billing-related content, plus 1 graph-expanded result (`topics/related`) reached via `overview -> LINKS_TO -> topics/related`, with vector/lexical/fused scores shown for every hit. |
| 4 | `uv run oneo query "How are customers billed?" --show-sources --show-paths` | Returns a natural-language answer with numbered citations (`[S1]`, `[S2]`, ...), each resolving to a real document/section/source path, and `insufficient_evidence: False`. |
| 5 | `uv run oneo query "What is the boiling point of mercury?"` | Returns `answer: insufficient evidence` and `insufficient_evidence: True` — proving the system refuses to answer questions unrelated to the indexed corpus rather than hallucinating. |
| 6 | Edit a `.md` file under `./knowledge`, then re-run `uv run oneo index ./knowledge --rebuild` and `uv run oneo verify` | The graph reflects the edited text (same section ID, updated content) and the verify counts still match. |
| 7 | `uv run pytest` | All tests pass (145 at time of writing), including integration tests that run against the live Neo4j instance and an end-to-end test proving filesystem-first rebuild semantics. |

**Important:** running the automated test suite (`uv run pytest`) resets the
shared Neo4j index as part of its own tests. If you want to inspect the
sample `./knowledge` corpus afterwards via `oneo retrieve`/`oneo query`, re-run
`uv run oneo index ./knowledge --rebuild` first.

## e. Known Limitations

- **Single shared Neo4j instance for tests and demo data.** The test suite's
  `reset()` calls delete all data owned by this index globally, not scoped
  to a particular corpus. Running the test suite after indexing
  `./knowledge` will wipe it; re-run `oneo index ./knowledge --rebuild`
  afterwards to restore the demo data.
- **Fixed embedding model.** The embedding model
  (`sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions) is intentionally
  hardcoded and not configurable. Changing it requires a code change and a
  full index rebuild.
- **One-hop graph expansion only.** Retrieval only follows a single hop
  across `LINKS_TO` relationships; deeper multi-hop traversal is out of
  scope for this proof of concept.
- **No incremental indexing.** There is no filesystem watcher or
  incremental-update path; every `index` run re-validates and re-projects
  the corpus (embeddings are skipped for unchanged section text via content
  hashing, but there is no background sync).
- **Small sample corpus.** The bundled `./knowledge` corpus is a small,
  hand-written sample (6 documents) intended to exercise every pipeline
  stage, not a realistic production-scale knowledge base. Retrieval quality
  and performance at larger scale have not been evaluated.
- **No authentication/authorization.** Neo4j credentials are plain
  environment variables intended for local/proof-of-concept use; this is
  explicitly out of scope per the project's non-goals (no production auth
  or multi-tenant deployment).
- **No web UI or MCP integration.** All functionality is exposed via the
  `oneo` CLI only.
- **Answer generation depends on retrieval quality.** Citation correctness
  is enforced (every citation must map to a real retrieved section), but
  the fluency/quality of the generated prose depends on the underlying
  language model and is not independently benchmarked here.
