"""Integration test for the Oneo coordinator's discover(), parse(),
index(), verify(), and reset() surfaces."""

from __future__ import annotations

import pytest

from oneo.answering import ExtractiveChatModel
from oneo.config import Settings
from oneo.corpus import Corpus, CorpusRegistry
from oneo.neo4j_store import Neo4jStore
from oneo.pipeline import Oneo


def _registry_for(root) -> CorpusRegistry:
    """Build a single-corpus registry fixture rooted at ``root``, used in
    place of the removed global ``Settings(corpus_root=...)``."""

    return CorpusRegistry({"test": Corpus(name="test", root=str(root))}, "test")


def test_discover_returns_sorted_supported_files(tmp_path):
    root = tmp_path
    (root / "topics").mkdir()
    (root / "overview.md").write_text("# Overview\n")
    (root / "topics" / "example.markdown").write_text("# Example\n")
    (root / "ignored.txt").write_text("not markdown\n")

    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    discovered = coordinator.discover(str(root))

    assert discovered == ["overview.md", "topics/example.markdown"]


def test_parse_loads_every_discovered_document(tmp_path):
    root = tmp_path
    (root / "topics").mkdir()
    (root / "overview.md").write_text(
        "---\ntitle: Overview\n---\n\n# Overview\n\nIntro text.\n"
    )
    (root / "topics" / "example.markdown").write_text(
        "---\ntitle: Example\n---\n\n# Example\n\nMore text.\n"
    )

    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    parsed = coordinator.parse(str(root))

    document_ids = sorted(p.document.document_id for p in parsed)
    assert document_ids == ["overview", "topics/example"]
    assert all(p.sections for p in parsed)


def test_validate_reports_unresolved_link_in_permissive_mode(tmp_path):
    root = tmp_path
    (root / "doc.md").write_text(
        "---\ntitle: Doc\ntype: concept\n---\n\n# Doc\n\n[broken](missing.md)\n"
    )

    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    result = coordinator.validate(str(root))

    assert result.ok is True
    assert any(d.code == "unresolved-link" for d in result.diagnostics)


def test_validate_fails_strict_on_unresolved_link(tmp_path):
    root = tmp_path
    (root / "doc.md").write_text(
        "---\ntitle: Doc\ntype: concept\n---\n\n# Doc\n\n[broken](missing.md)\n"
    )

    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    result = coordinator.validate(str(root), strict=True)

    assert result.ok is False


def test_validate_passes_strict_on_corrected_corpus(tmp_path):
    root = tmp_path
    (root / "doc.md").write_text(
        "---\ntitle: Doc\ntype: concept\n---\n\n# Doc\n\n[good](other.md)\n"
    )
    (root / "other.md").write_text("---\ntitle: Other\ntype: concept\n---\n\n# Other\n\nBody.\n")

    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    result = coordinator.validate(str(root), strict=True)

    assert result.ok is True
    assert result.diagnostics == ()


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


def _make_corpus(root):
    (root / "topics").mkdir()
    (root / "overview.md").write_text(
        "---\ntitle: Overview\ntype: concept\n---\n\n"
        "# Overview\n\n[example](topics/example.md)\n"
    )
    (root / "topics" / "example.md").write_text(
        "---\ntitle: Example\ntype: concept\n---\n\n# Example\n\nBody.\n"
    )


@requires_neo4j
def test_index_writes_documents_sections_and_links(tmp_path):
    root = tmp_path
    _make_corpus(root)
    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    try:
        summary = coordinator.index(str(root), rebuild=True, embeddings=False)

        assert summary.documents == 2
        assert summary.sections == 2
        assert summary.links == 1
    finally:
        coordinator.reset()


@requires_neo4j
def test_index_is_idempotent_across_repeated_runs(tmp_path):
    root = tmp_path
    _make_corpus(root)
    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    try:
        coordinator.index(str(root), rebuild=True, embeddings=False)
        summary = coordinator.index(str(root), rebuild=False, embeddings=False)

        assert summary.documents == 2
        assert summary.sections == 2
        assert summary.links == 1
    finally:
        coordinator.reset()


@requires_neo4j
def test_verify_reports_ok_after_index(tmp_path):
    root = tmp_path
    _make_corpus(root)
    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    try:
        coordinator.index(str(root), rebuild=True, embeddings=False)
        result = coordinator.verify(str(root))

        assert result.ok is True
        assert result.issues == ()
        assert result.documents == 2
        assert result.sections == 2
        assert result.links == 1
    finally:
        coordinator.reset()


