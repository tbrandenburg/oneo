> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

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
