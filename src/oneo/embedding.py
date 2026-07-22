"""Deterministic section embedding for Oneo.

The embedding model, its dimensionality, and its batch size are fixed
for the proof of concept and must not be made configurable (see
``doc/plan/steps/in-progress/00500-add-embeddings.md``). Only the
narrow ``SectionEmbedder`` surface required by the pipeline is
defined here; no embedding-provider registry or selection mechanism
is introduced.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence


class EmbeddingDimensionError(ValueError):
    """Raised when a generated embedding does not have the expected
    number of dimensions."""


def build_embedding_input(
    title: str, heading_path: Sequence[str], text: str
) -> str:
    """Deterministically construct the exact text sent to the
    embedding model for one section.

    The input never includes source paths, IDs, arbitrary metadata,
    or link targets -- only the document title, the heading path, and
    the normalized section text.
    """

    heading_line = " > ".join(heading_path)
    normalized_text = normalize_embedding_text(text)
    return f"Document: {title}\nSection: {heading_line}\n\n{normalized_text}"


def normalize_embedding_text(text: str) -> str:
    """Normalize line endings to ``\\n`` and trim leading/trailing
    whitespace while preserving paragraph boundaries, capitalization,
    and punctuation."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.strip()


def compute_embedding_input_hash(embedding_input: str) -> str:
    """Return the deterministic hash of the exact normalized text sent
    to the embedding model."""

    return hashlib.sha256(embedding_input.encode("utf-8")).hexdigest()


class SectionEmbedder:
    """Loads the fixed Sentence Transformers model and embeds section
    text and retrieval queries.

    This is the only concrete embedding implementation. A public
    embedding-provider abstraction, provider registry, or
    model-selection mechanism must not be introduced.
    """

    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    DIMENSIONS = 384
    BATCH_SIZE = 32

    def __init__(self) -> None:
        # Imported lazily so importing this module never requires
        # ``sentence-transformers``/``torch`` to be loaded until an
        # embedder is actually constructed.
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(self.MODEL_NAME)

    def embed_sections(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        """Embed a batch of section input texts, using the fixed batch
        size. Every returned vector is validated to contain exactly
        ``DIMENSIONS`` values."""

        vectors = self._model.encode(
            list(texts),
            batch_size=self.BATCH_SIZE,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        result = [vector.tolist() for vector in vectors]
        self._validate_dimensions(result)
        return result

    def embed_query(self, query: str) -> Sequence[float]:
        """Embed a single retrieval query."""

        vector = self._model.encode(
            [query], convert_to_numpy=True, show_progress_bar=False
        )[0]
        embedding = vector.tolist()
        self._validate_dimensions([embedding])
        return embedding

    def _validate_dimensions(self, vectors: Sequence[Sequence[float]]) -> None:
        for vector in vectors:
            if len(vector) != self.DIMENSIONS:
                raise EmbeddingDimensionError(
                    f"expected {self.DIMENSIONS}-dimensional embedding, "
                    f"got {len(vector)}"
                )
