from __future__ import annotations

import json

from typer.testing import CliRunner

from oneo import cli
from oneo.models import (
    AnswerResult,
    Citation,
    Diagnostic,
    GraphExpandedHit,
    HealthStatus,
    IndexedDocument,
    IndexSummary,
    OkfDocument,
    ParsedDocument,
    RetrievalHit,
    RetrievalResult,
    SectionMatch,
    ValidationResult,
    VerificationResult,
)
from oneo.security import PathSecurityError

runner = CliRunner()


class _FakeCoordinator:
    def __init__(
        self,
        *,
        health_status=None,
        discovered=None,
        discover_error=None,
        parsed=None,
        parse_error=None,
        validation_result=None,
        validate_error=None,
        index_summary=None,
        index_error=None,
        verification_result=None,
        verify_error=None,
        reset_error=None,
        retrieval_result=None,
        retrieve_error=None,
        query_result=None,
        query_error=None,
        vector_search_matches=None,
        vector_search_error=None,
    ):
        self._health_status = health_status
        self._discovered = discovered or []
        self._discover_error = discover_error
        self._parsed = parsed or []
        self._parse_error = parse_error
        self._validation_result = validation_result
        self._validate_error = validate_error
        self._index_summary = index_summary
        self._index_error = index_error
        self._verification_result = verification_result
        self._verify_error = verify_error
        self._reset_error = reset_error
        self._retrieval_result = retrieval_result
        self._retrieve_error = retrieve_error
        self._query_result = query_result
        self._query_error = query_error
        self._vector_search_matches = vector_search_matches or []
        self._vector_search_error = vector_search_error
        self.reset_called = False
        self.received_corpus = {}

    def health(self):
        return self._health_status

    def discover(self, input_path: str | None = None, corpus: str | None = None):
        self.received_corpus["discover"] = corpus
        if self._discover_error is not None:
            raise self._discover_error
        return self._discovered

    def parse(self, input_path: str | None = None, corpus: str | None = None):
        self.received_corpus["parse"] = corpus
        if self._parse_error is not None:
            raise self._parse_error
        return self._parsed

    def validate(self, input_path: str | None = None, strict: bool = False, corpus: str | None = None):
        self.received_corpus["validate"] = corpus
        if self._validate_error is not None:
            raise self._validate_error
        return self._validation_result

    def index(self, input_path: str | None = None, rebuild: bool = True, embeddings: bool = True, corpus: str | None = None):
        self.received_corpus["index"] = corpus
        if self._index_error is not None:
            raise self._index_error
        return self._index_summary

    def verify(self, input_path: str | None = None, corpus: str | None = None):
        self.received_corpus["verify"] = corpus
        if self._verify_error is not None:
            raise self._verify_error
        return self._verification_result

    def reset(self, corpus: str | None = None):
        self.received_corpus["reset"] = corpus
        if self._reset_error is not None:
            raise self._reset_error
        self.reset_called = True

    def retrieve(self, query: str, top_k: int | None = None, expand: bool = False, corpus: str | None = None):
        self.received_corpus["retrieve"] = corpus
        if self._retrieve_error is not None:
            raise self._retrieve_error
        return self._retrieval_result

    def query(self, query: str, top_k: int | None = None, expand: bool = True, corpus: str | None = None):
        self.received_corpus["query"] = corpus
        if self._query_error is not None:
            raise self._query_error
        return self._query_result

    def vector_search(self, query: str, top_k: int | None = None, corpus: str | None = None):
        self.received_corpus["vector_search"] = corpus
        if self._vector_search_error is not None:
            raise self._vector_search_error
        return self._vector_search_matches


def test_health_reports_connected(monkeypatch):
    status = HealthStatus(
        connected=True, database="neo4j", server_agent="Neo4j/5.0.0"
    )
    monkeypatch.setattr(
        cli, "_build_coordinator", lambda **_: _FakeCoordinator(health_status=status)
    )

    result = runner.invoke(cli.app, ["health"])

    assert result.exit_code == 0
    assert "connected to database" in result.output
    assert "neo4j" in result.output


