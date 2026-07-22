> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# 16. Implementation

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
