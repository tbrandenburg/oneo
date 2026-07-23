"""End-to-end proof that two registered corpuses are fully isolated in
Neo4j and each remains independently rebuildable from its own
filesystem root.

No direct database mutation is used anywhere in this test: every
expected state change is produced by editing files on disk and calling
``coordinator.index(...)`` / ``coordinator.reset(...)`` again.
"""

from __future__ import annotations

import pytest

from oneo.config import Settings
from oneo.corpus import Corpus, CorpusRegistry
from oneo.neo4j_store import Neo4jStore
from oneo.pipeline import Oneo

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "password"
NEO4J_DATABASE = "neo4j"


def _neo4j_available() -> bool:
    try:
        with Neo4jStore(
            uri=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            database=NEO4J_DATABASE,
        ) as store:
            return store.health().connected
    except Exception:
        return False


requires_neo4j = pytest.mark.skipif(
    not _neo4j_available(),
    reason="Neo4j is not reachable at bolt://localhost:7687; run `docker compose up -d`",
)


def _make_store() -> Neo4jStore:
    return Neo4jStore(
        uri=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
        database=NEO4J_DATABASE,
    )


def _write_corpus(root, *, overview_body: str, other_body: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "overview.md").write_text(
        "---\ntitle: Overview\ntype: concept\n---\n\n"
        f"# Overview\n\n{overview_body}\n"
    )
    (root / "other.md").write_text(
        "---\ntitle: Other\ntype: concept\n---\n\n"
        f"# Other\n\n{other_body}\n"
    )


