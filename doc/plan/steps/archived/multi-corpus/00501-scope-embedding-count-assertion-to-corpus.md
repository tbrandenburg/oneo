> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-fill for Step 5 — Prove Corpus Isolation, Reframe Docs, Update Demo

### Objective

Fix a latent test-isolation bug in
`tests/integration/test_pipeline.py::test_index_with_embeddings_generates_vectors`
that is now guaranteed to fail whenever the standard multi-corpus demo
data (`billing`, `engineering`, indexed by `./scripts/demo.sh`) is
present in the shared Neo4j database.

### Why this matters

`test_index_with_embeddings_generates_vectors` indexes a `tmp_path`
fixture corpus registered under the name `"test"`, then asserts:

```python
records = store._run(
    "MATCH (s:OkfSection) RETURN s.embedding AS embedding, ..."
)
assert len(records) == 2
```

This query is **not scoped to `corpus: "test"`**, so it counts every
`OkfSection` node in the whole database, regardless of which corpus
owns it. Before this step, running `./scripts/demo.sh` left one extra
demo corpus (`./knowledge`) indexed in the shared Neo4j instance, which
already had the potential to break this exact assertion — but Step 5
changed the demo to index **two** corpuses (`billing` and
`engineering`) as its normal, documented, steady-state artifact of
running the required E2E validation (`./scripts/demo.sh`). Verified
independently during this step's review:

```bash
$ uv run pytest -q
...
AssertionError: assert 12 == 2
```

The failure reproduces reliably any time `pytest` is run in a
database that also holds the demo's `billing`/`engineering` sections
(6 + 4 = 10, plus the fixture's own 2 = 12) — i.e. any time a
developer or CI job runs `./scripts/demo.sh` (as instructed by
README.md and by this project's own E2E validation) and then runs the
test suite without first calling `oneo reset --corpus billing` and
`oneo reset --corpus engineering`. This is exactly the kind of
uncorpus-scoped query the codebase's own Neo4j lessons repeatedly warn
about (see AGENTS.md's `reset()`/`index_owner` global-scope pitfalls),
but this particular test slipped through because a single-corpus
demo previously masked it well enough that `len(records) == 2` mostly
happened to hold in practice.

Left unfixed, this will intermittently and confusingly break CI/local
runs for every future step that happens to run the full test suite
after `./scripts/demo.sh`, with a failure message that gives no hint
that the real cause is demo-corpus pollution rather than a real
regression in embedding generation.

### Implementation

1. In `tests/integration/test_pipeline.py`, scope the Cypher query in
   `test_index_with_embeddings_generates_vectors` to the fixture's own
   corpus, e.g.:

   ```python
   records = store._run(
       "MATCH (s:OkfSection {corpus: $corpus}) RETURN s.embedding AS embedding, "
       "s.embedding_model AS embedding_model, "
       "s.embedding_dimensions AS embedding_dimensions, "
       "s.embedding_input_hash AS embedding_input_hash",
       corpus="test",
   )
   ```

   (matching the corpus name already used by this test's
   `_registry_for(root)` fixture helper).
2. Audit the rest of `tests/integration/test_pipeline.py` (and any
   other integration/e2e test using an unscoped `MATCH (s:OkfSection)`
   or `MATCH (d:OkfDocument)` query) for the same pattern; scope every
   such query to the fixture's own corpus name so tests remain correct
   regardless of what other corpuses happen to be indexed in the
   shared database at the time.

### End-to-end validation

```bash
uv run oneo index --corpus billing --rebuild
uv run oneo index --corpus engineering --rebuild
uv run pytest -q
```

Validate that the full suite passes with the demo's `billing` and
`engineering` corpuses left indexed in Neo4j (i.e. do not reset them
before running pytest) — this is the exact steady state a developer
following the README's demo instructions will be in.

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
```
