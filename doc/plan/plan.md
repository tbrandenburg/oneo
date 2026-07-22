# Oneo — Multi-Corpus

## Implementation Plan and Engineering RFC

**Project name:** Oneo
**CLI command:** `oneo`
**Milestone:** v2 — a small, serious, multi-corpus OKF knowledge index (clean breaking change from the single-corpus proof of concept).

## 1. Purpose

The first milestone (see
[`doc/plan/steps/archived/oneo-poc/plan.md`](steps/archived/oneo-poc/plan.md))
proved that a single Open Knowledge Format (OKF) repository can be
deterministically projected into Neo4j and used for hybrid,
graph-enhanced retrieval. Everything in that first milestone assumes
exactly one corpus: one `knowledge_root`, one global ownership marker,
one flat set of `OkfDocument`/`OkfSection` nodes, and retrieval that
searches all indexed sections at once.

This document defines the plan to turn that proof of concept into a
small but serious tool — **Oneo v2** — that indexes and serves
**multiple, isolated knowledge corpuses** from a single Neo4j database,
while keeping the qualities that made the first milestone valuable:
simplicity, determinism, filesystem-as-source-of-truth, and a single
derived datastore.

A "corpus" is one named OKF bundle rooted at its own directory (for
example `billing`, `engineering-wiki`, `product-specs`). Multiple
corpuses coexist in one Neo4j database, are indexed and reset
independently, and are queried one at a time by name.

**This is a clean breaking change, not an incremental add-on.** Multiple
corpuses become the *native and only* model: there is no single-corpus
mode, no implicit global `knowledge_root` pipeline, and no compatibility
shim for pre-v2 graph data. Misleading proof-of-concept framing is
removed from the codebase and documentation, and the single-corpus
assumptions are cut rather than preserved behind a flag. The result is a
clean, intentional feature set with no legacy surface.

The change must remain deliberately small, explicit, and easy to
understand. It is not an invitation to build a multi-tenant platform:
multi-corpus (several named bundles a single operator indexes and
queries) is explicitly distinct from multi-tenant (isolated, access-
controlled tenants), which remains a non-goal.

---

# 2. Goals

* Register and describe multiple named OKF corpuses through simple,
  explicit configuration.
* Index each corpus independently, without one corpus's index run
  affecting another.
* Scope every derived Neo4j node and relationship to its owning corpus.
* Reset a single corpus without disturbing the others.
* Retrieve, expand, and answer against one explicitly selected corpus.
* Preserve document/section identities, anchors, links, and provenance
  per corpus, exactly as in the first milestone.
* Preserve full filesystem-first rebuild semantics **per corpus**: any
  single corpus can be deleted from Neo4j and rebuilt from its
  filesystem root alone.
* Make multiple corpuses the native model: every operation is corpus-
  scoped; there is no implicit global single-corpus pipeline.
* Cut misleading single-corpus and proof-of-concept framing from the
  code and docs, leaving a clean, intentional feature set.
* Keep the implementation understandable without extensive framework
  documentation, and keep the total production-code growth small.

---

# 3. Success Criteria

The milestone is considered successful when the following capabilities
are demonstrated:

* Two or more OKF corpuses can be registered and listed.
* Each corpus can be indexed independently into the same Neo4j
  database.
* Indexing or resetting one corpus provably does not add, change, or
  remove any node, relationship, or vector owned by another corpus.
* Retrieval and grounded query against a corpus return only sections
  belonging to that corpus.
* Graph expansion traverses only relationships within the selected
  corpus.
* Every answer citation resolves to an indexed section of the selected
  corpus.
* Deleting one corpus's derived data and rebuilding it from its
  filesystem root reproduces an identical normalized graph export for
  that corpus, while every other corpus remains untouched.
* The same demo script runs the complete pipeline against two corpuses
  and prints a pass/fail summary proving isolation.
* At least one corpus must be explicitly selected for every corpus-
  scoped command; there is no hidden global single-corpus fallback.
* No proof-of-concept or single-corpus framing remains in the shipped
  code, CLI help, or documentation.

Success is measured primarily by:

* correctness
* determinism
* isolation between corpuses
* simplicity
* traceability
* reproducibility

Feature completeness, retrieval-quality optimization, and scale are not
success criteria.

---

# 4. Non-Goals

