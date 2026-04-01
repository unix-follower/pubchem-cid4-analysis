from __future__ import annotations

import json
import logging as log
from pathlib import Path

import env_utils
import fs_utils
import log_settings
from ml.common import to_builtin
from nlp.nltk_workflows import (
    run_bioactivity_workflow,
    run_literature_vs_patent_workflow,
    run_literature_workflow,
    run_pathway_workflow,
    run_taxonomy_workflow,
    run_toxicology_workflow,
)


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
