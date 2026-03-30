import json
import logging as log
from functools import reduce
from itertools import combinations
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, Draw, ValenceType
from scipy import linalg

import env_utils
import fs_utils as fs
import log_settings
from constants import ARR_1ST_IDX as IDX1
from constants import UTF_8
from matplotlib_utils import (
    plot_gradient_descent_fit,
    plot_gradient_descent_loss_curve,
    plot_hill_reference_curves,
    plot_pic50_transform,
)

CONFORMER_ATOM_COUNT = 14
NULL_SPACE_TOLERANCE = 1e-10
ANGLE_VECTOR_TOLERANCE = 1e-10
DEFAULT_HILL_COEFFICIENT = 1.0
DEFAULT_GRADIENT_DESCENT_LEARNING_RATE = 5e-5
DEFAULT_GRADIENT_DESCENT_EPOCHS = 250


def reduce_mol_weights(mol_weights: list[float]) -> float:
    return reduce(lambda prev, next: prev + next, mol_weights, 0.0)


def resolve_data_path(filename: str) -> Path:
    return Path(env_utils.get_data_dir()) / filename


def get_output_directory(work_directory: str) -> str:
    out_dir = f"{work_directory}/out"
    fs.create_dir_if_doesnt_exist(out_dir)
    return out_dir


def get_valid_molecules(sdf_file_path: str) -> list[Chem.Mol]:
    with Chem.SDMolSupplier(sdf_file_path, removeHs=False) as supplier:
        return [mol for mol in supplier if mol is not None]


def load_sdf_molecules(filename: str) -> list[Chem.Mol]:
    return get_valid_molecules(str(resolve_data_path(filename)))


def load_conformer_compound(filename: str) -> dict:
    json_file_path = resolve_data_path(filename)

    with json_file_path.open(encoding=UTF_8) as file:
        conformer_data = json.load(file)

    return conformer_data["PC_Compounds"][IDX1]


def extract_3d_coordinates(molecule: Chem.Mol) -> np.ndarray:
    if molecule.GetNumConformers() == 0:
        raise ValueError("SDF molecule does not contain a conformer with 3D coordinates")

    conformer = molecule.GetConformer()
    coordinates = np.array(
        [
            [
                conformer.GetAtomPosition(atom_index).x,
                conformer.GetAtomPosition(atom_index).y,
                conformer.GetAtomPosition(atom_index).z,
            ]
            for atom_index in range(molecule.GetNumAtoms())
        ],
        dtype=np.float64,
    )

    if coordinates.shape != (CONFORMER_ATOM_COUNT, 3):
        raise ValueError(f"Expected 3D coordinates for {CONFORMER_ATOM_COUNT} atoms, found {coordinates.shape}")

    return coordinates


def build_distance_matrix(coordinates: np.ndarray) -> np.ndarray:
    deltas = coordinates[:, np.newaxis, :] - coordinates[np.newaxis, :, :]
    distance_matrix = np.linalg.norm(deltas, axis=2)
    np.fill_diagonal(distance_matrix, 0.0)
    return distance_matrix


def get_bonded_atom_pairs_from_adjacency(adjacency_matrix: pd.DataFrame) -> list[tuple[int, int]]:
    atom_ids = adjacency_matrix.index.tolist()
    adjacency_values = adjacency_matrix.to_numpy(dtype=np.int64)
    bonded_pairs: list[tuple[int, int]] = []

    for row_index in range(len(atom_ids)):
        for column_index in range(row_index + 1, len(atom_ids)):
            if adjacency_values[row_index, column_index] > 0:
                bonded_pairs.append((int(atom_ids[row_index]), int(atom_ids[column_index])))

    if not bonded_pairs:
        raise ValueError("Expected at least one bonded atom pair in the adjacency matrix")

    return bonded_pairs


def partition_distances_by_bonding(
    atom_ids: list[int],
    distance_matrix: np.ndarray,
    bonded_pairs: list[tuple[int, int]],
) -> dict[str, list[dict[str, float | int]]]:
    atom_index_by_id = {atom_id: index for index, atom_id in enumerate(atom_ids)}
    bonded_pair_set = {tuple(sorted(pair)) for pair in bonded_pairs}
    bonded_distances: list[dict[str, float | int]] = []
    nonbonded_distances: list[dict[str, float | int]] = []

    for first_atom_id in atom_ids:
        for second_atom_id in atom_ids:
            if first_atom_id >= second_atom_id:
                continue

            first_index = atom_index_by_id[first_atom_id]
            second_index = atom_index_by_id[second_atom_id]
            pair_record = {
                "atom_id_1": int(first_atom_id),
                "atom_id_2": int(second_atom_id),
                "distance_angstrom": float(distance_matrix[first_index, second_index]),
            }

            if (first_atom_id, second_atom_id) in bonded_pair_set:
                bonded_distances.append(pair_record)
            else:
                nonbonded_distances.append(pair_record)

    expected_pair_count = len(atom_ids) * (len(atom_ids) - 1) // 2
    actual_pair_count = len(bonded_distances) + len(nonbonded_distances)
    if actual_pair_count != expected_pair_count:
        raise ValueError(
            f"Expected {expected_pair_count} unique atom pairs, partitioned {actual_pair_count} pairs instead"
        )

    return {
        "bonded": bonded_distances,
        "nonbonded": nonbonded_distances,
    }


def summarize_distance_partition(pair_records: list[dict[str, float | int]]) -> dict:
    distances = np.array([float(pair_record["distance_angstrom"]) for pair_record in pair_records], dtype=np.float64)
    if distances.size == 0:
        raise ValueError("Distance partition must contain at least one pair")

    quantiles = np.quantile(distances, [0.25, 0.5, 0.75])
    return {
        "count": int(distances.size),
        "min_distance_angstrom": float(distances.min()),
        "mean_distance_angstrom": float(distances.mean()),
        "std_distance_angstrom": float(distances.std(ddof=0)),
        "q25_distance_angstrom": float(quantiles[0]),
        "median_distance_angstrom": float(quantiles[1]),
        "q75_distance_angstrom": float(quantiles[2]),
        "max_distance_angstrom": float(distances.max()),
    }


