"""Integration tests that require a live Neo4j instance.

Run ``docker compose up -d`` before executing this suite (it is skipped
automatically when Neo4j is unreachable).
"""

from __future__ import annotations

import logging

import pytest

from oneo.models import OkfDocument, OkfLink, OkfSection
from oneo.neo4j_store import Neo4jStore

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "password"
NEO4J_DATABASE = "neo4j"
CORPUS = "test-corpus"


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


pytestmark = pytest.mark.skipif(
    not _neo4j_available(),
    reason="Neo4j is not reachable at bolt://localhost:7687; run `docker compose up -d`",
)


@pytest.fixture
def store():
    with Neo4jStore(
        uri=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
        database=NEO4J_DATABASE,
    ) as opened:
        opened.reset(CORPUS)
        opened.apply_schema()
        yield opened
        opened.reset(CORPUS)


def test_health_reports_connected():
    with Neo4jStore(
        uri=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
        database=NEO4J_DATABASE,
    ) as store:
        status = store.health()

    assert status.connected is True
    assert status.database == NEO4J_DATABASE
    assert status.detail is None


def test_health_reports_failure_for_wrong_credentials():
    with Neo4jStore(
        uri=NEO4J_URI,
        username=NEO4J_USERNAME,
        password="wrong-password",
        database=NEO4J_DATABASE,
    ) as store:
        status = store.health()

    assert status.connected is False
    assert status.detail is not None


def _sample_documents():
    return [
        OkfDocument(
            document_id="overview",
            title="Overview",
            source_path="overview.md",
            metadata={"type": "concept"},
            content_hash="doc-hash-1",
        ),
        OkfDocument(
            document_id="topics/example",
            title="Example",
            source_path="topics/example.markdown",
            metadata={"type": "concept"},
            content_hash="doc-hash-2",
        ),
    ]


def _sample_sections():
    return [
        OkfSection(
            section_id="overview::_::0",
            document_id="overview",
            heading="Billing",
            heading_path=("Billing",),
            ordinal=0,
            text="Customer billing details and invoice schedule.",
            anchor=None,
            source_path="overview.md",
            content_hash="section-hash-1",
        ),
        OkfSection(
            section_id="topics/example::_::0",
            document_id="topics/example",
            heading="Example",
            heading_path=("Example",),
            ordinal=0,
            text="A nested placeholder document body.",
            anchor=None,
            source_path="topics/example.markdown",
            content_hash="section-hash-2",
        ),
    ]


def _sample_links():
    return [
        OkfLink(
            source_document_id="overview",
            source_section_id="overview::_::0",
            raw_target="topics/example.markdown",
            target_document_id="topics/example",
            target_anchor=None,
            is_external=False,
        ),
    ]


def test_write_documents_sections_links_are_queryable(store):
    store.write_documents(_sample_documents(), CORPUS)
    store.write_sections(_sample_sections(), CORPUS)
    store.write_links(_sample_links(), CORPUS)

    documents = store.list_documents(CORPUS)
    assert sorted(d.document_id for d in documents) == ["overview", "topics/example"]
    assert store.count_sections(CORPUS) == 2
    assert store.count_links(CORPUS) == 1


def test_repeated_writes_create_no_duplicates(store):
    for _ in range(2):
        store.write_documents(_sample_documents(), CORPUS)
        store.write_sections(_sample_sections(), CORPUS)
        store.write_links(_sample_links(), CORPUS)

    assert len(store.list_documents(CORPUS)) == 2
    assert store.count_sections(CORPUS) == 2
    assert store.count_links(CORPUS) == 1


def test_reset_removes_only_owned_data(store):
    store.write_documents(_sample_documents(), CORPUS)
    store._run("CREATE (:Unrelated {name: 'keep-me'})")

    store.reset(CORPUS)

    assert store.list_documents(CORPUS) == []
    remaining = store._run("MATCH (n:Unrelated) RETURN count(n) AS n")
    assert remaining[0]["n"] == 1
    store._run("MATCH (n:Unrelated) DETACH DELETE n")