@requires_neo4j
def test_verify_reports_issue_when_graph_is_stale(tmp_path):
    root = tmp_path
    _make_corpus(root)
    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    try:
        coordinator.index(str(root), rebuild=True, embeddings=False)
        (root / "topics" / "extra.md").write_text(
            "---\ntitle: Extra\ntype: concept\n---\n\n# Extra\n\nBody.\n"
        )

        result = coordinator.verify(str(root))

        assert result.ok is False
        assert result.issues
    finally:
        coordinator.reset()


@requires_neo4j
def test_index_with_embeddings_generates_vectors(tmp_path):
    root = tmp_path
    _make_corpus(root)
    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    try:
        summary = coordinator.index(str(root), rebuild=True, embeddings=True)

        assert summary.documents == 2
        assert summary.sections == 2

        with Neo4jStore(
            uri=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            database=NEO4J_DATABASE,
        ) as store:
            records = store._run(
                "MATCH (s:OkfSection) RETURN s.embedding AS embedding, "
                "s.embedding_model AS embedding_model, "
                "s.embedding_dimensions AS embedding_dimensions, "
                "s.embedding_input_hash AS embedding_input_hash"
            )
            assert len(records) == 2
            for record in records:
                assert len(record["embedding"]) == 384
                assert record["embedding_model"] == (
                    "sentence-transformers/all-MiniLM-L6-v2"
                )
                assert record["embedding_dimensions"] == 384
                assert record["embedding_input_hash"]
            assert store.vector_index_state() == "ONLINE"
    finally:
        coordinator.reset()


@requires_neo4j
def test_vector_search_returns_indexed_section(tmp_path):
    root = tmp_path
    _make_corpus(root)
    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    try:
        coordinator.index(str(root), rebuild=True, embeddings=True)

        matches = coordinator.vector_search("nested document example", top_k=2)

        assert matches
        assert all(match.section_id for match in matches)
        assert all(match.document_id for match in matches)
        assert all(match.source_path for match in matches)
    finally:
        coordinator.reset()


@requires_neo4j
def test_reindex_skips_unchanged_section_embeddings(tmp_path):
    root = tmp_path
    _make_corpus(root)
    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    try:
        coordinator.index(str(root), rebuild=True, embeddings=True)

        with Neo4jStore(
            uri=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            database=NEO4J_DATABASE,
        ) as store:
            first_hashes = {
                record["section_id"]: record["embedding_input_hash"]
                for record in store._run(
                    "MATCH (s:OkfSection) RETURN s.section_id AS section_id, "
                    "s.embedding_input_hash AS embedding_input_hash"
                )
            }

        coordinator.index(str(root), rebuild=False, embeddings=True)

        with Neo4jStore(
            uri=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            database=NEO4J_DATABASE,
        ) as store:
            second_hashes = {
                record["section_id"]: record["embedding_input_hash"]
                for record in store._run(
                    "MATCH (s:OkfSection) RETURN s.section_id AS section_id, "
                    "s.embedding_input_hash AS embedding_input_hash"
                )
            }

        assert first_hashes == second_hashes
    finally:
        coordinator.reset()


@requires_neo4j
def test_reset_removes_only_owned_data(tmp_path):
    root = tmp_path
    _make_corpus(root)
    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    coordinator.index(str(root), rebuild=True, embeddings=False)
    coordinator.reset()

    with Neo4jStore(
        uri=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
        database=NEO4J_DATABASE,
    ) as store:
        assert store.list_documents("test") == []





def _make_retrieval_corpus(root):
    (root / "billing.md").write_text(
        "---\ntitle: Billing Guide\ntype: concept\n---\n\n"
        "# Billing Guide\n\n"
        "## Customer Billing\n\n"
        "Customer billing invoices are generated monthly and sent by "
        "email. The billing cycle starts on the first day of each "
        "month.\n"
    )
    (root / "payments.md").write_text(
        "---\ntitle: Payments Overview\ntype: concept\n---\n\n"
        "# Payments Overview\n\n"
        "## Charging Customers For Services\n\n"
        "When a client is charged for a subscription, the payment is "
        "processed automatically and a receipt is issued.\n"
    )
    (root / "weather.md").write_text(
        "---\ntitle: Weather Notes\ntype: concept\n---\n\n"
        "# Weather Notes\n\n"
        "## Rainfall Patterns\n\n"
        "Regional rainfall varies significantly between seasons.\n"
    )


