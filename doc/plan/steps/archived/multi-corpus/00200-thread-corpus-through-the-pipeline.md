> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# 13. Implementation

## Step 2 — Thread Corpus Through the Pipeline

### Objective

Make the `Oneo` coordinator and CLI corpus-aware by adding a corpus
selector to every command, resolving the corpus's root via the
registry, without yet changing what is written to or read from Neo4j.

### Implementation

1. Construct `Oneo` with (or give it access to) the `CorpusRegistry`.
2. Add an optional `corpus: str | None` parameter to `validate`,
   `index`, `discover`, `retrieve`, `query`, `reset`, `verify`, and
   `vector_search`. When `None`, use the registry's configured default
   corpus; if no default is resolvable, raise a clear error.
3. Resolve the selected corpus's root and use it as the effective
   knowledge root for discovery, parsing, and validation on that call.
   Remove every remaining reference to a global `settings.knowledge_root`.
4. Add a global `--corpus <name>` option to the CLI commands; default
   to the registry default when configured.
5. Keep `input_path` semantics: when omitted, default to the selected
   corpus's root; when given, it must still resolve within that
   corpus's root.
6. Leave `models.py`, `neo4j_store.py`, retrieval, and answering
   otherwise unchanged in this step (corpus is resolved to a root only,
   not yet persisted).
7. Migrate every test that constructs `Settings(knowledge_root=...)` to
   construct a corpus (a registered corpus or an equivalent
   `Corpus`/`CorpusRegistry` fixture) instead — named explicitly, this
   includes `tests/integration/test_pipeline.py` (~25 call sites) and
   `tests/e2e/test_filesystem_source_of_truth.py`. These files break as
   soon as `knowledge_root` is removed from `config.py` in this step, so
   their migration is owned here, not deferred to Step 5's general
   "retarget the pipeline E2E tests" note.

### Do not implement

* corpus property writes to Neo4j (Step 3)
* corpus filters in search Cypher (Step 4)
* new coordinator methods (corpus must be a parameter)

### Delivery constraints

| Metric                 |   Target |
| ---------------------- | -------: |
| New production LOC     |  100–200 |
| Unit tests             | Required |
| Integration tests      | As needed |
| E2E validation         | Required |
| Engineering checkpoint | Required |

### End-to-end validation

Run:

```bash
oneo files --corpus engineering
oneo validate --corpus billing --strict
```

Validate that:

* each command scans/validates the correct corpus's root
* omitting `--corpus` uses the configured default corpus (or errors
  clearly when none is configured)
* a path outside the selected corpus's root is rejected
* the coordinator surface still exposes exactly the documented methods
  (corpus is a parameter)
* no reference to a global `knowledge_root` remains anywhere in the code

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
Corpus isolation: PASS
```

