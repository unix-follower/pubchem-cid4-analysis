from __future__ import annotations

import json
import os
from typing import Any

import psycopg
from pgvector.psycopg import register_vector

from .documents import VectorDocument
from .embedding import HashedTokenEmbeddingProvider


def build_upsert_sql() -> str:
    return """
INSERT INTO documents (
    doc_id,
    doc_type,
    source_file,
    source_row_id,
    cid,
    sid,
    aid,
    pmid,
    doi,
    taxonomy_id,
    pathway_accession,
    title,
    text_payload,
    metadata,
    embedding
) VALUES (
    %(doc_id)s,
    %(doc_type)s,
    %(source_file)s,
    %(source_row_id)s,
    %(cid)s,
    %(sid)s,
    %(aid)s,
    %(pmid)s,
    %(doi)s,
    %(taxonomy_id)s,
    %(pathway_accession)s,
    %(title)s,
    %(text_payload)s,
    %(metadata)s::jsonb,
    %(embedding)s
)
ON CONFLICT (doc_id) DO UPDATE SET
    doc_type = EXCLUDED.doc_type,
    source_file = EXCLUDED.source_file,
    source_row_id = EXCLUDED.source_row_id,
    cid = EXCLUDED.cid,
    sid = EXCLUDED.sid,
    aid = EXCLUDED.aid,
    pmid = EXCLUDED.pmid,
    doi = EXCLUDED.doi,
    taxonomy_id = EXCLUDED.taxonomy_id,
    pathway_accession = EXCLUDED.pathway_accession,
    title = EXCLUDED.title,
    text_payload = EXCLUDED.text_payload,
    metadata = EXCLUDED.metadata,
    embedding = EXCLUDED.embedding
""".strip()


def build_similarity_query_sql(metadata_filters: dict[str, str] | None = None) -> str:
    where_clauses = ["TRUE"]
    if metadata_filters:
        for _ in metadata_filters:
            where_clauses.append("metadata ->> %s = %s")

    where_sql = " AND ".join(where_clauses)
    return f"""
SELECT
    doc_id,
    doc_type,
    title,
    source_file,
    source_row_id,
    metadata,
    1 - (embedding <=> %s) AS similarity
FROM documents
WHERE {where_sql}
ORDER BY embedding <=> %s
LIMIT %s
""".strip()


def prepare_upsert_rows(
    documents: list[VectorDocument],
    embedding_provider: HashedTokenEmbeddingProvider,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for document in documents:
        record = document.to_record()
        record["metadata"] = json.dumps(record["metadata"])
        record["embedding"] = embedding_provider.embed(document.text_payload)
        rows.append(record)
    return rows


def ingest_documents(
    documents: list[VectorDocument],
    embedding_provider: HashedTokenEmbeddingProvider,
) -> dict[str, Any]:
    DB_URL = os.environ.get("DB_URL")
    if not DB_URL:
        raise ValueError("DB_URL env variable is not set")

    rows = prepare_upsert_rows(documents, embedding_provider)
    with psycopg.connect(DB_URL, autocommit=True) as connection:
        register_vector(connection)
        with connection.cursor() as cursor:
            cursor.executemany(build_upsert_sql(), rows)

    return {
        "ingested_row_count": int(len(rows)),
    }