This milestone deliberately excludes, in addition to every non-goal
already listed in the first-milestone plan and `AGENTS.md` (with the
`multi-tenant` non-goal explicitly *not* forbidding multiple corpuses —
multiple named bundles are now native; only tenant isolation and access
control remain out of scope):

* Cross-corpus / federated retrieval (a single query fanning out over
  several corpuses and merging results). Each retrieval targets exactly
  one corpus.
* Cross-corpus links or graph traversal between corpuses.
* A separate Neo4j database (or schema, or index) per corpus. All
  corpuses share one database and one pair of vector/full-text indexes,
  scoped by a `corpus` property.
* A second derived datastore, a corpus catalog service, or a metadata
  database.
* Per-corpus embedding models or configurable embedding models. The
  fixed `sentence-transformers/all-MiniLM-L6-v2` model still applies to
  every corpus.
* Multi-tenant access control, per-corpus authentication, or
  authorization.
* Corpus-level concurrency control, locking, or parallel indexing.
* Incremental ingestion, filesystem watching, or remote-URL corpuses.
* Dynamic corpus discovery from arbitrary filesystem layouts, a plugin
  system for corpus sources, or a corpus-registry framework.
* A web interface or MCP integration.

Cross-corpus retrieval may be reconsidered in a later milestone. It is
intentionally excluded here to keep the mental model — "pick a corpus,
query it" — simple and the code small.

---

# 5. Implementation Constraints

Every constraint from the proof-of-concept plan (§5 of the archived
plan) continues to apply unchanged, in particular:

* Prefer composition and mature libraries over custom infrastructure.
* Introduce a new abstraction only for a demonstrated present need.
* Keep persistence limited to a single Neo4j database.
* Keep the filesystem as the only canonical source, now **per corpus**.
* Keep public interfaces small and typed; no framework objects across
  boundaries.
* Optimize for readability over extensibility.
* Use `uv` for all dependency, environment, execution, and locking
  workflows.

Additional constraints specific to this milestone:

* The corpus dimension must be a **parameter**, never a new coordinator
  method: the `Oneo` public surface stays `validate`, `index`,
  `discover`, `retrieve`, `query`, `reset` (plus the existing read-only
  `verify` / `vector_search` diagnostics), with a corpus selector added
  to each. A corpus registry must not become a service locator,
  factory framework, or dependency-injection container.
* Corpus configuration must use the standard library only: parse a
  single TOML file with `tomllib` (available in Python 3.12). No new
  runtime dependency may be added for corpus configuration.
* Each corpus's root must be independently validated by
  `oneo.security.resolve_within_root` against **its own** configured
  root — the existing per-root path-security guarantees must hold for
  every corpus.
* Node and relationship identity must remain the OKF-derived
  identifiers (bundle-relative document paths, semantic section IDs).
  Corpus isolation is achieved by adding a `corpus` property plus a
  composite uniqueness constraint, **not** by hashing, renaming, or
  content-deriving identities.
* One shared vector index and one shared full-text index cover all
  corpuses; corpus isolation at query time is enforced by a `corpus`
  filter in the Cypher `WHERE` clause, exactly as `index_owner` already
  is. No per-corpus indexes may be created.
* This is a clean breaking change: do not preserve a single-corpus
  code path, an implicit global `knowledge_root` pipeline, or a
  compatibility shim for pre-v2 graph data. Every corpus-scoped command
  requires an explicit corpus selection (a configured default corpus
  name is acceptable, but the pipeline must always resolve to a named
  corpus — never to an unnamed global root).

A pull request that adds more than ~300 production LOC, a new runtime
dependency, a new persistence mechanism, a per-corpus index, or a new
public abstraction must include the standard complexity justification
block from §13 of the archived plan.

---

# 6. Architectural Decision

Add a single new orthogonal dimension — **corpus** — to the existing
pipeline, and thread it through discovery, parsing, projection,
retrieval, expansion, and answering. Do not restructure the pipeline.