def test_health_reports_failure(monkeypatch):
    status = HealthStatus(
        connected=False, database="neo4j", detail="connection refused"
    )
    monkeypatch.setattr(
        cli, "_build_coordinator", lambda **_: _FakeCoordinator(health_status=status)
    )

    result = runner.invoke(cli.app, ["health"])

    assert result.exit_code == 1
    assert "failed to connect" in result.output
    assert "connection refused" in result.output


def test_files_prints_discovered_paths(monkeypatch):
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(discovered=["overview.md", "topics/example.md"]),
    )

    result = runner.invoke(cli.app, ["files", "some/path"])

    assert result.exit_code == 0
    assert result.output.splitlines() == ["overview.md", "topics/example.md"]


def test_files_rejects_path_security_error(monkeypatch):
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(discover_error=PathSecurityError("outside root")),
    )

    result = runner.invoke(cli.app, ["files", "../outside"])

    assert result.exit_code == 1
    assert "rejected:" in result.output
    assert "outside root" in result.output


def test_main_invokes_app(monkeypatch):
    called = {}
    monkeypatch.setattr(cli, "app", lambda: called.setdefault("invoked", True))

    cli.main()

    assert called.get("invoked") is True


def test_parse_writes_normalized_corpus_json(monkeypatch, tmp_path):
    parsed_document = ParsedDocument(
        document=OkfDocument(
            document_id="overview",
            title="Overview",
            source_path="overview.md",
            metadata={"title": "Overview"},
            content_hash="abc123",
        ),
        sections=(),
        links=(),
    )
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(parsed=[parsed_document]),
    )
    output_path = tmp_path / "out" / "corpus.json"

    result = runner.invoke(
        cli.app, ["parse", "some/path", "--output", str(output_path)]
    )

    assert result.exit_code == 0
    assert "wrote 1 document(s)" in result.output
    written = json.loads(output_path.read_text())
    assert written["documents"][0]["document_id"] == "overview"


def test_parse_rejects_path_security_error(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(parse_error=PathSecurityError("outside root")),
    )

    result = runner.invoke(
        cli.app,
        ["parse", "../outside", "--output", str(tmp_path / "corpus.json")],
    )

    assert result.exit_code == 1
    assert "rejected:" in result.output
    assert "outside root" in result.output


def test_validate_reports_diagnostics_and_exits_zero_when_ok(monkeypatch):
    validation_result = ValidationResult(
        diagnostics=(
            Diagnostic(
                severity="warning",
                code="unresolved-link",
                source_path="doc.md",
                source_section="doc::_::0",
                raw_target="missing.md",
                message="unresolved local document link: 'missing.md'",
            ),
        ),
        ok=True,
    )
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(validation_result=validation_result),
    )

    result = runner.invoke(cli.app, ["validate", "some/path"])

    assert result.exit_code == 0
    assert "unresolved-link" in result.output
    assert "doc.md" in result.output
    assert "raw_target=missing.md" in result.output
    assert "1 diagnostic(s)" in result.output


def test_validate_exits_non_zero_when_strict_fails(monkeypatch):
    validation_result = ValidationResult(
        diagnostics=(
            Diagnostic(
                severity="error",
                code="unresolved-link",
                source_path="doc.md",
                raw_target="missing.md",
                message="unresolved local document link: 'missing.md'",
            ),
        ),
        ok=False,
    )
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(validation_result=validation_result),
    )

    result = runner.invoke(cli.app, ["validate", "some/path", "--strict"])

    assert result.exit_code == 1


def test_validate_rejects_path_security_error(monkeypatch):
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(validate_error=PathSecurityError("outside root")),
    )

    result = runner.invoke(cli.app, ["validate", "../outside"])

    assert result.exit_code == 1
    assert "rejected:" in result.output
    assert "outside root" in result.output


def test_index_reports_summary(monkeypatch):
    summary = IndexSummary(documents=2, sections=2, links=1)
    monkeypatch.setattr(
        cli, "_build_coordinator", lambda **_: _FakeCoordinator(index_summary=summary)
    )

    result = runner.invoke(cli.app, ["index", "some/path", "--no-embeddings"])

    assert result.exit_code == 0
    assert "indexed 2 document(s)" in result.output
    assert "1 link(s)" in result.output


