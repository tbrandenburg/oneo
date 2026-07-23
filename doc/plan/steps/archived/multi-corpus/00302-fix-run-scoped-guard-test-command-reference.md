> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# 13. Implementation

## Step 3a-gap (gap) — Fix stale test-file reference in Step 3a's E2E validation command

### Gap

Step `00301-test-run-scoped-guard.md`'s "End-to-end validation" section
specifies the command:

```bash
uv run pytest tests/unit/test_neo4j_store.py tests/integration/test_neo4j_store.py -q
```

However, the unit tests satisfying that step's Implementation item 1
were actually created at `tests/unit/test_neo4j_store_run_scoped.py`,
not `tests/unit/test_neo4j_store.py` (no file with that exact name
exists anywhere under `tests/unit/`). Re-running the step's literal
command produces:

```
ERROR: file or directory not found: tests/unit/test_neo4j_store.py
no tests ran in 0.00s
```

The actual test content is correct and fully covers the guard (verified
independently, including confirming all three guard-specific tests fail
when the `if not corpus: raise ValueError(...)` check is temporarily
removed from `_run_scoped`, and pass with it restored). This is a
documentation-only discrepancy in the closed step file, which is
immutable and must not be edited. Because a future auditor or CI script
that copy-pastes the step's literal validation command will get a false
"file not found" failure instead of the intended pass/fail signal, the
correct command should be recorded going forward (e.g. in CI config or
developer docs) rather than left only in the immutable, incorrect step
file.

### Implementation

1. Wherever the Step 3a validation command is relied upon outside the
   immutable step file itself (CI workflow, README/dev docs, Makefile
   targets, etc.), use the correct path:
   ```bash
   uv run pytest tests/unit/test_neo4j_store_run_scoped.py tests/integration/test_neo4j_store.py -q
   ```
2. No production or test code changes are required — this gap is purely
   about not propagating the stale filename into any other
   currently-mutable location.

### Delivery constraints

| Metric                 |         Target |
| ----------------------- | --------------: |
| New production LOC      |               0 |
| Unit tests               |     Not required |
| Integration tests        |     Not required |
| E2E validation           |        Required |
| Engineering checkpoint   |        Required |

### End-to-end validation

Run:

```bash
uv run pytest tests/unit/test_neo4j_store_run_scoped.py tests/integration/test_neo4j_store.py -q
```

Confirm it exits 0, and confirm no other currently-mutable file (CI
config, docs, Makefile) references the incorrect
`tests/unit/test_neo4j_store.py` path.
