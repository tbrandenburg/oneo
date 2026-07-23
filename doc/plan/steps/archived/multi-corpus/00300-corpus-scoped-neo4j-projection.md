> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# 13. Implementation

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
9. Route every corpus-scoped read/write/delete through a single internal
   helper that requires a non-empty `corpus` bind parameter and injects
   the `AND n.corpus = $corpus` filter itself; no store method may
   hand-write the corpus filter. The helper raises if `corpus` is missing
   or empty, so a corpus-scoped query cannot be issued unscoped. This
   converts corpus isolation from a per-query convention into a
   structurally enforced guarantee — closing the single-forgotten-filter
   failure mode, most critically on the destructive `reset` path.

### Required behavior

* Identical bundle-relative paths in two corpuses produce distinct,
  non-colliding nodes.
* No corpus-scoped Cypher can execute without a `corpus` bind; a missing
  corpus is a hard error, not a silent full-graph operation.
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

