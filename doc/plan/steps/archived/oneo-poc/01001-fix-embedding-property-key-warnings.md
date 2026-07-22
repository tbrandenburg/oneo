> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-fill — Register embedding property key tokens to silence Neo4j warnings

## Why this matters

Running `./scripts/demo.sh` from a clean checkout (Step 01000's own
required E2E validation, on a freshly reset database) produces four
Neo4j driver warnings during the indexing step, one for each embedding
property queried by `Neo4jStore.sections_needing_embedding`:

```
warn: property key does not exist. The property `embedding` does not exist...
warn: property key does not exist. The property `embedding_model` does not exist...
warn: property key does not exist. The property `embedding_dimensions` does not exist...
warn: property key does not exist. The property `embedding_input_hash` does not exist...
```

This is the exact same class of issue already fixed once in Step 00402
for `LINKS_TO.target_anchor`: on a database where a property key has
*never* been set on any node, Neo4j has not registered the property key
token, and any `RETURN s.<property>` (even wrapped implicitly, as here)
triggers the "property key does not exist" notification for every
matching row — it is a schema/token-level check, not a per-row one.
`sections_needing_embedding` (added in Step 00500) reads
`s.embedding`, `s.embedding_model`, `s.embedding_dimensions`, and
`s.embedding_input_hash` before any embeddings have ever been written
(i.e. on the very first `oneo index` run after `oneo reset`), so this
fires on every clean-checkout demo run — exactly the scenario the
Step 01000 E2E validation is supposed to prove works cleanly. Left
unfixed, this noise will mask a real future schema regression the same
way the `target_anchor` warning would have.

## Actions

1. In `src/oneo/neo4j_store.py::apply_schema`, add index statements
   that register the `embedding`, `embedding_model`,
   `embedding_dimensions`, and `embedding_input_hash` property key
   tokens unconditionally (mirroring the existing
   `okf_links_to_target_anchor` index added in Step 00402), e.g.:
   ```cypher
   CREATE INDEX okf_section_embedding_model IF NOT EXISTS
   FOR (s:OkfSection) ON (s.embedding_model)
   CREATE INDEX okf_section_embedding_input_hash IF NOT EXISTS
   FOR (s:OkfSection) ON (s.embedding_input_hash)
   CREATE INDEX okf_section_embedding_dimensions IF NOT EXISTS
   FOR (s:OkfSection) ON (s.embedding_dimensions)
   ```
   Note `s.embedding` itself is already registered indirectly by the
   vector index (`create_vector_index`), but confirm this empirically
   rather than assuming — the vector index may only be created *after*
   `sections_needing_embedding` runs on the very first index, so the
   ordering of `apply_schema()` / `create_vector_index()` /
   `sections_needing_embedding()` in `pipeline.py`'s `index()` method
   may need adjusting so all four tokens exist before the first read.
2. Confirm the fix by running, from a clean checkout:
   ```bash
   docker compose down -v
   cp .env.example .env
   ./scripts/demo.sh
   ```
   and checking the full script output (not just exit code) contains
   no "property key does not exist" driver warnings.
3. Add/extend a unit or integration test asserting that calling
   `sections_needing_embedding` against a freshly reset (never
   embedded) database emits no Neo4j driver warning.
4. Re-run the full test suite (`pytest tests/unit tests/integration`)
   and confirm all tests still pass.
