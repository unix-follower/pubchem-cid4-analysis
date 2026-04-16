from __future__ import annotations

import json
import logging as log
from pathlib import Path

import env_utils
import fs_utils
import log_settings
from ml.common import to_builtin
from ml.datasets import (
    build_atom_element_dataset,
    build_atom_heavy_atom_dataset,
    build_bioactivity_binary_classification_dataset,
)
from ml.scaffold_workflows import build_scaffold_summary
from ml.tensorflow_workflows import (
    run_tensorflow_classification,
)
from ml.torch_workflows import run_torch_classification
from ml.xgboost_workflows import run_xgboost_classification


def resolve_output_directory() -> Path:
    data_dir = Path(env_utils.get_data_dir())
    output_directory = data_dir / "out"
    fs_utils.create_dir_if_doesnt_exist(str(output_directory))
    return output_directory


def write_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(to_builtin(payload), file, indent=2)


def write_ml_analysis() -> None:
    output_directory = resolve_output_directory()

    atom_heavy_dataset = build_atom_heavy_atom_dataset()
    atom_element_dataset = build_atom_element_dataset()
    bioactivity_dataset = build_bioactivity_binary_classification_dataset()

    comparison_results = {
        "atom_heavy_vs_hydrogen": {
            "pytorch": run_torch_classification(atom_heavy_dataset),
            "tensorflow": run_tensorflow_classification(atom_heavy_dataset),
        },
        "atom_element_multiclass": {
            "pytorch": run_torch_classification(atom_element_dataset),
            "tensorflow": run_tensorflow_classification(atom_element_dataset),
        },
        "bioactivity_binary_classification": {
            "xgboost": run_xgboost_classification(bioactivity_dataset),
            "pytorch": run_torch_classification(bioactivity_dataset),
            "tensorflow": run_tensorflow_classification(bioactivity_dataset),
        },
    }

    xgboost_suite = {
        "bioactivity_binary_classification": run_xgboost_classification(
            bioactivity_dataset
        ),
    }
    scaffold_summary = build_scaffold_summary(atom_heavy_dataset)

    write_json(
        output_directory / "cid4_ml.cross_library_comparison.summary.json",
        comparison_results,
    )
    write_json(output_directory / "cid4_ml.xgboost_suite.summary.json", xgboost_suite)
    write_json(
        output_directory / "cid4_ml.future_scaffolds.summary.json", scaffold_summary
    )

    log.info(
        "ML cross-library comparison written to %s",
        output_directory / "cid4_ml.cross_library_comparison.summary.json",
    )
    log.info(
        "ML sklearn suite written to %s",
        output_directory / "cid4_ml.sklearn_suite.summary.json",
    )
    log.info(
        "ML XGBoost suite written to %s",
        output_directory / "cid4_ml.xgboost_suite.summary.json",
    )
    log.info(
        "ML scaffold recommendations written to %s",
        output_directory / "cid4_ml.future_scaffolds.summary.json",
    )


if __name__ == "__main__":
    log_settings.configure_logging()
    write_ml_analysis()
