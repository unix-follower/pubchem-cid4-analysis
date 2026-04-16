from __future__ import annotations

import json
import logging as log
from pathlib import Path

import env_utils
import fs_utils
import log_settings
from langchain_cid4.workflows import (
    run_agent_workflow,
    run_assay_workflow,
    run_literature_workflow,
    run_pathway_workflow,
    run_taxonomy_workflow,
)
from ml.common import to_builtin


def resolve_output_directory() -> Path:
    data_dir = Path(env_utils.get_data_dir())
    output_directory = data_dir / "out"
    fs_utils.create_dir_if_doesnt_exist(str(output_directory))
    return output_directory


def write_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(to_builtin(payload), file, indent=2)


def write_langchain_analysis() -> None:
    output_directory = resolve_output_directory()
    outputs = {
        "cid4_langchain.literature.summary.json": run_literature_workflow(),
        "cid4_langchain.assay.summary.json": run_assay_workflow(),
        "cid4_langchain.pathway.summary.json": run_pathway_workflow(),
        "cid4_langchain.taxonomy.summary.json": run_taxonomy_workflow(),
        "cid4_langchain.agent.summary.json": run_agent_workflow(),
    }

    for filename, payload in outputs.items():
        path = output_directory / filename
        write_json(path, payload)
        log.info("LangChain summary written to %s", path)


if __name__ == "__main__":
    log_settings.configure_logging()
    write_langchain_analysis()