def test_export_graph_is_identical_after_rebuild(store):
    store.write_documents(_sample_documents(), CORPUS)
    store.write_sections(_sample_sections(), CORPUS)
    store.write_links(_sample_links(), CORPUS)
    first_export = store.export_graph(CORPUS)

    store.reset(CORPUS)
    store.apply_schema()
    store.write_documents(_sample_documents(), CORPUS)
    store.write_sections(_sample_sections(), CORPUS)
    store.write_links(_sample_links(), CORPUS)
    second_export = store.export_graph(CORPUS)

    assert first_export == second_export


def test_anchor_less_link_read_emits_no_driver_warning(store, caplog):
    """A ``LINKS_TO`` edge with ``target_anchor=None`` (e.g. a plain
    document link with no ``#anchor`` fragment) must not trigger a
    Neo4j "property key does not exist" driver warning when the
    property is later read, and reads must still return ``None``."""

    store.write_documents(_sample_documents(), CORPUS)
    store.write_sections(_sample_sections(), CORPUS)
    store.write_links(_sample_links(), CORPUS)

    with caplog.at_level(logging.WARNING, logger="neo4j.notifications"):
        export = store.export_graph(CORPUS)

    assert not any(
        "target_anchor" in record.message for record in caplog.records
    )
    assert export["links"] == [
        {
            "source_document_id": "overview",
            "target_document_id": "topics/example",
            "source_section_id": "overview::_::0",
            "raw_target": "topics/example.markdown",
            "target_anchor": None,
        }
    ]


def test_sections_needing_embedding_emits_no_driver_warning_on_fresh_db(
    store, caplog
):
    """``sections_needing_embedding`` reads `embedding`, `embedding_model`,
    `embedding_dimensions`, and `embedding_input_hash` on sections that
    have never been embedded (e.g. right after `oneo reset` on the very
    first `oneo index` run). None of these reads must trigger a Neo4j
    "property key does not exist" driver warning, and all sections must
    still be correctly reported as needing embedding."""

    store.write_documents(_sample_documents(), CORPUS)
    store.write_sections(_sample_sections(), CORPUS)

    section_ids = [section.section_id for section in _sample_sections()]
    input_hashes = {section_id: "hash-value" for section_id in section_ids}

    with caplog.at_level(logging.WARNING, logger="neo4j.notifications"):
        stale = store.sections_needing_embedding(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            dimensions=384,
            input_hashes=input_hashes,
            corpus=CORPUS,
        )

    assert not any(
        "property key does not exist" in record.message
        for record in caplog.records
    )
    assert sorted(stale) == sorted(section_ids)


def test_fulltext_search_returns_matching_owned_sections(store):
    store.write_documents(_sample_documents(), CORPUS)
    store.write_sections(_sample_sections(), CORPUS)
    store.wait_for_fulltext_index_online()

    matches = store.fulltext_search("billing", top_k=5)

    assert matches
    assert matches[0].section_id == "overview::_::0"
    assert matches[0].document_id == "overview"
    assert all(match.score > 0 for match in matches)


def test_fulltext_search_ignores_unrelated_data(store):
    store.write_documents(_sample_documents(), CORPUS)
    store.write_sections(_sample_sections(), CORPUS)
    store.wait_for_fulltext_index_online()

    matches = store.fulltext_search("nested placeholder", top_k=5)

    assert matches
    assert all(match.document_id in ("overview", "topics/example") for match in matches)


def test_wait_for_fulltext_index_online_reports_online_state(store):
    state = store.wait_for_fulltext_index_online()

    assert state == "ONLINE"


def _expansion_sample_documents():
    return [
        OkfDocument(
            document_id="billing",
            title="Billing Guide",
            source_path="billing.md",
            metadata={"type": "concept"},
            content_hash="doc-hash-billing",
        ),
        OkfDocument(
            document_id="payments",
            title="Payments Overview",
            source_path="payments.md",
            metadata={"type": "concept"},
            content_hash="doc-hash-payments",
        ),
        OkfDocument(
            document_id="unrelated",
            title="Unrelated Topic",
            source_path="unrelated.md",
            metadata={"type": "concept"},
            content_hash="doc-hash-unrelated",
        ),
    ]


