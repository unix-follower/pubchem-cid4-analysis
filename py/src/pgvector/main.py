from __future__ import annotations

import logging as log
from collections import Counter

from src import log_settings

from .documents import prepare_documents
from .embedding import HashedTokenEmbeddingProvider
from .storage import ingest_documents


def ingest_pgvector_data():
    log_settings.configure_logging()

    embedding_provider = HashedTokenEmbeddingProvider()
    documents = prepare_documents()
    document_type_counts = Counter(document.doc_type for document in documents)
    ingestion_result = ingest_documents(documents, embedding_provider)

    summary = {
        "document_count": int(len(documents)),
        "doc_type_counts": {key: int(value) for key, value in sorted(document_type_counts.items())},
        "database": ingestion_result,
    }
    log.info("result: %s", summary)


if __name__ == "__main__":
    ingest_pgvector_data()