def test_index_rejects_path_security_error(monkeypatch):
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(index_error=PathSecurityError("outside root")),
    )

    result = runner.invoke(cli.app, ["index", "../outside", "--no-embeddings"])

    assert result.exit_code == 1
    assert "rejected:" in result.output


def test_index_reports_not_implemented_error(monkeypatch):
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(index_error=NotImplementedError("no embeddings yet")),
    )

    result = runner.invoke(cli.app, ["index", "some/path"])

    assert result.exit_code == 1
    assert "no embeddings yet" in result.output


def test_reset_reports_completion(monkeypatch):
    coordinator = _FakeCoordinator()
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)

    result = runner.invoke(cli.app, ["reset"])

    assert result.exit_code == 0
    assert "reset complete" in result.output
    assert coordinator.reset_called is True


def test_verify_reports_ok(monkeypatch):
    verification_result = VerificationResult(
        ok=True, issues=(), documents=2, sections=2, links=1
    )
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(verification_result=verification_result),
    )

    result = runner.invoke(cli.app, ["verify", "./somewhere"])

    assert result.exit_code == 0
    assert "documents=2 sections=2 links=1" in result.output


def test_verify_exits_non_zero_on_issue(monkeypatch):
    verification_result = VerificationResult(
        ok=False,
        issues=("section count differs between filesystem and graph",),
        documents=2,
        sections=1,
        links=1,
    )
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(verification_result=verification_result),
    )

    result = runner.invoke(cli.app, ["verify", "./somewhere"])

    assert result.exit_code == 1
    assert "[issue]" in result.output


def test_verify_rejects_path_security_error(monkeypatch):
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(verify_error=PathSecurityError("outside root")),
    )

    result = runner.invoke(cli.app, ["verify", "../outside"])

    assert result.exit_code == 1
    assert "rejected:" in result.output


def test_retrieve_prints_fused_hits(monkeypatch):
    retrieval_result = RetrievalResult(
        query="customer billing",
        hits=(
            RetrievalHit(
                section_id="billing::customer-billing::0",
                document_id="billing",
                heading="Customer Billing",
                source_path="billing.md",
                vector_rank=1,
                vector_score=0.9,
                lexical_rank=1,
                lexical_score=4.2,
                fused_score=0.033,
                retrieval_origin="both",
            ),
        ),
    )
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(retrieval_result=retrieval_result),
    )

    result = runner.invoke(cli.app, ["retrieve", "customer billing", "--mode", "hybrid"])

    assert result.exit_code == 0
    assert "document_id=billing" in result.output
    assert "1 seed result(s)" in result.output


def test_retrieve_explain_prints_ranking_diagnostics(monkeypatch):
    retrieval_result = RetrievalResult(
        query="customer billing",
        hits=(
            RetrievalHit(
                section_id="billing::customer-billing::0",
                document_id="billing",
                heading="Customer Billing",
                source_path="billing.md",
                vector_rank=1,
                vector_score=0.9,
                lexical_rank=1,
                lexical_score=4.2,
                fused_score=0.033,
                retrieval_origin="both",
            ),
        ),
    )
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(retrieval_result=retrieval_result),
    )

    result = runner.invoke(
        cli.app, ["retrieve", "customer billing", "--mode", "hybrid", "--explain"]
    )

    assert result.exit_code == 0
    assert "vector_rank=1" in result.output
    assert "lexical_rank=1" in result.output


def test_retrieve_rejects_unsupported_mode(monkeypatch):
    monkeypatch.setattr(
        cli, "_build_coordinator", lambda **_: _FakeCoordinator()
    )

    result = runner.invoke(
        cli.app, ["retrieve", "customer billing", "--mode", "bogus-mode"]
    )

    assert result.exit_code == 1
    assert "unsupported mode" in result.output


