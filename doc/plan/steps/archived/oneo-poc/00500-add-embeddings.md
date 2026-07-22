> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# 16. Implementation

## Step 5 — Add Embeddings

### Objective

Generate embeddings for OKF sections using one fixed Sentence Transformers model and store the resulting vectors directly in Neo4j.

### Embedding model

The proof of concept must use:

```text
sentence-transformers/all-MiniLM-L6-v2
```

The model is fixed for the proof of concept and must not be configurable.

It produces 384-dimensional vectors.

The Neo4j vector index must therefore use:

```text
node label: OkfSection
vector property: embedding
dimensions: 384
similarity function: cosine
```

Changing the embedding model is outside the scope of the proof of concept and requires:

* a code change
* deletion or recreation of the vector index
* a complete index rebuild

### Embedding input

Each `OkfSection` must be embedded independently.

The input text must be constructed deterministically as:

```text
Document: <document title>
Section: <heading path joined with " > ">

<section text>
```

Example:

```text
Document: Customer Billing
Section: Billing > Invoice Schedule

Customers are invoiced on the first business day of each month.
```

Before embedding:

1. Normalize line endings to `\n`.
2. Trim leading and trailing whitespace.
3. Preserve paragraph boundaries.
4. Preserve capitalization and punctuation.
5. Split oversized sections before embedding.
6. Do not include source paths, IDs, arbitrary metadata, or link targets.

The embedding input hash must be calculated from the exact normalized text sent to the model.

### Implementation

1. Add a concrete `SectionEmbedder` implementation.
2. Load `sentence-transformers/all-MiniLM-L6-v2` directly.
3. Generate section embeddings in batches.
4. Use an initial fixed batch size of 32.
5. Validate that every generated vector contains 384 values.
6. Store the vector on the corresponding `OkfSection`.
7. Store:

   * `embedding`
   * `embedding_model`
   * `embedding_dimensions`
   * `embedding_input_hash`
8. Create the Neo4j vector index.
9. Verify that the index reaches `ONLINE`.
10. Re-embed a section when:

    * its embedding input hash changes
    * its embedding is missing
    * its stored model name differs
    * its stored dimensions differ
11. Fail the indexing operation when an embedding batch fails.
12. Report the affected section IDs in the failure output.

A suitable concrete implementation is:

```python
class SectionEmbedder:
    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    DIMENSIONS = 384
    BATCH_SIZE = 32

    def embed_sections(
        self,
        texts: Sequence[str],
    ) -> Sequence[Sequence[float]]:
        ...

    def embed_query(self, query: str) -> Sequence[float]:
        ...
```

A public embedding-provider abstraction, provider registry, or model-selection mechanism must not be introduced.

Tests may use a deterministic fake or stub in place of `SectionEmbedder`.

### Do not implement

* configurable embedding models
* multiple embedding providers
* an embedding-provider registry
* dynamic provider loading
* a separate vector database
* distributed embedding
* background embedding jobs
* automatic batch-size tuning
* incremental ingestion infrastructure
* support for vectors with multiple dimensions
* a generic embedding framework

### Delivery constraints

| Metric                 |                 Target |
| ---------------------- | ---------------------: |
| New production LOC     |                150–250 |
| Unit tests             |               Required |
| Integration tests      | Required against Neo4j |
| E2E validation         |               Required |
| Engineering checkpoint |               Required |

### Unit validation

Validate that:

* embedding input construction is deterministic
* title, heading path, and section text are included
* source paths and IDs are excluded
* line endings and whitespace are normalized
* the embedding input hash changes when relevant text changes
* the fake embedder produces deterministic test results
* invalid vector dimensions are rejected

### End-to-end validation

Run:

```bash
okf-graph index ./knowledge --rebuild
okf-graph vector-search "customer billing"
```

Validate that:

* `sentence-transformers/all-MiniLM-L6-v2` is loaded
* the vector index reports `ONLINE`
* the vector index uses 384 dimensions
* the similarity function is cosine
* every searchable section has a vector
* every stored vector contains 384 values
* every section stores the model name and input hash
* expected billing sections appear among the highest-ranked results
* each result includes:

  * document ID
  * section ID
  * heading
  * similarity score
  * source path

### Completion record

```text
Engineering checkpoint: PASS
Complexity deviation: None
Previous E2E validations: PASS
```
