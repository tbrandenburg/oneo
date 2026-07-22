"""Domain models shared across Oneo components.

Only the models required so far are defined here. Retrieval, graph, and
answer models are introduced in later steps.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class HealthStatus:
    """Result of a Neo4j connectivity health check."""

    connected: bool
    database: str
    server_agent: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class OkfDocument:
    """A single parsed OKF document.

    ``document_id`` is the bundle-relative source path with the
    ``.md``/``.markdown`` suffix removed. It is never derived from
    content.
    """

    document_id: str
    title: str
    source_path: str
    metadata: Mapping[str, object]
    content_hash: str


@dataclass(frozen=True)
class OkfSection:
    """A Markdown heading section, the base retrieval unit.

    ``section_id`` is derived from ``document_id``, the normalized
    heading path, and the section ordinal -- never from section text --
    so that editing section text does not change its identity.
    """

    section_id: str
    document_id: str
    heading: str
    heading_path: tuple[str, ...]
    ordinal: int
    text: str
    anchor: str | None
    source_path: str
    content_hash: str
    line: int | None = None


@dataclass(frozen=True)
class OkfLink:
    """A link discovered in an OKF document.

    Resolution of ``target_document_id`` against the corpus happens in
    a later step; the loader only distinguishes local from external
    links and extracts the raw target and any anchor fragment.
    """

    source_document_id: str
    source_section_id: str | None
    raw_target: str
    target_document_id: str | None
    target_anchor: str | None
    is_external: bool
    line: int | None = None


@dataclass(frozen=True)
class ParsedDocument:
    """The full parse result for one OKF source file."""

    document: OkfDocument
    sections: tuple[OkfSection, ...]
    links: tuple[OkfLink, ...]


@dataclass(frozen=True)
class Diagnostic:
    """A single structured corpus-validation finding.

    ``severity`` is either ``"error"`` or ``"warning"``. Diagnostics are
    always produced, in both strict and permissive mode; only strict
    mode treats specific diagnostic codes as validation failures.
    """

    severity: str
    code: str
    source_path: str
    message: str
    source_section: str | None = None
    line: int | None = None
    raw_target: str | None = None
    resolved_target: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    """The outcome of validating an OKF corpus.

    ``ok`` reflects whether validation passed for the requested mode:
    in permissive mode it is always ``True`` (recoverable issues are
    reported but never fail validation); in strict mode it is ``False``
    if any strict-failing diagnostic was produced.
    """

    diagnostics: tuple[Diagnostic, ...]
    ok: bool


@dataclass(frozen=True)
class IndexedDocument:
    """A document node as read back from the Neo4j graph index."""

    document_id: str
    title: str
    source_path: str
    content_hash: str


@dataclass(frozen=True)
class IndexSummary:
    """Counts of what was written during a single ``index`` run."""

    documents: int
    sections: int
    links: int


@dataclass(frozen=True)
class SectionMatch:
    """A single vector-search hit against the ``OkfSection`` index."""

    section_id: str
    document_id: str
    heading: str
    score: float
    source_path: str


@dataclass(frozen=True)
class VerificationResult:
    """The outcome of comparing the filesystem corpus against the
    graph index."""

    ok: bool
    issues: tuple[str, ...]
    documents: int
    sections: int
    links: int


@dataclass(frozen=True)
class RetrievalHit:
    """A single fused hybrid-retrieval result with full provenance and
    ranking diagnostics.

    ``vector_rank``/``vector_score`` and ``lexical_rank``/
    ``lexical_score`` are ``None`` when the section was not returned by
    that retrieval path. ``retrieval_origin`` is one of ``"vector"``,
    ``"lexical"``, or ``"both"``.
    """

    section_id: str
    document_id: str
    heading: str
    source_path: str
    vector_rank: int | None
    vector_score: float | None
    lexical_rank: int | None
    lexical_score: float | None
    fused_score: float
    retrieval_origin: str


@dataclass(frozen=True)
class LinkedDocument:
    """A single one-hop ``LINKS_TO`` edge from a seed document to a
    neighboring document that was not itself among the seeds.

    ``direction`` is ``"outgoing"`` when the edge points from the seed
    document to the neighbor, or ``"incoming"`` when it points from the
    neighbor to the seed document.
    """

    seed_document_id: str
    neighbor_document_id: str
    direction: str
    source_section_id: str | None
    raw_target: str
    target_anchor: str | None


@dataclass(frozen=True)
class GraphExpandedHit:
    """A section added to retrieval results through one-hop graph
    expansion, kept distinct from seed hybrid-retrieval hits.

    ``selection_strategy`` records which strategy chose this section:
    ``"anchor"`` (the link's target anchor resolved to this section),
    ``"relevance"`` (the highest lexical/vector match within the
    neighboring document), or ``"first-section"`` (the deterministic
    fallback when neither of the above applies).
    """

    section_id: str
    document_id: str
    heading: str
    source_path: str
    expansion_score: float
    graph_path: tuple[str, str, str]
    via_document_id: str
    selection_strategy: str


@dataclass(frozen=True)
class RetrievalResult:
    """The outcome of one hybrid-retrieval run.

    ``expanded_hits`` is populated only when graph expansion was
    requested (``mode="graph-hybrid"``); it is empty for plain hybrid
    retrieval.
    """

    query: str
    hits: tuple[RetrievalHit, ...]
    expanded_hits: tuple[GraphExpandedHit, ...] = ()


@dataclass(frozen=True)
class Citation:
    """A single grounded citation backing part of an answer.

    Every field is copied directly from the retrieval context (a seed
    ``RetrievalHit`` or a ``GraphExpandedHit``) the answer was
    generated from -- a citation can never reference an unindexed
    file, an invented source, or a graph node absent from that
    context. ``label`` is the stable ``"S<n>"`` marker used in the
    answer text; ``retrieval_origin`` is ``"seed"`` or ``"expanded"``.
    """

    label: str
    document_id: str
    section_id: str
    source_path: str
    heading: str
    retrieval_origin: str


@dataclass(frozen=True)
class AnswerResult:
    """The outcome of one grounded-answer-generation run.

    ``insufficient_evidence`` is ``True`` whenever no chat model is
    configured, the retrieval context contains no sufficiently
    relevant evidence, or the chat model itself reports it cannot
    answer from the supplied evidence -- in every such case
    ``citations`` and ``graph_paths`` are empty.
    """

    query: str
    answer: str
    citations: tuple[Citation, ...]
    retrieval: RetrievalResult
    graph_paths: tuple[tuple[str, str, str], ...]
    insufficient_evidence: bool
