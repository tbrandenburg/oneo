"""The OKF-aware loader.

Parses a single native OKF Markdown file into deterministic document,
section, anchor, metadata, and link models.

The loader and the token-based fallback splitter are kept conceptually
separate, even though they live in the same module:

    load  = parse OKF structure and semantics
    split = preserve sections and divide only oversized sections

Graph writes, embeddings, retrieval, answer generation, general-purpose
Markdown-to-document conversion, and link *resolution* (matching a raw
target against the corpus) are all out of scope here; link resolution
is implemented in a later step.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import frontmatter
from markdown_it import MarkdownIt

from oneo.models import OkfDocument, OkfLink, OkfSection, ParsedDocument
from oneo.security import resolve_within_root

MARKDOWN_SUFFIXES = (".md", ".markdown")

# A token-based fallback splitter divides only sections whose text
# exceeds this many whitespace-delimited tokens. Ordinary sections are
# never split.
MAX_SECTION_TOKENS = 300

_SLUG_STRIP_RE = re.compile(r"[^\w\s-]")
_SLUG_HYPHEN_RE = re.compile(r"[-\s]+")

_md = MarkdownIt("commonmark")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _frontmatter_line_offset(raw_text: str, body: str) -> int:
    """Return the number of lines consumed before ``body`` begins in
    ``raw_text``.

    ``python-frontmatter``'s ``parse()`` strips the raw text, splits off
    the frontmatter block, and strips the remaining body again before
    handing it back as ``Post.content``. Any ``start_line`` computed by
    ``markdown-it-py`` against that stripped ``body`` is therefore
    relative to the stripped body, not the real file on disk. This
    offset (0-indexed line count) must be added back to every
    body-relative line before it is stored, so reported line numbers
    point at the real source line.
    """

    if not body:
        return 0

    leading_whitespace = raw_text[: len(raw_text) - len(raw_text.lstrip())]
    leading_lines = leading_whitespace.count("\n")

    stripped = raw_text.strip()
    index = stripped.find(body)
    if index == -1:
        return 0
    return leading_lines + stripped[:index].count("\n")


def _slugify(text: str) -> str:
    """Produce a deterministic, GitHub-style anchor slug for ``text``."""

    normalized = _SLUG_STRIP_RE.sub("", text.strip().lower())
    slug = _SLUG_HYPHEN_RE.sub("-", normalized).strip("-")
    return slug or "section"


def _document_id(source_path: str) -> str:
    """Derive the OKF document ID: the bundle-relative path with the
    Markdown suffix removed (OKF spec 2)."""

    posix_path = Path(source_path).as_posix()
    for suffix in MARKDOWN_SUFFIXES:
        if posix_path.lower().endswith(suffix):
            return posix_path[: -len(suffix)]
    return posix_path


def _is_external_target(raw_target: str) -> bool:
    """Return True if ``raw_target`` points outside the local bundle."""

    if raw_target.startswith("//"):
        return True
    scheme = urlsplit(raw_target).scheme
    return bool(scheme)


def _split_target_anchor(raw_target: str) -> tuple[str, str | None]:
    """Split ``raw_target`` into a path portion and an optional anchor
    fragment."""

    path_part, _, fragment = raw_target.partition("#")
    return path_part, (fragment or None)


@dataclass(frozen=True)
class _HeadingBlock:
    """A single heading and the raw line range of its own section
    content (up to, but excluding, the next heading at any level)."""

    level: int
    text: str
    start_line: int
    content_start_line: int
    content_end_line: int


def _extract_heading_blocks(tokens, total_lines: int) -> list[_HeadingBlock]:
    """Walk the flat token stream and compute the raw content line range
    owned directly by each heading (excluding nested subheadings)."""

    raw_headings: list[tuple[int, str, int, int]] = []
    for index, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        level = int(token.tag[1:])
        inline_token = tokens[index + 1]
        heading_text = inline_token.content
        start_line = token.map[0] if token.map else 0
        content_start_line = token.map[1] if token.map else 0
        raw_headings.append((level, heading_text, start_line, content_start_line))

    blocks: list[_HeadingBlock] = []
    for position, (level, text, start_line, content_start) in enumerate(raw_headings):
        end_line = (
            raw_headings[position + 1][2]
            if position + 1 < len(raw_headings)
            else total_lines
        )
        blocks.append(_HeadingBlock(level, text, start_line, content_start, end_line))
    return blocks


def _extract_links(text: str) -> list[tuple[str, str, str | None]]:
    """Extract ``(raw_target, target_path, target_anchor)`` for every
    local/external link inside ``text``. External links have no
    anchor split applied to their raw target."""

    tokens = _md.parse(text)
    results: list[tuple[str, str, str | None]] = []
    for token in tokens:
        if token.type != "inline" or not token.children:
            continue
        for child in token.children:
            if child.type != "link_open":
                continue
            href = child.attrs.get("href")
            if not href:
                continue
            if _is_external_target(href):
                results.append((href, href, None))
            else:
                target_path, target_anchor = _split_target_anchor(href)
                results.append((href, target_path, target_anchor))
    return results


def _tokenize(text: str) -> list[str]:
    return text.split()


def _split_oversized_section(
    section_text: str, max_tokens: int
) -> list[str]:
    """Split ``section_text`` into deterministic fragments of at most
    ``max_tokens`` tokens each, using whitespace boundaries."""

    tokens = _tokenize(section_text)
    if len(tokens) <= max_tokens:
        return [section_text]

    fragments: list[str] = []
    for start in range(0, len(tokens), max_tokens):
        fragments.append(" ".join(tokens[start : start + max_tokens]))
    return fragments


class OkfLoader:
    """Parses native OKF Markdown files into typed document, section,
    and link models."""

    def __init__(
        self,
        knowledge_root: str,
        max_section_tokens: int = MAX_SECTION_TOKENS,
    ) -> None:
        self._knowledge_root = knowledge_root
        self._max_section_tokens = max_section_tokens

    def load(self, source_path: str) -> ParsedDocument:
        """Parse a single OKF source file into a :class:`ParsedDocument`.

        Args:
            source_path: Root-relative (or root-anchored absolute) path
                to the Markdown file, as returned by
                :func:`oneo.discovery.discover_files`.

        Returns:
            The parsed document, its ordered sections, and its links.

        Raises:
            oneo.security.PathSecurityError: If ``source_path`` violates
                the knowledge-root boundary.
        """

        # ``source_path`` is root-relative (as returned by
        # ``discover_files``); join it onto the configured root before
        # validating, since ``resolve_within_root`` resolves relative
        # paths against the current working directory, not the root.
        joined_path = str(Path(self._knowledge_root) / source_path)
        absolute_path = resolve_within_root(joined_path, self._knowledge_root)
        raw_text = absolute_path.read_text(encoding="utf-8")

        relative_path = Path(source_path).as_posix()
        document_id = _document_id(relative_path)

        post = frontmatter.loads(raw_text)
        metadata = dict(post.metadata)
        body = post.content
        line_offset = _frontmatter_line_offset(raw_text, body)

        sections, headings_used = self._build_sections(
            document_id=document_id,
            body=body,
            source_path=relative_path,
            line_offset=line_offset,
        )

        title = self._resolve_title(metadata, headings_used, document_id)

        document = OkfDocument(
            document_id=document_id,
            title=title,
            source_path=relative_path,
            metadata=metadata,
            content_hash=_sha256(raw_text),
        )

        links = self._build_links(
            document_id=document_id,
            sections=sections,
        )

        return ParsedDocument(
            document=document,
            sections=tuple(sections),
            links=tuple(links),
        )

    def _resolve_title(
        self,
        metadata: dict,
        headings_used: list[str],
        document_id: str,
    ) -> str:
        title = metadata.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
        if headings_used:
            return headings_used[0]
        return document_id

    def _build_sections(
        self,
        document_id: str,
        body: str,
        source_path: str,
        line_offset: int = 0,
    ) -> tuple[list[OkfSection], list[str]]:
        lines = body.splitlines()
        tokens = _md.parse(body)
        heading_blocks = _extract_heading_blocks(tokens, total_lines=len(lines))

        sections: list[OkfSection] = []
        heading_texts_in_order: list[str] = []
        used_anchors: dict[str, int] = {}
        ordinal = 0

        def _next_anchor(text: str) -> str:
            base = _slugify(text)
            count = used_anchors.get(base, 0)
            used_anchors[base] = count + 1
            return base if count == 0 else f"{base}-{count}"

        # Preamble content before the first heading, if any.
        first_start = heading_blocks[0].start_line if heading_blocks else 0
        preamble_start = 0
        if first_start > preamble_start:
            preamble_text = "\n".join(lines[preamble_start:first_start]).strip()
            if preamble_text:
                for fragment in self._maybe_split(preamble_text):
                    section = self._make_section(
                        document_id=document_id,
                        heading="",
                        heading_path=(),
                        ordinal=ordinal,
                        text=fragment,
                        anchor=None,
                        source_path=source_path,
                        line=preamble_start + 1 + line_offset,
                    )
                    sections.append(section)
                    ordinal += 1

        stack: list[tuple[int, str]] = []
        for block in heading_blocks:
            while stack and stack[-1][0] >= block.level:
                stack.pop()
            stack.append((block.level, block.text))
            heading_path = tuple(text for _, text in stack)
            heading_texts_in_order.append(block.text)

            anchor = _next_anchor(block.text)
            section_text = "\n".join(
                lines[block.content_start_line : block.content_end_line]
            ).strip()

            for fragment in self._maybe_split(section_text):
                section = self._make_section(
                    document_id=document_id,
                    heading=block.text,
                    heading_path=heading_path,
                    ordinal=ordinal,
                    text=fragment,
                    anchor=anchor,
                    source_path=source_path,
                    line=block.start_line + 1 + line_offset,
                )
                sections.append(section)
                ordinal += 1

        return sections, heading_texts_in_order

    def _maybe_split(self, section_text: str) -> list[str]:
        if not section_text:
            return [section_text]
        return _split_oversized_section(section_text, self._max_section_tokens)

    def _make_section(
        self,
        document_id: str,
        heading: str,
        heading_path: tuple[str, ...],
        ordinal: int,
        text: str,
        anchor: str | None,
        source_path: str,
        line: int | None = None,
    ) -> OkfSection:
        heading_slug_path = "/".join(_slugify(part) for part in heading_path) or "_"
        section_id = f"{document_id}::{heading_slug_path}::{ordinal}"
        return OkfSection(
            section_id=section_id,
            document_id=document_id,
            heading=heading,
            heading_path=heading_path,
            ordinal=ordinal,
            text=text,
            anchor=anchor,
            source_path=source_path,
            content_hash=_sha256(text),
            line=line,
        )

    def _build_links(
        self,
        document_id: str,
        sections: list[OkfSection],
    ) -> list[OkfLink]:
        links: list[OkfLink] = []
        for section in sections:
            for raw_target, target_path, target_anchor in _extract_links(
                section.text
            ):
                is_external = _is_external_target(raw_target)
                links.append(
                    OkfLink(
                        source_document_id=document_id,
                        source_section_id=section.section_id,
                        raw_target=raw_target,
                        target_document_id=None,
                        target_anchor=None if is_external else target_anchor,
                        is_external=is_external,
                        line=section.line,
                    )
                )
        return links


def corpus_to_dict(documents: list[ParsedDocument]) -> dict:
    """Produce a deterministic, JSON-serializable representation of a
    parsed corpus, suitable for ``oneo parse --output``."""

    return {
        "documents": [
            {
                "document_id": parsed.document.document_id,
                "title": parsed.document.title,
                "source_path": parsed.document.source_path,
                "metadata": parsed.document.metadata,
                "content_hash": parsed.document.content_hash,
                "sections": [
                    {
                        "section_id": section.section_id,
                        "heading": section.heading,
                        "heading_path": list(section.heading_path),
                        "ordinal": section.ordinal,
                        "anchor": section.anchor,
                        "text": section.text,
                        "content_hash": section.content_hash,
                        "source_path": section.source_path,
                    }
                    for section in parsed.sections
                ],
                "links": [
                    {
                        "source_section_id": link.source_section_id,
                        "raw_target": link.raw_target,
                        "target_document_id": link.target_document_id,
                        "target_anchor": link.target_anchor,
                        "is_external": link.is_external,
                    }
                    for link in parsed.links
                ],
            }
            for parsed in documents
        ]
    }