@requires_neo4j
def test_retrieve_returns_fused_hits_with_no_duplicate_sections(tmp_path):
    root = tmp_path
    _make_retrieval_corpus(root)
    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    try:
        coordinator.index(str(root), rebuild=True, embeddings=True)

        result = coordinator.retrieve("customer billing", top_k=5)

        assert result.query == "customer billing"
        assert result.hits
        section_ids = [hit.section_id for hit in result.hits]
        assert len(section_ids) == len(set(section_ids))
        for hit in result.hits:
            assert hit.fused_score > 0
            assert hit.retrieval_origin in ("vector", "lexical", "both")
            assert hit.document_id
            assert hit.section_id
            assert hit.source_path
    finally:
        coordinator.reset()


@requires_neo4j
def test_retrieve_keyword_heavy_query_surfaces_lexical_match(tmp_path):
    root = tmp_path
    _make_retrieval_corpus(root)
    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    try:
        coordinator.index(str(root), rebuild=True, embeddings=True)

        result = coordinator.retrieve("customer billing invoices", top_k=5)

        top_document_ids = {hit.document_id for hit in result.hits}
        assert "billing" in top_document_ids
        assert any(
            hit.document_id == "billing" and hit.lexical_rank is not None
            for hit in result.hits
        )
    finally:
        coordinator.reset()


@requires_neo4j
def test_retrieve_paraphrased_query_surfaces_vector_match(tmp_path):
    root = tmp_path
    _make_retrieval_corpus(root)
    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    try:
        coordinator.index(str(root), rebuild=True, embeddings=True)

        result = coordinator.retrieve(
            "how are clients invoiced for a subscription", top_k=5
        )

        assert result.hits
        assert any(hit.vector_rank is not None for hit in result.hits)
    finally:
        coordinator.reset()


@requires_neo4j
def test_retrieve_repeated_queries_produce_stable_ordering(tmp_path):
    root = tmp_path
    _make_retrieval_corpus(root)
    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    try:
        coordinator.index(str(root), rebuild=True, embeddings=True)

        first = coordinator.retrieve("customer billing", top_k=5)
        second = coordinator.retrieve("customer billing", top_k=5)

        assert [hit.section_id for hit in first.hits] == [
            hit.section_id for hit in second.hits
        ]
    finally:
        coordinator.reset()


def _make_graph_expansion_corpus(root):
    (root / "billing.md").write_text(
        "---\ntitle: Billing Guide\ntype: concept\n---\n\n"
        "# Billing Guide\n\n"
        "## Customer Billing\n\n"
        "Customer billing invoices are generated monthly and sent by "
        "email. See [payments](payments.md#charging-customers-for-services) "
        "for how charges are processed.\n"
    )
    (root / "payments.md").write_text(
        "---\ntitle: Payments Overview\ntype: concept\n---\n\n"
        "# Payments Overview\n\n"
        "## Charging Customers For Services\n\n"
        "When a client is charged for a subscription, the payment is "
        "processed automatically and a receipt is issued.\n"
    )
    (root / "weather.md").write_text(
        "---\ntitle: Weather Notes\ntype: concept\n---\n\n"
        "# Weather Notes\n\n"
        "## Rainfall Patterns\n\n"
        "Regional rainfall varies significantly between seasons.\n"
    )


@requires_neo4j
def test_retrieve_graph_hybrid_expands_linked_document(tmp_path):
    root = tmp_path
    _make_graph_expansion_corpus(root)
    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    try:
        coordinator.index(str(root), rebuild=True, embeddings=True)

        result = coordinator.retrieve("customer billing", top_k=1, expand=True)

        assert result.hits
        seed_document_ids = {hit.document_id for hit in result.hits}
        assert "billing" in seed_document_ids

        assert result.expanded_hits
        expanded_document_ids = {hit.document_id for hit in result.expanded_hits}
        assert "payments" in expanded_document_ids
        assert "payments" not in seed_document_ids

        for expanded in result.expanded_hits:
            assert expanded.section_id
            assert expanded.source_path
            assert expanded.graph_path
            assert expanded.selection_strategy in (
                "anchor",
                "relevance",
                "first-section",
            )
    finally:
        coordinator.reset()


@requires_neo4j
def test_retrieve_hybrid_mode_does_not_expand(tmp_path):
    root = tmp_path
    _make_graph_expansion_corpus(root)
    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    try:
        coordinator.index(str(root), rebuild=True, embeddings=True)

        result = coordinator.retrieve("customer billing", top_k=1, expand=False)

        assert result.expanded_hits == ()
    finally:
        coordinator.reset()


