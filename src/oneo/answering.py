"""Grounded answer generation with stable citations.

Builds a bounded evidence context from a :class:`~oneo.models.RetrievalResult`,
sends it to a narrowly injected :class:`ChatModel`, and returns an
:class:`~oneo.models.AnswerResult` whose citations are all validated
against that context -- a citation can never point at an unindexed
file, an invented source, or a graph node absent from retrieval.

No provider registry, prompt-template framework, or tool-calling
infrastructure is introduced. :class:`ExtractiveChatModel` is the only
built-in ``ChatModel``: a deterministic, offline default that quotes
evidence sentences directly, so `oneo query` produces grounded answers
without any external credentials or network access. A real LLM-backed
``ChatModel`` can be substituted without changing anything else.
"""

from __future__ import annotations

import re
from typing import Protocol

from oneo.models import (
    AnswerResult,
    Citation,
    GraphExpandedHit,
    RetrievalHit,
    RetrievalResult,
)

_CITATION_PATTERN = re.compile(r"\[S(\d+)\]")
_HEADER_PATTERN = re.compile(r"^\[S(\d+)\]")
_INSUFFICIENT_EVIDENCE = "insufficient evidence"


class ChatModel(Protocol):
    """The narrow chat/completion boundary answer generation depends
    on. Implementations receive one rendered prompt and return raw
    text; no memory, tool use, or routing is part of this contract."""

    def generate(self, prompt: str) -> str: ...


class _ContextEntry:
    """One piece of evidence exposed to the chat model under a stable
    citation label."""

    __slots__ = (
        "label",
        "document_id",
        "section_id",
        "heading",
        "source_path",
        "text",
        "origin",
        "graph_path",
    )

    def __init__(
        self,
        label: str,
        document_id: str,
        section_id: str,
        heading: str,
        source_path: str,
        text: str,
        origin: str,
        graph_path: tuple[str, str, str] | None,
    ) -> None:
        self.label = label
        self.document_id = document_id
        self.section_id = section_id
        self.heading = heading
        self.source_path = source_path
        self.text = text
        self.origin = origin
        self.graph_path = graph_path


def _is_relevant_seed(hit: RetrievalHit, *, min_vector_score: float) -> bool:
    """A seed hit counts as relevant evidence only when its
    vector-search cosine similarity reaches ``min_vector_score``.

    Neo4j full-text scores are not used as a relevance signal on their
    own: short stopword-heavy queries can still score positively
    against unrelated sections through common-word overlap, and
    rank-fusion scores are not a relevance signal either, since vector
    search always returns its top-k nearest neighbors even for an
    unrelated query. A hit without a vector score (lexical-only) is
    therefore never treated as relevant by itself."""

    return hit.vector_score is not None and hit.vector_score >= min_vector_score


def _build_context(
    retrieval: RetrievalResult,
    section_texts: dict[str, str],
    *,
    max_sections: int,
    min_vector_score: float,
) -> list[_ContextEntry]:
    """Select relevant, text-bearing hits (seed hits first, then
    graph-expanded hits reached from a relevant seed document) and
    assign each a stable ``S<n>`` citation label in that order."""

    relevant_document_ids: set[str] = set()
    candidates: list[tuple[RetrievalHit | GraphExpandedHit, str, tuple | None]] = []

    for hit in retrieval.hits:
        if not _is_relevant_seed(hit, min_vector_score=min_vector_score):
            continue
        relevant_document_ids.add(hit.document_id)
        candidates.append((hit, "seed", None))

    for expanded in retrieval.expanded_hits:
        if expanded.via_document_id not in relevant_document_ids:
            continue
        candidates.append((expanded, "expanded", expanded.graph_path))

    entries: list[_ContextEntry] = []
    for hit, origin, graph_path in candidates:
        if len(entries) >= max_sections:
            break
        text = section_texts.get(hit.section_id)
        if not text:
            continue
        entries.append(
            _ContextEntry(
                label=f"S{len(entries) + 1}",
                document_id=hit.document_id,
                section_id=hit.section_id,
                heading=hit.heading,
                source_path=hit.source_path,
                text=text,
                origin=origin,
                graph_path=graph_path,
            )
        )
    return entries


