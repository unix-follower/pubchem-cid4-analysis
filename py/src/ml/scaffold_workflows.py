from __future__ import annotations

from typing import Any

from ml.common import PreparedDataset


def build_gnn_scaffold_summary(dataset: PreparedDataset) -> dict[str, Any]:
    return {
        "status": "scaffold_only",
        "model_family": "graph-neural-network",
        "dataset": dataset.summary(),
        "recommended_primary_library": "pytorch-geometric",
        "recommended_alternatives": ["dgl", "deepchem"],
        "why_not_fully_implemented": (
            "The current CID 4 snapshot is effectively a single-molecule problem, "
            "which is not a credible training corpus for a real graph neural network."
        ),
        "current_reusable_inputs": {
            "atom_features": list(dataset.feature_columns),
            "target_column": dataset.target_column,
            "node_count": int(len(dataset.frame)),
        },
        "minimum_dataset_requirements": [
            "A corpus of many molecules instead of a single CID 4 conformer.",
            "A molecule-level or node-level label defined across that larger corpus.",
            "Consistent graph construction from RDKit bonds, atom features, and optional bond features.",
        ],
        "proposed_pipeline": [
            "Use RDKit to convert each molecule into atom and bond tensors.",
            "Build PyTorch Geometric Data objects with node features, edge indices, and optional edge attributes.",
            "Train a small message-passing network for graph or node prediction.",
            "Compare against the existing tabular sklearn baselines before trusting the GNN.",
        ],
        "next_code_targets": [
            "Add a graph dataset builder that returns Data-style records from multiple molecules.",
            "Add bond feature extraction for bond order, aromaticity, and ring membership.",
            "Add train/validation/test splitting at the molecule level rather than the atom level.",
        ],
    }


def build_smiles_rnn_scaffold_summary() -> dict[str, Any]:
    return {
        "status": "scaffold_only",
        "model_family": "smiles-rnn",
        "recommended_primary_library": "tensorflow",
        "recommended_alternatives": ["pytorch", "keras-nlp", "deepchem"],
        "why_not_fully_implemented": (
            "The repository currently centers on one molecule and associated assay metadata, "
            "which is not enough sequence diversity "
            "for a meaningful SMILES language model or sequence regressor."
        ),
        "minimum_dataset_requirements": [
            "A larger corpus of unique SMILES strings.",
            "A task definition such as generation, reconstruction, or property prediction across many molecules.",
            "A tokenizer and vocabulary built from that broader SMILES corpus.",
        ],
        "proposed_pipeline": [
            "Canonicalize SMILES strings with RDKit.",
            "Tokenize characters or substructures into integer sequences.",
            "Train an embedding plus recurrent or transformer-style sequence model.",
            "Evaluate validity, uniqueness, and task-specific accuracy depending on the objective.",
        ],
        "starter_architecture": {
            "embedding_dim": 64,
            "recurrent_layer": "LSTM",
            "hidden_units": 128,
            "output_heads": ["next-token prediction", "optional property regression"],
        },
        "next_code_targets": [
            "Add a SMILES corpus loader from a multi-molecule dataset.",
            "Add tokenizer serialization and train/validation splits.",
            "Add TensorFlow and PyTorch sequence baselines once adequate data exists.",
        ],
    }


def build_scaffold_summary(atom_dataset: PreparedDataset) -> dict[str, Any]:
    return {
        "gnn": build_gnn_scaffold_summary(atom_dataset),
        "smiles_rnn": build_smiles_rnn_scaffold_summary(),
    }
