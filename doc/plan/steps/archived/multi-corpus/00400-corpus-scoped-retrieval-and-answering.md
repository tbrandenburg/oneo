> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# 13. Implementation

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

