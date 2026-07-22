> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# 16. Implementation

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
