import json
import logging as log
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src import log_settings
from src.utils.fs_utils import resolve_output_directory

from .graphs import (
    build_assay_graph,
    build_molecular_graph,
    build_organism_graph,
    build_pathway_reaction_graph,
)
from .queries import build_query_catalog
from .storage import ingest_graph, load_config_from_env


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
    with path.open("w", encoding="utf-8") as file:
        json.dump(to_builtin(payload), file, indent=2)


def build_age_summary() -> dict:
    config = load_config_from_env()
    molecular_graph = build_molecular_graph("Conformer3D_COMPOUND_CID_4(1).json")
    structure_2d_graph = build_molecular_graph("Structure2D_COMPOUND_CID_4.json")
    organism_graph = build_organism_graph("cid_4.dot", "pubchem_cid_4_consolidatedcompoundtaxonomy.csv")
    pathway_graph = build_pathway_reaction_graph("pubchem_cid_4_pathway.csv", "pubchem_cid_4_pathwayreaction.csv")
    assay_graph = build_assay_graph("pubchem_cid_4_bioactivity.csv")
    query_catalog = build_query_catalog()
    ingestion_result = ingest_graph(molecular_graph, config)

    return {
        "status": ingestion_result["status"],
        "graph_name": config.graph_name,
        "graph_families": {
            "molecular": molecular_graph.to_summary(),
            "structure_2d": structure_2d_graph.to_summary(),
            "organism": organism_graph.to_summary(),
            "pathway_reaction": pathway_graph.to_summary(),
            "assay": assay_graph.to_summary(),
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
