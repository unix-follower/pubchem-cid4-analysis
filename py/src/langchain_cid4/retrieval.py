from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_cid4.documents import ChunkRecord
from pgvector.embedding import HashedTokenEmbeddingProvider
from pgvector.storage import PgvectorConfig, import_pgvector_stack, load_config_from_env


@dataclass(frozen=True)
class RetrievedPassage:
    source_id: str
    doc_type: str
    title: str
    content: str
    metadata: dict[str, Any]
    score: float
    backend: str


class InMemoryRetriever:
    def __init__(
        self, chunks: list[ChunkRecord], embedding_provider: HashedTokenEmbeddingProvider | None = None
    ) -> None:
        self.chunks = chunks
        self.embedding_provider = embedding_provider or HashedTokenEmbeddingProvider()
        self.chunk_embeddings = {chunk.chunk_id: self.embedding_provider.embed(chunk.content) for chunk in self.chunks}

    def retrieve(self, query: str, *, top_k: int = 4) -> list[RetrievedPassage]:
        query_embedding = self.embedding_provider.embed(query)
        scored: list[RetrievedPassage] = []
        for chunk in self.chunks:
            chunk_embedding = self.chunk_embeddings[chunk.chunk_id]
            score = sum(left * right for left, right in zip(query_embedding, chunk_embedding, strict=False))
            scored.append(
                RetrievedPassage(
                    source_id=chunk.chunk_id,
                    doc_type=chunk.doc_type,
                    title=chunk.title,
                    content=chunk.content,
                    metadata=dict(chunk.metadata),
                    score=float(score),
                    backend="in_memory",
                )
            )

        return sorted(scored, key=lambda item: (-item.score, item.title, item.source_id))[:top_k]


def retrieve_with_pgvector(
    query: str,
    *,
    doc_type: str,
    top_k: int = 4,
    config: PgvectorConfig | None = None,
    embedding_provider: HashedTokenEmbeddingProvider | None = None,
) -> dict[str, Any]:
    effective_config = load_config_from_env() if config is None else config
    effective_provider = embedding_provider or HashedTokenEmbeddingProvider(
        dimension=effective_config.embedding_dimension
    )

    if not effective_config.dsn:
        return {
            "status": "skipped",
            "reason": "PGVECTOR_DSN is not set; pgvector retrieval was not attempted.",
        }

    stack = import_pgvector_stack()
    if isinstance(stack, dict) and stack.get("status") == "skipped":
        return dict(stack)

    vector = effective_provider.embed(query)
    sql = f"""
SELECT
    doc_id,
    doc_type,
    title,
    text_payload,
    metadata,
    1 - (embedding <=> %s) AS similarity
FROM {effective_config.table_name}
WHERE doc_type = %s
ORDER BY embedding <=> %s
LIMIT %s
""".strip()

    try:
        with stack["psycopg"].connect(effective_config.dsn, autocommit=True) as connection:
            stack["register_vector"](connection)
            with connection.cursor() as cursor:
                cursor.execute(sql, (vector, doc_type, vector, top_k))
                rows = cursor.fetchall()
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "skipped",
            "reason": f"pgvector retrieval failed and should fall back to in-memory retrieval: {exc}",
        }

    passages = [
        RetrievedPassage(
            source_id=str(row[0]),
            doc_type=str(row[1]),
            title=str(row[2]),
            content=str(row[3]),
            metadata=dict(row[4] or {}),
            score=float(row[5]),
            backend="pgvector",
        )
        for row in rows
    ]
    return {
        "status": "ok",
        "hits": passages,
    }
