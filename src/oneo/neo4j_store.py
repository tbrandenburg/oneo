"""Narrow Neo4j graph-store boundary.

Isolates the Neo4j Python driver and Cypher from orchestration code.
``OkfGraphStore`` documents the exact surface the rest of the codebase
is allowed to depend on; ``Neo4jStore`` is its only implementation.

Owned nodes and relationships are scoped with an ``index_owner``
marker (``INDEX_OWNER``) so that ``reset()`` only removes data this
index created, never unrelated Neo4j data.
"""

from __future__ import annotations

import json
import time
from typing import Any, Protocol

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from oneo.models import (
    HealthStatus,
    IndexedDocument,
    OkfDocument,
    OkfLink,
    OkfSection,
    SectionMatch,
)

INDEX_OWNER = "oneo"
VECTOR_INDEX_NAME = "okf_section_embedding"
FULLTEXT_INDEX_NAME = "okf_section_fulltext"


class OkfGraphStore(Protocol):
    """The narrow persistence boundary the pipeline depends on."""

    def reset(self, corpus: str) -> None: ...
    def apply_schema(self) -> None: ...
    def write_documents(self, documents: list[OkfDocument], corpus: str) -> None: ...
    def write_sections(self, sections: list[OkfSection], corpus: str) -> None: ...
    def write_links(self, links: list[OkfLink], corpus: str) -> None: ...
    def list_documents(self, corpus: str) -> list[IndexedDocument]: ...
    def sections_needing_embedding(
        self,
        model_name: str,
        dimensions: int,
        input_hashes: dict[str, str],
        corpus: str,
    ) -> list[str]: ...
    def write_embeddings(self, rows: list[dict[str, Any]], corpus: str) -> None: ...
    def create_vector_index(self, dimensions: int) -> None: ...
    def vector_index_state(self) -> str | None: ...
    def wait_for_vector_index_online(
        self, timeout_seconds: float, poll_interval_seconds: float
    ) -> str | None: ...
    def vector_search(
        self, embedding: list[float], top_k: int, corpus: str
    ) -> Any: ...
    def wait_for_vector_index_queryable(
        self,
        sample_embedding: list[float],
        sample_section_id: str,
        corpus: str,
        timeout_seconds: float,
        poll_interval_seconds: float,
    ) -> bool: ...
    def fulltext_search(self, query: str, top_k: int, corpus: str) -> Any: ...
    def wait_for_fulltext_index_online(
        self, timeout_seconds: float, poll_interval_seconds: float
    ) -> str | None: ...
    def wait_for_fulltext_index_queryable(
        self,
        sample_query: str,
        sample_section_id: str,
        corpus: str,
        timeout_seconds: float,
        poll_interval_seconds: float,
    ) -> bool: ...
    def expand_neighbors(
        self, document_ids: list[str], hops: int, corpus: str
    ) -> Any: ...
    def section_by_anchor(
        self, document_id: str, anchor: str, corpus: str
    ) -> SectionMatch | None: ...
    def first_section(self, document_id: str, corpus: str) -> SectionMatch | None: ...
    def best_section_in_document(
        self, document_id: str, embedding: list[float], query_text: str, corpus: str
    ) -> SectionMatch | None: ...
    def get_section_texts(
        self, section_ids: list[str], corpus: str
    ) -> dict[str, str]: ...


