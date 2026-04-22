from __future__ import annotations

import json
import logging as log
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src import constants, log_settings
from src.utils import fs_utils

from .documents import build_all_documents
from .embedding import HashedTokenEmbeddingProvider
from .storage import ingest_documents, load_config_from_env


def to_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): to_builtin(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_builtin(item) for item in value]
    if isinstance(value, tuple):
        return [to_builtin(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, pd.Series):
        return value.to_list()
    return value


def write_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding=constants.UTF_8) as file:
        json.dump(to_builtin(payload), file, indent=2)


def build_pgvector_summary() -> dict:
    config = load_config_from_env()
    embedding_provider = HashedTokenEmbeddingProvider(dimension=config.embedding_dimension)
    documents = build_all_documents()
    document_type_counts = Counter(document.doc_type for document in documents)
    ingestion_result = ingest_documents(documents, config, embedding_provider)

    sample_documents = [
        {
            "doc_id": document.doc_id,
            "doc_type": document.doc_type,
            "title": document.title,
            "source_file": document.source_file,
            "source_row_id": document.source_row_id,
        }
        for document in documents[:10]
    ]

    return {
        "document_count": int(len(documents)),
        "doc_type_counts": {key: int(value) for key, value in sorted(document_type_counts.items())},
        "embedding": {
            "provider": embedding_provider.name,
            "dimension": int(embedding_provider.dimension),
            "note": "Deterministic hashed-token embeddings are used as a lightweight placeholder for "
            "schema and query prototyping.",
        },
        "database": ingestion_result,
        "sample_documents": sample_documents,
        "query_patterns": [
            "semantic literature search over titles and abstracts",
            "hybrid assay retrieval with metadata filters such as Aid_Type and Taxonomy_ID",
            "reaction and pathway lookup by meaning",
            "taxonomy and product-use semantic autocomplete",
        ],
    }


def write_pgvector_analysis() -> None:
    output_directory = fs_utils.resolve_output_directory()
    summary = build_pgvector_summary()
    output_path = output_directory / "cid4_pgvector.summary.json"
    write_json(output_path, summary)
    log.info("pgvector summary written to %s", output_path)


if __name__ == "__main__":
    log_settings.configure_logging()
    write_pgvector_analysis()
