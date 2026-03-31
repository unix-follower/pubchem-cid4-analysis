from __future__ import annotations

import json
import logging as log
from pathlib import Path

import env_utils
import fs_utils
import log_settings
from ml.common import to_builtin
from ml.datasets import (
    build_activity_value_regression_dataset,
    build_atom_element_dataset,
    build_atom_feature_frame,
    build_atom_heavy_atom_dataset,
    build_bioactivity_binary_classification_dataset,
    build_heavy_atom_pca_dataset,
    build_taxonomy_clustering_frame,
)
from ml.scaffold_workflows import build_scaffold_summary
from ml.sklearn_workflows import (
    run_atom_neighbor_report,
    run_decision_tree,
    run_hierarchical_clustering,
    run_kmeans,
    run_knn,
    run_linear_regression,
    run_logistic_regression,
    run_naive_bayes,
    run_pca,
    run_random_forest,
    run_svm,
)
from ml.tensorflow_workflows import run_tensorflow_classification, run_tensorflow_regression
from ml.torch_workflows import run_torch_classification, run_torch_regression


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

    atom_feature_df, _ = build_atom_feature_frame()
    atom_heavy_dataset = build_atom_heavy_atom_dataset()
    atom_element_dataset = build_atom_element_dataset()
    bioactivity_dataset = build_bioactivity_binary_classification_dataset()
    regression_dataset = build_activity_value_regression_dataset()
    heavy_atom_pca_dataset = build_heavy_atom_pca_dataset()
    taxonomy_frame = build_taxonomy_clustering_frame()

    atom_feature_df.to_csv(output_directory / "cid4_ml.atom_features.csv", index=False)
    bioactivity_dataset.frame.to_csv(output_directory / "cid4_ml.bioactivity_binary_features.csv", index=False)
    regression_dataset.frame.to_csv(output_directory / "cid4_ml.bioactivity_regression_features.csv", index=False)
    taxonomy_frame.to_csv(output_directory / "cid4_ml.taxonomy_features.csv", index=False)

    comparison_results = {
        "atom_heavy_vs_hydrogen": {
            "sklearn": run_logistic_regression(atom_heavy_dataset),
            "pytorch": run_torch_classification(atom_heavy_dataset),
            "tensorflow": run_tensorflow_classification(atom_heavy_dataset),
        },
        "atom_element_multiclass": {
            "sklearn": run_logistic_regression(atom_element_dataset),
            "pytorch": run_torch_classification(atom_element_dataset),
            "tensorflow": run_tensorflow_classification(atom_element_dataset),
        },
        "bioactivity_binary_classification": {
            "sklearn": run_logistic_regression(bioactivity_dataset),
            "pytorch": run_torch_classification(bioactivity_dataset),
            "tensorflow": run_tensorflow_classification(bioactivity_dataset),
        },
        "activity_value_regression": {
            "sklearn": run_linear_regression(regression_dataset),
            "pytorch": run_torch_regression(regression_dataset),
            "tensorflow": run_tensorflow_regression(regression_dataset),
        },
    }

    sklearn_suite = {
        "linear_regression": run_linear_regression(regression_dataset),
        "logistic_regression": run_logistic_regression(bioactivity_dataset),
        "svm": run_svm(bioactivity_dataset),
        "knn_classification": run_knn(atom_heavy_dataset),
        "knn_neighbors": run_atom_neighbor_report(atom_heavy_dataset),
        "decision_tree": run_decision_tree(bioactivity_dataset),
        "random_forest": run_random_forest(bioactivity_dataset),
        "kmeans": run_kmeans(atom_feature_df),
        "hierarchical_clustering": run_hierarchical_clustering(),
        "pca": run_pca(heavy_atom_pca_dataset),
        "naive_bayes": run_naive_bayes(atom_heavy_dataset),
    }
    scaffold_summary = build_scaffold_summary(atom_heavy_dataset)

    write_json(output_directory / "cid4_ml.cross_library_comparison.summary.json", comparison_results)
    write_json(output_directory / "cid4_ml.sklearn_suite.summary.json", sklearn_suite)
    write_json(output_directory / "cid4_ml.future_scaffolds.summary.json", scaffold_summary)

    log.info(
        "ML cross-library comparison written to %s", output_directory / "cid4_ml.cross_library_comparison.summary.json"
    )
    log.info("ML sklearn suite written to %s", output_directory / "cid4_ml.sklearn_suite.summary.json")
    log.info("ML scaffold recommendations written to %s", output_directory / "cid4_ml.future_scaffolds.summary.json")


if __name__ == "__main__":
    log_settings.configure_logging()
    write_ml_analysis()
