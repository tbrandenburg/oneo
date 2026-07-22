> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# 16. Implementation

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
