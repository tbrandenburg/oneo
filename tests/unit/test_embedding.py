"""Unit tests for deterministic embedding-input construction and
dimension validation. These tests never load the real Sentence
Transformers model."""

from __future__ import annotations

import pytest

from oneo.embedding import (
    EmbeddingDimensionError,
    SectionEmbedder,
    build_embedding_input,
    compute_embedding_input_hash,
    normalize_embedding_text,
)


def test_build_embedding_input_is_deterministic():
    first = build_embedding_input(
        "Customer Billing", ("Billing", "Invoice Schedule"), "Customers are invoiced.\n"
    )
    second = build_embedding_input(
        "Customer Billing", ("Billing", "Invoice Schedule"), "Customers are invoiced.\n"
    )

    assert first == second


def test_build_embedding_input_includes_title_heading_path_and_text():
    result = build_embedding_input(
        "Customer Billing",
        ("Billing", "Invoice Schedule"),
        "Customers are invoiced on the first business day of each month.",
    )

    assert "Document: Customer Billing" in result
    assert "Section: Billing > Invoice Schedule" in result
    assert "Customers are invoiced on the first business day" in result


def test_build_embedding_input_excludes_source_paths_and_ids():
    result = build_embedding_input("Title", ("Heading",), "Some section text.")

    assert "source_path" not in result
    assert "document_id" not in result
    assert "section_id" not in result


def test_normalize_embedding_text_normalizes_line_endings_and_trims():
    normalized = normalize_embedding_text("  \r\nLine one\r\nLine two\r\n  ")

    assert normalized == "Line one\nLine two"


def test_normalize_embedding_text_preserves_paragraph_boundaries():
    normalized = normalize_embedding_text("Paragraph one.\n\nParagraph two.")

    assert normalized == "Paragraph one.\n\nParagraph two."


def test_normalize_embedding_text_preserves_capitalization_and_punctuation():
    normalized = normalize_embedding_text("Hello, World! Is this OK?")

    assert normalized == "Hello, World! Is this OK?"


def test_embedding_input_hash_changes_when_text_changes():
    input_a = build_embedding_input("Title", ("Heading",), "Original text.")
    input_b = build_embedding_input("Title", ("Heading",), "Changed text.")

    assert compute_embedding_input_hash(input_a) != compute_embedding_input_hash(input_b)


def test_embedding_input_hash_is_stable_for_identical_text():
    input_a = build_embedding_input("Title", ("Heading",), "Same text.")
    input_b = build_embedding_input("Title", ("Heading",), "Same text.")

    assert compute_embedding_input_hash(input_a) == compute_embedding_input_hash(input_b)


class _FakeEmbedder(SectionEmbedder):
    """A deterministic stub used in place of the real model."""

    def __init__(self, dimensions: int = SectionEmbedder.DIMENSIONS) -> None:  # noqa: D401
        self._dimensions = dimensions

    def embed_sections(self, texts):
        vectors = [[float(len(text))] * self._dimensions for text in texts]
        self._validate_dimensions(vectors)
        return vectors

    def embed_query(self, query: str):
        vector = [float(len(query))] * self._dimensions
        self._validate_dimensions([vector])
        return vector


def test_fake_embedder_produces_deterministic_results():
    embedder = _FakeEmbedder()

    first = embedder.embed_sections(["hello", "world"])
    second = embedder.embed_sections(["hello", "world"])

    assert first == second
    assert all(len(vector) == SectionEmbedder.DIMENSIONS for vector in first)


def test_invalid_vector_dimensions_are_rejected():
    embedder = _FakeEmbedder(dimensions=10)

    with pytest.raises(EmbeddingDimensionError):
        embedder.embed_sections(["too short"])