```text
corpus registry (name -> root, from corpuses.toml; at least one corpus)
      ↓  select one corpus by name
OKF filesystem root for that corpus
      ↓
filesystem discovery and path validation   (unchanged, per-corpus root)
      ↓
OKF-aware loader                            (unchanged)
      ↓
OKF documents, sections, anchors, links     (+ corpus tag)
      ↓
corpus validation and link resolution        (unchanged, per corpus)
      ↓
Neo4j graph, vector index, full-text index   (+ corpus property, composite key)
      ↓
vector and lexical retrieval                  (+ corpus filter)
      ↓
rank fusion                                   (unchanged)
      ↓
one-hop graph expansion                       (+ corpus filter)
      ↓
grounded answer with citations and graph paths (per corpus)
```

Key modelling decisions:

* **Corpus registry** — a small, read-only object mapping a corpus name
  to its filesystem root, loaded from `corpuses.toml` (path configurable
  via `ONEO_CORPUS_CONFIG`). At least one corpus must be defined; there
  is no synthesized global fallback root. It exposes only lookup and
  listing; it holds no connections and performs no I/O beyond reading
  the one config file.
* **Neo4j scoping** — every owned node and relationship keeps
  `index_owner = "oneo"` (so Oneo still never touches unrelated Neo4j
  data) **and** gains a `corpus = <name>` property. `reset(corpus)`
  deletes only nodes matching both markers.
* **Identity** — `document_id` remains the bundle-relative path and
  `section_id` remains the semantic section ID, both scoped by the
  `corpus` property. Uniqueness constraints become composite:
  `(corpus, document_id)` and `(corpus, section_id)`. This prevents
  identical relative paths in two corpuses from colliding while keeping
  the IDs semantically pure.
* **Indexes** — the single `okf_section_embedding` vector index and
  single `okf_section_fulltext` full-text index remain global over the
  `OkfSection` label. Every search Cypher gains `AND node.corpus =
  $corpus` next to the existing `node.index_owner = $owner` filter.

The OKF filesystem for each corpus remains canonical. Neo4j remains
disposable and reproducible, now independently per corpus.

---

# 7. Data Ownership and Rebuild Semantics

Ownership rules from §7 of the archived plan hold **per corpus**:

* Each corpus's filesystem root owns that corpus's content,
  identifiers, titles, metadata, headings, anchors, links, and source
  paths.
* Neo4j owns only derived data, now tagged with `corpus`.
* Any single corpus may be deleted from Neo4j (`oneo reset --corpus
  <name>`) and rebuilt solely from its filesystem root, configuration,
  the fixed embedding model, and deterministic normalization rules.
* Resetting or rebuilding one corpus must not read, mutate, or delete
  another corpus's derived data.
* Direct database mutation must not be used for normal indexing,
  validation, or to satisfy any end-to-end rebuild/isolation test.

---

# 8. Component Model

The module set stays essentially the same; the milestone adds one small
module and touches the corpus-relevant seams of the rest.

```text
src/oneo/
├── config.py          (- knowledge_root; + corpus config path + default-corpus name)
├── corpus.py          (NEW: Corpus model + CorpusRegistry loader)
├── pipeline.py        (corpus parameter threaded through every method; no global root)
├── discovery.py       (unchanged; already root-parameterized)
├── security.py        (unchanged; already root-parameterized)
├── okf_loader.py      (unchanged)
├── models.py          (+ corpus field where identity is written)
├── validation.py      (unchanged; operates on parsed documents)
├── neo4j_store.py     (+ corpus property, composite constraints, corpus filters)
├── embedding.py       (unchanged)
├── retriever.py       (unchanged; fusion is corpus-agnostic)
├── graph_expander.py  (unchanged; operates on corpus-scoped inputs)
├── answering.py       (unchanged)
└── cli.py             (+ --corpus option, + `corpus` command group; de-PoC help text)
```

Exactly one new module (`corpus.py`) is expected. No module may be
added merely for symmetry. The single-corpus `knowledge_root` field and
its associated implicit global pipeline are removed, not retained.

---

# 9. Corpus Configuration

A single required TOML file describes the registered corpuses:

```toml
# corpuses.toml
[corpuses.billing]
root = "./corpuses/billing"

[corpuses.engineering]
root = "./corpuses/engineering"
```

Rules:

* The file path is `corpuses.toml` in the working directory by default,
  overridable via `ONEO_CORPUS_CONFIG`.
* Parsed with `tomllib` (standard library) — no new dependency.
* Each corpus name must be a simple, filesystem- and Cypher-safe slug
  (lowercase letters, digits, hyphens). Names are validated on load.