def _expansion_sample_sections():
    return [
        OkfSection(
            section_id="billing::_::0",
            document_id="billing",
            heading="Billing",
            heading_path=("Billing",),
            ordinal=0,
            text="Customer billing invoices are generated monthly.",
            anchor=None,
            source_path="billing.md",
            content_hash="section-hash-billing",
        ),
        OkfSection(
            section_id="payments::charging::0",
            document_id="payments",
            heading="Charging Customers",
            heading_path=("Charging Customers",),
            ordinal=0,
            text="Clients are charged automatically for subscriptions.",
            anchor="charging",
            source_path="payments.md",
            content_hash="section-hash-payments-0",
        ),
        OkfSection(
            section_id="payments::receipts::1",
            document_id="payments",
            heading="Receipts",
            heading_path=("Receipts",),
            ordinal=1,
            text="A receipt is issued after payment.",
            anchor="receipts",
            source_path="payments.md",
            content_hash="section-hash-payments-1",
        ),
        OkfSection(
            section_id="unrelated::_::0",
            document_id="unrelated",
            heading="Unrelated",
            heading_path=("Unrelated",),
            ordinal=0,
            text="Nothing relevant here.",
            anchor=None,
            source_path="unrelated.md",
            content_hash="section-hash-unrelated",
        ),
    ]


def test_expand_neighbors_returns_outgoing_edge(store):
    store.write_documents(_expansion_sample_documents(), CORPUS)
    store.write_sections(_expansion_sample_sections(), CORPUS)
    store.write_links(
        [
            OkfLink(
                source_document_id="billing",
                source_section_id="billing::_::0",
                raw_target="payments.md#charging",
                target_document_id="payments",
                target_anchor="charging",
                is_external=False,
            )
        ],
        CORPUS,
    )

    edges = store.expand_neighbors(["billing"])

    assert len(edges) == 1
    edge = edges[0]
    assert edge["seed_document_id"] == "billing"
    assert edge["direction"] == "outgoing"
    assert edge["neighbor_document_id"] == "payments"
    assert edge["target_anchor"] == "charging"


def test_expand_neighbors_returns_incoming_edge(store):
    store.write_documents(_expansion_sample_documents(), CORPUS)
    store.write_sections(_expansion_sample_sections(), CORPUS)
    store.write_links(
        [
            OkfLink(
                source_document_id="billing",
                source_section_id="billing::_::0",
                raw_target="payments.md",
                target_document_id="payments",
                target_anchor=None,
                is_external=False,
            )
        ],
        CORPUS,
    )

    edges = store.expand_neighbors(["payments"])

    assert len(edges) == 1
    assert edges[0]["direction"] == "incoming"
    assert edges[0]["neighbor_document_id"] == "billing"


def test_expand_neighbors_excludes_edges_between_seed_documents(store):
    store.write_documents(_expansion_sample_documents(), CORPUS)
    store.write_sections(_expansion_sample_sections(), CORPUS)
    store.write_links(
        [
            OkfLink(
                source_document_id="billing",
                source_section_id="billing::_::0",
                raw_target="payments.md",
                target_document_id="payments",
                target_anchor=None,
                is_external=False,
            )
        ],
        CORPUS,
    )

    edges = store.expand_neighbors(["billing", "payments"])

    assert edges == []


def test_expand_neighbors_rejects_hops_other_than_one(store):
    import pytest

    with pytest.raises(ValueError):
        store.expand_neighbors(["billing"], hops=2)


def test_section_by_anchor_returns_matching_section(store):
    store.write_documents(_expansion_sample_documents(), CORPUS)
    store.write_sections(_expansion_sample_sections(), CORPUS)

    match = store.section_by_anchor("payments", "receipts")

    assert match is not None
    assert match.section_id == "payments::receipts::1"


def test_section_by_anchor_returns_none_when_missing(store):
    store.write_documents(_expansion_sample_documents(), CORPUS)
    store.write_sections(_expansion_sample_sections(), CORPUS)

    assert store.section_by_anchor("payments", "does-not-exist") is None


def test_first_section_returns_lowest_ordinal(store):
    store.write_documents(_expansion_sample_documents(), CORPUS)
    store.write_sections(_expansion_sample_sections(), CORPUS)

    match = store.first_section("payments")

    assert match is not None
    assert match.section_id == "payments::charging::0"


