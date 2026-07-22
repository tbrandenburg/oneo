> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-fill — Commit the embeddings implementation to git

## Why this matters

Step 00500 ("Add Embeddings") was fully and correctly implemented and
verified at review time:

* 63 unit tests pass (`uv run pytest tests/unit -q`).
* 20 integration tests pass against a live Neo4j instance
  (`uv run pytest tests/integration -q`), including the three new
  embedding-specific tests (`test_index_with_embeddings_generates_vectors`,
  `test_vector_search_returns_indexed_section`,
  `test_reindex_skips_unchanged_section_embeddings`).
* End-to-end validation passed: `oneo index ./knowledge --rebuild`
  loads `sentence-transformers/all-MiniLM-L6-v2`, the
  `okf_section_embedding` vector index reaches `ONLINE` with 384
  dimensions and cosine similarity, and `oneo vector-search "customer
  billing"` returns ranked results with document ID, section ID,
  heading, score, and source path.

Despite this, the work was **never committed**. `git status` at
review time showed `src/oneo/embedding.py` and
`tests/unit/test_embedding.py` as untracked, and
`src/oneo/{cli,models,neo4j_store,pipeline}.py`,
`tests/integration/test_pipeline.py`, and `pyproject.toml`/`uv.lock`
as modified in the working tree, still sitting uncommitted on top of
commit `d34bd07` (Step 00402/00403).

This is the same uncommitted-step pitfall already documented in
AGENTS.md, now recurring a sixth time (previously steps 00101, 00304,
00400, and 00402 — see AGENTS.md "Key Pitfalls"/"Lessons Learned").
An uncommitted step is not durable or reproducible from a clean
checkout, even though the working tree is correct. Per AGENTS.md:
"Treat 'run `git status` and commit' as a mandatory last action item
on every implementation step."

## Actions

1. Run `git status` and `git diff` to review every change belonging to
   Step 00500: `src/oneo/embedding.py` (new), `src/oneo/cli.py`,
   `src/oneo/models.py`, `src/oneo/neo4j_store.py`,
   `src/oneo/pipeline.py`, `pyproject.toml`, `uv.lock`, and the
   corresponding test files `tests/unit/test_embedding.py` (new) and
   `tests/integration/test_pipeline.py`.
2. Stage exactly those files (do not include unrelated in-flight work,
   and do not touch the immutable files under `doc/plan/steps/`).
3. Commit with a message referencing Step 5 / Step 00500, following
   the existing commit message style (see `git log --oneline`).
4. Verify with `git status` that the working tree is clean with
   respect to these files after the commit.
5. Do not move or edit the immutable step file
   `doc/plan/steps/in-review/00500-add-embeddings.md`; only the step's
   own commit is missing, not its record.

## Secondary finding (Boy Scout, non-blocking)

The step's completion record states "Complexity deviation: None", but
the actual net new production LOC across
`src/oneo/{embedding,cli,models,neo4j_store,pipeline}.py` is
approximately 365 lines (106 new file + 259 net additions to existing
files), well above the step's own 150–250 target range. This does not
block the step (the implementation is correct, minimal, and free of
prohibited abstractions), but the completion record's deviation field
is inaccurate and should be reported honestly in future steps so LOC
trends are visible to reviewers without requiring a manual recount.