* Each `root` is resolved and, at use time, enforced by
  `resolve_within_root` against itself.
* At least one corpus must be defined. A missing or empty
  `corpuses.toml` is a clear configuration error — there is no
  synthesized global fallback corpus and no implicit `knowledge_root`.
* An optional `default` corpus name may be configured (via an
  `ONEO_DEFAULT_CORPUS` setting) so `--corpus` can be omitted; if unset
  and more than one corpus exists, corpus-scoped commands require an
  explicit `--corpus`.
* Duplicate corpus names are a configuration error reported clearly.

The registry exposes only:

```python
class CorpusRegistry:
    def names(self) -> list[str]: ...
    def get(self, name: str) -> Corpus: ...   # raises on unknown name
    def default_name(self) -> str: ...        # raises if no default is resolvable
```

```python
@dataclass(frozen=True)
class Corpus:
    name: str
    root: str
```

It must not grow connection handling, indexing state, or per-corpus
runtime objects.

---

# 10. Test and Demo Corpuses

Multi-corpus behavior cannot be demonstrated with the single existing
`./knowledge` bundle. This milestone therefore defines a small, fixed
set of OKF corpuses that must be **created as real on-disk content** (not
generated only inside test `tmp_path` bodies), so the CLI, demo, and
end-to-end tests all exercise the same reproducible bundles.

Create two committed demo corpuses under a `corpuses/` directory:

```text
corpuses/
├── billing/            # repurpose the current ./knowledge billing content
│   ├── overview.md
│   └── topics/…
└── engineering/        # a second, clearly distinct OKF bundle
    ├── overview.md
    └── topics/…
```

Requirements for the demo corpuses:

* `billing` is seeded from the existing `./knowledge` bundle (moved, not
  duplicated); `./knowledge` as a standalone top-level bundle is removed
  once `billing` exists, since there is no longer an implicit global
  root.
* `engineering` is a genuinely different bundle (different documents,
  headings, and vocabulary) so cross-corpus leakage is observable in
  retrieval.
* Both bundles must pass `oneo validate --strict` (include a non-empty
  `type` frontmatter field per OKF spec §9).
* At least one **identical bundle-relative path** (e.g. `overview.md`)
  must exist in *both* corpuses with **different content**, to prove the
  composite `(corpus, document_id)` key prevents collisions.
* At least one intra-corpus Markdown link must exist in each corpus so
  graph expansion has an edge to traverse; no link may cross a corpus
  boundary.

A committed `corpuses.toml.example` registers both demo corpuses, and
the demo script copies it to `corpuses.toml`.

For automated tests, provide **two minimal corpus fixtures** (a handful
of documents each) via ordinary `pytest` fixtures that write a temporary
`corpuses.toml` plus their bundle directories under `tmp_path`. These
test fixtures are separate from the committed demo corpuses and must
stay tiny; the committed demo corpuses are what the demo script and the
Step 5 isolation E2E exercise as realistic bundles.

Each implementation step's `### End-to-end validation` runs against the
committed demo corpuses (or, for isolation tests, the `tmp_path`
fixtures). The corpus content itself is created in Step 1 (see its
implementation task) and only extended, never re-invented, by later
steps.

---

# 11. Complexity Budget

This milestone inherits the complexity budget and review thresholds of
§13 of the archived plan. The additional production-code target is:

> **Approximately 600–1,000 lines of new production code total**

distributed roughly as below. The ranges are engineering review
triggers, not hard limits.

| Step                                    | Expected new production LOC |
| --------------------------------------- | --------------------------: |
| 1. Corpus registry and configuration    |                     150–250 |
| 2. Thread corpus through the pipeline    |                     100–200 |
| 3. Corpus-scoped Neo4j projection        |                     200–300 |
| 4. Corpus-scoped retrieval and answering |                     100–200 |
| 5. Isolation proof, demo, and docs       |                     100–200 |

If total new production code exceeds ~1,500 lines, pause for an
architecture review to check whether corpus handling is being
over-generalized.

---

# 12. Standard Engineering Checkpoint

Every step must pass the checkpoint from §15 of the archived plan,
extended with:

* Corpus is a parameter, not a new coordinator method or a service
  locator.
* No per-corpus index, database, or datastore was introduced.
* Every derived node and relationship carries a `corpus` property and
  the `index_owner` marker.
