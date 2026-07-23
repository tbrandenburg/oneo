# Oneo — Multi-Corpus Handover

## a. Executive summary

Oneo indexes one or more Open Knowledge Format (OKF) repositories —
**corpuses** — into a single shared Neo4j database and uses the
resulting graph for hybrid (vector + full-text), graph-expanded,
grounded retrieval, one corpus at a time.

This milestone (v2) turned the original single-corpus proof of concept
into a small, serious **multi-corpus** tool. It is a clean breaking
change, not an add-on: there is no single global `knowledge_root`
anymore. Instead, any number of named OKF bundles (e.g. `billing`,
`engineering`) are registered in `corpuses.toml`, each rooted at its own
directory. Every document, section, embedding, and relationship written
to Neo4j is tagged with the owning corpus, every retrieval and answer is
scoped to exactly one selected corpus, and every corpus can be reset and
rebuilt from its own filesystem without touching any other corpus.

The work was delivered in five main steps plus targeted gap-fills:

1. Corpus registry and configuration (`corpuses.toml`, `Corpus`,
   `CorpusRegistry`, `oneo corpus list/info`).
2. Threading the selected corpus through the whole pipeline
   (`--corpus` on every CLI command, corpus-aware coordinator methods).
3. Corpus-scoped Neo4j projection (composite uniqueness constraints,
   corpus property on every node/edge, a structurally-enforced
   `_run_scoped` guard that makes it impossible to issue a corpus-scoped
   query — including the destructive `reset` path — without a corpus
   filter).
4. Corpus-scoped retrieval and answering (vector search, full-text
   search, graph expansion, and citations all filtered to one corpus,
   using shared indexes with a `WHERE` clause rather than per-corpus
   indexes).
5. An end-to-end isolation proof, a two-corpus demo script, and a
   documentation reframe away from proof-of-concept / single-corpus
   language.

Two gap-fill steps hardened test coverage (`_run_scoped` guard unit
tests, corpus-scoped embedding-count assertions) after review found
untested or database-state-dependent assertions.

## b. What works — with evidence

All claims below were re-verified end-to-end in this handover run (see
linked artefacts in this directory).

| Feature | Evidence |
| --- | --- |
| Corpus registry: list/inspect registered corpuses | [`05-corpus-list.txt`](05-corpus-list.txt), [`06-corpus-info-billing.txt`](06-corpus-info-billing.txt), [`07-corpus-info-engineering.txt`](07-corpus-info-engineering.txt) |
| Strict OKF validation passes for both demo corpuses | [`08-validate-billing-strict.txt`](08-validate-billing-strict.txt), [`09-validate-engineering-strict.txt`](09-validate-engineering-strict.txt) |
| Full indexing into Neo4j (documents, sections, links, embeddings), per corpus | [`02-demo-sh-full-pipeline.txt`](02-demo-sh-full-pipeline.txt) |
| Filesystem-vs-graph verification per corpus | [`10-verify-billing.txt`](10-verify-billing.txt), [`11-verify-engineering.txt`](11-verify-engineering.txt) |
| Hybrid (vector + full-text) retrieval with rank-fusion diagnostics, scoped per corpus | [`12-retrieve-billing.txt`](12-retrieve-billing.txt), [`13-retrieve-engineering.txt`](13-retrieve-engineering.txt) |
| One-hop graph expansion within a corpus (`overview -> LINKS_TO -> topics/related`) | [`12-retrieve-billing.txt`](12-retrieve-billing.txt) |
| Grounded, cited answer generation per corpus | [`14-query-billing-with-citations.txt`](14-query-billing-with-citations.txt), [`15-query-engineering-with-citations.txt`](15-query-engineering-with-citations.txt) |
| Explicit "insufficient evidence" handling for unanswerable/off-topic questions | [`16-query-insufficient-evidence.txt`](16-query-insufficient-evidence.txt) |
| Full corpus isolation: identical relative paths, edits, link additions, deletions, and resets in one corpus never affect another | [`02-demo-sh-full-pipeline.txt`](02-demo-sh-full-pipeline.txt) (`Corpus isolation: PASS`, `Rebuild-from-filesystem: PASS`), [`03-test-corpus-isolation-e2e.txt`](03-test-corpus-isolation-e2e.txt) |
| Whole test suite (unit + integration + e2e) green | [`01-pytest-full-suite-184-passed.txt`](01-pytest-full-suite-184-passed.txt) — 184 passed |
| CLI surface (`corpus`, `files`, `parse`, `validate`, `index`, `retrieve`, `query`, `reset`, `verify`, `vector-search`, `health`) | [`04-cli-help.txt`](04-cli-help.txt) |

