from __future__ import annotations

import json
import logging as log
from pathlib import Path

import env_utils
import fs_utils
import log_settings
from age_cid4.graphs import (
    build_assay_graph,
    build_molecular_graph,
    build_organism_graph,
    build_pathway_reaction_graph,
    build_structure_2d_graph,
    build_unified_graph,
)
from age_cid4.queries import build_query_catalog
from age_cid4.storage import ingest_graph, load_config_from_env
from ml.common import to_builtin


def resolve_output_directory() -> Path:
    data_dir = Path(env_utils.get_data_dir())
    output_directory = data_dir / "out"
    fs_utils.create_dir_if_doesnt_exist(str(output_directory))
    return output_directory


def write_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(to_builtin(payload), file, indent=2)


def build_age_summary() -> dict:
    config = load_config_from_env()
    molecular_graph = build_molecular_graph()
    structure_2d_graph = build_structure_2d_graph()
    organism_graph = build_organism_graph()
    pathway_graph = build_pathway_reaction_graph()
    assay_graph = build_assay_graph()
    unified_graph = build_unified_graph()
    query_catalog = build_query_catalog()
    ingestion_result = ingest_graph(unified_graph, config)

    return {
        "status": ingestion_result["status"],
        "graph_name": config.graph_name,
        "graph_families": {
            "molecular": molecular_graph.to_summary(),
            "structure_2d": structure_2d_graph.to_summary(),
            "organism": organism_graph.to_summary(),
            "pathway_reaction": pathway_graph.to_summary(),
            "assay": assay_graph.to_summary(),
            "unified": unified_graph.to_summary(),
        },
        "database": ingestion_result,
        "query_catalog": query_catalog,
        "recommended_workflows": [
            "molecular graph traversal over atoms and bonds",
            "compound-to-organism graph exploration from cid_4.dot and taxonomy CSV",
            "pathway-reaction graph traversal across proteins, genes, enzymes, and taxa",
            "assay-target graph queries with source and taxonomy provenance",
            "unified CID 4 Cypher exploration inside PostgreSQL with Apache AGE",
        ],
    }


def write_age_analysis() -> None:
    output_directory = resolve_output_directory()
    summary = build_age_summary()
    output_path = output_directory / "cid4_age.summary.json"
    write_json(output_path, summary)
    log.info("Apache AGE summary written to %s", output_path)


if __name__ == "__main__":
    log_settings.configure_logging()
    write_age_analysis()