def test_retrieve_graph_hybrid_prints_expanded_hits(monkeypatch):
    retrieval_result = RetrievalResult(
        query="customer billing",
        hits=(
            RetrievalHit(
                section_id="billing::customer-billing::0",
                document_id="billing",
                heading="Customer Billing",
                source_path="billing.md",
                vector_rank=1,
                vector_score=0.9,
                lexical_rank=1,
                lexical_score=4.2,
                fused_score=0.033,
                retrieval_origin="both",
            ),
        ),
        expanded_hits=(
            GraphExpandedHit(
                section_id="payments::charging-customers::0",
                document_id="payments",
                heading="Charging Customers For Services",
                source_path="payments.md",
                expansion_score=0.5,
                graph_path=("billing", "LINKS_TO", "payments"),
                via_document_id="billing",
                selection_strategy="relevance",
            ),
        ),
    )
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(retrieval_result=retrieval_result),
    )

    result = runner.invoke(
        cli.app, ["retrieve", "customer billing", "--mode", "graph-hybrid", "--explain"]
    )

    assert result.exit_code == 0
    assert "[seed] document_id=billing" in result.output
    assert "[expanded] document_id=payments" in result.output
    assert "strategy=relevance" in result.output
    assert "graph_path=billing -> LINKS_TO -> payments" in result.output
    assert "1 expanded result(s)" in result.output


def test_retrieve_rejects_path_security_error(monkeypatch):
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(retrieve_error=PathSecurityError("outside root")),
    )

    result = runner.invoke(cli.app, ["retrieve", "customer billing"])

    assert result.exit_code == 1
    assert "rejected:" in result.output


def test_query_prints_answer_and_citations(monkeypatch):
    retrieval_result = RetrievalResult(
        query="How are customers billed?",
        hits=(
            RetrievalHit(
                section_id="billing::customer-billing::0",
                document_id="billing",
                heading="Customer Billing",
                source_path="billing.md",
                vector_rank=1,
                vector_score=0.9,
                lexical_rank=1,
                lexical_score=4.2,
                fused_score=0.033,
                retrieval_origin="both",
            ),
        ),
    )
    answer_result = AnswerResult(
        query="How are customers billed?",
        answer="Customers are billed monthly [S1].",
        citations=(
            Citation(
                label="S1",
                document_id="billing",
                section_id="billing::customer-billing::0",
                source_path="billing.md",
                heading="Customer Billing",
                retrieval_origin="seed",
            ),
        ),
        retrieval=retrieval_result,
        graph_paths=(),
        insufficient_evidence=False,
    )
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(query_result=answer_result),
    )

    result = runner.invoke(cli.app, ["query", "How are customers billed?"])

    assert result.exit_code == 0
    assert "answer: Customers are billed monthly [S1]." in result.output
    assert "insufficient_evidence: False" in result.output
    assert "[citation S1] document_id=billing" in result.output


def test_query_show_sources_and_paths(monkeypatch):
    retrieval_result = RetrievalResult(
        query="How are customers billed?",
        hits=(
            RetrievalHit(
                section_id="billing::customer-billing::0",
                document_id="billing",
                heading="Customer Billing",
                source_path="billing.md",
                vector_rank=1,
                vector_score=0.9,
                lexical_rank=1,
                lexical_score=4.2,
                fused_score=0.033,
                retrieval_origin="both",
            ),
        ),
        expanded_hits=(
            GraphExpandedHit(
                section_id="payments::charging-customers::0",
                document_id="payments",
                heading="Charging Customers For Services",
                source_path="payments.md",
                expansion_score=0.5,
                graph_path=("billing", "LINKS_TO", "payments"),
                via_document_id="billing",
                selection_strategy="relevance",
            ),
        ),
    )
    answer_result = AnswerResult(
        query="How are customers billed?",
        answer="Customers are billed monthly [S1], and payments recorded [S2].",
        citations=(
            Citation(
                label="S2",
                document_id="payments",
                section_id="payments::charging-customers::0",
                source_path="payments.md",
                heading="Charging Customers For Services",
                retrieval_origin="expanded",
            ),
        ),
        retrieval=retrieval_result,
        graph_paths=(("billing", "LINKS_TO", "payments"),),
        insufficient_evidence=False,
    )
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(query_result=answer_result),
    )

    result = runner.invoke(
        cli.app,
        ["query", "How are customers billed?", "--show-sources", "--show-paths"],
    )

    assert result.exit_code == 0
    assert "[source] document_id=billing" in result.output
    assert "[source-expanded] document_id=payments" in result.output
    assert "[graph_path] billing -> LINKS_TO -> payments" in result.output


