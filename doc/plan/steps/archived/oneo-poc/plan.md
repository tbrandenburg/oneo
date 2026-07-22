# Oneo

## Implementation Plan and Engineering RFC

**Project name:** Oneo  
**CLI command:** `oneo`

## 1. Purpose

This document defines the implementation plan for a proof of concept that indexes an Open Knowledge Format repository into Neo4j and uses the resulting graph for hybrid and graph-enhanced retrieval.

The OKF filesystem is the canonical source of truth.

Neo4j is a derived index that must be fully reproducible from the filesystem.

The proof of concept should demonstrate the value of combining:

* OKF-aware parsing
* explicit document relationships
* Neo4j graph projection
* vector retrieval
* full-text retrieval
* rank fusion
* graph expansion
* grounded answer generation

The implementation must remain deliberately small, explicit, and easy to remove or replace.

It is not intended to become a general-purpose retrieval framework.

---

# 2. Goals

The proof of concept has the following goals:

* Index an OKF repository without manual preprocessing.
* Preserve document identities, headings, metadata, anchors, and links.
* Project OKF documents and sections into Neo4j.
* Store section embeddings in Neo4j.
* Support vector and full-text retrieval.
* Combine retrieval results using explicit rank fusion.
* Expand retrieval context through document relationships.
* Generate answers grounded only in retrieved OKF content.
* Rebuild the complete derived index from the filesystem.
* Provide a single executable demo from a clean checkout.
* Keep the implementation understandable without extensive framework documentation.

---

# 3. Proof of Concept Success Criteria

The goal of this proof of concept is **not** to build a production GraphRAG framework.

The goal is to prove that an OKF corpus can be deterministically projected into Neo4j and used for graph-enhanced retrieval.

The proof of concept is considered successful when the following capabilities are demonstrated:

* An OKF repository can be indexed without manual preprocessing.
* The graph can be rebuilt entirely from the filesystem.
* Document identities and relationships are preserved.
* Markdown sections become stable retrieval units.
* Hybrid retrieval returns relevant sections.
* Graph expansion adds useful contextual documents.
* Generated answers are grounded in retrieved sources.
* Every answer citation resolves to an indexed OKF section.
* Unanswerable questions return an insufficient-evidence result.
* The complete pipeline runs from a clean checkout using one demo script.

The proof of concept is not intended to optimize:

* retrieval quality
* scalability
* throughput
* latency
* high availability
* operational resilience
* incremental update performance
* production security

Success is measured primarily by:

* correctness
* determinism
* simplicity
* traceability
* reproducibility

Feature completeness is not a success criterion.

---

# 4. Non-goals

The proof of concept will not include:

* a general-purpose RAG framework
* general document conversion in the normal OKF ingestion path
* a separate vector database
* a second derived datastore
* LLM-based graph extraction
* filesystem watching
* incremental ingestion
* remote URL ingestion
* an in-memory corpus-wide BM25 index
* a web interface
* MCP integration
* RDF projection
* production authentication
* production authorization
* high-availability deployment
* distributed ingestion
* automated retrieval tuning
* multi-tenant indexing
* generic plugin infrastructure
* dynamic pipeline composition
* support for arbitrary document schemas

External document formats such as PDF, DOCX, PPTX, or scanned documents may be considered later as import sources.

They are outside the normal OKF ingestion path and must be normalized into OKF-compatible structures before indexing.

---

# 5. Implementation Constraints

Every component must satisfy the following constraints:

* Prefer composition over custom infrastructure.
* Reuse mature open-source libraries whenever practical.
* Implement only behavior that is specific to OKF semantics or required orchestration.
* Avoid introducing abstractions without a concrete present need.
* Avoid abstractions that exist only to anticipate possible future requirements.
* Keep orchestration code explicit rather than highly generic.
* Avoid framework-specific coupling wherever possible.
* Keep persistence limited to Neo4j.
* Keep the filesystem as the only canonical source.
* Keep public interfaces small and typed.
* Prefer plain functions and small classes over inheritance hierarchies.
* Prefer readable duplication over premature generalization when the duplication is minor.
* Isolate external dependencies behind narrow boundaries only where replacement, testing, or dependency control requires it.
* Preserve source provenance throughout parsing, retrieval, graph expansion, and answer generation.

The implementation should optimize for readability over extensibility.

Even as a proof of concept, Oneo must be implemented as a clean, modern, state-of-the-art `uv` project. The PoC label must not be used to justify ad hoc packaging, unclear dependency management, inconsistent tooling, or disposable project structure. The repository should use `uv` as the standard interface for dependency resolution, environment management, command execution, locking, and reproducible setup.

A new abstraction is justified only when it:

* removes demonstrated duplication
* isolates a substantial external dependency
* enables meaningful testing
* supports at least two concrete implementations
* provides a stable boundary around OKF-specific behavior

The presence of a possible future implementation is not sufficient justification.

---

# 6. Architectural Decision

Use established open-source retrieval and graph patterns while implementing only the behavior required for OKF semantics.

Do not rebuild generic capabilities unnecessarily, including:

* filesystem traversal
* path normalization
* secure base-directory enforcement
* exclusion-pattern processing
* Markdown parsing
* YAML frontmatter parsing
* embedding model integration
* Neo4j connectivity
* vector indexing
* full-text indexing
* standard rank-fusion algorithms

Do not adopt an existing end-to-end retrieval coordinator unchanged when it tightly couples:

* ingestion to a document-conversion framework
* retrieval to framework-specific document objects
* persistence to a separate vector database
* embeddings to a concrete implementation
* answering to one model provider

The target architecture is:

```text
OKF filesystem
      ↓
filesystem discovery and path validation
      ↓
OKF-aware loader
      ↓
OKF documents, sections, anchors, and links
      ↓
corpus validation and link resolution
      ↓
Neo4j graph, vector index, and full-text index
      ↓
vector and lexical retrieval
      ↓
rank fusion
      ↓
one-hop graph expansion
      ↓
grounded answer with citations and graph paths
```

