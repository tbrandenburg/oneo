"""Runtime configuration for Oneo.

Configuration values are read from environment variables (optionally via a
``.env`` file). No pipeline behavior or graph construction is configurable
beyond the values listed here.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Oneo pipeline.

    Attributes:
        corpus_config: Path to the required ``corpuses.toml`` file that
            maps named OKF corpuses to their filesystem roots. There is
            no implicit global root; at least one corpus must be
            configured.
        default_corpus: Optional name of the corpus to use when a
            corpus-scoped command omits an explicit corpus selection.
        neo4j_uri: Bolt URI of the Neo4j instance.
        neo4j_username: Neo4j authentication username.
        neo4j_password: Neo4j authentication password.
        neo4j_database: Name of the Neo4j database to use.
        exclude_patterns: Glob patterns excluded from file discovery.
        retrieval_top_k: Default number of fused hits returned by
            ``retrieve``.
        retrieval_fusion_k: The ``k`` constant in the reciprocal-rank
            fusion formula ``1 / (k + rank)``.
        retrieval_vector_weight: Weight applied to the vector-search
            reciprocal-rank contribution during fusion.
        retrieval_lexical_weight: Weight applied to the full-text
            reciprocal-rank contribution during fusion.
        graph_expansion_weight: Weight applied to one-hop
            graph-expanded sections, scaled by selection-strategy
            confidence, when ``retrieve`` is called with
            ``expand=True``.
        graph_expansion_max_results: Maximum number of graph-expanded
            sections returned per ``retrieve`` call.
        answer_max_context_sections: Maximum number of retrieved
            sections included in the chat-model prompt for ``query``.
        answer_min_vector_score: Minimum vector-search cosine
            similarity a seed hit without a lexical match must reach
            to count as relevant evidence for answer generation.
    """

    model_config = SettingsConfigDict(
        env_prefix="ONEO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    corpus_config: str = "corpuses.toml"
    default_corpus: str | None = None
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "password"
    neo4j_database: str = "neo4j"
    exclude_patterns: tuple[str, ...] = (".git", "node_modules")
    retrieval_top_k: int = 5
    retrieval_fusion_k: int = 60
    retrieval_vector_weight: float = 1.0
    retrieval_lexical_weight: float = 1.0
    graph_expansion_weight: float = 0.5
    graph_expansion_max_results: int = 5
    answer_max_context_sections: int = 8
    answer_min_vector_score: float = 0.55


def load_settings() -> Settings:
    """Load runtime configuration from the environment."""

    return Settings()