* Every read/search/expansion Cypher filters by `corpus`.
* No implicit global single-corpus path or `knowledge_root` remains;
  every corpus-scoped operation resolves to a named corpus.
* No cross-corpus leakage exists in retrieval, expansion, answering, or
  reset.

Each step concludes with:

```text
Engineering checkpoint: PASS
Complexity deviation: None | <documented explanation>
Previous E2E validations: PASS
Corpus isolation: PASS
```

---

# 13. Documentation Authority and Sequencing

`AGENTS.md` describes the code **as it currently exists**; this plan
describes the code **as it will exist**. While this milestone is in
progress the two will temporarily disagree, so precedence must be
explicit:

* **For scope, intent, and target design, this plan
  (`doc/plan/plan.md`) is authoritative.** Where `AGENTS.md` still says
  "proof of concept", lists "multi-tenant indexing" as a non-goal, or
  states an un-scoped `Document ID = bundle-relative file path`, that
  reflects the *pre-v2 code*, not the goal. An agent must not conclude
  from `AGENTS.md` that multiple corpuses are out of scope.
* **For the behavior of code that has not yet been changed,
  `AGENTS.md` remains authoritative.** Its `knowledge_root` /
  `resolve_within_root` / `discover_files` pitfalls (single-root
  double-join, root-relative resolution, etc.) accurately describe the
  modules this milestone leaves unchanged until the step that touches
  them. Do not treat those pitfalls as obsolete before the relevant
  step.
* **`AGENTS.md` is reframed last, in Step 5, on purpose.** It must not
  be rewritten to describe corpus scoping, composite keys, or the
  removed `knowledge_root` until Steps 1–4 have actually made those
  statements true — otherwise agents implementing earlier steps would
  read guidance describing code that does not exist yet. The only early
  documentation change permitted is removing "proof of concept" wording
  from surfaces that carry no behavioral claim (`pyproject.toml`
  description, `__init__.py` docstring, Typer app help), done in Step 1.
* Per the repository's own convention, `AGENTS.md` is edited only when a
  step's work makes a change true, and its "Key Pitfalls" section is
  append-only and corrected surgically — never pre-emptively rewritten
  to match a not-yet-implemented design.

If this plan and `AGENTS.md` conflict on *intent*, follow the plan and
flag the `AGENTS.md` line for correction in the step that makes the
underlying code change. If they conflict on *how existing unchanged code
behaves*, follow `AGENTS.md`.

---

# 14. Implementation

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
5. In `config.py`, remove `knowledge_root` and add `ONEO_CORPUS_CONFIG`
   and an optional `ONEO_DEFAULT_CORPUS` name.
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

---

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

---

## Step 3 — Corpus-Scoped Neo4j Projection

### Objective

Persist the `corpus` dimension in Neo4j so that documents, sections,
and relationships from different corpuses coexist without collision, and
so that reset and rebuild operate on exactly one corpus.

### Implementation

1. Add a `corpus` property to every written `OkfDocument` node,
   `OkfSection` node, `HAS_SECTION` edge, and `LINKS_TO` edge, alongside
   the existing `index_owner` marker.
2. Change MERGE keys to include corpus:

   * documents: `MERGE (d:OkfDocument {corpus: $corpus, document_id: row.document_id})`
   * sections: `MERGE (s:OkfSection {corpus: $corpus, section_id: row.section_id})`
   * `LINKS_TO`: include `corpus` in the relationship MERGE pattern.
3. Replace the single-property uniqueness constraints with **composite
   uniqueness constraints** (Neo4j 5 Community supports
   `REQUIRE (n.a, n.b) IS UNIQUE`):

   * `(OkfDocument.corpus, OkfDocument.document_id)`
   * `(OkfSection.corpus, OkfSection.section_id)`
4. Add a supporting index on `OkfSection.corpus` (and register the
   `corpus` property key token, mirroring the existing token-
   registration indexes, to avoid "property key does not exist"
   warnings on the first read).
5. Scope `reset(corpus)` to `WHERE n.index_owner = $owner AND n.corpus =
   $corpus`.
6. Scope `list_documents`, `count_sections`, `count_links`,
   `sections_needing_embedding`, `write_embeddings`, `get_section_texts`,
   and `export_graph` by corpus.
7. Ensure the single shared vector and full-text indexes are created
   once (not per corpus) and are unaffected by corpus scoping.