def _render_prompt(query: str, entries: list[_ContextEntry]) -> str:
    lines = [
        "Answer the question using only the evidence sections below.",
        "Cite every fact you use with its bracket label, e.g. [S1].",
        "If the evidence does not answer the question, respond with "
        f'exactly: "{_INSUFFICIENT_EVIDENCE}".',
        "",
        f"Question: {query}",
        "",
    ]
    for entry in entries:
        lines.append(f"[{entry.label}] {entry.document_id} - {entry.heading} ({entry.source_path})")
        lines.append(entry.text)
        lines.append("")
    return "\n".join(lines)


def _is_insufficient(text: str) -> bool:
    return text.strip().lower().startswith(_INSUFFICIENT_EVIDENCE)


def _extract_cited_labels(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for number in _CITATION_PATTERN.findall(text):
        seen.setdefault(f"S{number}", None)
    return list(seen)


def generate_answer(
    query: str,
    retrieval: RetrievalResult,
    section_texts: dict[str, str],
    chat_model: ChatModel | None,
    *,
    max_context_sections: int,
    min_vector_score: float = 0.35,
) -> AnswerResult:
    """Generate a grounded answer for ``query`` from ``retrieval``.

    Returns an insufficient-evidence result without calling
    ``chat_model`` when it is ``None`` or when no retrieved section
    clears the relevance bar. Any citation label the model returns
    that does not map to an entry actually included in the prompt is
    silently dropped -- it can never be fabricated or point outside
    the retrieval context.
    """

    entries = _build_context(
        retrieval,
        section_texts,
        max_sections=max_context_sections,
        min_vector_score=min_vector_score,
    )
    if not entries or chat_model is None:
        return AnswerResult(
            query=query,
            answer=_INSUFFICIENT_EVIDENCE,
            citations=(),
            retrieval=retrieval,
            graph_paths=(),
            insufficient_evidence=True,
        )

    raw_answer = chat_model.generate(_render_prompt(query, entries))

    if _is_insufficient(raw_answer):
        return AnswerResult(
            query=query,
            answer=raw_answer.strip(),
            citations=(),
            retrieval=retrieval,
            graph_paths=(),
            insufficient_evidence=True,
        )

    entries_by_label = {entry.label: entry for entry in entries}
    citations = tuple(
        Citation(
            label=label,
            document_id=entry.document_id,
            section_id=entry.section_id,
            source_path=entry.source_path,
            heading=entry.heading,
            retrieval_origin=entry.origin,
        )
        for label in _extract_cited_labels(raw_answer)
        if (entry := entries_by_label.get(label)) is not None
    )

    if not citations:
        return AnswerResult(
            query=query,
            answer=_INSUFFICIENT_EVIDENCE,
            citations=(),
            retrieval=retrieval,
            graph_paths=(),
            insufficient_evidence=True,
        )

    cited_labels = {citation.label for citation in citations}
    graph_paths = tuple(
        dict.fromkeys(
            entry.graph_path
            for entry in entries
            if entry.label in cited_labels and entry.graph_path is not None
        )
    )

    return AnswerResult(
        query=query,
        answer=raw_answer.strip(),
        citations=citations,
        retrieval=retrieval,
        graph_paths=graph_paths,
        insufficient_evidence=False,
    )


class ExtractiveChatModel:
    """Deterministic, offline default ``ChatModel``.

    Quotes the first sentence of each evidence block directly out of
    the rendered prompt, tagged with that block's citation label. Used
    as the built-in default so ``oneo query`` produces grounded
    answers with real citations without any external LLM credentials;
    a real provider can be injected in its place without changing
    ``generate_answer`` or any caller.
    """

    def generate(self, prompt: str) -> str:
        lines = prompt.splitlines()
        sentences: list[str] = []

        index = 0
        while index < len(lines):
            header_match = _HEADER_PATTERN.match(lines[index])
            if header_match and index + 1 < len(lines):
                label = f"S{header_match.group(1)}"
                text_line = lines[index + 1].strip()
                if text_line:
                    first_sentence = text_line.split(". ", 1)[0].rstrip(".")
                    sentences.append(f"{first_sentence} [{label}]")
                index += 2
                continue
            index += 1

        if not sentences:
            return _INSUFFICIENT_EVIDENCE
        return ". ".join(sentences) + "."
