> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-fill — Commit Hybrid Retrieval (Step 6) to Git

## Why this matters

Step 00600 ("Implement Hybrid Retrieval") is fully and correctly
implemented on disk but was never committed to git. At review time the
working tree contained:

* `src/oneo/retriever.py` (new, 87 LOC) — reciprocal-rank fusion
* `tests/unit/test_retriever.py` (new, 132 LOC)
* Modifications to `src/oneo/cli.py` (new `retrieve` command),
  `src/oneo/config.py` (retrieval settings), `src/oneo/models.py`
  (`RetrievalHit`/`RetrievalResult`), `src/oneo/neo4j_store.py`
  (`fulltext_search`, `fulltext_index_state`,
  `wait_for_fulltext_index_online`, fulltext index schema), and
  `src/oneo/pipeline.py` (`Oneo.retrieve`)
* Modifications to `tests/integration/test_neo4j_store.py`,
  `tests/integration/test_pipeline.py`, `tests/unit/test_cli.py`

All unit tests (74 passed), integration tests against a live Neo4j
instance (27 passed), and manual E2E validation
(`oneo reset && oneo index ./knowledge --rebuild && oneo retrieve
"customer billing" --mode hybrid --explain`) passed, confirming:

* vector retrieval executes
* full-text retrieval executes
* fused results contain no duplicate sections
* a query matching both paths reports `retrieval_origin=both`
* every selected result exposes vector/lexical ranks, scores, and fused
  score
* repeated queries produce stable ordering (integration test asserts
  this explicitly)

This is a recurring pitfall (previously hit for steps 00100, 00300,
00302, 00304, 00400, 00402, 00500 — see AGENTS.md "Key pitfall" bullets
on the uncommitted-step issue). An implementation that is correct but
uncommitted is not durable or reproducible from a clean checkout.

## Actions

1. Run `git status` to confirm the exact set of changed/untracked files
   listed above (plus any other closed step files already moved into
   `doc/plan/steps/closed/` that are still untracked, e.g. 00305, 00400,
   00401, 00402, 00403, 00500, 00501).
2. `git add` the Step 6 implementation files:
   `src/oneo/retriever.py`, `tests/unit/test_retriever.py`,
   `src/oneo/cli.py`, `src/oneo/config.py`, `src/oneo/models.py`,
   `src/oneo/neo4j_store.py`, `src/oneo/pipeline.py`,
   `tests/integration/test_neo4j_store.py`,
   `tests/integration/test_pipeline.py`, `tests/unit/test_cli.py`.
3. Commit with a message describing the hybrid retrieval feature
   (e.g. "Implement hybrid retrieval with rank fusion (Step 6 / Step
   00600)").
4. Re-run `git status` after the commit and confirm the Step 6 files no
   longer appear as modified/untracked.
5. Move `doc/plan/steps/in-review/00600-implement-hybrid-retrieval.md`
   to `doc/plan/steps/closed/` as part of normal step lifecycle (this
   file itself remains immutable content-wise).
</content>