8. Thread `corpus` from the coordinator's `index`/`verify`/`reset` into
   every store call.

### Required behavior

* Identical bundle-relative paths in two corpuses produce distinct,
  non-colliding nodes.
* Indexing corpus A never creates, updates, or deletes any corpus-B
  node, section, vector, or edge.
* `reset --corpus A` removes only corpus A's owned data.
* Repeated indexing of a corpus creates no duplicates.
* A full rebuild of one corpus removes only that corpus's stale derived
  data.

### Delivery constraints

| Metric                 |                 Target |
| ---------------------- | ---------------------: |
| New production LOC     |                200–300 |
| Unit tests             |               Required |
| Integration tests      | Required against Neo4j |
| E2E validation         |               Required |
| Engineering checkpoint |               Required |

### End-to-end validation

Run:

```bash
oneo reset --corpus billing
oneo reset --corpus engineering
oneo index --corpus billing --no-embeddings
oneo index --corpus engineering --no-embeddings
oneo verify --corpus billing
oneo verify --corpus engineering
```

Validate that:

* both corpuses' filesystem document/section/link counts equal their
  respective graph counts
* the same relative path present in both corpuses yields two distinct
  nodes distinguished only by `corpus`
* re-indexing one corpus creates no duplicates
* `reset --corpus billing` removes only billing's data; engineering's
  export is unchanged before and after
* deleting and rebuilding one corpus reproduces an identical normalized
  graph export for that corpus while the other corpus's export is
  byte-for-byte unchanged

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
Corpus isolation: PASS
```

---

## Step 4 — Corpus-Scoped Retrieval and Answering

### Objective

Ensure vector search, full-text search, hybrid fusion, one-hop graph
expansion, and grounded answering all operate strictly within the
selected corpus, using the shared indexes with a corpus filter.

### Implementation

1. Add a `corpus` parameter to `vector_search`, `fulltext_search`,
   `expand_neighbors`, `section_by_anchor`, `first_section`,
   `best_section_in_document`, and `get_section_texts` in the store, and
   add `AND node.corpus = $corpus` to each search/traversal Cypher.
2. Keep one shared vector index and one shared full-text index; do not
   create per-corpus indexes. Corpus isolation is a `WHERE`-clause
   filter only.
3. Thread the corpus selector from `retrieve`/`query`/`vector_search`
   through to every store call.
4. Confirm `fuse_rankings` and `expand_hits` need no change (they
   operate on already corpus-filtered inputs).
5. Ensure graph expansion traverses `LINKS_TO` only within the same
   corpus (the corpus filter on both endpoints guarantees this).
6. Ensure grounded answering builds context only from the selected
   corpus's sections and that every citation resolves within that
   corpus.

### Do not implement

* cross-corpus / federated retrieval
* per-corpus indexes
* corpus-aware rank-fusion tuning

### Delivery constraints

| Metric                 |                 Target |
| ---------------------- | ---------------------: |
| New production LOC     |                100–200 |
| Unit tests             |               Required |
| Integration tests      | Required against Neo4j |
| E2E validation         |               Required |
| Engineering checkpoint |               Required |

### End-to-end validation

Run:

```bash
oneo retrieve "customer billing" --corpus billing --mode graph-hybrid --explain
oneo retrieve "customer billing" --corpus engineering --mode hybrid --explain
oneo query "How are customers billed?" --corpus billing --show-sources --show-paths
```

Validate that:

* every seed and expanded hit belongs to the selected corpus
* the same query against a different corpus returns only that corpus's
  sections (and no billing sections leak into engineering, or vice
  versa)
* graph expansion never crosses a corpus boundary
* every answer citation resolves to a section of the selected corpus
* an unanswerable question still returns insufficient evidence
* retrieval still works with answer generation disabled

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
Corpus isolation: PASS
```

