"""The ``Oneo`` pipeline coordinator.

Exposes a small public surface (`validate`, `index`, `discover`,
`retrieve`, `query`, `reset`), plus `verify` -- a read-only diagnostic
added in Step 4 to compare the filesystem corpus against the graph
index end-to-end -- and delegates all behavior to focused
collaborators. Command-line handlers must call only these methods and
must not contain domain logic themselves.
"""

from __future__ import annotations

from typing import Any

from oneo.answering import ChatModel, generate_answer
from oneo.config import Settings
from oneo.corpus import CorpusRegistry
from oneo.discovery import discover_files
from oneo.embedding import (
    SectionEmbedder,
    build_embedding_input,
    compute_embedding_input_hash,
)
from oneo.graph_expander import expand_hits
from oneo.models import (
    AnswerResult,
    HealthStatus,
    IndexSummary,
    LinkedDocument,
    OkfSection,
    ParsedDocument,
    RetrievalResult,
    SectionMatch,
    ValidationResult,
    VerificationResult,
)
from oneo.neo4j_store import Neo4jStore
from oneo.okf_loader import OkfLoader
from oneo.retriever import fuse_rankings
from oneo.validation import resolve_links, validate_corpus


class Oneo:
    """Coordinates OKF discovery, indexing, retrieval, and answering.

    ``chat_model`` is the narrow, optional boundary answer generation
    depends on (see :mod:`oneo.answering`). It defaults to ``None`` so
    the coordinator -- and therefore retrieval -- remains fully usable
    with no chat model configured; ``query`` then returns an explicit
    insufficient-evidence result instead of raising. Callers that want
    grounded answers (e.g. the CLI) inject a concrete ``ChatModel``.
    """

    def __init__(
        self,
        settings: Settings,
        registry: CorpusRegistry | None = None,
        chat_model: ChatModel | None = None,
    ) -> None:
        self._settings = settings
        self._registry_override = registry
        self._chat_model = chat_model

    @property
    def _registry(self) -> CorpusRegistry:
        """Return the corpus registry, loading it from the configured
        ``corpuses.toml`` on first use if none was injected at
        construction time."""

        if self._registry_override is None:
            self._registry_override = CorpusRegistry.load(
                self._settings.corpus_config, self._settings.default_corpus
            )
        return self._registry_override

    def _resolve_corpus_name(self, corpus: str | None) -> str:
        """Resolve ``corpus`` to a registered corpus name, falling back
        to the registry's configured default when ``corpus`` is
        ``None``. Raises :class:`oneo.corpus.CorpusConfigError` when no
        corpus can be resolved."""

        name = corpus if corpus is not None else self._registry.default_name()
        self._registry.get(name)  # validates the name is registered
        return name

    def _resolve_corpus_root(
        self, corpus: str | None, input_path: str | None
    ) -> tuple[str, str]:
        """Resolve the effective knowledge root for ``corpus`` and the
        effective ``input_path`` to scan/parse within it.

        When ``input_path`` is ``None``, it defaults to the corpus's
        root; when given, it is still validated against that root by
        the downstream discovery/loader calls.
        """

        name = self._resolve_corpus_name(corpus)
        root = self._registry.get(name).root
        effective_input_path = input_path if input_path is not None else root
        return root, effective_input_path

    def _graph_store(self) -> Neo4jStore:
        return Neo4jStore(
            uri=self._settings.neo4j_uri,
            username=self._settings.neo4j_username,
            password=self._settings.neo4j_password,
            database=self._settings.neo4j_database,
        )

    def health(self) -> HealthStatus:
        """Verify connectivity to the configured Neo4j database."""

        with self._graph_store() as store:
            return store.health()

    def discover(
        self, input_path: str | None = None, corpus: str | None = None
    ) -> list[str]:
        """Discover supported OKF source files under ``input_path``.

        Args:
            input_path: Directory to scan. When omitted, defaults to
                the selected corpus's root. Still used as (or
                validated against) the trusted root boundary for
                path-security validation -- there is no implicit
                global root, only the selected corpus's root (see
                :mod:`oneo.corpus`).
            corpus: Name of the corpus to select. When ``None``, the
                registry's configured default corpus is used.

        Returns:
            A sorted list of root-relative source paths.
        """

        root, effective_input_path = self._resolve_corpus_root(corpus, input_path)
        return discover_files(
            input_path=effective_input_path,
            knowledge_root=root,
            exclude_patterns=self._settings.exclude_patterns,
        )

    def parse(
        self, input_path: str | None = None, corpus: str | None = None
    ) -> list[ParsedDocument]:
        """Parse every discovered OKF document under ``input_path``.

        Delegates discovery to :func:`oneo.discovery.discover_files` and
        semantic parsing to :class:`oneo.okf_loader.OkfLoader`. Corpus
        validation and link resolution are added in a later step.
        """

        root, effective_input_path = self._resolve_corpus_root(corpus, input_path)
        source_paths = discover_files(
            input_path=effective_input_path,
            knowledge_root=root,
            exclude_patterns=self._settings.exclude_patterns,
        )
        loader = OkfLoader(knowledge_root=root)
        return [loader.load(source_path) for source_path in source_paths]

    def validate(
        self,
        input_path: str | None = None,
        strict: bool = False,
        corpus: str | None = None,
    ) -> ValidationResult:
        """Validate the OKF corpus under ``input_path``.

        Parses every discovered document and checks required
        metadata, document/section ID uniqueness, and local link/anchor
        resolution. Permissive mode (the default) reports every issue
        as a diagnostic without failing; strict mode fails on a fixed
        set of diagnostic codes. No Neo4j writes occur here.
        """

        documents = self.parse(input_path, corpus=corpus)
        return validate_corpus(documents, strict=strict)

    def index(
        self,
        input_path: str | None = None,
        rebuild: bool = True,
        embeddings: bool = True,
        corpus: str | None = None,
    ) -> IndexSummary:
        """Index the OKF corpus under ``input_path`` into Neo4j.

        Parses and resolves the corpus, then idempotently projects
        documents, sections, ``HAS_SECTION`` edges, and resolved
        ``LINKS_TO`` edges. When ``rebuild`` is True (the default) the
        owned index is reset first, so a full rebuild removes stale
        derived data.

        When ``embeddings`` is True (the default), every section whose
        embedding is missing or stale is (re-)embedded using the fixed
        ``SectionEmbedder`` and stored on its ``OkfSection`` node, and
        the cosine-similarity vector index is created/refreshed. Pass
        ``embeddings=False`` (``--no-embeddings`` on the CLI) to skip
        embedding generation entirely.
        """

        corpus_name = self._resolve_corpus_name(corpus)
        documents = self.parse(input_path, corpus=corpus_name)
        resolved_links = resolve_links(documents)
        all_sections = [
            section for parsed in documents for section in parsed.sections
        ]

        with self._graph_store() as store:
            if rebuild:
                store.reset(corpus_name)
            store.apply_schema()
            store.write_documents(
                [parsed.document for parsed in documents], corpus_name
            )
            store.write_sections(all_sections, corpus_name)
            store.write_links(resolved_links, corpus_name)
            store.wait_for_fulltext_index_online()
            self._wait_for_fulltext_queryable(store, all_sections, corpus_name)

            if embeddings:
                self._generate_embeddings(store, documents, corpus_name)

        return IndexSummary(
            documents=len(documents),
            sections=sum(len(parsed.sections) for parsed in documents),
            links=len(resolved_links),
        )

    @staticmethod
    def _wait_for_fulltext_queryable(
        store: Neo4jStore, sections: list[OkfSection], corpus: str
    ) -> None:
        """Probe the real full-text query path for a just-written
        section, in addition to trusting ``SHOW INDEXES`` state (see
        :meth:`Neo4jStore.wait_for_fulltext_index_queryable`).

        Best-effort: picks the first section whose heading yields a
        usable Lucene query term. If none is found (e.g. an empty
        corpus), silently relies on the ``ONLINE`` state check alone.
        """

        for section in sections:
            probe_term = "".join(
                ch if ch.isalnum() else " " for ch in section.heading
            ).split()
            if not probe_term:
                continue
            sample_query = " ".join(probe_term)
            store.wait_for_fulltext_index_queryable(
                sample_query, section.section_id, corpus
            )
            return

    def _generate_embeddings(
        self, store: Neo4jStore, documents: list[ParsedDocument], corpus: str
    ) -> None:
        """Re-embed every stale or missing section and (re-)create the
        vector index. Raises on any embedding batch failure, reporting
        the affected section IDs."""

        embedder = SectionEmbedder()

        inputs_by_section_id: dict[str, str] = {}
        titles_by_document_id = {
            parsed.document.document_id: parsed.document.title for parsed in documents
        }
        for parsed in documents:
            title = titles_by_document_id[parsed.document.document_id]
            for section in parsed.sections:
                inputs_by_section_id[section.section_id] = build_embedding_input(
                    title, section.heading_path, section.text
                )

        input_hashes = {
            section_id: compute_embedding_input_hash(text)
            for section_id, text in inputs_by_section_id.items()
        }

        stale_section_ids = store.sections_needing_embedding(
            model_name=embedder.MODEL_NAME,
            dimensions=embedder.DIMENSIONS,
            input_hashes=input_hashes,
            corpus=corpus,
        )

        sample_row: dict[str, Any] | None = None
        for batch_start in range(0, len(stale_section_ids), embedder.BATCH_SIZE):
            batch_ids = stale_section_ids[
                batch_start : batch_start + embedder.BATCH_SIZE
            ]
            batch_texts = [inputs_by_section_id[section_id] for section_id in batch_ids]
            try:
                batch_vectors = embedder.embed_sections(batch_texts)
            except Exception as exc:
                raise RuntimeError(
                    "embedding batch failed for section(s): "
                    f"{', '.join(batch_ids)}: {exc}"
                ) from exc

            rows = [
                {
                    "section_id": section_id,
                    "embedding": list(vector),
                    "embedding_model": embedder.MODEL_NAME,
                    "embedding_dimensions": embedder.DIMENSIONS,
                    "embedding_input_hash": input_hashes[section_id],
                }
                for section_id, vector in zip(batch_ids, batch_vectors)
            ]
            store.write_embeddings(rows, corpus)
            if rows:
                sample_row = rows[-1]

        store.create_vector_index(embedder.DIMENSIONS)
        final_state = store.wait_for_vector_index_online()
        if final_state != "ONLINE":
            raise RuntimeError(
                f"vector index did not reach ONLINE (state={final_state!r})"
            )

        if sample_row is not None:
            queryable = store.wait_for_vector_index_queryable(
                sample_row["embedding"], sample_row["section_id"], corpus
            )
            if not queryable:
                raise RuntimeError(
                    "vector index reported ONLINE but never became queryable "
                    f"for section {sample_row['section_id']!r}"
                )

    def verify(
        self, input_path: str | None = None, corpus: str | None = None
    ) -> VerificationResult:
        """Compare the filesystem corpus under ``input_path`` against
        the graph index and report any discrepancy.
        """

        corpus_name = self._resolve_corpus_name(corpus)
        documents = self.parse(input_path, corpus=corpus_name)
        resolved_links = resolve_links(documents)

        fs_document_ids = sorted(parsed.document.document_id for parsed in documents)
        fs_section_count = sum(len(parsed.sections) for parsed in documents)
        fs_link_count = len(resolved_links)

        with self._graph_store() as store:
            graph_documents = store.list_documents(corpus_name)
            graph_section_count = store.count_sections(corpus_name)
            graph_link_count = store.count_links(corpus_name)

        graph_document_ids = sorted(document.document_id for document in graph_documents)

        issues: list[str] = []
        if fs_document_ids != graph_document_ids:
            issues.append(
                "document IDs differ between filesystem and graph: "
                f"filesystem={fs_document_ids} graph={graph_document_ids}"
            )
        if fs_section_count != graph_section_count:
            issues.append(
                "section count differs between filesystem and graph: "
                f"filesystem={fs_section_count} graph={graph_section_count}"
            )
        if fs_link_count != graph_link_count:
            issues.append(
                "resolved link count differs between filesystem and graph: "
                f"filesystem={fs_link_count} graph={graph_link_count}"
            )

        return VerificationResult(
            ok=not issues,
            issues=tuple(issues),
            documents=len(graph_documents),
            sections=graph_section_count,
            links=graph_link_count,
        )

    def vector_search(
        self, query: str, top_k: int = 5, corpus: str | None = None
    ) -> tuple[SectionMatch, ...]:
        """Run a raw vector-similarity search over indexed sections.

        This is a narrow, read-only diagnostic exception to the fixed
        coordinator surface -- like ``verify`` -- added so embedding
        generation can be validated end-to-end before hybrid retrieval
        (rank fusion, graph expansion) is implemented in Step 6.

        ``corpus`` is resolved against the registry (falling back to
        its configured default) and used to filter results to that
        corpus.
        """

        corpus_name = self._resolve_corpus_name(corpus)
        embedder = SectionEmbedder()
        query_embedding = list(embedder.embed_query(query))
        with self._graph_store() as store:
            matches = store.vector_search(query_embedding, top_k, corpus_name)
        return tuple(matches)

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        expand: bool = False,
        corpus: str | None = None,
    ) -> RetrievalResult:
        """Run hybrid retrieval: query the Neo4j vector index and the
        Neo4j full-text index, fuse both ranked lists with weighted
        reciprocal-rank fusion, deduplicate by section, and return the
        top ``top_k`` fused hits with full provenance and per-path
        ranking diagnostics.

        When ``expand`` is True (``--mode graph-hybrid`` on the CLI),
        also traverses one hop across ``LINKS_TO`` from the seed
        documents and appends deduplicated ``expanded_hits`` selected
        by anchor, relevance, or first-section fallback, weighted by
        ``graph_expansion_weight``. Answer generation (Step 8) is not
        part of this method.

        ``corpus`` is resolved against the registry (falling back to
        its configured default) and used to filter every vector,
        full-text, and graph-expansion lookup to that corpus, so
        expansion can never surface a section from another corpus.
        """

        corpus_name = self._resolve_corpus_name(corpus)
        resolved_top_k = top_k if top_k is not None else self._settings.retrieval_top_k

        embedder = SectionEmbedder()
        query_embedding = list(embedder.embed_query(query))

        with self._graph_store() as store:
            vector_matches = list(
                store.vector_search(query_embedding, resolved_top_k, corpus_name)
            )
            lexical_matches = list(
                store.fulltext_search(query, resolved_top_k, corpus_name)
            )

            hits = fuse_rankings(
                vector_matches,
                lexical_matches,
                fusion_k=self._settings.retrieval_fusion_k,
                vector_weight=self._settings.retrieval_vector_weight,
                lexical_weight=self._settings.retrieval_lexical_weight,
            )
            seed_hits = hits[:resolved_top_k]

            expanded_hits: tuple = ()
            if expand and seed_hits:
                seed_document_ids = sorted(
                    {hit.document_id for hit in seed_hits}
                )
                edge_rows = store.expand_neighbors(
                    seed_document_ids, hops=1, corpus=corpus_name
                )
                links = [LinkedDocument(**row) for row in edge_rows]

                candidates: dict[str, tuple[SectionMatch, str]] = {}
                for link in links:
                    if link.neighbor_document_id in candidates:
                        continue

                    match = None
                    strategy = ""
                    if link.target_anchor:
                        match = store.section_by_anchor(
                            link.neighbor_document_id,
                            link.target_anchor,
                            corpus_name,
                        )
                        strategy = "anchor"
                    if match is None:
                        match = store.best_section_in_document(
                            link.neighbor_document_id,
                            query_embedding,
                            query,
                            corpus_name,
                        )
                        strategy = "relevance"
                    if match is None:
                        match = store.first_section(
                            link.neighbor_document_id, corpus_name
                        )
                        strategy = "first-section"

                    if match is not None:
                        candidates[link.neighbor_document_id] = (match, strategy)

                expanded_hits = tuple(
                    expand_hits(
                        seed_hits,
                        links,
                        candidates,
                        graph_expansion_weight=self._settings.graph_expansion_weight,
                        max_expanded=self._settings.graph_expansion_max_results,
                    )
                )

        return RetrievalResult(
            query=query, hits=tuple(seed_hits), expanded_hits=expanded_hits
        )

    def query(
        self,
        query: str,
        top_k: int | None = None,
        expand: bool = True,
        corpus: str | None = None,
    ) -> AnswerResult:
        """Generate a grounded answer for ``query``.

        Runs :meth:`retrieve` (graph-hybrid by default, so linked
        context can be cited), fetches the stored text of every seed
        and graph-expanded section, then delegates to
        :func:`oneo.answering.generate_answer`. When no chat model was
        injected at construction time, retrieval still runs and an
        explicit insufficient-evidence result is returned.

        ``corpus`` is resolved against the registry (falling back to
        its configured default) and threaded through both
        :meth:`retrieve` (so every seed and expanded hit belongs to
        that corpus) and the ``get_section_texts`` lookup below, so
        every citation resolves within the selected corpus.
        """

        corpus_name = self._resolve_corpus_name(corpus)
        retrieval = self.retrieve(query, top_k=top_k, expand=expand, corpus=corpus_name)

        section_ids = [hit.section_id for hit in retrieval.hits] + [
            hit.section_id for hit in retrieval.expanded_hits
        ]
        with self._graph_store() as store:
            section_texts = store.get_section_texts(section_ids, corpus_name)

        return generate_answer(
            query,
            retrieval,
            section_texts,
            self._chat_model,
            max_context_sections=self._settings.answer_max_context_sections,
            min_vector_score=self._settings.answer_min_vector_score,
        )

    def reset(self, corpus: str | None = None) -> None:
        """Delete only the Neo4j data owned by this index and scoped
        to the selected corpus.

        ``corpus`` is resolved against the registry (falling back to
        its configured default).
        """

        corpus_name = self._resolve_corpus_name(corpus)
        with self._graph_store() as store:
            store.reset(corpus_name)
