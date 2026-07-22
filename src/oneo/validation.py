"""OKF corpus validation and link resolution.

Validates a parsed corpus against OKF semantics before any Neo4j graph
writes occur. Per OKF spec 9, a broken cross-link is not malformed --
consumers must tolerate it -- so permissive mode (the default) reports
every issue as a diagnostic without failing validation. Strict mode is
a project-specific opt-in that fails on a fixed set of diagnostic
codes.

Link resolution here only determines whether a raw link target matches
a document/anchor already present in the corpus; it does not mutate
the loader's ``OkfLink`` models.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from posixpath import normpath
from pathlib import PurePosixPath

from oneo.models import Diagnostic, OkfLink, ParsedDocument, ValidationResult

# Diagnostic codes that fail validation in strict mode only. In
# permissive mode every code below is still reported, just never
# treated as a failure.
STRICT_FAILURE_CODES = frozenset(
    {
        "missing-required-field",
        "duplicate-document-id",
        "duplicate-section-id",
        "unresolved-link",
        "unresolved-anchor",
        "invalid-path",
    }
)


def validate_corpus(
    documents: list[ParsedDocument], strict: bool = False
) -> ValidationResult:
    """Validate ``documents`` and produce structured diagnostics.

    Args:
        documents: The parsed corpus, as produced by
            :meth:`oneo.okf_loader.OkfLoader.load`.
        strict: If True, unresolved links/anchors, duplicate IDs,
            missing required fields, and invalid paths fail
            validation. Permissive mode (the default) never fails.

    Returns:
        A :class:`~oneo.models.ValidationResult` containing every
        diagnostic found and whether validation passed for the
        requested mode.
    """

    diagnostics: list[Diagnostic] = []
    diagnostics.extend(_validate_required_fields(documents))
    diagnostics.extend(_validate_document_ids(documents))
    diagnostics.extend(_validate_duplicate_document_ids(documents))
    diagnostics.extend(_validate_duplicate_section_ids(documents))
    diagnostics.extend(_validate_links(documents, strict=strict))

    ok = True
    if strict:
        ok = not any(d.code in STRICT_FAILURE_CODES for d in diagnostics)

    return ValidationResult(diagnostics=tuple(diagnostics), ok=ok)


def _validate_required_fields(documents: list[ParsedDocument]) -> list[Diagnostic]:
    """Fail (in strict mode) when frontmatter is missing a non-empty
    ``type`` field (OKF spec 9)."""

    diagnostics: list[Diagnostic] = []
    for parsed in documents:
        document = parsed.document
        type_value = document.metadata.get("type")
        if not (isinstance(type_value, str) and type_value.strip()):
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="missing-required-field",
                    source_path=document.source_path,
                    message="frontmatter is missing a non-empty 'type' field",
                    line=1,
                )
            )
    return diagnostics


def _validate_document_ids(documents: list[ParsedDocument]) -> list[Diagnostic]:
    """Fail (in strict mode) on structurally invalid document IDs."""

    diagnostics: list[Diagnostic] = []
    for parsed in documents:
        document = parsed.document
        document_id = document.document_id
        if not document_id or document_id.startswith("/") or ".." in document_id:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="invalid-path",
                    source_path=document.source_path,
                    message=f"invalid document ID: {document_id!r}",
                )
            )
    return diagnostics


def _validate_duplicate_document_ids(
    documents: list[ParsedDocument],
) -> list[Diagnostic]:
    """Detect filesystem-level document ID collisions (OKF spec 9.3)."""

    by_id: dict[str, list[ParsedDocument]] = defaultdict(list)
    for parsed in documents:
        by_id[parsed.document.document_id].append(parsed)

    diagnostics: list[Diagnostic] = []
    for document_id, group in sorted(by_id.items()):
        if len(group) <= 1:
            continue
        for parsed in group:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="duplicate-document-id",
                    source_path=parsed.document.source_path,
                    message=f"duplicate document ID: {document_id!r}",
                )
            )
    return diagnostics


def _validate_duplicate_section_ids(
    documents: list[ParsedDocument],
) -> list[Diagnostic]:
    """Detect duplicate semantic section IDs across the corpus."""

    by_id: dict[str, list[tuple[ParsedDocument, object]]] = defaultdict(list)
    for parsed in documents:
        for section in parsed.sections:
            by_id[section.section_id].append((parsed, section))

    diagnostics: list[Diagnostic] = []
    for section_id, group in sorted(by_id.items()):
        if len(group) <= 1:
            continue
        for parsed, section in group:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="duplicate-section-id",
                    source_path=parsed.document.source_path,
                    source_section=section_id,
                    message=f"duplicate section ID: {section_id!r}",
                    line=section.line,
                )
            )
    return diagnostics


def resolve_local_target(
    source_document_id: str, path_part: str
) -> str:
    """Resolve a local link's path portion into a document ID, relative
    to the linking document's directory."""

    if not path_part:
        return source_document_id

    source_dir = PurePosixPath(source_document_id).parent
    combined = source_dir / path_part
    normalized = normpath(str(combined))

    for suffix in (".md", ".markdown"):
        if normalized.lower().endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break

    return normalized


