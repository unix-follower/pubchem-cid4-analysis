from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from pgvector import Vector
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, AsyncSessionTransaction

from src.embedding import HashedTokenEmbeddingProvider


@dataclass(frozen=True)
class RetrievedPassage:
    source_id: str
    doc_type: str
    title: str
    content: str
    metadata: dict[str, Any]
    score: float


async def retrieve_with_pgvector(
    query: str,
    *,
    doc_type: str,
    top_k: int = 4,
    embedding_provider: HashedTokenEmbeddingProvider | None = None,
    engine: AsyncEngine = None,
) -> dict[str, Any]:
    effective_provider = embedding_provider or HashedTokenEmbeddingProvider(
        dimension=96
    )
    vector = effective_provider.embed(query)
    sql = """
SELECT
    doc_id,
    doc_type,
    title,
    text_payload,
    metadata,
    1 - (embedding <=> :query_vector) AS similarity
FROM documents
WHERE doc_type = :doc_type
ORDER BY embedding <=> :query_vector
LIMIT :top_k
""".strip()

    async with (
        engine.connect() as connection,
        AsyncSession(connection).begin() as session_tx,
    ):
        session_tx: AsyncSessionTransaction

        cursor = await session_tx.session.execute(
            text(sql),
            {"query_vector": Vector(vector), "doc_type": doc_type, "top_k": top_k},
        )
        rows = cursor.fetchall()

    passages = [
        RetrievedPassage(
            source_id=str(row[0]),
            doc_type=str(row[1]),
            title=str(row[2]),
            content=str(row[3]),
            metadata=dict(row[4] or {}),
            score=float(row[5]),
        )
        for row in rows
    ]
    return passages
