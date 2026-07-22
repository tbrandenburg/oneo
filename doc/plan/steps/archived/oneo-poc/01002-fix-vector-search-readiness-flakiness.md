> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-fill — Fix vector-search readiness flakiness causing intermittent empty retrieval results

## Why this matters

While independently re-verifying Step 01001's E2E check (`./scripts/demo.sh`
from a clean checkout, `docker compose down -v` + fresh volume), the demo
intermittently fails *after* indexing completes successfully and
`Vector index: ONLINE` / `Full-text index: ONLINE` are both reported:

```
== Hybrid retrieval ==
PoC status: FAILURE
hybrid retrieval returned no seed hits
```

or, on a different run, later in the pipeline:

```
== Graph expansion ==
PoC status: FAILURE
graph expansion returned no expanded hits
```

`pytest tests/unit tests/integration` shows the same symptom: on a full
suite run (but not always when the affected test is run in isolation),
several `tests/integration/test_pipeline.py` tests fail with
`result.hits == ()` or `AnswerResult(insufficient_evidence=True)` even
though the corpus was just indexed with `embeddings=True` in the same
test. This was reproduced identically on the commit *before* Step 01001's
change (`32db19b`), confirming Step 01001 did not introduce it — but it
currently blocks Step 01001's own required action 4 ("re-run the full
test suite ... confirm all tests still pass") and undermines confidence
in `./scripts/demo.sh` as the promised single reproducible E2E proof
(Step 01000's stated goal).

The likely root cause: `wait_for_vector_index_online()` (and the
full-text equivalent) polls Neo4j's `SHOW VECTOR INDEXES YIELD state`
until it reports `'ONLINE'`, but `state = 'ONLINE'` does not guarantee
the index is immediately queryable via
`db.index.vector.queryNodes(...)` — there can be a further short lag
between the index reporting online and results actually being served,
or the seed/expansion query path may have its own race (e.g. reading
stale session data, or a query issued against a different session/
routing table before the write is visible). This needs root-causing,
not just papered over with a longer fixed sleep.

## Actions

1. Reproduce reliably: write a tight repro script or test that runs
   `docker compose down -v`, waits for readiness, runs `oneo index
   ./knowledge --rebuild`, and immediately runs `oneo retrieve` (or the
   equivalent `Oneo.retrieve()` call) in a loop, to characterize how
   often and how long after `ONLINE` the empty-hits condition occurs.
2. Inspect `wait_for_vector_index_online` / `wait_for_fulltext_index_online`
   in `src/oneo/neo4j_store.py` and the retrieval/query path in
   `src/oneo/pipeline.py` and `src/oneo/retrieval.py` (or wherever hybrid
   fusion lives) for a race between "index reports ONLINE" and "index
   actually returns matches for a just-written vector."
3. Fix the race at its root (e.g. an additional readiness probe that
   issues a real `db.index.vector.queryNodes` call against a known
   just-written embedding and retries until it returns a match, rather
   than trusting `SHOW VECTOR INDEXES` state alone; or a documented,
   bounded retry/backoff at the retrieval call site with a clear
   rationale) — avoid unconditionally lengthening timeouts as the only
   fix without understanding why `ONLINE` state is insufficient.
4. Confirm the fix: run `pytest tests/unit tests/integration` at least 3
   times in a row and confirm zero flaky failures in
   `tests/integration/test_pipeline.py`. Run `./scripts/demo.sh` from a
   clean checkout (`docker compose down -v`) at least 3 times in a row
   and confirm `PoC status: SUCCESS` every time with no seed/expansion
   hit failures.
5. After confirming the fix, re-run `oneo index ./knowledge --rebuild`
   once more against the real `./knowledge` demo corpus, per the
   existing AGENTS.md lesson about `reset()` being global — the repeated
   `docker compose down -v` cycles and test runs performed while
   investigating this gap will otherwise leave the demo index stale or
   deleted for the next manual validation.
