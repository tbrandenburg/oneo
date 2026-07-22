> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# 16. Implementation

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