---

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
      document `corpuses.toml`, `--corpus`, and per-corpus rebuild.
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

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
Corpus isolation: PASS
```

---

# 15. Testing Strategy

The testing pyramid and discipline from §17 of the archived plan hold.
This milestone adds, without building a generic harness:

## Unit tests

* corpus-name validation (accepted slugs, rejected names, duplicates)
* registry loading from a TOML fixture
* a missing/empty `corpuses.toml` raising a clear configuration error
  (no `knowledge_root` fallback)
* `ONEO_CORPUS_CONFIG` and `ONEO_DEFAULT_CORPUS` resolution
* per-corpus root resolution and path-security rejection

## Integration tests (real Neo4j)

* composite uniqueness constraints allow identical relative paths across
  corpuses and reject true duplicates within a corpus
* corpus-scoped writes, reset, export, and counts
* corpus-scoped vector search, full-text search, and one-hop expansion
  return only the selected corpus's sections
* resetting one corpus leaves another corpus's data unchanged

## End-to-end tests

* the two-corpus isolation test in Step 5
* per-corpus filesystem-first rebuild
* the pre-existing pipeline E2E tests, updated to run against a named
  corpus (the single-corpus test corpus becomes one registered corpus)

## Test scope discipline

Use ordinary `pytest` fixtures, the two minimal `tmp_path` corpus
fixtures from §10, Docker Compose, and the existing deterministic fake
embedding/chat providers. At least one end-to-end path must exercise the
two committed demo corpuses (§10) with the configured embedding and chat
integrations.

---

# 16. Pull Request Requirements

Every implementation pull request must include the block from §19 of the
archived plan, plus:

```text
Corpus dimension threaded through: <components>
Isolation proof: <how corpus A/B non-interference is demonstrated>
Removed single-corpus surface: <knowledge_root / PoC framing removed>
```

A pull request must not introduce a second datastore, a per-corpus
index, a corpus-source plugin system, cross-corpus retrieval, an
implicit global single-corpus path, or any new coordinator method
without a documented complexity justification.

---

# 17. Review Smells

In addition to the review smells in §20 of the archived plan,
reviewers should challenge:

* a per-corpus Neo4j database, schema, or index
* a corpus registry that holds connections or indexing state
* corpus threaded as a new coordinator method rather than a parameter
* content-derived or renamed identities used to separate corpuses
  instead of a `corpus` property + composite key
* cross-corpus links, traversal, or federated retrieval sneaking in
* a corpus-source abstraction with a single implementation
* search Cypher missing the `corpus` filter
* reset that is not corpus-scoped

---

# 18. Operational Model

## Supported commands

```text
health
corpus list
corpus info <name>
files            [--corpus <name>]
parse            [--corpus <name>]
validate         [--corpus <name>] [--strict]
reset            [--corpus <name>]
index            [--corpus <name>] [--rebuild/--no-rebuild] [--no-embeddings]
discover         [--corpus <name>]
verify           [--corpus <name>]
vector-search    [--corpus <name>]
retrieve         [--corpus <name>] [--mode hybrid|graph-hybrid] [--explain]
query            [--corpus <name>] [--mode ...] [--show-sources] [--show-paths]
```

When `--corpus` is omitted, the configured default corpus
(`ONEO_DEFAULT_CORPUS`) is used; if none is configured and more than one
corpus exists, an explicit `--corpus` is required.

## Configuration

`corpuses.toml` (or `ONEO_CORPUS_CONFIG`) maps corpus names to roots and
is required. `ONEO_DEFAULT_CORPUS` optionally names the default corpus.
The removed `ONEO_KNOWLEDGE_ROOT` setting no longer exists; all other
`ONEO_*` runtime settings (Neo4j connection, retrieval tuning, etc.)
carry over unchanged.

---

# 19. Breaking Change and Migration

This milestone is a clean breaking change; there is no compatibility
mode.

* The single-corpus `knowledge_root` setting and its implicit global
  pipeline are removed. `corpuses.toml` becomes the required entry point,
  defining one or more named corpuses.
* Pre-v2 Neo4j data has no `corpus` property and is incompatible. The
  migration is: write a `corpuses.toml`, then for each corpus run
  `oneo reset --corpus <name>` followed by `oneo index --corpus <name>`
  (a full rebuild from the filesystem — always safe, since the
  filesystem is canonical). No in-place data migration or manual Cypher
  is required or permitted.
* The composite uniqueness constraints replace the previous single-
  property constraints; applying them is part of `apply_schema` and is
  idempotent. A one-time `oneo reset` per corpus clears any stale pre-v2
  nodes before the new constraints and `corpus` scoping take effect.
* Proof-of-concept framing is removed from the code, CLI help, and
  documentation as part of Step 5.
