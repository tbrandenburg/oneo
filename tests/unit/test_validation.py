from __future__ import annotations

from oneo.okf_loader import OkfLoader
from oneo.validation import resolve_links, validate_corpus


def _write(root, relative_path, content):
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return relative_path


def _load_all(root, paths):
    loader = OkfLoader(corpus_root=str(root))
    return [loader.load(path) for path in paths]


def test_permissive_mode_never_fails(tmp_path):
    _write(
        tmp_path,
        "doc.md",
        "---\ntitle: Doc\n---\n\n# Doc\n\n[broken](missing.md)\n",
    )
    documents = _load_all(tmp_path, ["doc.md"])

    result = validate_corpus(documents, strict=False)

    assert result.ok is True
    assert any(d.code == "unresolved-link" for d in result.diagnostics)
    assert any(d.severity == "warning" for d in result.diagnostics)


def test_strict_mode_fails_on_missing_type_field(tmp_path):
    _write(tmp_path, "doc.md", "---\ntitle: Doc\n---\n\n# Doc\n\nBody.\n")
    documents = _load_all(tmp_path, ["doc.md"])

    result = validate_corpus(documents, strict=True)

    assert result.ok is False
    assert any(d.code == "missing-required-field" for d in result.diagnostics)


def test_strict_mode_passes_with_type_field(tmp_path):
    _write(tmp_path, "doc.md", "---\ntitle: Doc\ntype: concept\n---\n\n# Doc\n\nBody.\n")
    documents = _load_all(tmp_path, ["doc.md"])

    result = validate_corpus(documents, strict=True)

    assert result.ok is True
    assert result.diagnostics == ()


def _heading_line(content: str, heading: str) -> int:
    """Return the 1-indexed line number of ``heading`` within ``content``,
    matching the real file layout (used to compute expected diagnostic
    ``line`` values against the *actual* fixture text, not a
    body-relative guess)."""

    for index, line in enumerate(content.splitlines(), start=1):
        if line.strip() == heading:
            return index
    raise AssertionError(f"heading {heading!r} not found in fixture content")


def test_strict_mode_fails_on_unresolved_link(tmp_path):
    content = "---\ntitle: Doc\ntype: concept\n---\n\n# Doc\n\n[broken](missing.md)\n"
    _write(tmp_path, "doc.md", content)
    documents = _load_all(tmp_path, ["doc.md"])

    result = validate_corpus(documents, strict=True)

    assert result.ok is False
    diagnostic = next(d for d in result.diagnostics if d.code == "unresolved-link")
    assert diagnostic.severity == "error"
    assert diagnostic.source_path == "doc.md"
    assert diagnostic.raw_target == "missing.md"
    assert diagnostic.line == _heading_line(content, "# Doc")


def test_strict_mode_fails_on_unresolved_link_with_multiline_frontmatter(tmp_path):
    content = (
        "---\n"
        "title: Doc\n"
        "type: concept\n"
        "description: A longer piece of frontmatter metadata\n"
        "tags:\n"
        "  - one\n"
        "  - two\n"
        "---\n"
        "\n"
        "# Doc\n"
        "\n"
        "[broken](missing.md)\n"
    )
    _write(tmp_path, "doc.md", content)
    documents = _load_all(tmp_path, ["doc.md"])

    result = validate_corpus(documents, strict=True)

    assert result.ok is False
    diagnostic = next(d for d in result.diagnostics if d.code == "unresolved-link")
    assert diagnostic.line == _heading_line(content, "# Doc")
    assert diagnostic.line == 10


def test_strict_mode_fails_on_unresolved_anchor(tmp_path):
    a_content = "---\ntitle: A\ntype: concept\n---\n\n# A\n\n[bad anchor](b.md#no-such-anchor)\n"
    _write(tmp_path, "a.md", a_content)
    _write(tmp_path, "b.md", "---\ntitle: B\ntype: concept\n---\n\n# B\n\nBody.\n")
    documents = _load_all(tmp_path, ["a.md", "b.md"])

    result = validate_corpus(documents, strict=True)

    assert result.ok is False
    diagnostic = next(d for d in result.diagnostics if d.code == "unresolved-anchor")
    assert diagnostic.source_path == "a.md"
    assert diagnostic.line == _heading_line(a_content, "# A")