@requires_neo4j
def test_corpus_isolation(tmp_path):
    corpus_a_root = tmp_path / "corpus-a"
    corpus_b_root = tmp_path / "corpus-b"

    # 1. Register two corpuses with an identical relative path
    # (`overview.md`) in each, but different content.
    _write_corpus(
        corpus_a_root,
        overview_body="Corpus A billing invoices are generated monthly.",
        other_body="Corpus A unrelated notes about seasonal weather.",
    )
    _write_corpus(
        corpus_b_root,
        overview_body="Corpus B engineering deploys are shipped weekly.",
        other_body="Corpus B unrelated notes about office snacks.",
    )

    registry = CorpusRegistry(
        {
            "corpus-a": Corpus(name="corpus-a", root=str(corpus_a_root)),
            "corpus-b": Corpus(name="corpus-b", root=str(corpus_b_root)),
        },
        "corpus-a",
    )
    settings = Settings()
    coordinator = Oneo(settings, registry=registry)

    try:
        # 2. Index both corpuses (with embeddings).
        summary_a = coordinator.index(
            str(corpus_a_root), rebuild=True, embeddings=True, corpus="corpus-a"
        )
        summary_b = coordinator.index(
            str(corpus_b_root), rebuild=True, embeddings=True, corpus="corpus-b"
        )
        assert summary_a.documents == 2
        assert summary_b.documents == 2

        # 3. Assert each corpus's counts and exports are correct and
        # disjoint.
        with _make_store() as store:
            export_a = store.export_graph("corpus-a")
            export_b = store.export_graph("corpus-b")

        assert len(export_a["documents"]) == 2
        assert len(export_b["documents"]) == 2

        overview_a = next(
            d for d in export_a["documents"] if d["document_id"] == "overview"
        )
        overview_b = next(
            d for d in export_b["documents"] if d["document_id"] == "overview"
        )
        assert overview_a["content_hash"] != overview_b["content_hash"]

        # section_id is a semantic identity, not corpus-derived, so the
        # identical bundle-relative paths produce identical section_ids
        # in both corpuses; isolation is proven by the composite
        # (corpus, section_id) key and content differing per corpus,
        # not by section_id uniqueness across corpuses.
        section_ids_a = {s["section_id"] for s in export_a["sections"]}
        section_ids_b = {s["section_id"] for s in export_b["sections"]}
        assert section_ids_a == section_ids_b == {"overview::overview::0", "other::other::0"}
        overview_section_a = next(
            s for s in export_a["sections"] if s["document_id"] == "overview"
        )
        overview_section_b = next(
            s for s in export_b["sections"] if s["document_id"] == "overview"
        )
        assert overview_section_a["content_hash"] != overview_section_b["content_hash"]

        # 4. Edit a section in corpus A, rebuild corpus A, and verify
        # corpus A updated while corpus B is byte-for-byte unchanged.
        (corpus_a_root / "overview.md").write_text(
            "---\ntitle: Overview\ntype: concept\n---\n\n"
            "# Overview\n\n"
            "Corpus A billing invoices are now generated weekly instead.\n"
        )
        coordinator.index(
            str(corpus_a_root), rebuild=True, embeddings=True, corpus="corpus-a"
        )

        with _make_store() as store:
            edited_export_a = store.export_graph("corpus-a")
            unchanged_export_b = store.export_graph("corpus-b")

        edited_overview_a = next(
            d for d in edited_export_a["documents"] if d["document_id"] == "overview"
        )
        assert edited_overview_a["content_hash"] != overview_a["content_hash"]
        assert unchanged_export_b == export_b

        # 5. Add a Markdown link in corpus A, rebuild, verify the new
        # edge exists only in corpus A.
        assert edited_export_a["links"] == []
        (corpus_a_root / "overview.md").write_text(
            "---\ntitle: Overview\ntype: concept\n---\n\n"
            "# Overview\n\n"
            "Corpus A billing invoices are now generated weekly instead.\n\n"
            "See [other](other.md) for unrelated notes.\n"
        )
        coordinator.index(
            str(corpus_a_root), rebuild=True, embeddings=True, corpus="corpus-a"
        )

        with _make_store() as store:
            linked_export_a = store.export_graph("corpus-a")
            still_unchanged_export_b = store.export_graph("corpus-b")

        assert len(linked_export_a["links"]) == 1
        link = linked_export_a["links"][0]
        assert link["source_document_id"] == "overview"
        assert link["target_document_id"] == "other"
        assert still_unchanged_export_b == unchanged_export_b

        # 6. Delete a file in corpus A, rebuild, verify its document,
        # sections, vectors, and relationships disappear from corpus A
        # only.
        (corpus_a_root / "other.md").unlink()
        coordinator.index(
            str(corpus_a_root), rebuild=True, embeddings=True, corpus="corpus-a"
        )

        with _make_store() as store:
            final_export_a = store.export_graph("corpus-a")
            final_export_b = store.export_graph("corpus-b")
            remaining_a_embeddings = store._run(
                "MATCH (s:OkfSection {corpus: 'corpus-a', document_id: 'other'}) "
                "RETURN s.embedding AS embedding"
            )

        final_document_ids_a = {d["document_id"] for d in final_export_a["documents"]}
        assert "other" not in final_document_ids_a
        assert "overview" in final_document_ids_a
        assert final_export_a["links"] == []
        assert remaining_a_embeddings == []
        # corpus B still has its own "other" document, fully untouched.
        final_document_ids_b = {d["document_id"] for d in final_export_b["documents"]}
        assert final_document_ids_b == {"overview", "other"}
        assert final_export_b == still_unchanged_export_b

        # 7. Reset corpus A entirely and verify corpus B remains fully
        # indexed and queryable.
        coordinator.reset(corpus="corpus-a")

        with _make_store() as store:
            reset_export_a = store.export_graph("corpus-a")
            post_reset_export_b = store.export_graph("corpus-b")

        assert reset_export_a["documents"] == []
        assert reset_export_a["sections"] == []
        assert reset_export_a["links"] == []
        assert post_reset_export_b == final_export_b

        # 8. Run a retrieval/query against corpus B and assert no
        # corpus-A content appears.
        result_b = coordinator.retrieve(
            "engineering deploys", top_k=5, expand=True, corpus="corpus-b"
        )
        assert result_b.hits, "expected corpus B retrieval to return seed hits"
        all_hit_section_ids = [h.section_id for h in result_b.hits] + [
            h.section_id for h in result_b.expanded_hits
        ]
        for hit in result_b.hits:
            assert hit.document_id in {"overview", "other"}
        with _make_store() as store:
            rows = store._run(
                "MATCH (s:OkfSection) WHERE s.section_id IN $section_ids "
                "AND s.index_owner = 'oneo' "
                "RETURN s.corpus AS corpus",
                section_ids=all_hit_section_ids,
            )
        assert rows, "expected retrieval hits to resolve to indexed sections"
        assert all(row["corpus"] == "corpus-b" for row in rows)
    finally:
        coordinator.reset(corpus="corpus-a")
        coordinator.reset(corpus="corpus-b")
