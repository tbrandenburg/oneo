"""One-hop graph expansion over explicit OKF document relationships.

Expands hybrid-retrieval results with sections from neighboring
documents reached through a single ``LINKS_TO`` hop. This module is a
small, independently testable function -- not a generic traversal
policy -- and it operates entirely on data already fetched by the
Neo4j store; it issues no Cypher itself.

Neighbor section selection follows one explicit, deterministic
strategy per neighboring document, chosen by the caller and passed in
via ``candidates``: prefer the link's anchor target, fall back to the
highest lexical/vector relevance within the neighboring document, and
finally fall back to the neighboring document's first section.
"""

from __future__ import annotations

from oneo.models import GraphExpandedHit, LinkedDocument, RetrievalHit, SectionMatch

_FIRST_SECTION_STRATEGY = "first-section"
_STRATEGY_CONFIDENCE = {
    "anchor": 1.0,
    "relevance": 1.0,
    _FIRST_SECTION_STRATEGY: 0.5,
}


def expand_hits(
    seed_hits: list[RetrievalHit],
    links: list[LinkedDocument],
    candidates: dict[str, tuple[SectionMatch, str]],
    *,
    graph_expansion_weight: float,
    max_expanded: int,
) -> list[GraphExpandedHit]:
    """Expand ``seed_hits`` through the given one-hop ``links``.

    ``candidates`` maps a neighboring document ID to the section
    already selected for it (via anchor, relevance, or first-section
    fallback) and the name of the strategy used. Seed sections are
    never duplicated as expanded results. Results are deterministically
    ordered by descending expansion score, then by ``section_id``, and
    truncated to ``max_expanded`` to enforce a result-count limit.
    """

    seed_section_ids = {hit.section_id for hit in seed_hits}
    expanded_by_section: dict[str, GraphExpandedHit] = {}

    for link in links:
        candidate = candidates.get(link.neighbor_document_id)
        if candidate is None:
            continue
        match, strategy = candidate
        if match.section_id in seed_section_ids:
            continue

        if link.direction == "outgoing":
            graph_path = (
                link.seed_document_id,
                "LINKS_TO",
                link.neighbor_document_id,
            )
        else:
            graph_path = (
                link.neighbor_document_id,
                "LINKS_TO",
                link.seed_document_id,
            )

        expansion_score = graph_expansion_weight * _STRATEGY_CONFIDENCE.get(
            strategy, 0.0
        )

        existing = expanded_by_section.get(match.section_id)
        if existing is not None and existing.expansion_score >= expansion_score:
            continue

        expanded_by_section[match.section_id] = GraphExpandedHit(
            section_id=match.section_id,
            document_id=match.document_id,
            heading=match.heading,
            source_path=match.source_path,
            expansion_score=expansion_score,
            graph_path=graph_path,
            via_document_id=link.seed_document_id,
            selection_strategy=strategy,
        )

    ordered = sorted(
        expanded_by_section.values(),
        key=lambda hit: (-hit.expansion_score, hit.section_id),
    )
    return ordered[:max_expanded]
