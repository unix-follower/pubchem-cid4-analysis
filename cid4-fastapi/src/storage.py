from __future__ import annotations

import importlib
import json
import os
from dataclasses import dataclass
from typing import Any

from documents import VectorDocument
from embedding import HashedTokenEmbeddingProvider

DEFAULT_TABLE_NAME = "cid4_documents"


@dataclass(frozen=True)
class PgvectorConfig:
    dsn: str | None
    table_name: str = DEFAULT_TABLE_NAME
    embedding_dimension: int = 96


def load_config_from_env() -> PgvectorConfig:
    return PgvectorConfig(
        dsn=os.environ.get("PGVECTOR_DSN"),
        table_name=os.environ.get("PGVECTOR_TABLE", DEFAULT_TABLE_NAME),
        embedding_dimension=int(os.environ.get("PGVECTOR_EMBED_DIM", "96")),
    )


def import_pgvector_stack() -> dict[str, Any] | Any:
    try:
        psycopg = importlib.import_module("psycopg")
        pgvector_psycopg = importlib.import_module("pgvector.psycopg")
        return {
            "psycopg": psycopg,
            "register_vector": pgvector_psycopg.register_vector,
        }
    except (ImportError, ModuleNotFoundError) as exc:
        return {
            "status": "skipped",
            "reason": f"pgvector dependencies are not installed in the current environment: {exc}",
        }


def build_upsert_sql(table_name: str) -> str:
    return f"""
INSERT INTO {table_name} (
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


def build_similarity_query_sql(
    table_name: str, metadata_filters: dict[str, str] | None = None
) -> str:
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
FROM {table_name}
WHERE {where_sql}
ORDER BY embedding <=> %s
LIMIT %s
""".strip()


def ensure_schema(connection: Any, config: PgvectorConfig) -> None:
    create_extension_sql = "CREATE EXTENSION IF NOT EXISTS vector"
    create_table_sql = f"""
CREATE TABLE IF NOT EXISTS {config.table_name} (
    doc_id TEXT PRIMARY KEY,
    doc_type TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_row_id TEXT NOT NULL,
    cid BIGINT,
    sid BIGINT,
    aid BIGINT,
    pmid TEXT,
    doi TEXT,
    taxonomy_id BIGINT,
    pathway_accession TEXT,
    title TEXT NOT NULL,
    text_payload TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    embedding vector({config.embedding_dimension}) NOT NULL
)
""".strip()
    create_doc_type_index_sql = f"CREATE INDEX IF NOT EXISTS idx_{config.table_name}_doc_type ON {config.table_name} (doc_type)"
    create_taxonomy_index_sql = f"CREATE INDEX IF NOT EXISTS idx_{config.table_name}_taxonomy_id ON {config.table_name} (taxonomy_id)"

    with connection.cursor() as cursor:
        cursor.execute(create_extension_sql)
        cursor.execute(create_table_sql)
        cursor.execute(create_doc_type_index_sql)
        cursor.execute(create_taxonomy_index_sql)


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
    config: PgvectorConfig,
    embedding_provider: HashedTokenEmbeddingProvider,
) -> dict[str, Any]:
    if not documents:
        return {
            "status": "skipped",
            "reason": "No documents were generated for pgvector ingestion.",
        }

    if not config.dsn:
        return {
            "status": "dry_run",
            "reason": "PGVECTOR_DSN is not set; documents were prepared but not written to PostgreSQL.",
            "prepared_row_count": int(len(documents)),
            "table_name": config.table_name,
        }

    stack = import_pgvector_stack()
    if isinstance(stack, dict) and stack.get("status") == "skipped":
        result = dict(stack)
        result["prepared_row_count"] = int(len(documents))
        result["table_name"] = config.table_name
        return result

    rows = prepare_upsert_rows(documents, embedding_provider)
    with stack["psycopg"].connect(config.dsn, autocommit=True) as connection:
        stack["register_vector"](connection)
        ensure_schema(connection, config)
        with connection.cursor() as cursor:
            cursor.executemany(build_upsert_sql(config.table_name), rows)

    return {
        "status": "ok",
        "ingested_row_count": int(len(rows)),
        "table_name": config.table_name,
    }