def test_best_section_in_document_prefers_lexical_match_in_target_document(store):
    store.write_documents(_expansion_sample_documents(), CORPUS)
    store.write_sections(_expansion_sample_sections(), CORPUS)
    store.wait_for_fulltext_index_online()

    match = store.best_section_in_document("payments", [0.1] * 384, "receipt issued")

    assert match is not None
    assert match.document_id == "payments"


def test_best_section_in_document_returns_none_when_no_match_in_document(store):
    store.write_documents(_expansion_sample_documents(), CORPUS)
    store.write_sections(_expansion_sample_sections(), CORPUS)
    store.wait_for_fulltext_index_online()

    match = store.best_section_in_document(
        "does-not-exist", [0.1] * 384, "receipt issued"
    )

    assert match is None


def test_vector_search_returns_empty_when_index_does_not_exist(store):
    """``vector_search`` must return ``[]`` rather than raising when the
    vector index has never been created (e.g. a caller runs before the
    first ``create_vector_index``/``oneo index`` call). This guards the
    ``Neo.ClientError.Procedure.ProcedureCallFailed`` ("no such vector
    schema index") handling added in Step 01002."""

    store.write_documents(_sample_documents(), CORPUS)
    store.write_sections(_sample_sections(), CORPUS)

    matches = store.vector_search([0.1] * 384, top_k=5)

    assert matches == []


def _tie_tolerance_documents():
    return [
        OkfDocument(
            document_id="tie-tolerance",
            title="Tie Tolerance",
            source_path="tie-tolerance.md",
            metadata={"type": "concept"},
            content_hash="doc-hash-tie-tolerance",
        ),
    ]


def _tie_tolerance_sections(tied_vector: list[float], noise_vector: list[float]):
    """Ten sections sharing an identical embedding (a perfect cosine-
    similarity tie) plus five unrelated "noise" sections, all attached
    to one document."""

    sections = []
    for i in range(10):
        sections.append(
            OkfSection(
                section_id=f"tie-tolerance::tied-{i}::{i}",
                document_id="tie-tolerance",
                heading=f"Tied {i}",
                heading_path=(f"Tied {i}",),
                ordinal=i,
                text=f"Tied section number {i}.",
                anchor=None,
                source_path="tie-tolerance.md",
                content_hash=f"section-hash-tied-{i}",
            )
        )
    for i in range(5):
        ordinal = 10 + i
        sections.append(
            OkfSection(
                section_id=f"tie-tolerance::noise-{i}::{ordinal}",
                document_id="tie-tolerance",
                heading=f"Noise {i}",
                heading_path=(f"Noise {i}",),
                ordinal=ordinal,
                text=f"Unrelated noise section number {i}.",
                anchor=None,
                source_path="tie-tolerance.md",
                content_hash=f"section-hash-noise-{i}",
            )
        )
    return sections, {
        section.section_id: (
            tied_vector if section.section_id.split("::")[1].startswith("tied")
            else noise_vector
        )
        for section in sections
    }


def test_wait_for_vector_index_queryable_tolerates_ranking_ties(store):
    """Documents the ``top_k=10`` tie-tolerance behavior added in Step
    01002: the sample section does not have to be the single top-ranked
    match to be found, as long as it is one of exactly ``top_k`` sections
    tied for the best cosine similarity score alongside other, unrelated
    sections in the graph."""

    tied_vector = [1.0, 0.0] + [0.0] * 382
    noise_vector = [0.0, 1.0] + [0.0] * 382
    sections, vectors_by_id = _tie_tolerance_sections(tied_vector, noise_vector)
    sample_section_id = "tie-tolerance::tied-0::0"

    store.write_documents(_tie_tolerance_documents(), CORPUS)
    store.write_sections(sections, CORPUS)
    store.create_vector_index(dimensions=len(tied_vector))
    store.wait_for_vector_index_online()
    store.write_embeddings(
        [
            {
                "section_id": section_id,
                "embedding": vector,
                "embedding_model": "test-fixture",
                "embedding_dimensions": len(vector),
                "embedding_input_hash": f"hash-{section_id}",
            }
            for section_id, vector in vectors_by_id.items()
        ],
        CORPUS,
    )

    is_queryable = store.wait_for_vector_index_queryable(
        sample_embedding=tied_vector,
        sample_section_id=sample_section_id,
        timeout_seconds=30.0,
    )

    assert is_queryable is True