class Neo4jStore:
    """Thin wrapper around the Neo4j driver for connectivity checks and
    OKF graph projection."""

    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: str,
    ) -> None:
        self._database = database
        self._driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self) -> None:
        """Release the underlying driver's connection pool."""

        self._driver.close()

    def __enter__(self) -> "Neo4jStore":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _run(self, query: str, **parameters: object) -> Any:
        records, _, _ = self._driver.execute_query(
            query, parameters_=parameters, database_=self._database
        )
        return records

    def _run_scoped(self, query: str, corpus: str, **parameters: object) -> Any:
        """Run a corpus-scoped Cypher statement, binding ``$corpus``.

        This is the single seam every corpus-scoped read, write, or
        delete must go through. It requires a non-empty ``corpus`` and
        raises before issuing any query when it is missing or blank --
        turning "a corpus filter was forgotten on this query" from a
        possible silent full-graph operation into a hard, immediate
        error, most critically on the destructive :meth:`reset` path.
        Every corpus-scoped query text still names its own ``corpus``
        match/filter explicitly (Cypher patterns differ too much
        between ``MERGE`` property maps and ``WHERE`` clauses to
        generate generically), but none of them may be issued without
        going through this validating seam.
        """

        if not corpus:
            raise ValueError(
                "corpus is required for a corpus-scoped Neo4j operation"
            )
        return self._run(query, corpus=corpus, **parameters)

    def health(self) -> HealthStatus:
        """Run a real Neo4j query to verify connectivity.

        Returns:
            A :class:`~oneo.models.HealthStatus` describing whether the
            connection and query succeeded.
        """

        try:
            records, summary, _ = self._driver.execute_query(
                "RETURN 1 AS ok",
                database_=self._database,
            )
            if not records or records[0]["ok"] != 1:
                return HealthStatus(
                    connected=False,
                    database=self._database,
                    detail="unexpected health-check result",
                )
            server_agent = summary.server.agent
            return HealthStatus(
                connected=True,
                database=self._database,
                server_agent=server_agent,
            )
        except (ServiceUnavailable, Neo4jError) as exc:
            return HealthStatus(
                connected=False,
                database=self._database,
                detail=str(exc),
            )

    def reset(self, corpus: str) -> None:
        """Delete only the nodes (and their relationships) owned by this
        index for ``corpus``. Unrelated Neo4j data, and other
        corpuses' owned data, is never touched."""

        self._run_scoped(
            "MATCH (n) WHERE n.index_owner = $owner AND n.corpus = $corpus "
            "DETACH DELETE n",
            corpus=corpus,
            owner=INDEX_OWNER,
        )

    def apply_schema(self) -> None:
        """Apply uniqueness constraints and supporting indexes for the
        OKF graph model. Idempotent; safe to call on every index run."""

        statements = (
            # Composite uniqueness constraints scoped by corpus, replacing
            # the single-corpus, single-property constraints. Explicit
            # `DROP ... IF EXISTS` first so a pre-v2 Neo4j database (or a
            # persistent test/dev instance) that still carries the old
            # single-property constraint under the same conceptual
            # purpose does not silently block these composite constraints
            # under a new name.
            "DROP CONSTRAINT okf_document_id_unique IF EXISTS",
            "DROP CONSTRAINT okf_section_id_unique IF EXISTS",
            "CREATE CONSTRAINT okf_document_corpus_id_unique IF NOT EXISTS "
            "FOR (d:OkfDocument) REQUIRE (d.corpus, d.document_id) IS UNIQUE",
            "CREATE CONSTRAINT okf_section_corpus_id_unique IF NOT EXISTS "
            "FOR (s:OkfSection) REQUIRE (s.corpus, s.section_id) IS UNIQUE",
            "CREATE INDEX okf_document_index_owner IF NOT EXISTS "
            "FOR (d:OkfDocument) ON (d.index_owner)",
            "CREATE INDEX okf_section_index_owner IF NOT EXISTS "
            "FOR (s:OkfSection) ON (s.index_owner)",
            "CREATE INDEX okf_section_document_id IF NOT EXISTS "
            "FOR (s:OkfSection) ON (s.document_id)",
            # Supporting index on the corpus dimension itself, used by
            # every corpus-scoped read that filters `OkfSection` by
            # `corpus` outside of the composite uniqueness constraint
            # (which only backs `document_id`/`section_id` lookups).
            "CREATE INDEX okf_section_corpus IF NOT EXISTS "
            "FOR (s:OkfSection) ON (s.corpus)",
            # Registers the `target_anchor` property key token even when no
            # LINKS_TO relationship currently has it set (e.g. a corpus
            # whose only links have no #anchor fragment). Without this,
            # Neo4j never creates the property key and every later read of
            # `r.target_anchor` emits a "property key does not exist"
            # driver warning.
            "CREATE INDEX okf_links_to_target_anchor IF NOT EXISTS "
            "FOR ()-[r:LINKS_TO]-() ON (r.target_anchor)",
            # Registers the embedding property key tokens even before any
            # embedding has ever been written. `sections_needing_embedding`
            # reads `s.embedding`, `s.embedding_model`,
            # `s.embedding_dimensions`, and `s.embedding_input_hash` on the
            # very first `oneo index` run after `oneo reset`, before
            # `create_vector_index` has run; without these, each of those
            # reads emits a "property key does not exist" driver warning.
            # `s.embedding` itself is intentionally NOT range-indexed here
            # under the name `okf_section_embedding`: that name is reserved
            # for the VECTOR index created in `create_vector_index`, and a
            # `CREATE INDEX ... IF NOT EXISTS` sharing that name would
            # silently no-op once the range index exists, permanently
            # preventing the real vector index from ever being created.
            # The `embedding` property key token is instead registered
            # unconditionally via the range index below under a distinct
            # name.
            "CREATE INDEX okf_section_embedding_present IF NOT EXISTS "
            "FOR (s:OkfSection) ON (s.embedding)",
            "CREATE INDEX okf_section_embedding_model IF NOT EXISTS "
            "FOR (s:OkfSection) ON (s.embedding_model)",
            "CREATE INDEX okf_section_embedding_dimensions IF NOT EXISTS "
            "FOR (s:OkfSection) ON (s.embedding_dimensions)",
            "CREATE INDEX okf_section_embedding_input_hash IF NOT EXISTS "
            "FOR (s:OkfSection) ON (s.embedding_input_hash)",
        )
        for statement in statements:
            self._run(statement)
        self._run(
            f"""
            CREATE FULLTEXT INDEX {FULLTEXT_INDEX_NAME} IF NOT EXISTS
            FOR (s:OkfSection) ON EACH [s.heading, s.text]
            """
        )

    def write_documents(self, documents: list[OkfDocument], corpus: str) -> None:
        """Idempotently write ``OkfDocument`` nodes, keyed by
        ``(corpus, document_id)``. Metadata is serialized to JSON, since
        Neo4j node properties cannot hold nested maps."""

        rows = [
            {
                "document_id": document.document_id,
                "title": document.title,
                "source_path": document.source_path,
                "metadata": json.dumps(dict(document.metadata), sort_keys=True),
                "content_hash": document.content_hash,
            }
            for document in documents
        ]
        self._run_scoped(
            """
            UNWIND $rows AS row
            MERGE (d:OkfDocument {corpus: $corpus, document_id: row.document_id})
            SET d.title = row.title,
                d.source_path = row.source_path,
                d.metadata = row.metadata,
                d.content_hash = row.content_hash,
                d.index_owner = $owner
            """,
            corpus=corpus,
            rows=rows,
            owner=INDEX_OWNER,
        )

    def write_sections(self, sections: list[OkfSection], corpus: str) -> None:
        """Idempotently write ``OkfSection`` nodes, keyed by
        ``(corpus, section_id)``, and their ``HAS_SECTION`` edge from
        the owning document."""

        rows = [
            {
                "section_id": section.section_id,
                "document_id": section.document_id,
                "heading": section.heading,
                "heading_path": list(section.heading_path),
                "ordinal": section.ordinal,
                "anchor": section.anchor,
                "text": section.text,
                "content_hash": section.content_hash,
                "source_path": section.source_path,
            }
            for section in sections
        ]
        self._run_scoped(
            """
            UNWIND $rows AS row
            MATCH (d:OkfDocument {corpus: $corpus, document_id: row.document_id})
            MERGE (s:OkfSection {corpus: $corpus, section_id: row.section_id})
            SET s.document_id = row.document_id,
                s.heading = row.heading,
                s.heading_path = row.heading_path,
                s.ordinal = row.ordinal,
                s.anchor = row.anchor,
                s.text = row.text,
                s.content_hash = row.content_hash,
                s.source_path = row.source_path,
                s.index_owner = $owner
            MERGE (d)-[r:HAS_SECTION]->(s)
            SET r.corpus = $corpus
            """,
            corpus=corpus,
            rows=rows,
            owner=INDEX_OWNER,
        )

    def sections_needing_embedding(
        self,
        model_name: str,
        dimensions: int,
        input_hashes: dict[str, str],
        corpus: str,
    ) -> list[str]:
        """Return the IDs of ``corpus``'s owned sections that must be
        (re-)embedded.

        A section is re-embedded when its embedding is missing, its
        stored model name or dimensions differ from the current fixed
        model, or its stored embedding input hash differs from
        ``input_hashes[section_id]``.
        """

        records = self._run_scoped(
            """
            MATCH (s:OkfSection {index_owner: $owner, corpus: $corpus})
            RETURN s.section_id AS section_id,
                   s.embedding IS NULL AS missing_embedding,
                   s.embedding_model AS embedding_model,
                   s.embedding_dimensions AS embedding_dimensions,
                   s.embedding_input_hash AS embedding_input_hash
            """,
            corpus=corpus,
            owner=INDEX_OWNER,
        )
        stale: list[str] = []
        for record in records:
            section_id = record["section_id"]
            current_hash = input_hashes.get(section_id)
            if current_hash is None:
                continue
            if (
                record["missing_embedding"]
                or record["embedding_model"] != model_name
                or record["embedding_dimensions"] != dimensions
                or record["embedding_input_hash"] != current_hash
            ):
                stale.append(section_id)
        return stale

    def write_embeddings(self, rows: list[dict[str, Any]], corpus: str) -> None:
        """Store the embedding vector and embedding metadata for each
        given section of ``corpus``. Each row must contain
        ``section_id``, ``embedding``, ``embedding_model``,
        ``embedding_dimensions``, and ``embedding_input_hash``."""

        self._run_scoped(
            """
            UNWIND $rows AS row
            MATCH (s:OkfSection {corpus: $corpus, section_id: row.section_id})
            SET s.embedding = row.embedding,
                s.embedding_model = row.embedding_model,
                s.embedding_dimensions = row.embedding_dimensions,
                s.embedding_input_hash = row.embedding_input_hash
            """,
            corpus=corpus,
            rows=rows,
        )

    def create_vector_index(self, dimensions: int) -> None:
        """Idempotently create the cosine-similarity vector index over
        ``OkfSection.embedding``."""

        self._run(
            f"""
            CREATE VECTOR INDEX {VECTOR_INDEX_NAME} IF NOT EXISTS
            FOR (s:OkfSection) ON (s.embedding)
            OPTIONS {{ indexConfig: {{
                `vector.dimensions`: $dimensions,
                `vector.similarity_function`: 'cosine'
            }} }}
            """,
            dimensions=dimensions,
        )

    def vector_index_state(self) -> str | None:
        """Return the current state (e.g. ``ONLINE``, ``POPULATING``)
        of the section embedding vector index, or ``None`` if it does
        not exist."""

        records = self._run(
            "SHOW VECTOR INDEXES YIELD name, state WHERE name = $name RETURN state",
            name=VECTOR_INDEX_NAME,
        )
        if not records:
            return None
        return str(records[0]["state"])

    def wait_for_vector_index_online(
        self, timeout_seconds: float = 30.0, poll_interval_seconds: float = 0.2
    ) -> str | None:
        """Poll the vector index state until it reports ``ONLINE`` or
        ``timeout_seconds`` elapses, returning the final observed
        state."""

        deadline = time.monotonic() + timeout_seconds
        state = self.vector_index_state()
        while state != "ONLINE" and time.monotonic() < deadline:
            time.sleep(poll_interval_seconds)
            state = self.vector_index_state()
        return state

    def wait_for_vector_index_queryable(
        self,
        sample_embedding: list[float],
        sample_section_id: str,
        corpus: str,
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 0.2,
    ) -> bool:
        """Poll a real ``db.index.vector.queryNodes`` call for a known,
        just-written embedding until it actually returns that section,
        or ``timeout_seconds`` elapses.

        ``SHOW VECTOR INDEXES YIELD state`` reporting ``ONLINE`` does
        not guarantee the index is immediately queryable -- there can
        be a further short lag before a just-written vector is served
        by ``db.index.vector.queryNodes``. This probes the real query
        path with a known section instead of trusting index state
        alone, closing that race at its root.

        Uses ``top_k=10`` rather than ``top_k=1``: under repeated
        reset/rebuild churn (e.g. a full test suite run), a just-
        deleted node's vector can briefly remain visible to the ANN
        index alongside the fresh write, and an identical-scoring
        stale entry can occupy rank 1 ahead of the sample section. A
        wider ``top_k`` tolerates that transient tie without weakening
        the check -- it still requires the exact known section ID to
        appear among real query results before declaring the index
        queryable."""

        deadline = time.monotonic() + timeout_seconds
        while True:
            matches = self.vector_search(sample_embedding, top_k=10, corpus=corpus)
            if any(match.section_id == sample_section_id for match in matches):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(poll_interval_seconds)

    def write_links(self, links: list[OkfLink], corpus: str) -> None:
        """Idempotently write resolved ``LINKS_TO`` edges between
        documents of ``corpus``. ``links`` must already have
        ``target_document_id`` resolved (see
        :func:`oneo.validation.resolve_links`); links without a
        resolved target are silently skipped."""

        rows = [
            {
                "source_document_id": link.source_document_id,
                "target_document_id": link.target_document_id,
                "source_section_id": link.source_section_id,
                "raw_target": link.raw_target,
                "target_anchor": link.target_anchor,
            }
            for link in links
            if link.target_document_id is not None
        ]
        self._run_scoped(
            """
            UNWIND $rows AS row
            MATCH (src:OkfDocument {corpus: $corpus, document_id: row.source_document_id})
            MATCH (tgt:OkfDocument {corpus: $corpus, document_id: row.target_document_id})
            MERGE (src)-[r:LINKS_TO {
                corpus: $corpus,
                source_section_id: row.source_section_id,
                raw_target: row.raw_target
            }]->(tgt)
            SET r.index_owner = $owner
            FOREACH (_ IN CASE WHEN row.target_anchor IS NOT NULL THEN [1] ELSE [] END |
                SET r.target_anchor = row.target_anchor
            )
            """,
            corpus=corpus,
            rows=rows,
            owner=INDEX_OWNER,
        )

    def list_documents(self, corpus: str) -> list[IndexedDocument]:
        """Return every document node owned by this index in
        ``corpus``, sorted by ``document_id``."""

        records = self._run_scoped(
            """
            MATCH (d:OkfDocument {index_owner: $owner, corpus: $corpus})
            RETURN d.document_id AS document_id,
                   d.title AS title,
                   d.source_path AS source_path,
                   d.content_hash AS content_hash
            ORDER BY d.document_id
            """,
            corpus=corpus,
            owner=INDEX_OWNER,
        )
        return [
            IndexedDocument(
                document_id=record["document_id"],
                title=record["title"],
                source_path=record["source_path"],
                content_hash=record["content_hash"],
            )
            for record in records
        ]

    def count_sections(self, corpus: str) -> int:
        """Return the number of section nodes owned by this index in
        ``corpus``."""

        records = self._run_scoped(
            "MATCH (s:OkfSection {index_owner: $owner, corpus: $corpus}) "
            "RETURN count(s) AS n",
            corpus=corpus,
            owner=INDEX_OWNER,
        )
        return int(records[0]["n"])

    def count_links(self, corpus: str) -> int:
        """Return the number of ``LINKS_TO`` edges owned by this index
        in ``corpus``."""

        records = self._run_scoped(
            """
            MATCH (:OkfDocument)-[r:LINKS_TO {index_owner: $owner, corpus: $corpus}]->(:OkfDocument)
            RETURN count(r) AS n
            """,
            corpus=corpus,
            owner=INDEX_OWNER,
        )
        return int(records[0]["n"])

    def export_graph(self, corpus: str) -> dict[str, Any]:
        """Return a deterministic, JSON-serializable snapshot of
        ``corpus``'s owned graph, suitable for comparing two
        independent rebuilds of that corpus."""

        document_records = self._run_scoped(
            """
            MATCH (d:OkfDocument {index_owner: $owner, corpus: $corpus})
            RETURN d.document_id AS document_id, d.title AS title,
                   d.source_path AS source_path, d.content_hash AS content_hash
            ORDER BY d.document_id
            """,
            corpus=corpus,
            owner=INDEX_OWNER,
        )
        section_records = self._run_scoped(
            """
            MATCH (s:OkfSection {index_owner: $owner, corpus: $corpus})
            RETURN s.section_id AS section_id, s.document_id AS document_id,
                   s.heading AS heading, s.ordinal AS ordinal,
                   s.anchor AS anchor, s.content_hash AS content_hash
            ORDER BY s.section_id
            """,
            corpus=corpus,
            owner=INDEX_OWNER,
        )
        link_records = self._run_scoped(
            """
            MATCH (a:OkfDocument)-[r:LINKS_TO {index_owner: $owner, corpus: $corpus}]->(b:OkfDocument)
            RETURN a.document_id AS source_document_id,
                   b.document_id AS target_document_id,
                   r.source_section_id AS source_section_id,
                   r.raw_target AS raw_target,
                   coalesce(r.target_anchor, null) AS target_anchor
            ORDER BY source_document_id, raw_target, source_section_id
            """,
            corpus=corpus,
            owner=INDEX_OWNER,
        )
        return {
            "documents": [dict(record) for record in document_records],
            "sections": [dict(record) for record in section_records],
            "links": [dict(record) for record in link_records],
        }

    def vector_search(
        self, embedding: list[float], top_k: int, corpus: str
    ) -> list[SectionMatch]:
        """Vector similarity search over owned ``OkfSection`` nodes of
        ``corpus`` using the cosine-similarity vector index.

        Returns an empty result set (rather than raising) when the
        vector index has not been created yet: a missing index means
        no vector matches can exist, which is indistinguishable in
        practice from a real empty result set for every caller.
        This keeps callers such as :meth:`best_section_in_document`
        (used by graph expansion before any embeddings may exist)
        and :meth:`wait_for_vector_index_queryable` (polled
        immediately after ``create_vector_index``, before the index
        is guaranteed to exist as a queryable object) robust to that
        ordering without masking genuine query errors.
        """

        try:
            records = self._run(
                f"""
                CALL db.index.vector.queryNodes('{VECTOR_INDEX_NAME}', $top_k, $embedding)
                YIELD node, score
                WHERE node.index_owner = $owner AND node.corpus = $corpus
                RETURN node.section_id AS section_id,
                       node.document_id AS document_id,
                       node.heading AS heading,
                       node.source_path AS source_path,
                       score AS score
                """,
                embedding=embedding,
                top_k=top_k,
                owner=INDEX_OWNER,
                corpus=corpus,
            )
        except Neo4jError as exc:
            if "no such vector schema index" in str(exc).lower():
                return []
            raise
        return [
            SectionMatch(
                section_id=record["section_id"],
                document_id=record["document_id"],
                heading=record["heading"],
                score=float(record["score"]),
                source_path=record["source_path"],
            )
            for record in records
        ]

    def fulltext_index_state(self) -> str | None:
        """Return the current state (e.g. ``ONLINE``, ``POPULATING``)
        of the section full-text index, or ``None`` if it does not
        exist."""

        records = self._run(
            "SHOW INDEXES YIELD name, state WHERE name = $name RETURN state",
            name=FULLTEXT_INDEX_NAME,
        )
        if not records:
            return None
        return str(records[0]["state"])

    def wait_for_fulltext_index_online(
        self, timeout_seconds: float = 30.0, poll_interval_seconds: float = 0.2
    ) -> str | None:
        """Poll the full-text index state until it reports ``ONLINE``
        or ``timeout_seconds`` elapses, returning the final observed
        state."""

        deadline = time.monotonic() + timeout_seconds
        state = self.fulltext_index_state()
        while state != "ONLINE" and time.monotonic() < deadline:
            time.sleep(poll_interval_seconds)
            state = self.fulltext_index_state()
        return state

    def wait_for_fulltext_index_queryable(
        self,
        sample_query: str,
        sample_section_id: str,
        corpus: str,
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 0.2,
    ) -> bool:
        """Poll a real ``db.index.fulltext.queryNodes`` call for a
        known, just-written section until it actually returns that
        section, or ``timeout_seconds`` elapses.

        Mirrors :meth:`wait_for_vector_index_queryable`: ``SHOW
        INDEXES YIELD state`` reporting ``ONLINE`` does not guarantee
        the full-text index is immediately queryable for a just-
        written section."""

        deadline = time.monotonic() + timeout_seconds
        while True:
            matches = self.fulltext_search(sample_query, top_k=5, corpus=corpus)
            if any(match.section_id == sample_section_id for match in matches):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(poll_interval_seconds)

    def fulltext_search(self, query: str, top_k: int, corpus: str) -> list[SectionMatch]:
        """Full-text search over owned ``OkfSection`` nodes of
        ``corpus`` using the Neo4j full-text index on ``heading`` and
        ``text``."""

        records = self._run(
            f"""
            CALL db.index.fulltext.queryNodes('{FULLTEXT_INDEX_NAME}', $search_text, {{limit: $top_k}})
            YIELD node, score
            WHERE node.index_owner = $owner AND node.corpus = $corpus
            RETURN node.section_id AS section_id,
                   node.document_id AS document_id,
                   node.heading AS heading,
                   node.source_path AS source_path,
                   score AS score
            """,
            search_text=query,
            top_k=top_k,
            owner=INDEX_OWNER,
            corpus=corpus,
        )
        return [
            SectionMatch(
                section_id=record["section_id"],
                document_id=record["document_id"],
                heading=record["heading"],
                score=float(record["score"]),
                source_path=record["source_path"],
            )
            for record in records
        ]

    def expand_neighbors(
        self, document_ids: list[str], hops: int, corpus: str
    ) -> list[dict[str, Any]]:
        """Return every one-hop ``LINKS_TO`` edge connecting any of the
        owned ``document_ids`` (within ``corpus``) to a neighboring
        owned document, in the same corpus, that is not itself among
        ``document_ids``.

        Only one-hop expansion is supported; additional traversal
        depth is outside the initial scope (see Step 7 of the plan).
        Each returned row has ``seed_document_id``, ``direction``
        (``"outgoing"`` or ``"incoming"``), ``neighbor_document_id``,
        ``source_section_id``, ``raw_target``, and ``target_anchor``.
        The corpus filter on both the seed and neighbor documents
        guarantees expansion never crosses a corpus boundary.
        """

        if hops != 1:
            raise ValueError("only one-hop graph expansion is supported")

        records = self._run(
            """
            MATCH (seed:OkfDocument {index_owner: $owner, corpus: $corpus})
            WHERE seed.document_id IN $document_ids
            OPTIONAL MATCH (seed)-[out:LINKS_TO {corpus: $corpus}]->(outNeighbor:OkfDocument {corpus: $corpus})
            WHERE NOT outNeighbor.document_id IN $document_ids
            WITH seed, collect(DISTINCT {
                direction: 'outgoing', neighbor: outNeighbor.document_id,
                source_section_id: out.source_section_id,
                raw_target: out.raw_target,
                target_anchor: coalesce(out.target_anchor, null)
            }) AS outgoing_edges
            OPTIONAL MATCH (inNeighbor:OkfDocument {corpus: $corpus})-[incoming:LINKS_TO {corpus: $corpus}]->(seed)
            WHERE NOT inNeighbor.document_id IN $document_ids
            WITH seed, outgoing_edges, collect(DISTINCT {
                direction: 'incoming', neighbor: inNeighbor.document_id,
                source_section_id: incoming.source_section_id,
                raw_target: incoming.raw_target,
                target_anchor: coalesce(incoming.target_anchor, null)
            }) AS incoming_edges
            UNWIND (outgoing_edges + incoming_edges) AS edge
            WITH seed, edge
            WHERE edge.neighbor IS NOT NULL
            RETURN seed.document_id AS seed_document_id,
                   edge.direction AS direction,
                   edge.neighbor AS neighbor_document_id,
                   edge.source_section_id AS source_section_id,
                   edge.raw_target AS raw_target,
                   edge.target_anchor AS target_anchor
            """,
            owner=INDEX_OWNER,
            corpus=corpus,
            document_ids=document_ids,
        )
        return [dict(record) for record in records]

    def section_by_anchor(
        self, document_id: str, anchor: str, corpus: str
    ) -> SectionMatch | None:
        """Return the owned section of ``corpus`` matching ``anchor``
        within ``document_id``, or ``None`` if no section carries that
        anchor."""

        records = self._run(
            """
            MATCH (s:OkfSection {
                index_owner: $owner, corpus: $corpus,
                document_id: $document_id, anchor: $anchor
            })
            RETURN s.section_id AS section_id, s.document_id AS document_id,
                   s.heading AS heading, s.source_path AS source_path
            LIMIT 1
            """,
            owner=INDEX_OWNER,
            corpus=corpus,
            document_id=document_id,
            anchor=anchor,
        )
        if not records:
            return None
        record = records[0]
        return SectionMatch(
            section_id=record["section_id"],
            document_id=record["document_id"],
            heading=record["heading"],
            score=1.0,
            source_path=record["source_path"],
        )

    def first_section(self, document_id: str, corpus: str) -> SectionMatch | None:
        """Return the first owned section (lowest ``ordinal``) of
        ``corpus`` within ``document_id``, the deterministic fallback
        used when no anchor or relevant section is found."""

        records = self._run(
            """
            MATCH (s:OkfSection {index_owner: $owner, corpus: $corpus, document_id: $document_id})
            RETURN s.section_id AS section_id, s.document_id AS document_id,
                   s.heading AS heading, s.source_path AS source_path
            ORDER BY s.ordinal ASC
            LIMIT 1
            """,
            owner=INDEX_OWNER,
            corpus=corpus,
            document_id=document_id,
        )
        if not records:
            return None
        record = records[0]
        return SectionMatch(
            section_id=record["section_id"],
            document_id=record["document_id"],
            heading=record["heading"],
            score=1.0,
            source_path=record["source_path"],
        )

    def best_section_in_document(
        self, document_id: str, embedding: list[float], query_text: str, corpus: str
    ) -> SectionMatch | None:
        """Return the highest lexical- or vector-relevance owned
        section within ``document_id`` (in ``corpus``) for the given
        query, or ``None`` if neither search path returns a match in
        that document.

        Reuses the existing vector and full-text search paths,
        filtering their results to ``document_id`` in Python, rather
        than issuing a document-scoped Cypher query.
        """

        for match in self.fulltext_search(query_text, top_k=20, corpus=corpus):
            if match.document_id == document_id:
                return match
        for match in self.vector_search(embedding, top_k=20, corpus=corpus):
            if match.document_id == document_id:
                return match
        return None

    def get_section_texts(self, section_ids: list[str], corpus: str) -> dict[str, str]:
        """Return the stored ``text`` for each owned section of
        ``corpus`` in ``section_ids``, keyed by ``section_id``.

        Used exclusively to build grounded answer-generation context;
        missing IDs are simply absent from the returned mapping.
        """

        if not section_ids:
            return {}

        records = self._run_scoped(
            """
            MATCH (s:OkfSection {index_owner: $owner, corpus: $corpus})
            WHERE s.section_id IN $section_ids
            RETURN s.section_id AS section_id, s.text AS text
            """,
            corpus=corpus,
            owner=INDEX_OWNER,
            section_ids=section_ids,
        )
        return {record["section_id"]: record["text"] for record in records}

