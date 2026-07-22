"""Explicit, explainable rank fusion for hybrid retrieval.

Combines a vector-search result list and a full-text result list into
a single deduplicated, ranked list of :class:`~oneo.models.RetrievalHit`
using reciprocal-rank fusion (RRF). This is intentionally a small,
independently testable function -- not a generic ranking framework.
"""

from __future__ import annotations

from oneo.models import RetrievalHit, SectionMatch


def fuse_rankings(
    vector_matches: list[SectionMatch],
    lexical_matches: list[SectionMatch],
    *,
    fusion_k: int,
    vector_weight: float,
    lexical_weight: float,
) -> list[RetrievalHit]:
    """Fuse vector and lexical result lists using weighted
    reciprocal-rank fusion.

    Each result list is assumed to already be ranked best-first (rank
    1 is the best match). The fused score for a section is:

        score = vector_weight * 1 / (fusion_k + vector_rank)
              + lexical_weight * 1 / (fusion_k + lexical_rank)

    where a rank term is omitted entirely when the section was not
    returned by that retrieval path. Sections are deduplicated by
    ``section_id``; ties in fused score are broken deterministically
    by ``section_id`` so repeated queries produce stable ordering.
    """

    sections: dict[str, SectionMatch] = {}
    vector_rank_by_id: dict[str, int] = {}
    vector_score_by_id: dict[str, float] = {}
    lexical_rank_by_id: dict[str, int] = {}
    lexical_score_by_id: dict[str, float] = {}

    for rank, match in enumerate(vector_matches, start=1):
        sections[match.section_id] = match
        vector_rank_by_id[match.section_id] = rank
        vector_score_by_id[match.section_id] = match.score

    for rank, match in enumerate(lexical_matches, start=1):
        sections.setdefault(match.section_id, match)
        lexical_rank_by_id[match.section_id] = rank
        lexical_score_by_id[match.section_id] = match.score

    hits: list[RetrievalHit] = []
    for section_id, match in sections.items():
        vector_rank = vector_rank_by_id.get(section_id)
        lexical_rank = lexical_rank_by_id.get(section_id)

        fused_score = 0.0
        if vector_rank is not None:
            fused_score += vector_weight / (fusion_k + vector_rank)
        if lexical_rank is not None:
            fused_score += lexical_weight / (fusion_k + lexical_rank)

        if vector_rank is not None and lexical_rank is not None:
            origin = "both"
        elif vector_rank is not None:
            origin = "vector"
        else:
            origin = "lexical"

        hits.append(
            RetrievalHit(
                section_id=match.section_id,
                document_id=match.document_id,
                heading=match.heading,
                source_path=match.source_path,
                vector_rank=vector_rank,
                vector_score=vector_score_by_id.get(section_id),
                lexical_rank=lexical_rank,
                lexical_score=lexical_score_by_id.get(section_id),
                fused_score=fused_score,
                retrieval_origin=origin,
            )
        )

    hits.sort(key=lambda hit: (-hit.fused_score, hit.section_id))
    return hits
