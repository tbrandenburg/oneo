> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# 13. Implementation

## Step 5 — Prove Corpus Isolation, Reframe Docs, Update Demo

### Objective

Demonstrate end to end that corpuses are fully isolated and each remains
independently rebuildable from its filesystem; then update the demo
script and surgically reframe all documentation away from "proof of
concept" / single-corpus framing to a clean multi-corpus feature set.

### Implementation

Create an end-to-end test that:

1. registers two corpuses with a fixture `corpuses.toml`, including at
   least one identical relative path in both corpuses with different
   content
2. indexes both corpuses (with embeddings)
3. asserts each corpus's counts and exports are correct and disjoint
4. edits a section in corpus A, rebuilds corpus A, and verifies corpus
   A updated while corpus B is byte-for-byte unchanged
5. adds a Markdown link in corpus A, rebuilds, verifies the new edge
   exists only in corpus A
6. deletes a file in corpus A, rebuilds, verifies its document,
   sections, vectors, and relationships disappear from corpus A only
7. resets corpus A entirely and verifies corpus B remains fully indexed
   and queryable
8. runs a retrieval/query against corpus B and asserts no corpus-A
   content appears

No direct database mutation may be used to prepare expected state.

Then:

9. Extend `scripts/demo.sh` to index two corpuses and print a summary
   proving isolation (each corpus's counts, a query per corpus, and an
   isolation check). Replace `PoC status:` framing with a
   multi-corpus status summary.
10. Surgically reframe documentation and metadata away from
    "proof of concept" and single-corpus assumptions:

    * `README.md` — describe Oneo as a multi-corpus OKF knowledge index;
      remove the "proof of concept, not a production system" framing;
      document `corpuses.toml`, `--corpus`, and per-corpus rebuild;
      replace every example command that passes `./knowledge` as a
      positional argument (e.g. `oneo files ./knowledge`, `oneo validate
      ./knowledge --strict`, `oneo index ./knowledge --rebuild`, `oneo
      verify ./knowledge`) with an equivalent `--corpus <name>` example.
    * `AGENTS.md` — update Purpose/Goals/Constraints so a corpus is the
      unit of ingestion; make `document_id` = corpus-scoped
      bundle-relative path; keep `multi-tenant` a non-goal but state
      explicitly that **multiple corpuses are supported and native**, so
      the guidelines never read as forbidding multiple corpuses.
    * `pyproject.toml`, `src/oneo/__init__.py`, CLI Typer help,
      `CHANGELOG.md` — drop "proof of concept" wording.
    * Add `corpuses.toml.example` (and update `.env.example` to drop
      `ONEO_KNOWLEDGE_ROOT`, add `ONEO_CORPUS_CONFIG` /
      `ONEO_DEFAULT_CORPUS`).
    * Archived material under `doc/plan/steps/archived/oneo-poc/` and
      `doc/plan/demo/oneo-poc/` is historical record and is explicitly
      out of scope for this cleanup — do not edit it, and exclude it
      from the acceptance grep below.

### Delivery constraints

| Metric                 |                 Target |
| ---------------------- | ---------------------: |
| New production LOC     |                100–200 |
| Unit tests             |              As needed |
| Integration tests      | Required against Neo4j |
| E2E validation         |               Required |
| Engineering checkpoint |               Required |

### End-to-end validation

From a clean checkout:

```bash
docker compose down -v
cp .env.example .env
cp corpuses.toml.example corpuses.toml
./scripts/demo.sh
```

Required output includes, per corpus:

```text
Corpus billing: indexed, retrieval PASS, query PASS
Corpus engineering: indexed, retrieval PASS, query PASS
Corpus isolation: PASS
Rebuild-from-filesystem (per corpus): PASS
Multi-corpus status: SUCCESS
```

And:

```bash
pytest tests/e2e/test_corpus_isolation.py
```

Validate that:

* the isolation test passes without any direct database mutation
* the pre-existing pipeline E2E tests, retargeted to a named corpus,
  still pass (proving the core pipeline is unchanged, only corpus-scoped)
* a repo-wide grep for `knowledge_root`, `KNOWLEDGE_ROOT`, and
  `proof of concept`/`PoC`, excluding `doc/plan/steps/archived/` and
  `doc/plan/demo/`, returns zero matches

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
Corpus isolation: PASS
```

