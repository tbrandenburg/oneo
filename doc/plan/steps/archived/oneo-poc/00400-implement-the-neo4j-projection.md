> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# 16. Implementation

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
