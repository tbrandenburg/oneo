> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# 13. Implementation

## Step 1 — Corpus Registry and Configuration

### Objective

Introduce the corpus concept as configuration only: a `Corpus` model, a
`CorpusRegistry` that loads named corpuses from a required
`corpuses.toml`, and CLI commands to list and describe them. Remove the
single `knowledge_root` setting and its implicit global pipeline. No
graph or retrieval behavior changes yet.

### Implementation

1. Add `src/oneo/corpus.py` with the frozen `Corpus` dataclass and the
   `CorpusRegistry`.
2. Load `corpuses.toml` with `tomllib`; resolve the path from
   `ONEO_CORPUS_CONFIG` (default `corpuses.toml` in the working
   directory).
3. Require at least one corpus. A missing/empty config is a clear
   configuration error — there is no `knowledge_root` fallback.
4. Validate corpus names against a strict slug pattern
   (`[a-z0-9][a-z0-9-]*`); reject duplicates and empty roots with clear
   errors.
5. In `config.py`, remove `knowledge_root` — including its field
   docstring and any prose describing it as the canonical root — and add
   `ONEO_CORPUS_CONFIG` and an optional `ONEO_DEFAULT_CORPUS` name.
6. Add a thin `oneo corpus` command group:

   * `oneo corpus list` — print each corpus name and root.
   * `oneo corpus info <name>` — print one corpus's name and resolved
     root, and whether the root exists.

7. Keep CLI handlers thin; delegate to the registry.
8. Create the committed demo corpuses defined in §10: seed
   `corpuses/billing` from the existing `./knowledge` bundle (move it),
   author a distinct `corpuses/engineering` bundle, add an identical
   bundle-relative path in both with different content, ensure both pass
   `oneo validate --strict`, and add a `corpuses.toml.example`
   registering both. Remove the now-orphaned top-level `./knowledge`
   bundle.
9. Remove proof-of-concept framing from the Typer app help,
   `src/oneo/__init__.py`, and `pyproject.toml` description as part of
   this step's surface change (full doc reframing lands in Step 5).
10. Update `Makefile`: remove the `KNOWLEDGE_ROOT`/`./knowledge` default
    and help text, and replace the `validate`/`index` targets with
    corpus-scoped invocations (e.g. `--corpus $(CORPUS)`, with a
    documented default corpus).

### Do not implement

* any Neo4j change
* any corpus property on nodes
* threading corpus into `index`/`retrieve`/`query`
* corpus add/remove mutation commands (config is edited by hand)
* a corpus-source plugin system

### Delivery constraints

| Metric                 |   Target |
| ---------------------- | -------: |
| New production LOC     |  150–250 |
| Unit tests             | Required |
| Integration tests      | As needed |
| E2E validation         | Required |
| Engineering checkpoint | Required |

### End-to-end validation

Run:

```bash
oneo corpus list
oneo corpus info billing
```

Validate that:

* a missing/empty `corpuses.toml` fails with a clear configuration
  error and non-zero exit code (no `knowledge_root` fallback)
* with the committed two-corpus `corpuses.toml`, both `billing` and
  `engineering` are listed with correct, existing roots
* `oneo corpus info <unknown>` fails with a clear error and non-zero
  exit code
* invalid corpus names and duplicate names are rejected on load
* both demo corpuses exist on disk and pass `oneo validate --strict`
* `overview.md` exists in both corpuses with different content
* no proof-of-concept string remains in `oneo --help`
* output is deterministic

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
Corpus isolation: PASS
```

