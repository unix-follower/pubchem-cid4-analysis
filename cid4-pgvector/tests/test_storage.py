from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from documents import VectorDocument  # noqa: E402
from embedding import HashedTokenEmbeddingProvider  # noqa: E402
from storage import (  # noqa: E402
    PgvectorConfig,
    build_similarity_query_sql,
    build_upsert_sql,
    ingest_documents,
    prepare_upsert_rows,
)


class PgvectorStorageTests(unittest.TestCase):
    def test_build_upsert_sql_targets_requested_table(self) -> None:
        sql = build_upsert_sql("cid4_documents_test")

        self.assertIn("INSERT INTO cid4_documents_test", sql)
        self.assertIn("ON CONFLICT (doc_id)", sql)

    def test_build_similarity_query_uses_metadata_filters(self) -> None:
        sql = build_similarity_query_sql(
            "cid4_documents", {"aid_type": "Confirmatory", "taxonomy_id": "9606"}
        )

        self.assertIn("metadata ->> %s = %s", sql)
        self.assertIn("ORDER BY embedding <=> %s", sql)

    def test_prepare_upsert_rows_serializes_metadata_and_embeddings(self) -> None:
        provider = HashedTokenEmbeddingProvider(dimension=8)
        documents = [
            VectorDocument(
                doc_id="bioactivity:test:1",
                doc_type="bioactivity",
                source_file="pubchem_cid_4_bioactivity.csv",
                source_row_id="1",
                title="Example assay",
                text_payload="estrogen receptor antagonism",
                cid=4,
                aid=743069,
                metadata={"aid_type": "Confirmatory"},
            )
        ]

        rows = prepare_upsert_rows(documents, provider)

        self.assertEqual(len(rows), 1)
        self.assertIsInstance(rows[0]["metadata"], str)
        self.assertEqual(len(rows[0]["embedding"]), 8)

    def test_ingest_documents_dry_runs_without_dsn(self) -> None:
        provider = HashedTokenEmbeddingProvider(dimension=8)
        documents = [
            VectorDocument(
                doc_id="literature:test:1",
                doc_type="literature",
                source_file="pubchem_cid_4_literature.csv",
                source_row_id="1",
                title="Example literature",
                text_payload="isopropanolamine fungicide",
            )
        ]

        result = ingest_documents(
            documents,
            PgvectorConfig(
                dsn=None, table_name="cid4_documents", embedding_dimension=8
            ),
            provider,
        )

        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(result["prepared_row_count"], 1)


if __name__ == "__main__":
    unittest.main()