@requires_neo4j
def test_retrieve_graph_hybrid_enforces_max_expanded_results(tmp_path):
    root = tmp_path
    _make_graph_expansion_corpus(root)
    settings = Settings(graph_expansion_max_results=1)
    coordinator = Oneo(settings, registry=_registry_for(root))

    try:
        coordinator.index(str(root), rebuild=True, embeddings=True)

        result = coordinator.retrieve("customer billing", top_k=5, expand=True)

        assert len(result.expanded_hits) <= 1
    finally:
        coordinator.reset()


@requires_neo4j
def test_query_without_chat_model_returns_insufficient_evidence(tmp_path):
    root = tmp_path
    _make_retrieval_corpus(root)
    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root))

    try:
        coordinator.index(str(root), rebuild=True, embeddings=True)

        result = coordinator.query("customer billing", expand=False)

        assert result.insufficient_evidence
        assert result.citations == ()
        assert result.retrieval.hits
    finally:
        coordinator.reset()


@requires_neo4j
def test_query_generates_grounded_answer_with_valid_citations(tmp_path):
    root = tmp_path
    _make_retrieval_corpus(root)
    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root), chat_model=ExtractiveChatModel())

    try:
        coordinator.index(str(root), rebuild=True, embeddings=True)

        result = coordinator.query("customer billing", expand=False)

        assert not result.insufficient_evidence
        assert result.citations
        retrieved_section_ids = {hit.section_id for hit in result.retrieval.hits}
        for citation in result.citations:
            assert citation.section_id in retrieved_section_ids
    finally:
        coordinator.reset()


@requires_neo4j
def test_query_unanswerable_question_returns_insufficient_evidence(tmp_path):
    root = tmp_path
    _make_retrieval_corpus(root)
    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root), chat_model=ExtractiveChatModel())

    try:
        coordinator.index(str(root), rebuild=True, embeddings=True)

        result = coordinator.query(
            "what is the capital of France", expand=False
        )

        assert result.insufficient_evidence
        assert result.citations == ()
    finally:
        coordinator.reset()


@requires_neo4j
def test_query_graph_hybrid_cites_expanded_document(tmp_path):
    root = tmp_path
    (root / "topics").mkdir()
    (root / "overview.md").write_text(
        "---\ntitle: Overview\ntype: concept\n---\n\n"
        "# Overview\n\n"
        "This document explains how a customer is billed for using the "
        "service, including invoicing, payment, and subscription charges.\n\n"
        "See the [related topic](topics/related.md) for more.\n"
    )
    (root / "topics" / "related.md").write_text(
        "---\ntitle: Related Topic\ntype: concept\n---\n\n"
        "# Related Topic\n\n"
        "This section describes seasonal garden irrigation scheduling and "
        "soil moisture monitoring practices, used only to demonstrate "
        "one-hop graph expansion through link traversal, with wording kept "
        "far removed from subscriptions, payments, or accounts.\n"
    )
    settings = Settings()
    coordinator = Oneo(settings, registry=_registry_for(root), chat_model=ExtractiveChatModel())

    try:
        coordinator.index(str(root), rebuild=True, embeddings=True)

        result = coordinator.query(
            "How are customers billed?",
            top_k=1,
            expand=True,
        )

        assert not result.insufficient_evidence
        expanded_document_ids = {
            hit.document_id for hit in result.retrieval.expanded_hits
        }
        cited_document_ids = {citation.document_id for citation in result.citations}
        assert expanded_document_ids
        assert cited_document_ids & expanded_document_ids or result.graph_paths
    finally:
        coordinator.reset()


def _two_corpus_registry(billing_root, engineering_root) -> CorpusRegistry:
    return CorpusRegistry(
        {
            "billing": Corpus(name="billing", root=str(billing_root)),
            "engineering": Corpus(name="engineering", root=str(engineering_root)),
        },
        "billing",
    )


def _make_engineering_corpus(root):
    """A corpus with document/section identifiers and vocabulary
    deliberately disjoint from ``_make_retrieval_corpus``/
    ``_make_graph_expansion_corpus``, used to prove corpus isolation
    without relying on identical fixture content."""

    (root / "deployment.md").write_text(
        "---\ntitle: Deployment Pipeline\ntype: concept\n---\n\n"
        "# Deployment Pipeline\n\n"
        "## Continuous Integration Stages\n\n"
        "Every merge triggers a build, a linting pass, and a full test "
        "suite before an artifact is published to the registry. See "
        "[test strategy](testing.md#automated-test-strategy) for how "
        "coverage is enforced.\n"
    )
    (root / "testing.md").write_text(
        "---\ntitle: Testing Strategy\ntype: concept\n---\n\n"
        "# Testing Strategy\n\n"
        "## Automated Test Strategy\n\n"
        "Unit tests run on every commit, while integration tests run "
        "nightly against a staging cluster.\n"
    )