def test_query_reports_insufficient_evidence(monkeypatch):
    retrieval_result = RetrievalResult(query="unanswerable?", hits=())
    answer_result = AnswerResult(
        query="unanswerable?",
        answer="insufficient evidence",
        citations=(),
        retrieval=retrieval_result,
        graph_paths=(),
        insufficient_evidence=True,
    )
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(query_result=answer_result),
    )

    result = runner.invoke(cli.app, ["query", "unanswerable?"])

    assert result.exit_code == 0
    assert "insufficient_evidence: True" in result.output


def test_query_rejects_unsupported_mode(monkeypatch):
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: _FakeCoordinator())

    result = runner.invoke(
        cli.app, ["query", "How are customers billed?", "--mode", "bogus-mode"]
    )

    assert result.exit_code == 1
    assert "unsupported mode" in result.output


def test_query_rejects_path_security_error(monkeypatch):
    monkeypatch.setattr(
        cli,
        "_build_coordinator",
        lambda **_: _FakeCoordinator(query_error=PathSecurityError("outside root")),
    )

    result = runner.invoke(cli.app, ["query", "How are customers billed?"])

    assert result.exit_code == 1
    assert "rejected:" in result.output


def test_corpus_list_prints_names_and_roots(monkeypatch, tmp_path):
    config_path = tmp_path / "corpuses.toml"
    config_path.write_text(
        '[corpuses.billing]\nroot = "./corpuses/billing"\n'
        '[corpuses.engineering]\nroot = "./corpuses/engineering"\n'
    )
    monkeypatch.setenv("ONEO_CORPUS_CONFIG", str(config_path))

    result = runner.invoke(cli.app, ["corpus", "list"])

    assert result.exit_code == 0
    assert "billing ./corpuses/billing" in result.output
    assert "engineering ./corpuses/engineering" in result.output


def test_corpus_info_reports_existing_root(monkeypatch, tmp_path):
    root = tmp_path / "billing"
    root.mkdir()
    config_path = tmp_path / "corpuses.toml"
    config_path.write_text(f'[corpuses.billing]\nroot = "{root}"\n')
    monkeypatch.setenv("ONEO_CORPUS_CONFIG", str(config_path))

    result = runner.invoke(cli.app, ["corpus", "info", "billing"])

    assert result.exit_code == 0
    assert "name=billing" in result.output
    assert "exists=True" in result.output


def test_corpus_info_unknown_name_exits_non_zero(monkeypatch, tmp_path):
    config_path = tmp_path / "corpuses.toml"
    config_path.write_text('[corpuses.billing]\nroot = "./corpuses/billing"\n')
    monkeypatch.setenv("ONEO_CORPUS_CONFIG", str(config_path))

    result = runner.invoke(cli.app, ["corpus", "info", "unknown"])

    assert result.exit_code == 1
    assert "corpus configuration error" in result.output


def test_corpus_list_missing_config_exits_non_zero(monkeypatch, tmp_path):
    monkeypatch.setenv("ONEO_CORPUS_CONFIG", str(tmp_path / "missing.toml"))

    result = runner.invoke(cli.app, ["corpus", "list"])

    assert result.exit_code == 1
    assert "corpus configuration error" in result.output


# --- --corpus flag threading coverage (gap-fill for Step 2) ---------------


def test_files_threads_corpus_flag(monkeypatch):
    coordinator = _FakeCoordinator(discovered=["overview.md"])
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)

    result = runner.invoke(cli.app, ["files", "some/path", "--corpus", "engineering"])

    assert result.exit_code == 0
    assert coordinator.received_corpus["discover"] == "engineering"


