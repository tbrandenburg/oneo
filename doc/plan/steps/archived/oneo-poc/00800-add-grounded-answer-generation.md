> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# 16. Implementation

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