def compute_bonded_nonbonded_distance_statistics(
    partitions: dict[str, list[dict[str, float | int]]],
) -> dict:
    bonded_summary = summarize_distance_partition(partitions["bonded"])
    nonbonded_summary = summarize_distance_partition(partitions["nonbonded"])

    return {
        "bonded_distances": bonded_summary,
        "nonbonded_distances": nonbonded_summary,
        "comparison": {
            "mean_distance_difference_angstrom": float(
                nonbonded_summary["mean_distance_angstrom"] - bonded_summary["mean_distance_angstrom"]
            ),
            "nonbonded_to_bonded_mean_ratio": float(
                nonbonded_summary["mean_distance_angstrom"] / bonded_summary["mean_distance_angstrom"]
            ),
        },
    }


def enumerate_bonded_angle_triplets(adjacency_matrix: pd.DataFrame) -> list[tuple[int, int, int]]:
    atom_ids = adjacency_matrix.index.tolist()
    adjacency_values = adjacency_matrix.to_numpy(dtype=np.int64)
    angle_triplets: list[tuple[int, int, int]] = []

    for central_index, central_atom_id in enumerate(atom_ids):
        neighbor_atom_ids = [
            int(atom_ids[neighbor_index])
            for neighbor_index in range(len(atom_ids))
            if adjacency_values[central_index, neighbor_index] > 0
        ]

        for neighbor_atom_id_1, neighbor_atom_id_2 in combinations(sorted(neighbor_atom_ids), 2):
            angle_triplets.append((int(central_atom_id), int(neighbor_atom_id_1), int(neighbor_atom_id_2)))

    if not angle_triplets:
        raise ValueError("Expected at least one bonded angle triplet in the adjacency matrix")

    return angle_triplets


def compute_bond_angle_degrees(first_bond_vector: np.ndarray, second_bond_vector: np.ndarray) -> float:
    first_norm = float(np.linalg.norm(first_bond_vector))
    second_norm = float(np.linalg.norm(second_bond_vector))

    if first_norm <= ANGLE_VECTOR_TOLERANCE or second_norm <= ANGLE_VECTOR_TOLERANCE:
        raise ValueError("Bond angle computation requires non-zero bond vectors")

    cosine = float(np.dot(first_bond_vector, second_bond_vector) / (first_norm * second_norm))
    cosine = float(np.clip(cosine, -1.0, 1.0))
    return float(np.degrees(np.arccos(cosine)))


def compute_bonded_angle_records(
    atom_ids: list[int],
    coordinates: np.ndarray,
    angle_triplets: list[tuple[int, int, int]],
) -> list[dict[str, float | int]]:
    atom_index_by_id = {atom_id: index for index, atom_id in enumerate(atom_ids)}
    angle_records: list[dict[str, float | int]] = []

    for central_atom_id, neighbor_atom_id_1, neighbor_atom_id_2 in angle_triplets:
        central_index = atom_index_by_id[central_atom_id]
        neighbor_index_1 = atom_index_by_id[neighbor_atom_id_1]
        neighbor_index_2 = atom_index_by_id[neighbor_atom_id_2]

        first_bond_vector = coordinates[neighbor_index_1] - coordinates[central_index]
        second_bond_vector = coordinates[neighbor_index_2] - coordinates[central_index]
        angle_records.append(
            {
                "central_atom_id": int(central_atom_id),
                "neighbor_atom_id_1": int(neighbor_atom_id_1),
                "neighbor_atom_id_2": int(neighbor_atom_id_2),
                "angle_degrees": compute_bond_angle_degrees(first_bond_vector, second_bond_vector),
            }
        )

    return angle_records


def summarize_bond_angles(angle_records: list[dict[str, float | int]]) -> dict:
    angle_values = np.array([float(angle_record["angle_degrees"]) for angle_record in angle_records], dtype=np.float64)
    if angle_values.size == 0:
        raise ValueError("Bond angle analysis must contain at least one angle")

    quantiles = np.quantile(angle_values, [0.25, 0.5, 0.75])
    return {
        "count": int(angle_values.size),
        "min_angle_degrees": float(angle_values.min()),
        "mean_angle_degrees": float(angle_values.mean()),
        "std_angle_degrees": float(angle_values.std(ddof=0)),
        "q25_angle_degrees": float(quantiles[0]),
        "median_angle_degrees": float(quantiles[1]),
        "q75_angle_degrees": float(quantiles[2]),
        "max_angle_degrees": float(angle_values.max()),
    }


def extract_atom_feature_matrix(molecules: list[Chem.Mol]) -> pd.DataFrame:
    atom_data: list[dict[str, object]] = []

    for molecule_index, mol in enumerate(molecules):
        for atom in mol.GetAtoms():
            atom_data.append(
                {
                    "moleculeIndex": molecule_index,
                    "index": atom.GetIdx(),
                    "bondCount": atom.GetDegree(),
                    "charge": atom.GetFormalCharge(),
                    "implicitHydrogenCount": atom.GetNumImplicitHs(),
                    "totalHydrogenCount": atom.GetTotalNumHs(),
                    "atomicNumber": atom.GetAtomicNum(),
                    "symbol": atom.GetSymbol(),
                    "valency": atom.GetValence(which=ValenceType.EXPLICIT),
                    "isAromatic": atom.GetIsAromatic(),
                    "mass": atom.GetMass(),
                    "hybridization": str(atom.GetHybridization()),
                    "properties": atom.GetPropsAsDict(),
                }
            )

    atom_feature_df = pd.DataFrame(atom_data)
    if atom_feature_df.empty:
        raise ValueError("Expected at least one atom when building the atom feature matrix")

    return atom_feature_df


