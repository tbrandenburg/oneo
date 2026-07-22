"""Unit tests for hybrid-retrieval rank fusion."""

from __future__ import annotations

from oneo.models import SectionMatch
from oneo.retriever import fuse_rankings


def _match(section_id: str, score: float, document_id: str = "doc") -> SectionMatch:
    return SectionMatch(
        section_id=section_id,
        document_id=document_id,
        heading="Heading",
        score=score,
        source_path=f"{document_id}.md",
    )


def test_fuse_rankings_combines_vector_and_lexical_hits():
    vector_matches = [_match("a", 0.9), _match("b", 0.8)]
    lexical_matches = [_match("b", 5.0), _match("c", 4.0)]

    hits = fuse_rankings(
        vector_matches,
        lexical_matches,
        fusion_k=60,
        vector_weight=1.0,
        lexical_weight=1.0,
    )

    by_id = {hit.section_id: hit for hit in hits}
    assert set(by_id) == {"a", "b", "c"}
    assert by_id["a"].retrieval_origin == "vector"
    assert by_id["a"].vector_rank == 1
    assert by_id["a"].lexical_rank is None
    assert by_id["b"].retrieval_origin == "both"
    assert by_id["b"].vector_rank == 2
    assert by_id["b"].lexical_rank == 1
    assert by_id["c"].retrieval_origin == "lexical"
    assert by_id["c"].lexical_rank == 2


def test_fuse_rankings_deduplicates_sections_present_in_both_lists():
    vector_matches = [_match("a", 0.9)]
    lexical_matches = [_match("a", 5.0)]

    hits = fuse_rankings(
        vector_matches,
        lexical_matches,
        fusion_k=60,
        vector_weight=1.0,
        lexical_weight=1.0,
    )

    assert len(hits) == 1
    assert hits[0].section_id == "a"
    assert hits[0].retrieval_origin == "both"


def test_fuse_rankings_ranks_hit_present_in_both_lists_above_single_source_hits():
    vector_matches = [_match("a", 0.9), _match("b", 0.8)]
    lexical_matches = [_match("b", 5.0), _match("c", 4.0)]

    hits = fuse_rankings(
        vector_matches,
        lexical_matches,
        fusion_k=60,
        vector_weight=1.0,
        lexical_weight=1.0,
    )

    assert hits[0].section_id == "b"


def test_fuse_rankings_orders_by_descending_fused_score():
    vector_matches = [_match("a", 0.9), _match("b", 0.8), _match("c", 0.7)]

    hits = fuse_rankings(
        vector_matches,
        [],
        fusion_k=60,
        vector_weight=1.0,
        lexical_weight=1.0,
    )

    assert [hit.section_id for hit in hits] == ["a", "b", "c"]
    assert hits[0].fused_score > hits[1].fused_score > hits[2].fused_score


def test_fuse_rankings_breaks_score_ties_deterministically_by_section_id():
    vector_matches = [_match("z", 0.9)]
    lexical_matches = [_match("a", 5.0)]

    hits_first = fuse_rankings(
        vector_matches,
        lexical_matches,
        fusion_k=60,
        vector_weight=1.0,
        lexical_weight=1.0,
    )
    hits_second = fuse_rankings(
        vector_matches,
        lexical_matches,
        fusion_k=60,
        vector_weight=1.0,
        lexical_weight=1.0,
    )

    # both are rank 1 in their own list, so scores tie; "a" sorts first.
    assert [hit.section_id for hit in hits_first] == ["a", "z"]
    assert hits_first == hits_second


def test_fuse_rankings_returns_empty_list_for_no_matches():
    assert fuse_rankings([], [], fusion_k=60, vector_weight=1.0, lexical_weight=1.0) == []


def test_fuse_rankings_respects_weights():
    vector_matches = [_match("a", 0.9)]
    lexical_matches = [_match("b", 5.0)]

    hits = fuse_rankings(
        vector_matches,
        lexical_matches,
        fusion_k=60,
        vector_weight=2.0,
        lexical_weight=1.0,
    )

    by_id = {hit.section_id: hit for hit in hits}
    assert by_id["a"].fused_score == 2.0 / 61
    assert by_id["b"].fused_score == 1.0 / 61
