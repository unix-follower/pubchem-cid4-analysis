from __future__ import annotations

import json
import logging as log
from pathlib import Path
from typing import Any

import env_utils
import fs_utils
import numpy as np
import pandas as pd
from nltk_workflows import (
    run_bioactivity_workflow,
    run_literature_vs_patent_workflow,
    run_literature_workflow,
    run_pathway_workflow,
    run_taxonomy_workflow,
    run_toxicology_workflow,
)

import log_settings


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


def resolve_output_directory() -> Path:
    data_dir = Path(env_utils.get_data_dir())
    output_directory = data_dir / "out"
    fs_utils.create_dir_if_doesnt_exist(str(output_directory))
    return output_directory


def write_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(to_builtin(payload), file, indent=2)


def write_nltk_analysis() -> None:
    output_directory = resolve_output_directory()
    outputs = {
        "cid4_nltk.literature.summary.json": run_literature_workflow(),
        "cid4_nltk.literature_vs_patent.summary.json": run_literature_vs_patent_workflow(),
        "cid4_nltk.bioactivity.summary.json": run_bioactivity_workflow(),
        "cid4_nltk.taxonomy.summary.json": run_taxonomy_workflow(),
        "cid4_nltk.toxicology.summary.json": run_toxicology_workflow(),
        "cid4_nltk.pathway.summary.json": run_pathway_workflow(),
    }

    for filename, payload in outputs.items():
        write_json(output_directory / filename, payload)
        log.info("NLTK summary written to %s", output_directory / filename)


if __name__ == "__main__":
    log_settings.configure_logging()
    write_nltk_analysis()