def _validate_links(
    documents: list[ParsedDocument], strict: bool
) -> list[Diagnostic]:
    """Resolve every local link's document and anchor target and report
    unresolved cross-links and anchors as diagnostics."""

    document_ids = {parsed.document.document_id for parsed in documents}
    anchors_by_document: dict[str, set[str]] = defaultdict(set)
    for parsed in documents:
        for section in parsed.sections:
            if section.anchor:
                anchors_by_document[parsed.document.document_id].add(section.anchor)

    diagnostics: list[Diagnostic] = []
    for parsed in documents:
        for link in parsed.links:
            if link.is_external:
                continue
            diagnostics.extend(
                _validate_local_link(
                    link=link,
                    source_path=parsed.document.source_path,
                    document_ids=document_ids,
                    anchors_by_document=anchors_by_document,
                    strict=strict,
                )
            )
    return diagnostics


def _validate_local_link(
    link: OkfLink,
    source_path: str,
    document_ids: set[str],
    anchors_by_document: dict[str, set[str]],
    strict: bool,
) -> list[Diagnostic]:
    severity = "error" if strict else "warning"
    path_part, _, _ = link.raw_target.partition("#")
    target_document_id = resolve_local_target(link.source_document_id, path_part)

    if target_document_id not in document_ids:
        return [
            Diagnostic(
                severity=severity,
                code="unresolved-link",
                source_path=source_path,
                source_section=link.source_section_id,
                raw_target=link.raw_target,
                resolved_target=target_document_id,
                message=f"unresolved local document link: {link.raw_target!r}",
                line=link.line,
            )
        ]

    if link.target_anchor and link.target_anchor not in anchors_by_document.get(
        target_document_id, set()
    ):
        return [
            Diagnostic(
                severity=severity,
                code="unresolved-anchor",
                source_path=source_path,
                source_section=link.source_section_id,
                raw_target=link.raw_target,
                resolved_target=f"{target_document_id}#{link.target_anchor}",
                message=f"unresolved local anchor: {link.raw_target!r}",
                line=link.line,
            )
        ]

    return []


def resolve_links(documents: list[ParsedDocument]) -> list[OkfLink]:
    """Resolve every local link's target document against the corpus.

    Returns only local links whose target document actually exists in
    ``documents``, with ``target_document_id`` populated. External
    links and unresolved local links are omitted -- this list is used
    to project ``LINKS_TO`` graph edges, which must point at real
    document nodes.
    """

    document_ids = {parsed.document.document_id for parsed in documents}
    resolved: list[OkfLink] = []
    for parsed in documents:
        for link in parsed.links:
            if link.is_external:
                continue
            path_part, _, _ = link.raw_target.partition("#")
            target_document_id = resolve_local_target(link.source_document_id, path_part)
            if target_document_id not in document_ids:
                continue
            resolved.append(replace(link, target_document_id=target_document_id))
    return resolved