def test_files_omits_corpus_flag_defaults_to_none(monkeypatch):
    coordinator = _FakeCoordinator(discovered=["overview.md"])
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)

    result = runner.invoke(cli.app, ["files", "some/path"])

    assert result.exit_code == 0
    assert coordinator.received_corpus["discover"] is None


def test_parse_threads_corpus_flag(monkeypatch, tmp_path):
    parsed_document = ParsedDocument(
        document=OkfDocument(
            document_id="overview",
            title="Overview",
            source_path="overview.md",
            metadata={"title": "Overview"},
            content_hash="abc123",
        ),
        sections=(),
        links=(),
    )
    coordinator = _FakeCoordinator(parsed=[parsed_document])
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)
    output_path = tmp_path / "out" / "corpus.json"

    result = runner.invoke(
        cli.app,
        ["parse", "some/path", "--output", str(output_path), "--corpus", "billing"],
    )

    assert result.exit_code == 0
    assert coordinator.received_corpus["parse"] == "billing"


def test_parse_omits_corpus_flag_defaults_to_none(monkeypatch, tmp_path):
    parsed_document = ParsedDocument(
        document=OkfDocument(
            document_id="overview",
            title="Overview",
            source_path="overview.md",
            metadata={"title": "Overview"},
            content_hash="abc123",
        ),
        sections=(),
        links=(),
    )
    coordinator = _FakeCoordinator(parsed=[parsed_document])
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)
    output_path = tmp_path / "out" / "corpus.json"

    result = runner.invoke(
        cli.app, ["parse", "some/path", "--output", str(output_path)]
    )

    assert result.exit_code == 0
    assert coordinator.received_corpus["parse"] is None


def test_validate_threads_corpus_flag(monkeypatch):
    validation_result = ValidationResult(diagnostics=(), ok=True)
    coordinator = _FakeCoordinator(validation_result=validation_result)
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)

    result = runner.invoke(
        cli.app, ["validate", "some/path", "--strict", "--corpus", "billing"]
    )

    assert result.exit_code == 0
    assert coordinator.received_corpus["validate"] == "billing"


def test_validate_omits_corpus_flag_defaults_to_none(monkeypatch):
    validation_result = ValidationResult(diagnostics=(), ok=True)
    coordinator = _FakeCoordinator(validation_result=validation_result)
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)

    result = runner.invoke(cli.app, ["validate", "some/path"])

    assert result.exit_code == 0
    assert coordinator.received_corpus["validate"] is None


def test_index_threads_corpus_flag(monkeypatch):
    summary = IndexSummary(documents=2, sections=2, links=1)
    coordinator = _FakeCoordinator(index_summary=summary)
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)

    result = runner.invoke(
        cli.app,
        ["index", "some/path", "--no-embeddings", "--corpus", "engineering"],
    )

    assert result.exit_code == 0
    assert coordinator.received_corpus["index"] == "engineering"


def test_index_omits_corpus_flag_defaults_to_none(monkeypatch):
    summary = IndexSummary(documents=2, sections=2, links=1)
    coordinator = _FakeCoordinator(index_summary=summary)
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)

    result = runner.invoke(cli.app, ["index", "some/path", "--no-embeddings"])

    assert result.exit_code == 0
    assert coordinator.received_corpus["index"] is None


def test_vector_search_threads_corpus_flag(monkeypatch):
    matches = [
        SectionMatch(
            section_id="billing::customer-billing::0",
            document_id="billing",
            heading="Customer Billing",
            score=0.9,
            source_path="billing.md",
        )
    ]
    coordinator = _FakeCoordinator(vector_search_matches=matches)
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)

    result = runner.invoke(
        cli.app, ["vector-search", "billing question", "--corpus", "billing"]
    )

    assert result.exit_code == 0
    assert coordinator.received_corpus["vector_search"] == "billing"


def test_vector_search_omits_corpus_flag_defaults_to_none(monkeypatch):
    coordinator = _FakeCoordinator(vector_search_matches=[])
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)

    result = runner.invoke(cli.app, ["vector-search", "billing question"])

    assert result.exit_code == 0
    assert coordinator.received_corpus["vector_search"] is None


