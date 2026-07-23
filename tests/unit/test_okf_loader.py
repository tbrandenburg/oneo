from __future__ import annotations

from oneo.okf_loader import OkfLoader, corpus_to_dict


def _write(root, relative_path, content):
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return relative_path


def test_document_id_strips_markdown_suffix(tmp_path):
    _write(
        tmp_path,
        "tables/users.md",
        "---\ntitle: Users\n---\n\n# Users\n\nUser table.\n",
    )

    loader = OkfLoader(corpus_root=str(tmp_path))
    parsed = loader.load("tables/users.md")

    assert parsed.document.document_id == "tables/users"
    assert parsed.document.source_path == "tables/users.md"


def test_frontmatter_and_title_are_preserved(tmp_path):
    _write(
        tmp_path,
        "doc.md",
        "---\ntitle: My Doc\nowner: team-a\n---\n\n# My Doc\n\nBody.\n",
    )

    loader = OkfLoader(corpus_root=str(tmp_path))
    parsed = loader.load("doc.md")

    assert parsed.document.title == "My Doc"
    assert parsed.document.metadata["owner"] == "team-a"


def test_title_falls_back_to_first_heading_when_missing(tmp_path):
    _write(tmp_path, "doc.md", "---\nowner: team-a\n---\n\n# Heading Title\n\nBody.\n")

    loader = OkfLoader(corpus_root=str(tmp_path))
    parsed = loader.load("doc.md")

    assert parsed.document.title == "Heading Title"


def test_section_line_matches_real_file_position_with_multiline_frontmatter(
    tmp_path,
):
    content = (
        "---\n"
        "title: Doc\n"
        "type: concept\n"
        "owner: team-a\n"
        "tags:\n"
        "  - one\n"
        "  - two\n"
        "---\n"
        "\n"
        "Intro paragraph before any heading.\n"
        "\n"
        "# Intro\n"
        "\n"
        "Intro body.\n"
        "\n"
        "## Sub Heading\n"
        "\n"
        "Sub body.\n"
    )
    _write(tmp_path, "doc.md", content)
    lines = content.splitlines()
    expected_intro_line = lines.index("# Intro") + 1
    expected_sub_line = lines.index("## Sub Heading") + 1
    expected_preamble_line = (
        lines.index("Intro paragraph before any heading.") + 1
    )

    loader = OkfLoader(corpus_root=str(tmp_path))
    parsed = loader.load("doc.md")

    sections_by_heading = {section.heading: section for section in parsed.sections}
    preamble_section = next(
        section for section in parsed.sections if section.heading == ""
    )

    assert preamble_section.line == expected_preamble_line
    assert sections_by_heading["Intro"].line == expected_intro_line
    assert sections_by_heading["Sub Heading"].line == expected_sub_line


def test_heading_hierarchy_and_anchors(tmp_path):
    _write(
        tmp_path,
        "doc.md",
        "---\ntitle: Doc\n---\n\n"
        "# Doc\n\nIntro.\n\n"
        "## Section A\n\nText A.\n\n"
        "### Sub A1\n\nText A1.\n\n"
        "## Section B\n\nText B.\n",
    )

    loader = OkfLoader(corpus_root=str(tmp_path))
    parsed = loader.load("doc.md")

    headings = [(s.heading, s.heading_path, s.anchor) for s in parsed.sections]
    assert headings == [
        ("Doc", ("Doc",), "doc"),
        ("Section A", ("Doc", "Section A"), "section-a"),
        ("Sub A1", ("Doc", "Section A", "Sub A1"), "sub-a1"),
        ("Section B", ("Doc", "Section B"), "section-b"),
    ]


def test_duplicate_headings_get_deduplicated_anchors(tmp_path):
    _write(
        tmp_path,
        "doc.md",
        "---\ntitle: Doc\n---\n\n# Doc\n\nIntro.\n\n"
        "## Notes\n\nFirst.\n\n## Notes\n\nSecond.\n",
    )

    loader = OkfLoader(corpus_root=str(tmp_path))
    parsed = loader.load("doc.md")

    anchors = [s.anchor for s in parsed.sections if s.heading == "Notes"]
    assert anchors == ["notes", "notes-1"]


