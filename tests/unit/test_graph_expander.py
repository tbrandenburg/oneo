"""Unit tests for one-hop graph expansion."""

from __future__ import annotations

from oneo.graph_expander import expand_hits
from oneo.models import LinkedDocument, RetrievalHit, SectionMatch


def _seed_hit(document_id: str, section_id: str) -> RetrievalHit:
    return RetrievalHit(
        section_id=section_id,
        document_id=document_id,
        heading="Heading",
        source_path=f"{document_id}.md",
        vector_rank=1,
        vector_score=0.9,
        lexical_rank=1,
        lexical_score=4.0,
        fused_score=0.03,
        retrieval_origin="both",
    )


def _link(
    seed: str,
    neighbor: str,
    *,
    direction: str = "outgoing",
    target_anchor: str | None = None,
) -> LinkedDocument:
    return LinkedDocument(
        seed_document_id=seed,
        neighbor_document_id=neighbor,
        direction=direction,
        source_section_id=f"{seed}::_::0",
        raw_target=f"{neighbor}.md",
        target_anchor=target_anchor,
    )


def _match(document_id: str, section_id: str, score: float = 1.0) -> SectionMatch:
    return SectionMatch(
        section_id=section_id,
        document_id=document_id,
        heading="Neighbor Heading",
        score=score,
        source_path=f"{document_id}.md",
    )


def test_expand_hits_adds_neighbor_section_with_graph_path():
    seed_hits = [_seed_hit("billing", "billing::_::0")]
    links = [_link("billing", "payments")]
    candidates = {"payments": (_match("payments", "payments::_::0"), "relevance")}

    expanded = expand_hits(
        seed_hits, links, candidates, graph_expansion_weight=0.5, max_expanded=5
    )

    assert len(expanded) == 1
    hit = expanded[0]
    assert hit.section_id == "payments::_::0"
    assert hit.document_id == "payments"
    assert hit.graph_path == ("billing", "LINKS_TO", "payments")
    assert hit.via_document_id == "billing"
    assert hit.selection_strategy == "relevance"
    assert hit.expansion_score == 0.5


def test_expand_hits_reverses_graph_path_for_incoming_direction():
    seed_hits = [_seed_hit("billing", "billing::_::0")]
    links = [_link("billing", "payments", direction="incoming")]
    candidates = {"payments": (_match("payments", "payments::_::0"), "anchor")}

    expanded = expand_hits(
        seed_hits, links, candidates, graph_expansion_weight=0.5, max_expanded=5
    )

    assert expanded[0].graph_path == ("payments", "LINKS_TO", "billing")


def test_expand_hits_excludes_sections_already_in_seed_hits():
    seed_hits = [_seed_hit("billing", "billing::_::0")]
    links = [_link("billing", "payments")]
    candidates = {"payments": (_match("payments", "billing::_::0"), "relevance")}

    expanded = expand_hits(
        seed_hits, links, candidates, graph_expansion_weight=0.5, max_expanded=5
    )

    assert expanded == []


def test_expand_hits_skips_neighbors_with_no_candidate_section():
    seed_hits = [_seed_hit("billing", "billing::_::0")]
    links = [_link("billing", "unindexed-neighbor")]
    candidates: dict = {}

    expanded = expand_hits(
        seed_hits, links, candidates, graph_expansion_weight=0.5, max_expanded=5
    )

    assert expanded == []


def test_expand_hits_first_section_strategy_scores_lower_than_relevance():
    seed_hits = [_seed_hit("billing", "billing::_::0")]
    links = [_link("billing", "a"), _link("billing", "b")]
    candidates = {
        "a": (_match("a", "a::_::0"), "first-section"),
        "b": (_match("b", "b::_::0"), "relevance"),
    }

    expanded = expand_hits(
        seed_hits, links, candidates, graph_expansion_weight=1.0, max_expanded=5
    )

    by_id = {hit.section_id: hit for hit in expanded}
    assert by_id["a::_::0"].expansion_score < by_id["b::_::0"].expansion_score
    assert expanded[0].section_id == "b::_::0"


def test_expand_hits_deduplicates_section_reached_via_multiple_seeds():
    seed_hits = [_seed_hit("billing", "billing::_::0"), _seed_hit("invoices", "invoices::_::0")]
    links = [
        _link("billing", "payments"),
        _link("invoices", "payments"),
    ]
    candidates = {"payments": (_match("payments", "payments::_::0"), "anchor")}

    expanded = expand_hits(
        seed_hits, links, candidates, graph_expansion_weight=0.5, max_expanded=5
    )

    assert len(expanded) == 1


def test_expand_hits_enforces_max_expanded_result_count_limit():
    seed_hits = [_seed_hit("billing", "billing::_::0")]
    links = [_link("billing", f"doc{i}") for i in range(10)]
    candidates = {
        f"doc{i}": (_match(f"doc{i}", f"doc{i}::_::0", score=float(i)), "relevance")
        for i in range(10)
    }

    expanded = expand_hits(
        seed_hits, links, candidates, graph_expansion_weight=1.0, max_expanded=3
    )

    assert len(expanded) == 3


def test_expand_hits_orders_deterministically_by_score_then_section_id():
    seed_hits = [_seed_hit("billing", "billing::_::0")]
    links = [_link("billing", "a"), _link("billing", "z")]
    candidates = {
        "a": (_match("a", "a::_::0"), "relevance"),
        "z": (_match("z", "z::_::0"), "relevance"),
    }

    expanded = expand_hits(
        seed_hits, links, candidates, graph_expansion_weight=1.0, max_expanded=5
    )

    assert [hit.section_id for hit in expanded] == ["a::_::0", "z::_::0"]


def test_expand_hits_returns_empty_list_for_no_links():
    seed_hits = [_seed_hit("billing", "billing::_::0")]

    expanded = expand_hits(
        seed_hits, [], {}, graph_expansion_weight=0.5, max_expanded=5
    )

    assert expanded == []