def test_resolved_link_and_anchor_produce_no_diagnostics(tmp_path):
    _write(
        tmp_path,
        "a.md",
        "---\ntitle: A\ntype: concept\n---\n\n# A\n\n[good](b.md#b)\n",
    )
    _write(tmp_path, "b.md", "---\ntitle: B\ntype: concept\n---\n\n# B\n\nBody.\n")
    documents = _load_all(tmp_path, ["a.md", "b.md"])

    result = validate_corpus(documents, strict=True)

    assert result.ok is True
    assert result.diagnostics == ()


def test_external_links_are_never_validated(tmp_path):
    _write(
        tmp_path,
        "doc.md",
        "---\ntitle: Doc\ntype: concept\n---\n\n# Doc\n\n"
        "[ext](https://example.com/nope)\n",
    )
    documents = _load_all(tmp_path, ["doc.md"])

    result = validate_corpus(documents, strict=True)

    assert result.ok is True
    assert result.diagnostics == ()


def test_duplicate_document_ids_fail_strict_validation(tmp_path):
    _write(tmp_path, "doc.md", "---\ntitle: Doc\ntype: concept\n---\n\n# Doc\n\nA.\n")
    _write(
        tmp_path, "doc.MD", "---\ntitle: Doc2\ntype: concept\n---\n\n# Doc2\n\nB.\n"
    )
    documents = _load_all(tmp_path, ["doc.md", "doc.MD"])

    result = validate_corpus(documents, strict=True)

    assert result.ok is False
    assert any(d.code == "duplicate-document-id" for d in result.diagnostics)


def test_duplicate_section_ids_carry_line_numbers(tmp_path):
    doc_content = "---\ntitle: Doc\ntype: concept\n---\n\n# Same\n\nA.\n"
    doc2_content = "---\ntitle: Doc2\ntype: concept\n---\n\n# Same\n\nB.\n"
    _write(tmp_path, "doc.md", doc_content)
    _write(tmp_path, "doc.MD", doc2_content)
    documents = _load_all(tmp_path, ["doc.md", "doc.MD"])

    result = validate_corpus(documents, strict=True)

    assert result.ok is False
    duplicates = [d for d in result.diagnostics if d.code == "duplicate-section-id"]
    assert len(duplicates) == 2
    expected_line = _heading_line(doc_content, "# Same")
    for diagnostic in duplicates:
        assert diagnostic.line == expected_line


def test_diagnostics_are_deterministic_across_runs(tmp_path):
    _write(
        tmp_path,
        "doc.md",
        "---\ntitle: Doc\n---\n\n# Doc\n\n[broken](missing.md)\n",
    )
    documents = _load_all(tmp_path, ["doc.md"])

    first = validate_corpus(documents, strict=True)
    second = validate_corpus(documents, strict=True)

    assert first.diagnostics == second.diagnostics


def test_resolve_links_populates_target_for_resolvable_local_link(tmp_path):
    _write(
        tmp_path,
        "doc.md",
        "---\ntitle: Doc\ntype: concept\n---\n\n# Doc\n\n[good](other.md)\n",
    )
    _write(
        tmp_path,
        "other.md",
        "---\ntitle: Other\ntype: concept\n---\n\n# Other\n\nBody.\n",
    )
    documents = _load_all(tmp_path, ["doc.md", "other.md"])

    resolved = resolve_links(documents)

    assert len(resolved) == 1
    assert resolved[0].source_document_id == "doc"
    assert resolved[0].target_document_id == "other"


def test_resolve_links_omits_unresolved_and_external_links(tmp_path):
    _write(
        tmp_path,
        "doc.md",
        "---\ntitle: Doc\ntype: concept\n---\n\n# Doc\n\n"
        "[broken](missing.md) [ext](https://example.com)\n",
    )
    documents = _load_all(tmp_path, ["doc.md"])

    resolved = resolve_links(documents)

    assert resolved == []


def test_resolve_links_is_deterministic_across_runs(tmp_path):
    _write(
        tmp_path,
        "doc.md",
        "---\ntitle: Doc\ntype: concept\n---\n\n# Doc\n\n[good](other.md)\n",
    )
    _write(
        tmp_path,
        "other.md",
        "---\ntitle: Other\ntype: concept\n---\n\n# Other\n\nBody.\n",
    )
    documents = _load_all(tmp_path, ["doc.md", "other.md"])

    assert resolve_links(documents) == resolve_links(documents)
