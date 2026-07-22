> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# 16. Implementation

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