def build_atom_gradient_descent_dataset(atom_feature_df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    required_columns = {"index", "symbol", "mass", "atomicNumber"}
    missing_columns = required_columns.difference(atom_feature_df.columns)
    if missing_columns:
        raise ValueError(f"Atom feature matrix is missing required columns: {sorted(missing_columns)}")

    dataset_df = atom_feature_df.loc[:, ["index", "symbol", "mass", "atomicNumber"]].copy()
    dataset_df["mass"] = pd.to_numeric(dataset_df["mass"], errors="coerce")
    dataset_df["atomicNumber"] = pd.to_numeric(dataset_df["atomicNumber"], errors="coerce")
    dataset_df = dataset_df.dropna(subset=["mass", "atomicNumber"]).reset_index(drop=True)

    if dataset_df.empty:
        raise ValueError("Atom feature matrix did not contain any numeric mass/atomic-number rows")

    x_values = dataset_df["mass"].to_numpy(dtype=np.float64)
    y_values = dataset_df["atomicNumber"].to_numpy(dtype=np.float64)
    return x_values, y_values, dataset_df


def compute_gradient_descent_predictions(x_values: np.ndarray, weight: float) -> np.ndarray:
    return weight * x_values


def compute_sum_squared_error(x_values: np.ndarray, y_values: np.ndarray, weight: float) -> float:
    residuals = y_values - compute_gradient_descent_predictions(x_values, weight)
    return float(np.sum(residuals**2))


def compute_mean_squared_error(x_values: np.ndarray, y_values: np.ndarray, weight: float) -> float:
    residuals = y_values - compute_gradient_descent_predictions(x_values, weight)
    return float(np.mean(residuals**2))


def compute_sum_squared_error_gradient(x_values: np.ndarray, y_values: np.ndarray, weight: float) -> float:
    return float(2.0 * np.sum(x_values * ((weight * x_values) - y_values)))


def finite_difference_gradient(
    x_values: np.ndarray,
    y_values: np.ndarray,
    weight: float,
    epsilon: float = 1e-6,
) -> float:
    forward_loss = compute_sum_squared_error(x_values, y_values, weight + epsilon)
    backward_loss = compute_sum_squared_error(x_values, y_values, weight - epsilon)
    return float((forward_loss - backward_loss) / (2.0 * epsilon))


def run_manual_gradient_descent(
    x_values: np.ndarray,
    y_values: np.ndarray,
    learning_rate: float = DEFAULT_GRADIENT_DESCENT_LEARNING_RATE,
    epochs: int = DEFAULT_GRADIENT_DESCENT_EPOCHS,
    initial_weight: float = 0.0,
) -> tuple[pd.DataFrame, dict[str, float | int]]:
    if learning_rate <= 0.0:
        raise ValueError("Gradient descent learning rate must be positive")
    if epochs <= 0:
        raise ValueError("Gradient descent epochs must be positive")

    weight = float(initial_weight)
    trace_records: list[dict[str, float | int]] = []

    for epoch in range(epochs + 1):
        sse_loss = compute_sum_squared_error(x_values, y_values, weight)
        mse_loss = compute_mean_squared_error(x_values, y_values, weight)
        gradient = compute_sum_squared_error_gradient(x_values, y_values, weight)
        trace_records.append(
            {
                "epoch": epoch,
                "weight": weight,
                "gradient": gradient,
                "sum_squared_error": sse_loss,
                "mse": mse_loss,
            }
        )

        if epoch < epochs:
            weight = weight - (learning_rate * gradient)

    closed_form_weight = float(np.sum(x_values * y_values) / np.sum(x_values**2))
    summary = {
        "initial_weight": float(initial_weight),
        "final_weight": float(trace_records[-1]["weight"]),
        "learning_rate": float(learning_rate),
        "epochs": int(epochs),
        "closed_form_weight": closed_form_weight,
        "initial_sum_squared_error": float(trace_records[0]["sum_squared_error"]),
        "final_sum_squared_error": float(trace_records[-1]["sum_squared_error"]),
        "initial_mse": float(trace_records[0]["mse"]),
        "final_mse": float(trace_records[-1]["mse"]),
    }
    return pd.DataFrame(trace_records), summary


def summarize_atom_gradient_descent_analysis(
    dataset_df: pd.DataFrame,
    trace_df: pd.DataFrame,
    training_summary: dict[str, float | int],
) -> dict:
    x_values = dataset_df["mass"].to_numpy(dtype=np.float64)
    y_values = dataset_df["atomicNumber"].to_numpy(dtype=np.float64)
    initial_weight = float(training_summary["initial_weight"])
    final_weight = float(training_summary["final_weight"])
    initial_gradient = compute_sum_squared_error_gradient(x_values, y_values, initial_weight)
    final_gradient = compute_sum_squared_error_gradient(x_values, y_values, final_weight)

    return {
        "dataset": {
            "row_count": int(len(dataset_df)),
            "feature": "mass",
            "target": "atomicNumber",
            "feature_matrix_shape": [int(len(dataset_df)), 1],
            "mass_range": [float(dataset_df["mass"].min()), float(dataset_df["mass"].max())],
            "atomic_number_range": [
                int(dataset_df["atomicNumber"].min()),
                int(dataset_df["atomicNumber"].max()),
            ],
            "atom_rows": [
                {
                    "index": int(row["index"]),
                    "symbol": str(row["symbol"]),
                    "mass": float(row["mass"]),
                    "atomicNumber": int(row["atomicNumber"]),
                }
                for _, row in dataset_df.iterrows()
            ],
        },
        "model": {
            "prediction_equation": "y_hat = w * x",
            "objective_name": "sum_squared_error",
            "objective_equation": "L(w) = sum_i (y_i - w x_i)^2",
            "mse_equation": "MSE(w) = (1 / n) * sum_i (y_i - w x_i)^2",
            "gradient_equation": "dL/dw = sum_i -2 x_i (y_i - w x_i) = 2 sum_i x_i (w x_i - y_i)",
            "feature_name": "atom mass",
            "target_name": "atomic number",
        },
        "optimization": {
            **training_summary,
            "weight_error_vs_closed_form": float(
                training_summary["final_weight"] - training_summary["closed_form_weight"]
            ),
            "gradient_checks": {
                "initial_weight": {
                    "analytic": float(initial_gradient),
                    "finite_difference": float(finite_difference_gradient(x_values, y_values, initial_weight)),
                },
                "final_weight": {
                    "analytic": float(final_gradient),
                    "finite_difference": float(finite_difference_gradient(x_values, y_values, final_weight)),
                },
            },
            "loss_trace": {
                "monotonic_nonincreasing_mse": bool(
                    np.all(np.diff(trace_df["mse"].to_numpy(dtype=np.float64)) <= 1e-12)
                ),
                "best_epoch": int(trace_df.loc[trace_df["mse"].idxmin(), "epoch"]),
            },
        },
    }


def build_hill_reference_dataframe(
    bioactivity_df: pd.DataFrame,
    hill_coefficient: float = DEFAULT_HILL_COEFFICIENT,
) -> tuple[pd.DataFrame, dict[str, int]]:
    if hill_coefficient <= 0:
        raise ValueError("Hill coefficient must be positive")

    activity_value = pd.to_numeric(bioactivity_df["Activity_Value"], errors="coerce")
    has_curve_series = pd.to_numeric(bioactivity_df["Has_Dose_Response_Curve"], errors="coerce").fillna(0).astype(int)
    positive_numeric_mask = activity_value.notna() & (activity_value > 0)

    hill_df = bioactivity_df.loc[positive_numeric_mask].copy()
    hill_df["Activity_Value"] = activity_value.loc[positive_numeric_mask]
    hill_df["Has_Dose_Response_Curve"] = has_curve_series.loc[positive_numeric_mask]
    hill_df["Activity_Type"] = hill_df["Activity_Type"].astype("string").str.strip().fillna("Unknown")
    hill_df["Target_Name"] = hill_df["Target_Name"].astype("string").str.strip().fillna("Unknown")
    hill_df["hill_coefficient_n"] = float(hill_coefficient)
    hill_df["inferred_K_activity_value"] = hill_df["Activity_Value"].astype(np.float64)
    hill_df["midpoint_concentration"] = hill_df["inferred_K_activity_value"]
    hill_df["midpoint_response"] = 0.5
    hill_df["midpoint_first_derivative"] = hill_response_first_derivative(
        hill_df["midpoint_concentration"].to_numpy(dtype=np.float64),
        hill_df["inferred_K_activity_value"].to_numpy(dtype=np.float64),
        hill_coefficient,
    )
    hill_df["log10_midpoint_concentration"] = np.log10(hill_df["midpoint_concentration"])
    hill_df["linear_inflection_concentration"] = np.nan
    hill_df["linear_inflection_response"] = np.nan
    hill_df["fit_status"] = "reference_curve_inferred_from_activity_value"
    hill_df["analysis_mode"] = "reference_curve"

    if hill_coefficient > 1.0:
        inflection_scale = ((hill_coefficient - 1.0) / (hill_coefficient + 1.0)) ** (1.0 / hill_coefficient)
        hill_df["linear_inflection_concentration"] = hill_df["inferred_K_activity_value"] * inflection_scale
        hill_df["linear_inflection_response"] = hill_response(
            hill_df["linear_inflection_concentration"].to_numpy(dtype=np.float64),
            hill_df["inferred_K_activity_value"].to_numpy(dtype=np.float64),
            hill_coefficient,
        )

    hill_df = hill_df.sort_values(by=["inferred_K_activity_value", "BioAssay_AID"], ascending=[True, True]).reset_index(
        drop=True
    )

    counts = {
        "total_rows": int(len(bioactivity_df)),
        "rows_with_numeric_activity_value": int(activity_value.notna().sum()),
        "rows_with_positive_activity_value": int(positive_numeric_mask.sum()),
        "rows_flagged_has_dose_response_curve": int((has_curve_series == 1).sum()),
        "retained_rows": int(len(hill_df)),
        "retained_rows_flagged_has_dose_response_curve": int((hill_df["Has_Dose_Response_Curve"] == 1).sum()),
        "retained_unique_bioassays": int(hill_df["BioAssay_AID"].nunique()),
    }

    if hill_df.empty:
        raise ValueError("No positive numeric Activity_Value rows were found in the bioactivity dataset")

    return hill_df, counts


def hill_response(
    concentration: np.ndarray, half_maximal_concentration: np.ndarray | float, hill_coefficient: float
) -> np.ndarray:
    concentration_array = np.asarray(concentration, dtype=np.float64)
    half_maximal_array = np.asarray(half_maximal_concentration, dtype=np.float64)
    numerator = concentration_array**hill_coefficient
    denominator = (half_maximal_array**hill_coefficient) + numerator
    return numerator / denominator


def hill_response_first_derivative(
    concentration: np.ndarray,
    half_maximal_concentration: np.ndarray | float,
    hill_coefficient: float,
) -> np.ndarray:
    concentration_array = np.asarray(concentration, dtype=np.float64)
    half_maximal_array = np.asarray(half_maximal_concentration, dtype=np.float64)
    numerator = (
        hill_coefficient * (half_maximal_array**hill_coefficient) * (concentration_array ** (hill_coefficient - 1.0))
    )
    denominator = ((half_maximal_array**hill_coefficient) + (concentration_array**hill_coefficient)) ** 2
    return numerator / denominator


def hill_response_second_derivative(
    concentration: np.ndarray,
    half_maximal_concentration: np.ndarray | float,
    hill_coefficient: float,
) -> np.ndarray:
    concentration_array = np.asarray(concentration, dtype=np.float64)
    half_maximal_array = np.asarray(half_maximal_concentration, dtype=np.float64)
    numerator = (
        hill_coefficient
        * (half_maximal_array**hill_coefficient)
        * (concentration_array ** (hill_coefficient - 2.0))
        * (
            ((hill_coefficient - 1.0) * (half_maximal_array**hill_coefficient))
            - ((hill_coefficient + 1.0) * (concentration_array**hill_coefficient))
        )
    )
    denominator = ((half_maximal_array**hill_coefficient) + (concentration_array**hill_coefficient)) ** 3
    return numerator / denominator


def summarize_hill_reference_analysis(hill_df: pd.DataFrame, counts: dict[str, int], hill_coefficient: float) -> dict:
    inferred_k_values = hill_df["inferred_K_activity_value"].to_numpy(dtype=np.float64)
    midpoint_derivatives = hill_df["midpoint_first_derivative"].to_numpy(dtype=np.float64)
    representative_positions = sorted({0, len(hill_df) // 2, len(hill_df) - 1})
    representative_rows = hill_df.iloc[representative_positions]
    activity_type_counts = {
        str(key): int(value) for key, value in hill_df["Activity_Type"].value_counts(dropna=False).items()
    }

    linear_inflection = None
    if hill_coefficient > 1.0:
        response_at_inflection = float((hill_coefficient - 1.0) / (2.0 * hill_coefficient))
        linear_inflection = {
            "formula": "c* = K * ((n - 1)/(n + 1))^(1/n)",
            "response_formula": "f(c*) = (n - 1)/(2n)",
            "relative_to_K": float(((hill_coefficient - 1.0) / (hill_coefficient + 1.0)) ** (1.0 / hill_coefficient)),
            "normalized_response": response_at_inflection,
        }

    return {
        "row_counts": counts,
        "statistics": {
            "activity_value_as_inferred_K": {
                "min": float(inferred_k_values.min()),
                "median": float(np.median(inferred_k_values)),
                "max": float(inferred_k_values.max()),
            },
            "midpoint_first_derivative": {
                "min": float(midpoint_derivatives.min()),
                "median": float(np.median(midpoint_derivatives)),
                "max": float(midpoint_derivatives.max()),
            },
        },
        "activity_type_counts": activity_type_counts,
        "analysis": {
            "model": "normalized Hill equation",
            "equation": "f(c) = c^n / (K^n + c^n)",
            "first_derivative": "f'(c) = n K^n c^(n-1) / (K^n + c^n)^2",
            "second_derivative": ("f''(c) = n K^n c^(n-2) * ((n - 1)K^n - (n + 1)c^n) / (K^n + c^n)^3"),
            "reference_hill_coefficient_n": float(hill_coefficient),
            "parameter_interpretation": (
                "Activity_Value is treated as an inferred K parameter because this dataset provides potency-style "
                "summary values rather than raw concentration-response observations for CID 4."
            ),
            "midpoint_in_log_concentration_space": {
                "condition": "c = K",
                "response": 0.5,
                "interpretation": "The Hill curve is centered at c = K in log-concentration space.",
            },
            "linear_concentration_inflection": linear_inflection,
            "fit_status": "reference_curve_inferred_from_activity_value",
            "representative_rows": [
                {
                    "Bioactivity_ID": int(row["Bioactivity_ID"]),
                    "BioAssay_AID": int(row["BioAssay_AID"]),
                    "Activity_Type": str(row["Activity_Type"]),
                    "Target_Name": str(row["Target_Name"]),
                    "Activity_Value": float(row["Activity_Value"]),
                    "inferred_K_activity_value": float(row["inferred_K_activity_value"]),
                    "log10_midpoint_concentration": float(row["log10_midpoint_concentration"]),
                }
                for _, row in representative_rows.iterrows()
            ],
            "notes": [
                "No nonlinear dose-response fitting was performed because "
                "the CSV does not contain raw per-concentration response series for CID 4.",
                "Rows with positive numeric Activity_Value are modeled as reference Hill curves "
                "using Activity_Value as the inferred half-maximal scale K.",
            ],
        },
    }


def select_hill_plot_representatives(hill_df: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    representative_positions = sorted({0, len(hill_df) // 2, len(hill_df) - 1})
    representative_rows = hill_df.iloc[representative_positions]
    representative_k_values = representative_rows["inferred_K_activity_value"].to_numpy(dtype=np.float64)
    representative_labels = [
        f"AID {int(row['BioAssay_AID'])} | {str(row['Activity_Type'])} | "
        + "K={float(row['inferred_K_activity_value']):.4g}"
        for _, row in representative_rows.iterrows()
    ]
    return representative_k_values, representative_labels


def load_bioactivity_dataframe(filename: str) -> pd.DataFrame:
    return pd.read_csv(resolve_data_path(filename))


def build_pic50_dataframe(bioactivity_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    activity_type = bioactivity_df["Activity_Type"].astype("string").str.strip().str.upper()
    activity_value = pd.to_numeric(bioactivity_df["Activity_Value"], errors="coerce")
    positive_numeric_mask = activity_value.notna() & (activity_value > 0)
    retained_mask = activity_type.eq("IC50") & positive_numeric_mask

    pic50_df = bioactivity_df.loc[retained_mask].copy()
    pic50_df["Activity_Value"] = activity_value.loc[retained_mask]
    pic50_df["IC50_uM"] = pic50_df["Activity_Value"]
    pic50_df["pIC50"] = -np.log10(pic50_df["IC50_uM"])
    pic50_df = pic50_df.sort_values(by="pIC50", ascending=False).reset_index(drop=True)

    counts = {
        "total_rows": int(len(bioactivity_df)),
        "rows_with_numeric_activity_value": int(positive_numeric_mask.sum()),
        "rows_with_ic50_activity_type": int(activity_type.eq("IC50").sum()),
        "retained_ic50_rows": int(len(pic50_df)),
        "dropped_rows": int(len(bioactivity_df) - len(pic50_df)),
    }

    if pic50_df.empty:
        raise ValueError("No positive numeric IC50 rows were found in the bioactivity dataset")

    return pic50_df, counts


def summarize_pic50_analysis(pic50_df: pd.DataFrame, counts: dict[str, int]) -> dict:
    ic50_values = pic50_df["IC50_uM"]
    pic50_values = pic50_df["pIC50"]
    strongest_row = pic50_df.loc[pic50_values.idxmax()]
    weakest_row = pic50_df.loc[pic50_values.idxmin()]

    return {
        "row_counts": counts,
        "statistics": {
            "ic50_uM": {
                "min": float(ic50_values.min()),
                "median": float(ic50_values.median()),
                "max": float(ic50_values.max()),
            },
            "pIC50": {
                "min": float(pic50_values.min()),
                "median": float(pic50_values.median()),
                "max": float(pic50_values.max()),
            },
        },
        "analysis": {
            "transform": "pIC50 = -log10(IC50_uM)",
            "interpretation": "Lower IC50 values map to higher pIC50 values, so potency increases as the curve rises.",
            "observed_ic50_domain_uM": [float(ic50_values.min()), float(ic50_values.max())],
            "strongest_retained_measurement": {
                "Bioactivity_ID": int(strongest_row["Bioactivity_ID"]),
                "BioAssay_AID": int(strongest_row["BioAssay_AID"]),
                "IC50_uM": float(strongest_row["IC50_uM"]),
                "pIC50": float(strongest_row["pIC50"]),
            },
            "weakest_retained_measurement": {
                "Bioactivity_ID": int(weakest_row["Bioactivity_ID"]),
                "BioAssay_AID": int(weakest_row["BioAssay_AID"]),
                "IC50_uM": float(weakest_row["IC50_uM"]),
                "pIC50": float(weakest_row["pIC50"]),
            },
        },
    }


def build_adjacency_matrix(filename: str) -> pd.DataFrame:
    compound = load_conformer_compound(filename)
    atom_ids = sorted(compound["atoms"]["aid"])
    bonds = compound["bonds"]

    if len(atom_ids) != CONFORMER_ATOM_COUNT:
        raise ValueError(f"Expected {CONFORMER_ATOM_COUNT} atoms in {filename}, found {len(atom_ids)}")

    if not (len(bonds["aid1"]) == len(bonds["aid2"]) == len(bonds["order"])):
        raise ValueError(f"Bond arrays in {filename} must be aligned")

    graph = nx.Graph()
    zero_based_nodes = list(range(len(atom_ids)))
    atom_index_by_id = {atom_id: index for index, atom_id in enumerate(atom_ids)}
    graph.add_nodes_from(zero_based_nodes)

    for first_atom_id, second_atom_id, bond_order in zip(bonds["aid1"], bonds["aid2"], bonds["order"], strict=True):
        graph.add_edge(
            atom_index_by_id[first_atom_id],
            atom_index_by_id[second_atom_id],
            weight=bond_order,
        )

    adjacency_matrix = nx.to_pandas_adjacency(graph, nodelist=zero_based_nodes, dtype=int, weight="weight")
    adjacency_matrix.index = atom_ids
    adjacency_matrix.columns = atom_ids
    return adjacency_matrix


def compute_adjacency_spectrum(adjacency_matrix: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    adjacency_array = adjacency_matrix.to_numpy(dtype=np.float64)
    return np.linalg.eigh(adjacency_array)


def build_degree_matrix(adjacency_matrix: pd.DataFrame) -> pd.DataFrame:
    degree_values = adjacency_matrix.sum(axis=1).to_numpy(dtype=np.float64)
    return pd.DataFrame(
        np.diag(degree_values),
        index=adjacency_matrix.index,
        columns=adjacency_matrix.columns,
    )


def build_laplacian_matrix(adjacency_matrix: pd.DataFrame) -> pd.DataFrame:
    degree_matrix = build_degree_matrix(adjacency_matrix)
    return degree_matrix - adjacency_matrix.astype(np.float64)


def compute_laplacian_spectrum(laplacian_matrix: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    laplacian_array = laplacian_matrix.to_numpy(dtype=np.float64)
    return np.linalg.eigh(laplacian_array)


def compute_laplacian_null_space(
    laplacian_matrix: pd.DataFrame,
    tolerance: float = NULL_SPACE_TOLERANCE,
) -> np.ndarray:
    laplacian_array = laplacian_matrix.to_numpy(dtype=np.float64)
    return linalg.null_space(laplacian_array, rcond=tolerance)


def build_graph_from_adjacency_matrix(adjacency_matrix: pd.DataFrame) -> nx.Graph:
    return nx.from_pandas_adjacency(adjacency_matrix, create_using=nx.Graph)


def extract_connected_components(
    adjacency_matrix: pd.DataFrame,
    null_space_vectors: np.ndarray,
) -> dict:
    graph = build_graph_from_adjacency_matrix(adjacency_matrix)
    atom_ids = adjacency_matrix.index.tolist()
    components = [sorted(component) for component in nx.connected_components(graph)]
    component_by_atom_id = {
        atom_id: component_index for component_index, component in enumerate(components) for atom_id in component
    }
    assignment = [component_by_atom_id[atom_id] for atom_id in atom_ids]
    null_space_dimension = int(null_space_vectors.shape[1])

    if null_space_dimension != len(components):
        raise ValueError("Null-space dimension does not match NetworkX connected-components count")

    return {
        "count": len(components),
        "assignment": assignment,
        "components_atom_ids": components,
        "verification_networkx_count": len(components),
    }


def write_laplacian_analysis(
    filename: str,
    adjacency_matrix: pd.DataFrame,
    tolerance: float = NULL_SPACE_TOLERANCE,
):
    work_directory = env_utils.get_data_dir()
    out_dir = get_output_directory(work_directory)
    atom_ids = adjacency_matrix.index.tolist()
    degree_matrix = build_degree_matrix(adjacency_matrix)
    laplacian_matrix = build_laplacian_matrix(adjacency_matrix)
    laplacian_eigenvalues, laplacian_eigenvectors = compute_laplacian_spectrum(laplacian_matrix)
    null_space_vectors = compute_laplacian_null_space(laplacian_matrix, tolerance=tolerance)
    connected_components = extract_connected_components(adjacency_matrix, null_space_vectors)
    output_path = Path(out_dir) / f"{Path(filename).stem}.laplacian_analysis.json"

    laplacian_array = laplacian_matrix.to_numpy(dtype=np.float64)
    positive_eigenvalues = laplacian_eigenvalues[laplacian_eigenvalues > tolerance]
    smallest_nonzero_eigenvalue = float(positive_eigenvalues[0]) if positive_eigenvalues.size > 0 else 0.0
    bond_count = int(np.count_nonzero(np.triu(adjacency_matrix.to_numpy(dtype=np.float64), k=1)))

    with output_path.open("w", encoding=UTF_8) as file:
        json.dump(
            {
                "atom_ids": atom_ids,
                "degree_matrix": degree_matrix.values.tolist(),
                "laplacian_matrix": laplacian_matrix.values.tolist(),
                "laplacian_eigenvalues": laplacian_eigenvalues.tolist(),
                "laplacian_eigenvectors": laplacian_eigenvectors.tolist(),
                "null_space": {
                    "basis_vectors": null_space_vectors.tolist(),
                    "dimension": int(null_space_vectors.shape[1]),
                    "tolerance_used": tolerance,
                    "smallest_nonzero_eigenvalue": smallest_nonzero_eigenvalue,
                },
                "connected_components": connected_components,
                "metadata": {
                    "atom_count": len(atom_ids),
                    "bond_count": bond_count,
                    "laplacian_rank": int(np.linalg.matrix_rank(laplacian_array, tol=tolerance)),
                    "graph_is_connected": connected_components["count"] == 1,
                },
            },
            file,
            indent=2,
        )

    log.info("Laplacian analysis written to %s", output_path)


def write_distance_matrix(sdf_filename: str, json_filename: str):
    work_directory = env_utils.get_data_dir()
    out_dir = get_output_directory(work_directory)
    molecules = load_sdf_molecules(sdf_filename)

    if not molecules:
        raise ValueError(f"No valid molecules found in {sdf_filename}")

    coordinates = extract_3d_coordinates(molecules[IDX1])
    distance_matrix = build_distance_matrix(coordinates)
    atom_ids = sorted(load_conformer_compound(json_filename)["atoms"]["aid"])

    if len(atom_ids) != distance_matrix.shape[0]:
        raise ValueError(
            f"Expected {len(atom_ids)} atom ids from {json_filename}, found {distance_matrix.shape[0]} coordinates"
        )

    output_path = Path(out_dir) / f"{Path(sdf_filename).stem}.distance_matrix.json"

    with output_path.open("w", encoding=UTF_8) as file:
        json.dump(
            {
                "atom_ids": atom_ids,
                "xyz_coordinates": coordinates.tolist(),
                "distance_matrix": distance_matrix.tolist(),
                "metadata": {
                    "atom_count": len(atom_ids),
                    "coordinate_dimension": int(coordinates.shape[1]),
                    "source_sdf": sdf_filename,
                    "units": "angstrom",
                },
            },
            file,
            indent=2,
        )

    log.info("Distance matrix written to %s", output_path)


def write_bonded_distance_analysis(sdf_filename: str, json_filename: str):
    work_directory = env_utils.get_data_dir()
    out_dir = get_output_directory(work_directory)
    molecules = load_sdf_molecules(sdf_filename)

    if not molecules:
        raise ValueError(f"No valid molecules found in {sdf_filename}")

    coordinates = extract_3d_coordinates(molecules[IDX1])
    distance_matrix = build_distance_matrix(coordinates)
    adjacency_matrix = build_adjacency_matrix(json_filename)
    atom_ids = adjacency_matrix.index.tolist()
    bonded_pairs = get_bonded_atom_pairs_from_adjacency(adjacency_matrix)
    partitions = partition_distances_by_bonding(atom_ids, distance_matrix, bonded_pairs)
    statistics = compute_bonded_nonbonded_distance_statistics(partitions)
    output_path = Path(out_dir) / f"{Path(sdf_filename).stem}.bonded_distance_analysis.json"

    with output_path.open("w", encoding=UTF_8) as file:
        json.dump(
            {
                "atom_ids": atom_ids,
                "bonded_atom_pairs": [{"atom_id_1": pair[0], "atom_id_2": pair[1]} for pair in bonded_pairs],
                "bonded_pair_distances": partitions["bonded"],
                "nonbonded_pair_distances": partitions["nonbonded"],
                "statistics": statistics,
                "metadata": {
                    "atom_count": len(atom_ids),
                    "bonded_pair_count": len(partitions["bonded"]),
                    "nonbonded_pair_count": len(partitions["nonbonded"]),
                    "total_unique_pair_count": len(partitions["bonded"]) + len(partitions["nonbonded"]),
                    "source_sdf": sdf_filename,
                    "source_bond_json": json_filename,
                    "units": "angstrom",
                },
            },
            file,
            indent=2,
        )

    log.info("Bonded distance analysis written to %s", output_path)


def write_bonded_angle_analysis(sdf_filename: str, json_filename: str):
    work_directory = env_utils.get_data_dir()
    out_dir = get_output_directory(work_directory)
    molecules = load_sdf_molecules(sdf_filename)

    if not molecules:
        raise ValueError(f"No valid molecules found in {sdf_filename}")

    coordinates = extract_3d_coordinates(molecules[IDX1])
    adjacency_matrix = build_adjacency_matrix(json_filename)
    atom_ids = adjacency_matrix.index.tolist()

    if len(atom_ids) != coordinates.shape[0]:
        raise ValueError(
            f"Expected {len(atom_ids)} atom ids from {json_filename}, found {coordinates.shape[0]} coordinates"
        )

    angle_triplets = enumerate_bonded_angle_triplets(adjacency_matrix)
    angle_records = compute_bonded_angle_records(atom_ids, coordinates, angle_triplets)
    statistics = summarize_bond_angles(angle_records)
    output_path = Path(out_dir) / f"{Path(sdf_filename).stem}.bonded_angle_analysis.json"

    with output_path.open("w", encoding=UTF_8) as file:
        json.dump(
            {
                "atom_ids": atom_ids,
                "bonded_angle_triplets": [
                    {
                        "central_atom_id": triplet[0],
                        "neighbor_atom_id_1": triplet[1],
                        "neighbor_atom_id_2": triplet[2],
                    }
                    for triplet in angle_triplets
                ],
                "bonded_triplet_angles": angle_records,
                "statistics": statistics,
                "metadata": {
                    "atom_count": len(atom_ids),
                    "bonded_angle_triplet_count": len(angle_records),
                    "source_sdf": sdf_filename,
                    "source_bond_json": json_filename,
                    "units": "degrees",
                    "selection_rule": "angles A-B-C where A-B and B-C are bonded and B is the central atom",
                },
            },
            file,
            indent=2,
        )

    log.info("Bonded angle analysis written to %s", output_path)


def write_bioactivity_analysis(filename: str):
    work_directory = env_utils.get_data_dir()
    out_dir = get_output_directory(work_directory)
    bioactivity_df = load_bioactivity_dataframe(filename)
    pic50_df, counts = build_pic50_dataframe(bioactivity_df)
    summary = summarize_pic50_analysis(pic50_df, counts)
    output_stem = Path(filename).stem
    filtered_output_path = Path(out_dir) / f"{output_stem}.ic50_pic50.csv"
    summary_output_path = Path(out_dir) / f"{output_stem}.ic50_pic50.summary.json"
    plot_output_path = Path(out_dir) / f"{output_stem}.ic50_pic50.png"

    pic50_df.to_csv(filtered_output_path, index=False)

    with summary_output_path.open("w", encoding=UTF_8) as file:
        json.dump(summary, file, indent=2)

    plot_pic50_transform(
        pic50_df["IC50_uM"].to_numpy(dtype=np.float64),
        pic50_df["pIC50"].to_numpy(dtype=np.float64),
        str(plot_output_path),
    )

    log.info("Bioactivity pIC50 rows written to %s", filtered_output_path)
    log.info("Bioactivity pIC50 summary written to %s", summary_output_path)
    log.info("Bioactivity pIC50 plot written to %s", plot_output_path)


def write_hill_dose_response_analysis(filename: str, hill_coefficient: float = DEFAULT_HILL_COEFFICIENT):
    work_directory = env_utils.get_data_dir()
    out_dir = get_output_directory(work_directory)
    bioactivity_df = load_bioactivity_dataframe(filename)
    hill_df, counts = build_hill_reference_dataframe(bioactivity_df, hill_coefficient=hill_coefficient)
    summary = summarize_hill_reference_analysis(hill_df, counts, hill_coefficient)
    output_stem = Path(filename).stem
    records_output_path = Path(out_dir) / f"{output_stem}.hill_dose_response.csv"
    summary_output_path = Path(out_dir) / f"{output_stem}.hill_dose_response.summary.json"
    plot_output_path = Path(out_dir) / f"{output_stem}.hill_dose_response.png"

    hill_df.to_csv(records_output_path, index=False)

    with summary_output_path.open("w", encoding=UTF_8) as file:
        json.dump(summary, file, indent=2)

    representative_k_values, representative_labels = select_hill_plot_representatives(hill_df)
    plot_hill_reference_curves(
        representative_k_values,
        representative_labels,
        hill_coefficient=hill_coefficient,
        out_file_path=str(plot_output_path),
    )

    log.info("Hill dose-response rows written to %s", records_output_path)
    log.info("Hill dose-response summary written to %s", summary_output_path)
    log.info("Hill dose-response plot written to %s", plot_output_path)


def write_adjacency_matrix(filename: str) -> pd.DataFrame:
    work_directory = env_utils.get_data_dir()
    out_dir = get_output_directory(work_directory)
    adjacency_matrix = build_adjacency_matrix(filename)
    output_path = Path(out_dir) / f"{Path(filename).stem}.adjacency_matrix.json"

    with output_path.open("w", encoding=UTF_8) as file:
        json.dump(
            {
                "atom_ids": adjacency_matrix.index.tolist(),
                "adjacency_matrix": adjacency_matrix.values.tolist(),
            },
            file,
            indent=2,
        )

    log.info("Adjacency matrix written to %s", output_path)
    return adjacency_matrix


def write_adjacency_spectrum(filename: str, adjacency_matrix: pd.DataFrame):
    work_directory = env_utils.get_data_dir()
    out_dir = get_output_directory(work_directory)
    eigenvalues, eigenvectors = compute_adjacency_spectrum(adjacency_matrix)
    output_path = Path(out_dir) / f"{Path(filename).stem}.eigendecomposition.json"

    with output_path.open("w", encoding=UTF_8) as file:
        json.dump(
            {
                "atom_ids": adjacency_matrix.index.tolist(),
                "eigenvalues": eigenvalues.tolist(),
                "eigenvectors": eigenvectors.tolist(),
            },
            file,
            indent=2,
        )

    log.info("Adjacency eigendecomposition written to %s", output_path)


def write_image(sdf_file_path: str, out_img_filepath: str):
    ms = get_valid_molecules(sdf_file_path)

    for m in ms:
        AllChem.Compute2DCoords(m)

    Draw.MolToFile(ms[IDX1], out_img_filepath)


def process_sdf_file(filename: str) -> pd.DataFrame:
    work_directory = env_utils.get_data_dir()
    sdf_file_path = resolve_data_path(filename)
    molecules = load_sdf_molecules(filename)

    avg_mol_weights = [Descriptors.MolWt(mol) for mol in molecules]
    log.info(f"Average molecular weight: {reduce_mol_weights(avg_mol_weights)}")
    mol_exact_mass = [Descriptors.ExactMolWt(mol) for mol in molecules]
    log.info(f"Exact molecular mass: {reduce_mol_weights(mol_exact_mass)}")

    out_dir = get_output_directory(work_directory)

    df = extract_atom_feature_matrix(molecules)
    df.to_json(f"{out_dir}/{filename}.json")

    out_img_filepath = f"{out_dir}/{filename.split('.')[IDX1]}.png"
    write_image(str(sdf_file_path), out_img_filepath)
    return df


def write_atom_gradient_descent_analysis(
    sdf_filename: str,
    atom_feature_df: pd.DataFrame | None = None,
    learning_rate: float = DEFAULT_GRADIENT_DESCENT_LEARNING_RATE,
    epochs: int = DEFAULT_GRADIENT_DESCENT_EPOCHS,
):
    work_directory = env_utils.get_data_dir()
    out_dir = get_output_directory(work_directory)
    feature_df = atom_feature_df if atom_feature_df is not None else process_sdf_file(sdf_filename)
    x_values, y_values, dataset_df = build_atom_gradient_descent_dataset(feature_df)
    trace_df, training_summary = run_manual_gradient_descent(
        x_values,
        y_values,
        learning_rate=learning_rate,
        epochs=epochs,
    )
    summary = summarize_atom_gradient_descent_analysis(dataset_df, trace_df, training_summary)
    output_stem = Path(sdf_filename).stem
    trace_output_path = Path(out_dir) / f"{output_stem}.mass_to_atomic_number_gradient_descent.csv"
    summary_output_path = Path(out_dir) / f"{output_stem}.mass_to_atomic_number_gradient_descent.summary.json"
    loss_plot_output_path = Path(out_dir) / f"{output_stem}.mass_to_atomic_number_gradient_descent.loss.png"
    fit_plot_output_path = Path(out_dir) / f"{output_stem}.mass_to_atomic_number_gradient_descent.fit.png"

    trace_df.to_csv(trace_output_path, index=False)

    with summary_output_path.open("w", encoding=UTF_8) as file:
        json.dump(summary, file, indent=2)

    plot_gradient_descent_loss_curve(
        trace_df["epoch"].to_numpy(dtype=np.int64),
        trace_df["mse"].to_numpy(dtype=np.float64),
        str(loss_plot_output_path),
    )
    plot_gradient_descent_fit(
        dataset_df["mass"].to_numpy(dtype=np.float64),
        dataset_df["atomicNumber"].to_numpy(dtype=np.float64),
        float(training_summary["final_weight"]),
        str(fit_plot_output_path),
    )

    log.info("Atom gradient-descent trace written to %s", trace_output_path)
    log.info("Atom gradient-descent summary written to %s", summary_output_path)
    log.info("Atom gradient-descent loss plot written to %s", loss_plot_output_path)
    log.info("Atom gradient-descent fit plot written to %s", fit_plot_output_path)


def main():
    log_settings.configure_logging()
    sdf_filename = "Conformer3D_COMPOUND_CID_4(1).sdf"
    json_filename = "Conformer3D_COMPOUND_CID_4(1).json"
    bioactivity_filename = "pubchem_cid_4_bioactivity.csv"
    atom_feature_df = process_sdf_file(sdf_filename)
    write_atom_gradient_descent_analysis(sdf_filename, atom_feature_df=atom_feature_df)
    write_distance_matrix(sdf_filename, json_filename)
    write_bonded_distance_analysis(sdf_filename, json_filename)
    write_bonded_angle_analysis(sdf_filename, json_filename)
    adjacency_matrix = write_adjacency_matrix(json_filename)
    write_adjacency_spectrum(json_filename, adjacency_matrix)
    write_laplacian_analysis(json_filename, adjacency_matrix)
    write_bioactivity_analysis(bioactivity_filename)
    write_hill_dose_response_analysis(bioactivity_filename)


if __name__ == "__main__":
    main()
