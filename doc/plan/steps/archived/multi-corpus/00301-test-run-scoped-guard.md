> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# 13. Implementation

## Step 3a (gap) — Unit Test Coverage for the `_run_scoped` Corpus Guard

### Gap

Step 3 (`00300-corpus-scoped-neo4j-projection.md`) introduced
`Neo4jStore._run_scoped`, explicitly described in its own docstring and
in the step's Implementation item 9 as the mechanism that "converts
corpus isolation from a per-query convention into a structurally
enforced guarantee" by raising when `corpus` is missing or empty,
closing the single-forgotten-filter failure mode on the destructive
`reset` path in particular.

This guard has zero test coverage. A full repo-wide search
(`grep -rn "_run_scoped\|corpus is required" tests/`) finds no test
anywhere that exercises the empty/`None`/missing-corpus branch of
`_run_scoped`, on `reset` or on any of the other eleven store methods
routed through it. The step's own review manually confirmed the guard
works today, but nothing in the test suite would catch a future
regression (e.g. someone refactoring `_run_scoped` and dropping the
`if not corpus: raise ...` check, or a caller accidentally passing
`corpus=""`) — precisely the safety property this seam exists to
guarantee is the one thing not automatically verified.

### Implementation

1. Add a unit test (no live Neo4j required — this can be a plain unit
   test against `Neo4jStore._run_scoped` using a stub/mock driver, or a
   focused integration test if a unit-level stub is impractical) that
   asserts `_run_scoped` raises `ValueError` for each of: `corpus=""`,
   `corpus=None` (if the type checker/tests allow exercising the
   runtime path), and confirms no query is executed against the driver
   in that case (i.e. the guard short-circuits before any network call).
2. Add at least one integration test that calls `store.reset("")` (the
   most safety-critical caller) and asserts it raises `ValueError`
   without deleting any data, to cover the guard on the actual
   destructive path end-to-end.
3. Do not weaken or change `_run_scoped` itself — this is a test-only
   gap fill.

### Delivery constraints

| Metric                 |         Target |
| ----------------------- | --------------: |
| New production LOC      |               0 |
| Unit tests               |        Required |
| Integration tests        |        Required |
| E2E validation           |     Not required |
| Engineering checkpoint   |        Required |

### End-to-end validation

Run:

```bash
uv run pytest tests/unit/test_neo4j_store.py tests/integration/test_neo4j_store.py -q
```

Validate that the new tests fail if the `if not corpus: raise
ValueError(...)` guard is temporarily removed from `_run_scoped`, and
pass with it present.
