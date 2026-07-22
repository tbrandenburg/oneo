> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-fill — Add regression tests for the vector-search readiness race fix

## Why this matters

Step 01002 fixed two concrete races in `src/oneo/neo4j_store.py`:

1. `vector_search()` now catches the Neo4j `Neo.ClientError.Procedure.
   ProcedureCallFailed` ("no such vector schema index") error and
   returns `[]` instead of raising, so callers that may run before the
   vector index has ever been created (e.g. `best_section_in_document`,
   and `wait_for_vector_index_queryable` itself right after
   `create_vector_index`) don't hard-fail.
2. `wait_for_vector_index_queryable()` now probes with `top_k=10`
   instead of `top_k=1` so a transient stale/deleted-node tie under
   repeated reset/rebuild churn can't rank ahead of the real
   just-written section and hide it from the readiness check.

Both fixes were verified empirically (3+ consecutive clean
`pytest`/`./scripts/demo.sh` runs), but neither behavior has a
dedicated unit or integration test. `tests/integration/test_neo4j_store.py`
has no test that calls `vector_search()` against a store where the
vector index has never been created, and no test that exercises
`wait_for_vector_index_queryable`'s `top_k=10` tie-tolerance. Without
such a test, a future refactor of `vector_search` or
`wait_for_vector_index_queryable` (e.g. someone "simplifying" the
`try`/`except Neo4jError` block, or reverting `top_k` back to `1` for
readability) could silently reintroduce the exact flakiness Step 01002
fixed, and the existing full-suite/demo runs used to verify the fix
are not reliable enough on their own to catch a regression (the whole
point of Step 01002 is that the race is intermittent and load-dependent).

## Actions

1. Add an integration test in `tests/integration/test_neo4j_store.py`
   that calls `store.vector_search(...)` against a freshly-reset store
   where `create_vector_index` has not yet been called (or the vector
   index otherwise does not exist), and asserts it returns `[]` rather
   than raising.
2. Add an integration test (or extend an existing one) that documents
   the `top_k=10` tie-tolerance behavior of
   `wait_for_vector_index_queryable` — at minimum, assert it still
   returns `True` when other non-matching sections exist in the graph
   alongside the sample section (i.e. the sample section does not have
   to be the single top-ranked match to be found).
3. Run `pytest tests/unit tests/integration` and confirm the new tests
   pass alongside the full existing suite, with no regressions.