def test_section_ordinals_are_deterministic_sequence(tmp_path):
    _write(
        tmp_path,
        "doc.md",
        "---\ntitle: Doc\n---\n\n# Doc\n\nIntro.\n\n## A\n\nX.\n\n## B\n\nY.\n",
    )

    loader = OkfLoader(corpus_root=str(tmp_path))
    parsed = loader.load("doc.md")

    assert [s.ordinal for s in parsed.sections] == [0, 1, 2]
    assert [s.section_id for s in parsed.sections] == [
        "doc::doc::0",
        "doc::doc/a::1",
        "doc::doc/b::2",
    ]


def test_local_and_external_links_are_distinguished(tmp_path):
    _write(
        tmp_path,
        "doc.md",
        "---\ntitle: Doc\n---\n\n# Doc\n\n"
        "See [local](tables/users.md#schema) and "
        "[external](https://example.com/page).\n",
    )

    loader = OkfLoader(corpus_root=str(tmp_path))
    parsed = loader.load("doc.md")

    assert len(parsed.links) == 2
    local, external = parsed.links
    assert local.is_external is False
    assert local.raw_target == "tables/users.md#schema"
    assert local.target_anchor == "schema"
    assert external.is_external is True
    assert external.raw_target == "https://example.com/page"
    assert external.target_anchor is None


def test_source_paths_are_retained_on_every_section(tmp_path):
    _write(
        tmp_path,
        "topics/doc.md",
        "---\ntitle: Doc\n---\n\n# Doc\n\nBody.\n",
    )

    loader = OkfLoader(corpus_root=str(tmp_path))
    parsed = loader.load("topics/doc.md")

    assert all(s.source_path == "topics/doc.md" for s in parsed.sections)
    assert parsed.document.source_path == "topics/doc.md"


def test_section_id_unchanged_after_text_edit_but_content_hash_changes(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text("---\ntitle: Doc\n---\n\n# Doc\n\nOriginal text.\n")

    loader = OkfLoader(corpus_root=str(tmp_path))
    first = loader.load("doc.md")

    path.write_text("---\ntitle: Doc\n---\n\n# Doc\n\nEdited text now.\n")
    second = loader.load("doc.md")

    assert first.sections[0].section_id == second.sections[0].section_id
    assert first.sections[0].content_hash != second.sections[0].content_hash
    assert first.document.content_hash != second.document.content_hash


def test_repeated_parsing_is_deterministic(tmp_path):
    _write(
        tmp_path,
        "doc.md",
        "---\ntitle: Doc\n---\n\n# Doc\n\n## A\n\nText.\n",
    )

    loader = OkfLoader(corpus_root=str(tmp_path))
    first = corpus_to_dict([loader.load("doc.md")])
    second = corpus_to_dict([loader.load("doc.md")])

    assert first == second


def test_oversized_section_splits_deterministically(tmp_path):
    big_text = " ".join(f"word{i}" for i in range(700))
    _write(tmp_path, "big.md", f"---\ntitle: Big\n---\n\n# Big\n\n{big_text}\n")

    loader = OkfLoader(corpus_root=str(tmp_path), max_section_tokens=300)
    parsed = loader.load("big.md")

    assert len(parsed.sections) == 3
    assert [len(s.text.split()) for s in parsed.sections] == [300, 300, 100]
    # Fragments preserve the parent heading path.
    assert all(s.heading_path == ("Big",) for s in parsed.sections)
    # Re-parsing an unchanged oversized document splits identically.
    parsed_again = loader.load("big.md")
    assert [s.section_id for s in parsed.sections] == [
        s.section_id for s in parsed_again.sections
    ]


def test_small_section_is_not_split(tmp_path):
    _write(tmp_path, "doc.md", "---\ntitle: Doc\n---\n\n# Doc\n\nShort text.\n")

    loader = OkfLoader(corpus_root=str(tmp_path), max_section_tokens=300)
    parsed = loader.load("doc.md")

    assert len(parsed.sections) == 1
