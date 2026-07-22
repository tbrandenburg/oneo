"""Unit tests for grounded answer generation."""

from __future__ import annotations

from oneo.answering import ExtractiveChatModel, generate_answer
from oneo.models import GraphExpandedHit, RetrievalHit, RetrievalResult


def _seed_hit(
    section_id: str,
    document_id: str,
    *,
    lexical_rank: int | None = 1,
    vector_score: float | None = 0.9,
) -> RetrievalHit:
    return RetrievalHit(
        section_id=section_id,
        document_id=document_id,
        heading="Heading",
        source_path=f"{document_id}.md",
        vector_rank=1,
        vector_score=vector_score,
        lexical_rank=lexical_rank,
        lexical_score=4.0 if lexical_rank else None,
        fused_score=0.03,
        retrieval_origin="both",
    )


def _expanded_hit(section_id: str, document_id: str, via_document_id: str) -> GraphExpandedHit:
    return GraphExpandedHit(
        section_id=section_id,
        document_id=document_id,
        heading="Neighbor Heading",
        source_path=f"{document_id}.md",
        expansion_score=0.5,
        graph_path=(via_document_id, "LINKS_TO", document_id),
        via_document_id=via_document_id,
        selection_strategy="relevance",
    )


class _FakeChatModel:
    def __init__(self, response: str) -> None:
        self._response = response

    def generate(self, prompt: str) -> str:
        return self._response


def test_generate_answer_without_chat_model_is_insufficient_evidence():
    retrieval = RetrievalResult(
        query="q", hits=(_seed_hit("billing::_::0", "billing"),)
    )

    result = generate_answer(
        "q", retrieval, {"billing::_::0": "text"}, None, max_context_sections=8
    )

    assert result.insufficient_evidence
    assert result.citations == ()
    assert result.answer == "insufficient evidence"


def test_generate_answer_without_relevant_evidence_is_insufficient():
    retrieval = RetrievalResult(
        query="q",
        hits=(_seed_hit("weather::_::0", "weather", lexical_rank=None, vector_score=0.1),),
    )
    chat_model = _FakeChatModel("some answer [S1].")

    result = generate_answer(
        "q",
        retrieval,
        {"weather::_::0": "text"},
        chat_model,
        max_context_sections=8,
        min_vector_score=0.35,
    )

    assert result.insufficient_evidence
    assert result.citations == ()


def test_generate_answer_returns_valid_citations_and_drops_invalid_ones():
    retrieval = RetrievalResult(
        query="How are customers billed?",
        hits=(_seed_hit("billing::_::0", "billing"),),
    )
    chat_model = _FakeChatModel("Customers are billed monthly [S1] [S99].")

    result = generate_answer(
        "How are customers billed?",
        retrieval,
        {"billing::_::0": "Customers are billed monthly."},
        chat_model,
        max_context_sections=8,
    )

    assert not result.insufficient_evidence
    assert [c.label for c in result.citations] == ["S1"]
    assert result.citations[0].document_id == "billing"
    assert result.citations[0].section_id == "billing::_::0"


def test_generate_answer_drops_citation_that_resolves_to_no_valid_label():
    retrieval = RetrievalResult(
        query="q", hits=(_seed_hit("billing::_::0", "billing"),)
    )
    chat_model = _FakeChatModel("An answer with no bracket citations at all.")

    result = generate_answer(
        "q",
        retrieval,
        {"billing::_::0": "Customers are billed monthly."},
        chat_model,
        max_context_sections=8,
    )

    assert result.insufficient_evidence
    assert result.citations == ()


def test_generate_answer_reports_model_declared_insufficient_evidence():
    retrieval = RetrievalResult(
        query="q", hits=(_seed_hit("billing::_::0", "billing"),)
    )
    chat_model = _FakeChatModel("insufficient evidence")

    result = generate_answer(
        "q",
        retrieval,
        {"billing::_::0": "Customers are billed monthly."},
        chat_model,
        max_context_sections=8,
    )

    assert result.insufficient_evidence
    assert result.citations == ()


def test_generate_answer_includes_graph_path_for_cited_expanded_hit():
    retrieval = RetrievalResult(
        query="q",
        hits=(_seed_hit("billing::_::0", "billing"),),
        expanded_hits=(_expanded_hit("related::_::0", "related", "billing"),),
    )
    chat_model = _FakeChatModel("Billed monthly [S1], also related here [S2].")

    result = generate_answer(
        "q",
        retrieval,
        {
            "billing::_::0": "Customers are billed monthly.",
            "related::_::0": "Related content.",
        },
        chat_model,
        max_context_sections=8,
    )

    assert not result.insufficient_evidence
    assert [c.label for c in result.citations] == ["S1", "S2"]
    assert result.graph_paths == (("billing", "LINKS_TO", "related"),)


def test_generate_answer_excludes_expanded_hit_from_irrelevant_seed():
    retrieval = RetrievalResult(
        query="q",
        hits=(_seed_hit("weather::_::0", "weather", lexical_rank=None, vector_score=0.1),),
        expanded_hits=(_expanded_hit("related::_::0", "related", "weather"),),
    )
    chat_model = _FakeChatModel("some answer [S1].")

    result = generate_answer(
        "q",
        retrieval,
        {"weather::_::0": "text", "related::_::0": "text"},
        chat_model,
        max_context_sections=8,
        min_vector_score=0.35,
    )

    assert result.insufficient_evidence


def test_extractive_chat_model_quotes_evidence_sentences_with_labels():
    prompt = (
        "Question: How are customers billed?\n\n"
        "[S1] billing - Billing (billing.md)\n"
        "Customers are billed monthly. Extra detail.\n\n"
    )

    model = ExtractiveChatModel()
    answer = model.generate(prompt)

    assert "Customers are billed monthly [S1]" in answer


def test_extractive_chat_model_returns_insufficient_evidence_with_no_blocks():
    model = ExtractiveChatModel()
    assert model.generate("Question: unrelated?\n\n") == "insufficient evidence"