The OKF filesystem remains canonical.

Neo4j remains disposable and reproducible.

No information may exist only in Neo4j if it is required to rebuild or interpret the index.

---

# 7. Data Ownership and Rebuild Semantics

The filesystem owns:

* document content
* document identifiers
* titles
* metadata
* heading structure
* anchors
* links
* source paths

Neo4j owns only derived data:

* normalized document nodes
* normalized section nodes
* graph relationships
* full-text indexes
* embedding vectors
* vector indexes
* retrieval metadata
* rebuild metadata

A complete Neo4j database may be deleted without loss of canonical knowledge.

The index must be rebuildable solely from:

* the OKF repository
* configuration
* the selected embedding model
* deterministic normalization rules

Direct database edits must not be required for normal indexing or validation.

Direct database mutation must not be used to satisfy end-to-end rebuild tests.

---

# 8. Reuse Assessment

## 8.1 Filesystem discovery

Use established filesystem behavior for:

* recursive traversal
* extension filtering
* exclusion patterns
* path normalization
* allowed base directories
* symbolic-path handling
* consistent relative source paths

The initial implementation accepts only:

```text
.md
.markdown
```

Remote URLs remain disabled.

Unsupported files must be ignored or reported according to the selected command behavior.

`index.md` and `log.md` are OKF-reserved filenames ([OKF spec §3.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md#31-reserved-filenames), [§6](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md#6-index-files), [§7](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md#7-log-files-optional)) and must not be treated as concept documents:

* `index.md` has no frontmatter and must be skipped by the concept loader, or parsed separately as a directory listing.
* `log.md` has no frontmatter and must be skipped by the concept loader, or parsed separately as a change history.
* Neither file should be required to satisfy concept-level frontmatter validation.

## 8.2 Path-security validation

All ingest paths must be checked against a configured knowledge root.

The implementation must:

* normalize the requested path
* resolve the effective filesystem location
* verify that the path remains inside the configured root
* reject parent traversal outside the root
* reject unrelated absolute paths
* reject remote URLs
* validate paths before opening or parsing files

Security checks must apply to both individual files and directories.

## 8.3 Markdown parsing

Use `markdown-it-py` for Markdown tokenization and structure discovery.

Do not create a custom Markdown parser.

The OKF loader may add semantic interpretation for:

* heading hierarchy
* anchors
* relative links
* document IDs
* section boundaries
* source positions

## 8.4 YAML frontmatter

Use a mature frontmatter parser.

Do not create a custom YAML parser.

Frontmatter must be preserved as structured metadata.

## 8.5 Embeddings

Use a standard Sentence Transformers or Hugging Face implementation when local embeddings are selected.

The embedding provider must be injected through a narrow interface.

The pipeline coordinator must not instantiate a concrete model directly.

## 8.6 Neo4j

Use the official Neo4j Python driver.

Use Neo4j-native:

* graph storage
* vector indexes
* full-text indexes
* Cypher traversal
* schema constraints

Do not add a second database to reproduce capabilities already available in Neo4j.

## 8.7 Rank fusion

Use a small, explicit implementation of reciprocal-rank fusion or weighted-rank fusion.

Do not build a general ranking framework.

The algorithm must be independently testable and expose enough diagnostics to explain why a result was selected.

---

# 9. Components That Must Not Be Reused Unchanged

## 9.1 Generic document-conversion loaders

Do not use a document-conversion pipeline for ordinary OKF ingestion.

OKF already contains:

* Markdown structure
* YAML metadata
* explicit identifiers
* explicit links
* meaningful heading hierarchy

The normal ingestion path requires semantic parsing, not document conversion.

A conversion tool may later be used only as an import adapter for external formats.

## 9.2 Generic hybrid chunkers

Do not use a document-conversion chunker as the primary OKF splitter.

Markdown headings define the first-level retrieval units.

A token-based fallback splitter may divide only oversized sections.

## 9.3 Content-derived identities

Do not use the hash of section content as the section identity.

Use stable semantic identifiers:

```text
document ID = OKF metadata ID

section ID =
    document ID
    + normalized heading path
    + section ordinal
```

Content hashes are stored separately for:

* change detection
* embedding invalidation
* rebuild comparison

Editing section text must not automatically change its semantic identity.

## 9.4 Separate vector storage

Do not introduce another vector database.

Neo4j stores:

* document nodes
* section nodes
* graph relationships
* vectors
* vector indexes
* full-text indexes

## 9.5 In-memory corpus-wide lexical indexing

Do not load every indexed section into application memory solely to create a BM25 index.

Use Neo4j’s full-text index for the initial lexical path.

---

# 10. Component Model

```text
src/oneo/
├── pipeline.py
├── discovery.py
├── security.py
├── okf_loader.py
├── models.py
├── validator.py
├── link_resolver.py
├── neo4j_store.py
├── embeddings.py
├── retriever.py
├── graph_expander.py
└── answering.py
```

The expected module count is approximate.

A module should not be added merely to create architectural symmetry.

Small related behaviors may remain together when separation would make the code harder to follow.

---

# 11. Core Domain Models

The implementation should use typed models for the main data exchanged between components.

Suggested models include:

```python
@dataclass(frozen=True)
class OkfDocument:
    document_id: str
    title: str
    source_path: str
    metadata: Mapping[str, object]
    content_hash: str
```

```python
@dataclass(frozen=True)
class OkfSection:
    section_id: str
    document_id: str
    heading: str
    heading_path: tuple[str, ...]
    ordinal: int
    text: str
    anchor: str | None
    source_path: str
    content_hash: str
```

```python
@dataclass(frozen=True)
class OkfLink:
    source_document_id: str
    source_section_id: str | None
    raw_target: str
    target_document_id: str | None
    target_anchor: str | None
    is_external: bool
```

```python
@dataclass(frozen=True)
class RetrievalHit:
    section: OkfSection
    vector_rank: int | None
    lexical_rank: int | None
    vector_score: float | None
    lexical_score: float | None
    fused_score: float
    retrieval_origin: str
```

```python
@dataclass(frozen=True)
class RetrievalResult:
    query: str
    hits: tuple[RetrievalHit, ...]
    graph_paths: tuple[GraphPath, ...]
```

```python
@dataclass(frozen=True)
class AnswerResult:
    answer: str
    citations: tuple[Citation, ...]
    retrieval: RetrievalResult
    insufficient_evidence: bool
```

The precise names may change, but framework-specific document objects must not cross the application boundary.

---

# 12. Pipeline Coordinator

The coordinator exposes a small public surface:

```python
class Oneo:
    def validate(self, input_path: str) -> ValidationReport: ...
    def index(self, input_path: str, rebuild: bool = True) -> IndexReport: ...
    def discover(self) -> list[IndexedDocument]: ...
    def retrieve(self, query: str) -> RetrievalResult: ...
    def query(self, query: str) -> AnswerResult: ...
    def reset(self) -> None: ...
```

The coordinator delegates:

* discovery
* security validation
* parsing
* corpus validation
* link resolution
* graph persistence
* embeddings
* retrieval
* graph expansion
* answering

Use Typer for the `oneo` command-line interface. Keep command functions thin and delegate all application behavior to the `Oneo` coordinator. Do not introduce a custom command framework or expose domain logic directly through CLI handlers.

It must not become a service locator or dependency-injection framework.

Dependencies may be supplied through a constructor or a small configuration factory.

---

# 13. Complexity Budget

This proof of concept intentionally limits architectural and implementation complexity.

The project should contain approximately:

* 10–12 Python modules
* no more than 20 exported application classes
* no more than 40 exported application functions
* one executable ingestion and retrieval pipeline
* one derived datastore
* one primary graph model
* one embedding-provider boundary
* one chat-model boundary
* one hybrid-ranking implementation

“Public” means exported application interfaces intended for use outside their defining module.

It does not include every internal method or helper function.

These figures are review thresholds rather than absolute limits.

Exceeding them is acceptable only when the additional complexity is necessary and explicitly justified.

New abstractions should be introduced only when they:

* eliminate demonstrated duplication
* isolate a substantial dependency
* enable meaningful substitution
* improve testability
* support a concrete present requirement

They must not be introduced solely to anticipate future requirements.

A pull request should include a complexity justification when it:

* adds more than approximately 300 lines of production code
* introduces a new public abstraction
* introduces a new runtime dependency
* adds another persistence mechanism
* expands the public API
* creates a new extension or plugin mechanism
* adds a second execution path for the same pipeline stage

The justification should include:

```text
Complexity introduced:
Why existing components are insufficient:
Simpler alternatives considered:
Why the additional complexity is warranted:
```

The total implementation target is:

> **Approximately 2,000–2,700 lines of production code**

This excludes:

* tests
* thin CLI wiring
* generated Cypher
* configuration
* documentation
* fixtures
* example knowledge files

If the proof of concept grows beyond approximately 5,000 lines of production code, implementation should pause for an architecture review.

The review should determine whether:

* generic infrastructure is being rebuilt
* unnecessary abstractions have accumulated
* framework capabilities are being duplicated
* scope has expanded beyond the proof of concept
* modules can be removed or collapsed
* a dependency would provide the same behavior more simply

---

# 14. Suggested Production LOC Budget

| Step                              | Expected production LOC |
| --------------------------------- | ----------------------: |
| 1. Bootstrap                      |                 200–250 |
| 2. OKF Loader                     |                 300–400 |
| 3. Validation and Link Resolution |                 200–300 |
| 4. Neo4j Projection               |                 300–400 |
| 5. Embeddings                     |                 150–250 |
| 6. Hybrid Retrieval               |                 200–300 |
| 7. Graph Expansion                |                 150–250 |
| 8. Answer Generation              |                 150–250 |
| 9. Filesystem Rebuild Proof       |                 100–150 |
| 10. Packaging and Demo            |                 100–150 |

The ranges are engineering review triggers, not hard limits.

A step may exceed its target when the additional code is necessary, tested, and explained.

The budget should not encourage:

* dense code
* hidden complexity
* large functions
* missing validation
* reduced test coverage
* removal of useful types

---

# 15. Standard Engineering Checkpoint

Every implementation phase must pass this checkpoint before the next phase begins.

Verify that:

* No generic infrastructure has been introduced without a demonstrated need.
* Existing libraries are used where they provide the required behavior.
* Custom code remains focused on OKF semantics and explicit orchestration.
* The public API remains minimal.
* New abstractions are supported by a concrete present requirement.
* The codebase remains understandable without extensive architectural documentation.
* The filesystem remains the canonical source.
* Neo4j remains the only derived datastore.
* No previously implemented end-to-end behavior has regressed.
* Production-code growth remains within the expected range or has documented justification.
* Source provenance remains intact.
* Framework-specific objects have not leaked into domain interfaces.

Each phase should conclude with:

```text
Engineering checkpoint: PASS
Complexity deviation: None | <documented explanation>
Previous E2E validations: PASS
```

---

# 16. Implementation

## Step 1 — Bootstrap the Project

### Objective

Create the smallest executable project capable of:

* validating filesystem boundaries
* discovering supported files
* connecting to Neo4j
* exposing the intended CLI and coordinator surface

### Implementation

1. Create a clean, modern `uv`-managed Python project with a committed lockfile and reproducible commands.
2. Create the Typer-based `oneo` command-line interface.
3. Keep CLI command functions thin and delegate application behavior to the `Oneo` coordinator.
5. Add Neo4j through Docker Compose.
5. Add configuration for:

   * knowledge root
   * Neo4j URI
   * Neo4j username
   * Neo4j password
   * database name
   * exclusion patterns
6. Add the `Oneo` coordinator with:

   * `validate`
   * `index`
   * `discover`
   * `retrieve`
   * `query`
   * `reset`
7. Implement allowed-base-path validation.
8. Implement supported-file discovery.
9. Restrict input files to:

   * `.md`
   * `.markdown`
10. Support recursive traversal.
11. Support exclusion patterns.
12. Normalize returned source paths.
13. Reject:

* parent traversal outside the knowledge root
* unrelated absolute paths
* remote URLs

14. Add a real Neo4j health query.

### Do not implement

* OKF parsing
* embeddings
* graph projection
* retrieval
* graph expansion
* answer generation
* a custom command framework
* domain logic inside CLI handlers
* generic dependency-injection infrastructure

### Delivery constraints

| Metric                 |   Target |
| ---------------------- | -------: |
| New production LOC     |  200–250 |
| Unit tests             | Required |
| Integration tests      | Required |
| E2E validation         | Required |
| Engineering checkpoint | Required |

### End-to-end validation

Run:

```bash
docker compose up -d
oneo health
oneo files ./knowledge
```

Validate that:

* a real Neo4j query succeeds
* only `.md` and `.markdown` files are returned
* nested directories are traversed
* excluded paths are absent
* results are deterministic
* `../` traversal outside the allowed root is rejected
* directories outside the knowledge root are rejected
* remote URLs are rejected

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
```

---

## Step 2 — Implement the OKF-Aware Loader

### Objective

Parse native [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) files into deterministic document, section, anchor, metadata, and link models.

### Implementation

1. Create `OkfLoader`.
2. Parse YAML frontmatter using a mature library.
3. Parse Markdown using `markdown-it-py`.
4. Extract:

   * document ID
   * title
   * metadata
   * source path
   * sections
   * heading hierarchy
   * heading anchors
   * local links
   * external links
5. Define Markdown sections as normal retrieval units.
6. Preserve the heading path for every section.
7. Generate deterministic section ordinals.
8. Generate stable semantic section IDs.
9. Store content hashes separately from identities.
10. Apply a token-based fallback splitter only to oversized sections.
11. Preserve the parent heading path for split fragments.
12. Produce deterministic normalized output.

The loader and splitter should remain conceptually separate:

```text
load = parse OKF structure and semantics

split = preserve sections and divide only oversized sections
```

### Stable identifiers

Per [OKF spec §2](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md#2-terminology), a document's Concept ID is derived from its file path relative to the bundle root, with the `.md`/`.markdown` suffix removed (for example, `tables/users.md` has concept ID `tables/users`). OKF frontmatter has no dedicated identifier field.

```text
document ID = bundle-relative path with the markdown suffix removed

section ID =
    document ID
    + normalized heading path
    + section ordinal
```

For oversized sections, split-fragment identity may additionally include a stable fragment ordinal.

Because document IDs are derived from unique filesystem paths, duplicate document IDs cannot occur within a single well-formed bundle. Duplicate-ID validation exists only to catch symlink cycles, case-insensitive filesystem collisions, or other filesystem-level anomalies.

### Do not implement

* graph writes
* embeddings
* retrieval
* answer generation
* general-purpose Markdown-to-document conversion
* support for arbitrary file formats

### Delivery constraints

| Metric                 |   Target |
| ---------------------- | -------: |
| New production LOC     |  300–400 |
| Unit tests             | Required |
| Integration tests      | Required |
| E2E validation         | Required |
| Engineering checkpoint | Required |

### End-to-end validation

Run:

```bash
oneo parse ./knowledge \
  --output build/corpus.json
```

Validate that:

* every expected OKF ID is present
* frontmatter is preserved
* titles are resolved correctly
* heading hierarchy is correct
* local and external links are distinguished
* anchors are extracted
* source paths are retained
* section IDs remain unchanged after section text is edited
* content hashes change after text edits
* repeated runs produce identical normalized output
* oversized sections split deterministically

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
```

---

## Step 3 — Validate and Resolve the OKF Corpus

### Objective

Validate [OKF semantics](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md#9-conformance) before any graph data is written.

### Implementation

1. Validate required metadata fields.
2. Validate document IDs.
3. Detect duplicate document IDs.
4. Detect duplicate section IDs.
5. Resolve relative links.
6. Resolve document targets.
7. Resolve anchor targets.
8. Distinguish external links from local links.
9. Produce structured diagnostics.
10. Support strict mode.
11. Support permissive mode.
12. Include source positions where practical.
13. Ensure strict validation completes before graph writes begin.

Suggested diagnostic fields:

```text
severity
code
source_path
source_section
line
raw_target
resolved_target
message
```

### Strict mode

[OKF spec §9](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md#9-conformance) explicitly states that consumers must tolerate broken cross-links — a link whose target does not exist is not malformed, and bundles must not be rejected on that basis. Failing on unresolved links is therefore a project-specific strictness opt-in, not an OKF requirement, and must never be the default behavior.

Strict mode must fail on:

* missing required fields (a non-empty `type` in frontmatter, per [OKF spec §9](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md#9-conformance))
* duplicate document IDs (filesystem-level anomalies only; see §9.3)
* duplicate semantic section IDs
* unresolved local document links
* unresolved local anchors
* invalid paths

### Permissive mode (default)

Permissive mode is the OKF-conformant default and must continue when recoverable issues are present, including broken cross-links and missing optional metadata.

All issues must still be reported as diagnostics even when they do not fail validation.

### Delivery constraints

| Metric                 |   Target |
| ---------------------- | -------: |
| New production LOC     |  200–300 |
| Unit tests             | Required |
| Integration tests      | Required |
| E2E validation         | Required |
| Engineering checkpoint | Required |

### End-to-end validation

Run:

```bash
oneo validate ./knowledge --strict
```

Validate that:

* a deliberately broken link returns a non-zero exit code
* the source file is reported
* the raw unresolved target is reported
* missing anchors fail validation
* duplicate document IDs fail validation
* a corrected corpus exits successfully
* validation output is deterministic
* no Neo4j nodes are written when strict validation fails

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
```

---

## Step 4 — Implement the Neo4j Projection

### Objective

Project validated [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) documents, sections, and relationships into Neo4j using stable identities.

### Storage boundary

Define a narrow graph-store protocol:

```python
class OkfGraphStore(Protocol):
    def reset(self) -> None: ...
    def apply_schema(self) -> None: ...
    def write_documents(self, documents) -> None: ...
    def write_sections(self, sections) -> None: ...
    def write_links(self, links) -> None: ...
    def list_documents(self) -> list[IndexedDocument]: ...
    def vector_search(self, embedding, top_k: int): ...
    def fulltext_search(self, query: str, top_k: int): ...
    def expand_neighbors(self, document_ids, hops: int): ...
```

This boundary exists to:

* isolate the database driver
* make integration tests explicit
* keep Cypher out of orchestration code

It must not become a generic persistence framework.

### Graph model

Create:

```text
(:OkfDocument)
(:OkfSection)

(:OkfDocument)-[:HAS_SECTION]->(:OkfSection)
(:OkfDocument)-[:LINKS_TO]->(:OkfDocument)
```

Optional relationship properties may include:

```text
source_section_id
target_anchor
raw_target
source_path
```

Suggested document properties:

```text
document_id
title
source_path
metadata
content_hash
index_owner
```

Suggested section properties:

```text
section_id
document_id
heading
heading_path
ordinal
anchor
text
content_hash
source_path
index_owner
```

### Implementation

1. Apply uniqueness constraints.
2. Apply supporting indexes.
3. Write documents idempotently.
4. Write sections idempotently.
5. Write `HAS_SECTION` relationships.
6. Write resolved `LINKS_TO` relationships.
7. Preserve provenance properties.
8. Scope all owned nodes using an index-owner marker.
9. Ensure reset deletes only data owned by this index.
10. Implement document discovery.
11. Implement normalized graph export for comparison.
12. Use transactions and batched writes where practical.

### Required behavior

* IDs come from OKF semantics (bundle-relative file paths).
* Repeated indexing does not create duplicates.
* A full rebuild removes stale derived data.
* Graph relationships are first-class.
* Neo4j may be deleted and reconstructed.
* Unrelated Neo4j data must not be deleted by reset.

### Delivery constraints

| Metric                 |                 Target |
| ---------------------- | ---------------------: |
| New production LOC     |                300–400 |
| Unit tests             |               Required |
| Integration tests      | Required against Neo4j |
| E2E validation         |               Required |
| Engineering checkpoint |               Required |

### End-to-end validation

Run:

```bash
oneo reset
oneo index ./knowledge --no-embeddings
oneo verify
```

Validate that:

* filesystem document count equals graph document count
* parsed section count equals graph section count
* every resolved Markdown link has a graph edge
* document IDs equal bundle-relative file paths (per [OKF spec §2](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md#2-terminology))
* section IDs equal semantic section IDs
* repeated indexing creates no duplicates
* reset removes only owned data
* deleting Neo4j and rebuilding produces an identical normalized graph export

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
```

---

## Step 5 — Add Embeddings

### Objective

Generate embeddings for OKF sections using one fixed Sentence Transformers model and store the resulting vectors directly in Neo4j.

### Embedding model

The proof of concept must use:

```text
sentence-transformers/all-MiniLM-L6-v2
```

The model is fixed for the proof of concept and must not be configurable.

It produces 384-dimensional vectors.

The Neo4j vector index must therefore use:

```text
node label: OkfSection
vector property: embedding
dimensions: 384
similarity function: cosine
```

Changing the embedding model is outside the scope of the proof of concept and requires:

* a code change
* deletion or recreation of the vector index
* a complete index rebuild

### Embedding input

Each `OkfSection` must be embedded independently.

The input text must be constructed deterministically as:

```text
Document: <document title>
Section: <heading path joined with " > ">

<section text>
```

Example:

```text
Document: Customer Billing
Section: Billing > Invoice Schedule

Customers are invoiced on the first business day of each month.
```

Before embedding:

1. Normalize line endings to `\n`.
2. Trim leading and trailing whitespace.
3. Preserve paragraph boundaries.
4. Preserve capitalization and punctuation.
5. Split oversized sections before embedding.
6. Do not include source paths, IDs, arbitrary metadata, or link targets.

The embedding input hash must be calculated from the exact normalized text sent to the model.

### Implementation

1. Add a concrete `SectionEmbedder` implementation.
2. Load `sentence-transformers/all-MiniLM-L6-v2` directly.
3. Generate section embeddings in batches.
4. Use an initial fixed batch size of 32.
5. Validate that every generated vector contains 384 values.
6. Store the vector on the corresponding `OkfSection`.
7. Store:

   * `embedding`
   * `embedding_model`
   * `embedding_dimensions`
   * `embedding_input_hash`
8. Create the Neo4j vector index.
9. Verify that the index reaches `ONLINE`.
10. Re-embed a section when:

    * its embedding input hash changes
    * its embedding is missing
    * its stored model name differs
    * its stored dimensions differ
11. Fail the indexing operation when an embedding batch fails.
12. Report the affected section IDs in the failure output.

A suitable concrete implementation is:

```python
class SectionEmbedder:
    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    DIMENSIONS = 384
    BATCH_SIZE = 32

    def embed_sections(
        self,
        texts: Sequence[str],
    ) -> Sequence[Sequence[float]]:
        ...

    def embed_query(self, query: str) -> Sequence[float]:
        ...
```

A public embedding-provider abstraction, provider registry, or model-selection mechanism must not be introduced.

Tests may use a deterministic fake or stub in place of `SectionEmbedder`.

### Do not implement

* configurable embedding models
* multiple embedding providers
* an embedding-provider registry
* dynamic provider loading
* a separate vector database
* distributed embedding
* background embedding jobs
* automatic batch-size tuning
* incremental ingestion infrastructure
* support for vectors with multiple dimensions
* a generic embedding framework

### Delivery constraints

| Metric                 |                 Target |
| ---------------------- | ---------------------: |
| New production LOC     |                150–250 |
| Unit tests             |               Required |
| Integration tests      | Required against Neo4j |
| E2E validation         |               Required |
| Engineering checkpoint |               Required |

### Unit validation

Validate that:

* embedding input construction is deterministic
* title, heading path, and section text are included
* source paths and IDs are excluded
* line endings and whitespace are normalized
* the embedding input hash changes when relevant text changes
* the fake embedder produces deterministic test results
* invalid vector dimensions are rejected

### End-to-end validation

Run:

```bash
okf-graph index ./knowledge --rebuild
okf-graph vector-search "customer billing"
```

Validate that:

* `sentence-transformers/all-MiniLM-L6-v2` is loaded
* the vector index reports `ONLINE`
* the vector index uses 384 dimensions
* the similarity function is cosine
* every searchable section has a vector
* every stored vector contains 384 values
* every section stores the model name and input hash
* expected billing sections appear among the highest-ranked results
* each result includes:

  * document ID
  * section ID
  * heading
  * similarity score
  * source path

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
```

---

## Step 6 — Implement Hybrid Retrieval

### Objective

Combine Neo4j vector and full-text results using explicit and explainable rank fusion.

### Implementation

1. Query the Neo4j vector index.
2. Query the Neo4j full-text index.
3. Normalize both result sets into a shared retrieval type.
4. Fuse the ranked lists.
5. Deduplicate sections.
6. Return the top `k` sections.
7. Preserve provenance.
8. Expose retrieval diagnostics.

Use reciprocal-rank fusion or a small weighted-rank variant.

A basic reciprocal-rank formula may use:

```text
score(document) =
    Σ 1 / (k + rank)
```

The constant and weights must be configuration values with sensible defaults.

### Retrieval diagnostics

Each hit should expose:

* vector rank
* vector score
* lexical rank
* lexical score
* fused score
* retrieval origin
* source path
* document ID
* section ID

### Do not implement

* an in-memory corpus-wide BM25 index
* a generic ranking framework
* a large ensemble-retrieval abstraction
* automatic weight tuning
* relevance feedback
* query rewriting
* reranking models

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
oneo retrieve \
  "customer billing" \
  --mode hybrid \
  --explain
```

Validate that:

* vector retrieval executes
* full-text retrieval executes
* fused results contain no duplicate sections
* keyword-heavy benchmark queries improve over vector-only retrieval
* paraphrased benchmark queries improve over lexical-only retrieval
* every selected result exposes ranks and fused score
* repeated queries produce stable ordering when scores are equal

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
```

---

## Step 7 — Add Graph Expansion

### Objective

Expand hybrid retrieval results through explicit OKF document relationships.

### Implementation

1. Map seed sections to their owning documents.
2. Traverse one hop across `LINKS_TO`.
3. Optionally consider incoming and outgoing relationships separately.
4. Retrieve selected sections from neighboring documents.
5. Apply a graph-expansion weight.
6. Deduplicate seed and expanded sections.
7. Enforce result-count and token limits.
8. Preserve the graph path for each expanded result.
9. Distinguish seed results from graph-expanded results.
10. Keep graph expansion after hybrid rank fusion.

The initial proof of concept should use one-hop expansion only.

Additional traversal depth is outside the initial scope.

### Selection behavior

Neighbor sections may be selected using one simple strategy:

* highest lexical or vector relevance within the neighboring document
* linked anchor target when available
* first relevant section under the linked heading
* deterministic fallback when no anchor exists

The chosen strategy must be explicit and tested.

### Do not implement

* unrestricted graph traversal
* path-learning algorithms
* graph neural networks
* LLM-selected traversal
* generic traversal policies
* multi-stage planning

### Delivery constraints

| Metric                 |                 Target |
| ---------------------- | ---------------------: |
| New production LOC     |                150–250 |
| Unit tests             |               Required |
| Integration tests      | Required against Neo4j |
| E2E validation         |               Required |
| Engineering checkpoint |               Required |

### End-to-end validation

Run:

```bash
oneo retrieve \
  "How is a customer billed?" \
  --mode graph-hybrid \
  --explain
```

Validate that:

* hybrid seed sections are shown
* graph-expanded sections are shown separately
* traversed relationships are displayed
* at least one expected neighboring document is added
* the neighboring document was not present in the seed results
* every expanded result retains source provenance
* every expanded result retains its graph path
* context limits are enforced

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
```

---

## Step 8 — Add Grounded Answer Generation

### Objective

Generate answers exclusively from retrieved OKF context.

### Chat-model boundary

Define a narrow injected interface:

```python
class ChatModel(Protocol):
    def generate(self, prompt: str) -> str: ...
```

A slightly richer typed request may be used if needed.

Do not create:

* provider registries
* model-routing systems
* prompt-template frameworks
* tool-calling infrastructure
* multi-agent workflows

### Implementation

1. Build an answer context from retrieved sections.
2. Assign stable citation labels.
3. Include source identifiers and headings in the model context.
4. Instruct the model to use only the supplied evidence.
5. Instruct the model to report insufficient evidence when necessary.
6. Return:

   * answer text
   * cited sections
   * retrieved sources
   * graph paths
   * insufficiency status
7. Validate that every returned citation exists in the retrieval context.
8. Keep retrieval usable when no chat model is configured.

### Citation requirements

Every citation must map to:

* document ID
* section ID
* source path
* heading
* retrieval result

No citation may point to:

* an unindexed file
* an invented source
* a graph node absent from the retrieval result
* an external URL unless explicitly represented as evidence

### Do not implement

* conversation memory
* agent loops
* automatic tool use
* model routing
* answer caching
* evaluation frameworks
* hallucination scoring systems

### Delivery constraints

| Metric                 |   Target |
| ---------------------- | -------: |
| New production LOC     |  150–250 |
| Unit tests             | Required |
| Integration tests      | Required |
| E2E validation         | Required |
| Engineering checkpoint | Required |

### End-to-end validation

Run:

```bash
oneo query \
  "How are customers billed?" \
  --show-sources \
  --show-paths
```

Validate that:

* every answer citation maps to a retrieved section
* every cited file exists
* graph-expanded content is cited in at least one benchmark
* an unanswerable question returns insufficient evidence
* no unindexed path appears as a citation
* retrieval still works with answer generation disabled
* invalid model citations are rejected or removed

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
```

---

## Step 9 — Prove Filesystem-First Rebuild Semantics

### Objective

Demonstrate that Neo4j is disposable and the filesystem is the complete source of truth.

### Implementation

Create an end-to-end test that:

1. indexes a baseline corpus
2. edits an existing section
3. rebuilds the index
4. verifies updated graph content
5. verifies updated vector behavior
6. adds a Markdown link
7. rebuilds the index
8. verifies the new graph relationship
9. deletes an OKF file
10. rebuilds the index
11. verifies removal of:

    * the document node
    * its section nodes
    * its vectors
    * incoming relationships
    * outgoing relationships

No direct database mutation may be used to prepare the expected final state.

### Delivery constraints

| Metric                 |    Target |
| ---------------------- | --------: |
| New production LOC     |   100–150 |
| Unit tests             | As needed |
| Integration tests      |  Required |
| E2E validation         |  Required |
| Engineering checkpoint |  Required |

### End-to-end validation

Run:

```bash
pytest tests/e2e/test_filesystem_source_of_truth.py
```

Validate:

```text
edit section text
→ rebuild
→ graph text and vector behavior are updated

add Markdown link
→ rebuild
→ corresponding graph edge is created

delete Markdown file
→ rebuild
→ document, sections, vectors, and relationships disappear
```

Also validate that:

* stable section identity survives text-only edits
* content hash changes after text edits
* deleted files do not remain discoverable
* unrelated Neo4j data remains untouched

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
```

---

## Step 10 — Package the Proof of Concept

### Objective

Provide one deterministic demo that proves the complete pipeline from a clean checkout.

### Implementation

Create:

```bash
./scripts/demo.sh
```

The script must:

1. start Neo4j
2. wait for Neo4j readiness
3. run a health check
4. validate filesystem security
5. validate the [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) corpus
6. reset the derived index
7. apply the Neo4j schema
8. project documents and sections
9. project graph relationships
10. embed sections
11. verify the vector index
12. verify the full-text index
13. run hybrid retrieval
14. run graph expansion
15. generate one grounded answer
16. verify citations
17. print a final status summary

The script must fail immediately when a required step fails.

### Delivery constraints

| Metric                 |    Target |
| ---------------------- | --------: |
| New production LOC     |   100–150 |
| Unit tests             | As needed |
| Integration tests      |  Required |
| E2E validation         |  Required |
| Engineering checkpoint |  Required |

### End-to-end validation

From a clean checkout:

```bash
docker compose down -v
cp .env.example .env
./scripts/demo.sh
```

Required output:

```text
Filesystem security: PASS
OKF validation: PASS
Graph projection: PASS
Vector index: ONLINE
Full-text index: ONLINE
Hybrid retrieval: PASS
Graph expansion: PASS
Answer grounding: PASS
PoC status: SUCCESS
```

The demo must not require:

* manual preprocessing
* manual database edits
* manual Cypher execution
* hidden local state
* undocumented environment variables

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
```

---

# 17. Testing Strategy

## Unit tests

Unit tests should cover deterministic application behavior, including:

* path validation
* exclusion patterns
* section ID generation
* content hashing
* heading normalization
* anchor normalization
* link parsing
* link resolution
* duplicate detection
* rank fusion
* result deduplication
* context-limit enforcement
* citation validation

## Integration tests

Integration tests should use a real Neo4j instance for:

* schema creation
* uniqueness constraints
* document writes
* section writes
* relationship writes
* reset behavior
* vector search
* full-text search
* graph traversal
* normalized graph export

Database behavior should not be proven only through mocks.

## End-to-end tests

End-to-end tests should cover:

* clean corpus indexing
* invalid corpus rejection
* hybrid retrieval
* graph expansion
* grounded answer generation
* insufficient evidence
* complete rebuild
* file deletion
* content edits
* new relationships
* deterministic output

## Test scope discipline

Do not build a generic test harness.

Use:

* normal `pytest` fixtures
* small corpus fixtures
* Docker Compose
* deterministic fake embedding and chat providers where appropriate

At least one full end-to-end path must use the real configured embedding and chat integrations intended for the demo.

---

# 18. Retrieval Benchmark

Create a small fixed benchmark containing:

* exact keyword queries
* paraphrased queries
* relationship-dependent queries
* unanswerable queries

Each benchmark case should define:

```text
query
expected seed document or section
expected related document, when applicable
answerable: yes | no
```

The benchmark exists to verify that:

* lexical retrieval contributes value
* vector retrieval contributes value
* rank fusion contributes value
* graph expansion contributes context
* insufficient-evidence behavior works

It is not intended to become a comprehensive evaluation framework.

---

# 19. Pull Request Requirements

Every implementation pull request must include:

```text
Existing component evaluated:
Reuse decision:
Reason custom code is still required:
Production LOC added:
Public API changes:
New dependencies:
Complexity justification:
E2E validation:
```

The reuse assessment must consider, where relevant:

1. the Open Knowledge Format implementation and specification
2. Neo4j GraphRAG for Python
3. `markdown-it-py`
4. `python-frontmatter`
5. the Neo4j Python driver
6. Sentence Transformers
7. standard-library functionality

A pull request should not introduce custom infrastructure without documenting why existing components are insufficient.

---

# 20. Review Smells

Reviewers should challenge changes that introduce:

* base classes with one implementation
* registries with one registered component
* factories that only call one constructor
* configuration-driven pipeline composition
* custom plugin systems
* generic event buses
* repository patterns over a single graph store
* a second persistence layer
* framework-specific domain models
* duplicate embedding wrappers
* duplicated Neo4j query abstractions
* large coordinator classes
* hidden database mutations
* non-deterministic IDs
* content hashes used as identities
* broad “future-proofing” changes
* more than one way to run the same pipeline stage

These patterns are not automatically forbidden, but they require strong evidence that they solve a current problem.

---

# 21. Operational Model

The initial operational model is intentionally simple.

## Supported commands

```text
health
files
parse
validate
reset
index
discover
verify
vector-search
retrieve
query
```

The exact CLI grouping may vary.

The CLI must use Typer. Command functions must remain thin adapters that validate and translate command-line input, invoke the `Oneo` coordinator, render results, and map failures to exit codes. They must not contain parsing, validation, persistence, retrieval, graph-expansion, embedding, or answer-generation logic.

Do not create a large or custom command framework.

## Configuration

Configuration should cover only required runtime values:

* knowledge root
* Neo4j connection details
* database name
* exclusion patterns
* embedding model
* embedding dimensions, when required
* retrieval limits
* rank-fusion settings
* graph-expansion weight
* context limits
* chat-model settings

Configuration should not allow arbitrary pipeline graph construction.

---

# 22. Security Boundaries

The proof of concept is not production hardened, but it must enforce basic boundaries.

Required protections include:

* allowed-root path enforcement
* URL rejection
* path normalization
* parameterized Cypher
* no arbitrary Cypher from document content
* no secrets committed to the repository
* `.env.example` without real credentials
* bounded retrieval limits
* bounded graph traversal depth
* bounded answer context
* ownership-scoped reset behavior

Production authentication and authorization remain out of scope.

---

# 23. Determinism Requirements

Given the same:

* OKF corpus
* configuration
* parser version
* normalization rules
* embedding model
* embedding model version

the pipeline should produce the same:

* document IDs
* section IDs
* anchors
* resolved links
* graph structure
* normalized graph export
* index metadata

Embedding values may vary slightly across platforms or runtime versions.

Structural determinism must not depend on embedding values.

Tie-breaking in retrieval should be deterministic.

---

# 24. Expected Final Repository Shape

```text
.
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
├── .env.example
├── README.md
├── knowledge/
├── scripts/
│   └── demo.sh
├── src/
│   └── oneo/
│       ├── pipeline.py
│       ├── discovery.py
│       ├── security.py
│       ├── okf_loader.py
│       ├── models.py
│       ├── validator.py
│       ├── link_resolver.py
│       ├── neo4j_store.py
│       ├── embeddings.py
│       ├── retriever.py
│       ├── graph_expander.py
│       └── answering.py
└── tests/
    ├── unit/
    ├── integration/
    ├── e2e/
    └── fixtures/
```

This structure is illustrative rather than mandatory.

A simpler structure is preferable when it remains clear.

---

# 25. Final Deliverables

The proof of concept is complete when the repository contains:

* a clean, modern, state-of-the-art `uv` project with reproducible dependency and command workflows
* a documented OKF ingestion pipeline
* deterministic filesystem discovery
* secure knowledge-root enforcement
* an OKF-aware parser
* structured corpus validation
* deterministic link resolution
* a Neo4j graph projection
* Neo4j vector indexing
* Neo4j full-text indexing
* explicit rank fusion
* one-hop graph expansion
* grounded answer generation
* stable citations
* rebuild verification
* tests
* one complete demo script
* a concise README describing setup, execution, and limitations

---

# 26. References

## Open Knowledge Format

* Introducing the Open Knowledge Format
  https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing?hl=en

* Google Open Knowledge Format Specification
  https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md

* Google Open Knowledge Format Repository
  https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf

## Neo4j

* Neo4j GraphRAG for Python
  https://github.com/neo4j/neo4j-graphrag-python

* Neo4j Vector Indexes
  https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/

* Neo4j Full-Text Indexes
  https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/full-text-indexes/

* Neo4j Python Driver
  https://github.com/neo4j/neo4j-python-driver

## Markdown

* markdown-it-py
  https://github.com/executablebooks/markdown-it-py

* python-frontmatter
  https://github.com/eyeseast/python-frontmatter

## Embeddings

* Sentence Transformers
  https://www.sbert.net/

## Supporting Concepts

* Reciprocal Rank Fusion, Cormack et al., 2009
  https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf

---

# 27. Summary

This proof of concept should prove one narrow architectural claim:

> An OKF repository can serve as the canonical knowledge source for a deterministic Neo4j projection that supports hybrid retrieval, relationship-based context expansion, and grounded answer generation.

The implementation should remain small enough to inspect directly.

Even as a proof of concept, it should be a clean, modern, state-of-the-art `uv` project with reproducible setup, dependency management, and execution.

Its value comes from proving the data model and retrieval path, not from creating a reusable framework.

The preferred result is a straightforward 2,000–2,700-line implementation that works reliably and can be understood by a new engineer in a short review.

A larger or more abstract system is not a stronger proof of concept.
