"""End-to-end proof that the filesystem is the sole source of truth
and Neo4j is a fully disposable, rebuildable derived index.

This test never mutates the graph directly: every expected final
state is produced by editing files on disk and calling
``coordinator.index(..., rebuild=True)`` again.
"""

from __future__ import annotations

import pytest

from oneo.config import Settings
from oneo.corpus import Corpus, CorpusRegistry
from oneo.neo4j_store import Neo4jStore
from oneo.pipeline import Oneo


def _registry_for(root) -> CorpusRegistry:
    """Build a single-corpus registry fixture rooted at ``root``, used in
    place of the removed global ``Settings(knowledge_root=...)``."""

    return CorpusRegistry({"test": Corpus(name="test", root=str(root))}, "test")

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


def _section_embedding_hashes(store: Neo4jStore) -> dict[str, str]:
    records = store._run(
        "MATCH (s:OkfSection) RETURN s.section_id AS section_id, "
        "s.embedding_input_hash AS embedding_input_hash"
    )
    return {record["section_id"]: record["embedding_input_hash"] for record in records}


@requires_neo4j
def test_filesystem_first_rebuild_semantics(tmp_path):
    root = tmp_path
    (root / "overview.md").write_text(
        "---\ntitle: Overview\ntype: concept\n---\n\n"
        "# Overview\n\n"
        "Customer billing invoices are generated monthly.\n"
    )
    (root / "other.md").write_text(
        "---\ntitle: Other\ntype: concept\n---\n\n"
        "# Other\n\n"
        "Unrelated notes about seasonal weather patterns.\n"
    )

    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    unrelated_marker_id = "unrelated-marker-doc"

    try:
        # --- baseline index ---
        summary = coordinator.index(str(root), rebuild=True, embeddings=True)
        assert summary.documents == 2
        assert summary.sections == 2

        with _make_store() as store:
            baseline_export = store.export_graph("test")
            baseline_hashes = _section_embedding_hashes(store)
            store._run(
                "MERGE (m:UnrelatedMarker {id: $id}) SET m.note = 'not owned by oneo'",
                id=unrelated_marker_id,
            )

        overview_document = next(
            d for d in baseline_export["documents"] if d["document_id"] == "overview"
        )
        overview_section = next(
            s for s in baseline_export["sections"] if s["document_id"] == "overview"
        )
        overview_section_id = overview_section["section_id"]

        # --- 1. edit an existing section, rebuild, verify text + vector update ---
        (root / "overview.md").write_text(
            "---\ntitle: Overview\ntype: concept\n---\n\n"
            "# Overview\n\n"
            "Customer billing invoices are now generated weekly instead.\n"
        )

        coordinator.index(str(root), rebuild=True, embeddings=True)

        with _make_store() as store:
            edited_export = store.export_graph("test")
            edited_hashes = _section_embedding_hashes(store)
            edited_texts = store.get_section_texts([overview_section_id], "test")

        edited_document = next(
            d for d in edited_export["documents"] if d["document_id"] == "overview"
        )
        edited_section = next(
            s for s in edited_export["sections"] if s["document_id"] == "overview"
        )

        # stable section identity survives a text-only edit
        assert edited_section["section_id"] == overview_section_id
        # content hash changes after the text edit
        assert edited_document["content_hash"] != overview_document["content_hash"]
        assert edited_section["content_hash"] != overview_section["content_hash"]
        assert "weekly" in edited_texts[overview_section_id]
        # embedding input hash is refreshed for the edited section
        assert (
            edited_hashes[overview_section_id]
            != baseline_hashes[overview_section_id]
        )

        # --- 2. add a Markdown link, rebuild, verify new graph relationship ---
        assert edited_export["links"] == []
        (root / "overview.md").write_text(
            "---\ntitle: Overview\ntype: concept\n---\n\n"
            "# Overview\n\n"
            "Customer billing invoices are now generated weekly instead.\n\n"
            "See [other](other.md) for unrelated notes.\n"
        )

        coordinator.index(str(root), rebuild=True, embeddings=True)

        with _make_store() as store:
            linked_export = store.export_graph("test")

        assert len(linked_export["links"]) == 1
        link = linked_export["links"][0]
        assert link["source_document_id"] == "overview"
        assert link["target_document_id"] == "other"

        # --- 3. delete an OKF file, rebuild, verify complete removal ---
        (root / "other.md").unlink()

        coordinator.index(str(root), rebuild=True, embeddings=True)

        with _make_store() as store:
            final_export = store.export_graph("test")
            final_texts = store._run(
                "MATCH (s:OkfSection) RETURN s.document_id AS document_id"
            )

        final_document_ids = {d["document_id"] for d in final_export["documents"]}
        assert "other" not in final_document_ids
        assert "overview" in final_document_ids

        # deleted files do not remain discoverable
        assert "other.md" not in coordinator.discover(str(root))

        # its section nodes are gone
        assert all(row["document_id"] != "other" for row in final_texts)

        # its vectors are gone (no remaining section belongs to "other")
        with _make_store() as store:
            remaining_embeddings = store._run(
                "MATCH (s:OkfSection) WHERE s.document_id = 'other' "
                "RETURN s.embedding AS embedding"
            )
        assert remaining_embeddings == []

        # incoming and outgoing relationships to/from the deleted document
        # are gone
        assert final_export["links"] == []

        # unrelated Neo4j data remains untouched throughout the rebuilds
        with _make_store() as store:
            marker_records = store._run(
                "MATCH (m:UnrelatedMarker {id: $id}) RETURN m.note AS note",
                id=unrelated_marker_id,
            )
        assert len(marker_records) == 1
        assert marker_records[0]["note"] == "not owned by oneo"
    finally:
        coordinator.reset()
        with _make_store() as store:
            store._run(
                "MATCH (m:UnrelatedMarker {id: $id}) DETACH DELETE m",
                id=unrelated_marker_id,
            )