All artefacts were produced by a real run against a live Neo4j 5.26
instance and the real `sentence-transformers/all-MiniLM-L6-v2` embedding
model — no mocking, stubbing, or skipped steps.

## c. How to build and run

Requires [uv](https://docs.astral.sh/uv/) and Docker.

1. `uv sync`
2. `cp .env.example .env`
3. `cp corpuses.toml.example corpuses.toml`
4. `docker compose up -d neo4j`
5. `uv run oneo health` — confirm connectivity.
6. `uv run oneo index --corpus billing --rebuild`
7. `uv run oneo index --corpus engineering --rebuild`
8. `uv run oneo query "How are customers billed?" --corpus billing --show-sources --show-paths`

Or, to reproduce the entire pipeline (both demo corpuses, retrieval,
graph expansion, answering, rebuild-from-filesystem, and an isolation
check) in one command from a clean checkout:

```bash
docker compose down -v
cp .env.example .env
cp corpuses.toml.example corpuses.toml
./scripts/demo.sh
```

Expected final lines:

```text
Corpus billing: indexed, retrieval PASS, query PASS
Corpus engineering: indexed, retrieval PASS, query PASS
Corpus isolation: PASS
Rebuild-from-filesystem (per corpus): PASS
Multi-corpus status: SUCCESS
```

## d. How to test

| Action | Expected result |
| --- | --- |
| `uv run oneo corpus list` | Lists `billing` and `engineering` with their filesystem roots |
| `uv run oneo validate --corpus billing --strict` | `0 diagnostic(s)` |
| `uv run oneo index --corpus billing --rebuild` then `uv run oneo verify --corpus billing` | Filesystem and graph document/section/link counts match exactly |
| `uv run oneo retrieve "How are customers billed?" --corpus billing --mode graph-hybrid --explain` | Only `billing` sections appear as seeds/expansions; no `engineering` content |
| `uv run oneo retrieve "How are customers billed?" --corpus engineering --mode hybrid --explain` | No billing-specific sections (e.g. invoices, subscriptions) appear |
| `uv run oneo query "How are customers billed?" --corpus billing --show-sources` | A grounded answer with `[S1]`-style citations, each resolving to a real `billing` section path |
| `uv run oneo query "What is the boiling point of mercury?" --corpus billing --show-sources` | `insufficient_evidence: True` and answer `insufficient evidence`, not a fabricated answer |
| `uv run oneo reset --corpus billing` then `uv run oneo verify --corpus engineering` | `engineering` counts are unaffected by resetting `billing` |
| `uv run pytest -q` | All tests pass (184 at time of writing) |
| `uv run pytest tests/e2e/test_corpus_isolation.py` | Passes, proving isolation without any direct database mutation |

After running tests or the isolation check, re-run
`uv run oneo index --corpus billing --rebuild` and
`uv run oneo index --corpus engineering --rebuild` before manually
exploring `retrieve`/`query` again, since `reset`/isolation tests
mutate the shared database.

## e. Known limitations

- Multi-corpus here means several named, operator-managed bundles
  queried one at a time — it is explicitly **not** multi-tenant
  (isolated, access-controlled tenants). There is no per-corpus access
  control; anyone who can reach the CLI/Neo4j can query or reset any
  registered corpus.
- Cross-corpus / federated retrieval is out of scope by design: a query
  only ever returns results from the one `--corpus` selected.
- No filesystem watching or incremental ingestion — every `index` run
  re-scans the corpus's full filesystem bundle.
- No remote/URL ingestion; corpus roots must be local directories under
  the enforced knowledge boundary.
- `Neo4jStore.reset()` deletes all `index_owner="oneo"` data matching
  the given corpus, but shares one physical Neo4j database with every
  other registered corpus — running integration/e2e tests that index a
  throwaway corpus (e.g. `test`) and then resetting it is safe, but
  operators should still avoid pointing two differently-configured
  `Oneo` deployments at the same Neo4j database with mismatched corpus
  registries.
- No production authentication/authorization or high-availability
  deployment story; this remains a single-operator tool as documented
  in the project's non-goals.
- General document conversion (PDF/DOCX/PPTX) is not supported; only
  Markdown (`.md`/`.markdown`) OKF bundles are ingested.