@requires_neo4j
def test_retrieve_never_leaks_hits_across_corpuses(tmp_path):
    """A query that matches content in one corpus but not the other
    must only return hits belonging to the explicitly selected corpus,
    never a document from the other corpus."""

    billing_root = tmp_path / "billing"
    engineering_root = tmp_path / "engineering"
    billing_root.mkdir()
    engineering_root.mkdir()
    _make_retrieval_corpus(billing_root)
    _make_engineering_corpus(engineering_root)

    settings = Settings()
    coordinator = Oneo(
        settings, registry=_two_corpus_registry(billing_root, engineering_root)
    )

    try:
        coordinator.index(str(billing_root), rebuild=True, embeddings=True, corpus="billing")
        coordinator.index(
            str(engineering_root), rebuild=True, embeddings=True, corpus="engineering"
        )

        billing_result = coordinator.retrieve(
            "customer billing", top_k=5, corpus="billing"
        )
        engineering_result = coordinator.retrieve(
            "customer billing", top_k=5, corpus="engineering"
        )

        assert billing_result.hits
        billing_document_ids = {"billing", "payments", "weather"}
        engineering_document_ids = {"deployment", "testing"}

        for hit in billing_result.hits:
            assert hit.document_id in billing_document_ids

        for hit in engineering_result.hits:
            assert hit.document_id in engineering_document_ids
            assert hit.document_id not in billing_document_ids
    finally:
        coordinator.reset(corpus="billing")
        coordinator.reset(corpus="engineering")


@requires_neo4j
def test_retrieve_graph_hybrid_never_expands_across_corpuses(tmp_path):
    """Graph expansion must stay within the selected corpus even when
    another corpus is indexed alongside it with its own link topology."""

    billing_root = tmp_path / "billing"
    engineering_root = tmp_path / "engineering"
    billing_root.mkdir()
    engineering_root.mkdir()
    _make_graph_expansion_corpus(billing_root)
    _make_engineering_corpus(engineering_root)

    settings = Settings()
    coordinator = Oneo(
        settings, registry=_two_corpus_registry(billing_root, engineering_root)
    )

    try:
        coordinator.index(str(billing_root), rebuild=True, embeddings=True, corpus="billing")
        coordinator.index(
            str(engineering_root), rebuild=True, embeddings=True, corpus="engineering"
        )

        result = coordinator.retrieve(
            "customer billing", top_k=1, expand=True, corpus="billing"
        )

        assert result.expanded_hits
        for hit in result.hits + result.expanded_hits:
            assert hit.document_id in ("billing", "payments")
            assert hit.document_id not in ("deployment", "testing")
    finally:
        coordinator.reset(corpus="billing")
        coordinator.reset(corpus="engineering")


@requires_neo4j
def test_query_citations_never_resolve_outside_selected_corpus(tmp_path):
    """Every citation in a grounded answer must resolve to a section of
    the selected corpus, even when another corpus is indexed alongside
    it."""

    billing_root = tmp_path / "billing"
    engineering_root = tmp_path / "engineering"
    billing_root.mkdir()
    engineering_root.mkdir()
    _make_retrieval_corpus(billing_root)
    _make_engineering_corpus(engineering_root)

    settings = Settings()
    coordinator = Oneo(
        settings,
        registry=_two_corpus_registry(billing_root, engineering_root),
        chat_model=ExtractiveChatModel(),
    )

    try:
        coordinator.index(str(billing_root), rebuild=True, embeddings=True, corpus="billing")
        coordinator.index(
            str(engineering_root), rebuild=True, embeddings=True, corpus="engineering"
        )

        result = coordinator.query(
            "How are customers billed?", top_k=3, corpus="billing"
        )

        assert not result.insufficient_evidence
        assert result.citations
        for citation in result.citations:
            assert citation.document_id in ("billing", "payments", "weather")
            assert citation.document_id not in ("deployment", "testing")
    finally:
        coordinator.reset(corpus="billing")
        coordinator.reset(corpus="engineering")
