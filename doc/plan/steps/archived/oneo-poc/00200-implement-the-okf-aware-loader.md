> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# 16. Implementation

## Step 2 — Implement the OKF-Aware Loader

### Objective

Parse native [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) files into deterministic document, section, anchor, metadata, and link models.

### Implementation

1. Create `OkfLoader`.
2. Parse YAML frontmatter using a mature library.
3. Parse Markdown using `markdown-it-py`.
4. Extract:

   * document ID
   * title
   * metadata
   * source path
   * sections
   * heading hierarchy
   * heading anchors
   * local links
   * external links
5. Define Markdown sections as normal retrieval units.
6. Preserve the heading path for every section.
7. Generate deterministic section ordinals.
8. Generate stable semantic section IDs.
9. Store content hashes separately from identities.
10. Apply a token-based fallback splitter only to oversized sections.
11. Preserve the parent heading path for split fragments.
12. Produce deterministic normalized output.

The loader and splitter should remain conceptually separate:

```text
load = parse OKF structure and semantics

split = preserve sections and divide only oversized sections
```

### Stable identifiers

Per [OKF spec §2](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md#2-terminology), a document's Concept ID is derived from its file path relative to the bundle root, with the `.md`/`.markdown` suffix removed (for example, `tables/users.md` has concept ID `tables/users`). OKF frontmatter has no dedicated identifier field.

```text
document ID = bundle-relative path with the markdown suffix removed

section ID =
    document ID
    + normalized heading path
    + section ordinal
```

For oversized sections, split-fragment identity may additionally include a stable fragment ordinal.

Because document IDs are derived from unique filesystem paths, duplicate document IDs cannot occur within a single well-formed bundle. Duplicate-ID validation exists only to catch symlink cycles, case-insensitive filesystem collisions, or other filesystem-level anomalies.

### Do not implement

* graph writes
* embeddings
* retrieval
* answer generation
* general-purpose Markdown-to-document conversion
* support for arbitrary file formats

### Delivery constraints

| Metric                 |   Target |
| ---------------------- | -------: |
| New production LOC     |  300–400 |
| Unit tests             | Required |
| Integration tests      | Required |
| E2E validation         | Required |
| Engineering checkpoint | Required |

### End-to-end validation

Run:

```bash
oneo parse ./knowledge \
  --output build/corpus.json
```

Validate that:

* every expected OKF ID is present
* frontmatter is preserved
* titles are resolved correctly
* heading hierarchy is correct
* local and external links are distinguished
* anchors are extracted
* source paths are retained
* section IDs remain unchanged after section text is edited
* content hashes change after text edits
* repeated runs produce identical normalized output
* oversized sections split deterministically

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
```