def test_retrieve_threads_corpus_flag(monkeypatch):
    retrieval_result = RetrievalResult(query="customer billing", hits=())
    coordinator = _FakeCoordinator(retrieval_result=retrieval_result)
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)

    result = runner.invoke(
        cli.app, ["retrieve", "customer billing", "--corpus", "billing"]
    )

    assert result.exit_code == 0
    assert coordinator.received_corpus["retrieve"] == "billing"


def test_retrieve_omits_corpus_flag_defaults_to_none(monkeypatch):
    retrieval_result = RetrievalResult(query="customer billing", hits=())
    coordinator = _FakeCoordinator(retrieval_result=retrieval_result)
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)

    result = runner.invoke(cli.app, ["retrieve", "customer billing"])

    assert result.exit_code == 0
    assert coordinator.received_corpus["retrieve"] is None


def test_query_threads_corpus_flag(monkeypatch):
    retrieval_result = RetrievalResult(query="How are customers billed?", hits=())
    answer_result = AnswerResult(
        query="How are customers billed?",
        answer="insufficient evidence",
        citations=(),
        retrieval=retrieval_result,
        graph_paths=(),
        insufficient_evidence=True,
    )
    coordinator = _FakeCoordinator(query_result=answer_result)
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)

    result = runner.invoke(
        cli.app, ["query", "How are customers billed?", "--corpus", "billing"]
    )

    assert result.exit_code == 0
    assert coordinator.received_corpus["query"] == "billing"


def test_query_omits_corpus_flag_defaults_to_none(monkeypatch):
    retrieval_result = RetrievalResult(query="How are customers billed?", hits=())
    answer_result = AnswerResult(
        query="How are customers billed?",
        answer="insufficient evidence",
        citations=(),
        retrieval=retrieval_result,
        graph_paths=(),
        insufficient_evidence=True,
    )
    coordinator = _FakeCoordinator(query_result=answer_result)
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)

    result = runner.invoke(cli.app, ["query", "How are customers billed?"])

    assert result.exit_code == 0
    assert coordinator.received_corpus["query"] is None


def test_reset_threads_corpus_flag(monkeypatch):
    coordinator = _FakeCoordinator()
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)

    result = runner.invoke(cli.app, ["reset", "--corpus", "billing"])

    assert result.exit_code == 0
    assert coordinator.received_corpus["reset"] == "billing"


def test_reset_omits_corpus_flag_defaults_to_none(monkeypatch):
    coordinator = _FakeCoordinator()
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)

    result = runner.invoke(cli.app, ["reset"])

    assert result.exit_code == 0
    assert coordinator.received_corpus["reset"] is None


def test_verify_threads_corpus_flag(monkeypatch):
    verification_result = VerificationResult(
        ok=True, issues=(), documents=2, sections=2, links=1
    )
    coordinator = _FakeCoordinator(verification_result=verification_result)
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)

    result = runner.invoke(
        cli.app, ["verify", "./somewhere", "--corpus", "billing"]
    )

    assert result.exit_code == 0
    assert coordinator.received_corpus["verify"] == "billing"


def test_verify_omits_corpus_flag_defaults_to_none(monkeypatch):
    verification_result = VerificationResult(
        ok=True, issues=(), documents=2, sections=2, links=1
    )
    coordinator = _FakeCoordinator(verification_result=verification_result)
    monkeypatch.setattr(cli, "_build_coordinator", lambda **_: coordinator)

    result = runner.invoke(cli.app, ["verify", "./somewhere"])

    assert result.exit_code == 0
    assert coordinator.received_corpus["verify"] is None


def test_mcp_rejects_unsupported_transport():
    result = runner.invoke(cli.app, ["mcp", "--transport", "sse"])

    assert result.exit_code == 1
    assert "unsupported transport" in result.output


def test_mcp_reports_missing_dependency_cleanly(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "oneo.mcp_server":
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    result = runner.invoke(cli.app, ["mcp"])

    assert result.exit_code == 1
    assert "oneo[mcp]" in result.output
