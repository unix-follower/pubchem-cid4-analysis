import json
import logging as log
from functools import reduce
from itertools import combinations
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import py.src.tf.log_settings as log_settings
from py.src.tf.constants import ARR_1ST_IDX as IDX1
from py.src.tf.constants import UTF_8
from py.src.tf.utils import env_utils
from py.src.tf.utils import fs_utils as fs
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, Draw, ValenceType
from scipy import linalg, stats

from matplotlib_utils import (
    plot_activity_value_statistics,
    plot_atom_element_entropy,
    plot_gradient_descent_fit,
    plot_gradient_descent_loss_curve,
    plot_hill_reference_curves,
    plot_pic50_transform,
)

CONFORMER_ATOM_COUNT = 14
NULL_SPACE_TOLERANCE = 1e-10
ANGLE_VECTOR_TOLERANCE = 1e-10
DEFAULT_HILL_COEFFICIENT = 1.0
DEFAULT_HILL_AUC_LOWER_BOUND_SCALE = 1e-2
DEFAULT_HILL_AUC_UPPER_BOUND_SCALE = 1e2
DEFAULT_HILL_AUC_GRID_SIZE = 400
DEFAULT_POSTERIOR_PRIOR_ALPHA = 1.0
DEFAULT_POSTERIOR_PRIOR_BETA = 1.0
DEFAULT_POSTERIOR_CREDIBLE_INTERVAL = 0.95
DEFAULT_BINOMIAL_TAIL_THRESHOLD = 0.0
DEFAULT_CHI_SQUARE_EXPECTED_COUNT_THRESHOLD = 5.0
DEFAULT_SHAPIRO_ALPHA = 0.05
DEFAULT_SHAPIRO_MAX_SAMPLE_SIZE = 5000
DEFAULT_GRADIENT_DESCENT_LEARNING_RATE = 5e-5
DEFAULT_GRADIENT_DESCENT_EPOCHS = 250
SPRING_DISTANCE_TOLERANCE = 1e-12
REQUIRED_ATOM_ENTROPY_ELEMENTS = ("O", "N", "C", "H")
DEFAULT_BOND_ORDER_SPRING_CONSTANTS = {
    1: 300.0,
    2: 500.0,
    3: 700.0,
}
DEFAULT_BOND_ORDER_LENGTH_SCALES = {
    1: 1.0,
    2: 0.9,
    3: 0.85,
}
DEFAULT_REFERENCE_BOND_LENGTHS_ANGSTROM = {
    ("C", "C", 1): 1.54,
    ("C", "C", 2): 1.34,
    ("C", "C", 3): 1.20,
    ("C", "N", 1): 1.47,
    ("C", "N", 2): 1.28,
    ("C", "N", 3): 1.16,
    ("C", "O", 1): 1.43,
    ("C", "O", 2): 1.23,
    ("C", "H", 1): 1.09,
    ("N", "H", 1): 1.01,
    ("O", "H", 1): 0.96,
}
PERIODIC_TABLE = Chem.GetPeriodicTable()


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


def get_bonded_atom_pairs_from_adjacency(
    adjacency_matrix: pd.DataFrame,
) -> list[tuple[int, int]]:
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
    distances = np.array(
        [float(pair_record["distance_angstrom"]) for pair_record in pair_records],
        dtype=np.float64,
    )
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


def enumerate_bonded_angle_triplets(
    adjacency_matrix: pd.DataFrame,
) -> list[tuple[int, int, int]]:
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
    angle_values = np.array(
        [float(angle_record["angle_degrees"]) for angle_record in angle_records],
        dtype=np.float64,
    )
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


def infer_reference_bond_length_angstrom(symbol_1: str, symbol_2: str, bond_order: int) -> tuple[float, str]:
    if bond_order <= 0:
        raise ValueError("Bond order must be positive when inferring a spring reference distance")

    normalized_key = tuple(sorted((str(symbol_1), str(symbol_2)))) + (int(bond_order),)
    if normalized_key in DEFAULT_REFERENCE_BOND_LENGTHS_ANGSTROM:
        return float(DEFAULT_REFERENCE_BOND_LENGTHS_ANGSTROM[normalized_key]), "lookup_table"

    atomic_number_1 = PERIODIC_TABLE.GetAtomicNumber(str(symbol_1))
    atomic_number_2 = PERIODIC_TABLE.GetAtomicNumber(str(symbol_2))
    if atomic_number_1 <= 0 or atomic_number_2 <= 0:
        raise ValueError(f"Could not infer atomic numbers for bond symbols {symbol_1!r} and {symbol_2!r}")

    covalent_radius_sum = float(
        PERIODIC_TABLE.GetRcovalent(atomic_number_1) + PERIODIC_TABLE.GetRcovalent(atomic_number_2)
    )
    length_scale = float(DEFAULT_BOND_ORDER_LENGTH_SCALES.get(int(bond_order), 1.0 / np.sqrt(float(bond_order))))
    return covalent_radius_sum * length_scale, "covalent_radius_fallback"


def resolve_spring_constant_for_bond_order(bond_order: int) -> float:
    if bond_order <= 0:
        raise ValueError("Bond order must be positive when resolving a spring constant")

    return float(
        DEFAULT_BOND_ORDER_SPRING_CONSTANTS.get(int(bond_order), DEFAULT_BOND_ORDER_SPRING_CONSTANTS[1] * bond_order)
    )


def compute_spring_bond_partial_derivative_records(
    atom_ids: list[int],
    coordinates: np.ndarray,
    adjacency_matrix: pd.DataFrame,
    molecule: Chem.Mol,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    if len(atom_ids) != coordinates.shape[0] or molecule.GetNumAtoms() != coordinates.shape[0]:
        raise ValueError("Spring bond derivative analysis requires aligned atom ids, coordinates, and RDKit atoms")

    atom_index_by_id = {atom_id: index for index, atom_id in enumerate(atom_ids)}
    atom_symbol_by_id = {
        int(atom_id): molecule.GetAtomWithIdx(index).GetSymbol() for index, atom_id in enumerate(atom_ids)
    }
    bonded_pairs = get_bonded_atom_pairs_from_adjacency(adjacency_matrix)

    atom_gradient_accumulators = {
        int(atom_id): {
            "atom_id": int(atom_id),
            "atom_symbol": atom_symbol_by_id[int(atom_id)],
            "incident_bond_count": 0,
            "gradient_vector": np.zeros(3, dtype=np.float64),
        }
        for atom_id in atom_ids
    }
    reference_distance_source_counts: dict[str, int] = {}
    bond_records: list[dict[str, object]] = []

    for atom_id_1, atom_id_2 in bonded_pairs:
        atom_index_1 = atom_index_by_id[atom_id_1]
        atom_index_2 = atom_index_by_id[atom_id_2]
        atom_symbol_1 = atom_symbol_by_id[atom_id_1]
        atom_symbol_2 = atom_symbol_by_id[atom_id_2]
        bond_order = int(adjacency_matrix.loc[atom_id_1, atom_id_2])

        bond_vector = coordinates[atom_index_1] - coordinates[atom_index_2]
        distance = float(np.linalg.norm(bond_vector))
        if distance <= SPRING_DISTANCE_TOLERANCE:
            raise ValueError(
                f"Spring bond derivative analysis requires non-zero bonded distances, "
                f"found {distance} for pair {(atom_id_1, atom_id_2)}"
            )

        reference_distance, reference_distance_source = infer_reference_bond_length_angstrom(
            atom_symbol_1,
            atom_symbol_2,
            bond_order,
        )
        reference_distance_source_counts[reference_distance_source] = (
            reference_distance_source_counts.get(reference_distance_source, 0) + 1
        )
        spring_constant = resolve_spring_constant_for_bond_order(bond_order)
        distance_residual = float(distance - reference_distance)
        d_e_ddistance = float(spring_constant * distance_residual)
        gradient_atom_1 = d_e_ddistance * (bond_vector / distance)
        gradient_atom_2 = -gradient_atom_1
        spring_energy = float(0.5 * spring_constant * (distance_residual**2))

        atom_gradient_accumulators[atom_id_1]["gradient_vector"] += gradient_atom_1
        atom_gradient_accumulators[atom_id_1]["incident_bond_count"] += 1
        atom_gradient_accumulators[atom_id_2]["gradient_vector"] += gradient_atom_2
        atom_gradient_accumulators[atom_id_2]["incident_bond_count"] += 1

        bond_records.append(
            {
                "atom_id_1": int(atom_id_1),
                "atom_id_2": int(atom_id_2),
                "atom_symbol_1": atom_symbol_1,
                "atom_symbol_2": atom_symbol_2,
                "bond_order": bond_order,
                "distance_angstrom": distance,
                "reference_distance_angstrom": float(reference_distance),
                "reference_distance_source": reference_distance_source,
                "distance_residual_angstrom": distance_residual,
                "spring_constant": spring_constant,
                "spring_energy": spring_energy,
                "dE_ddistance": d_e_ddistance,
                "atom_1_partial_derivatives": {
                    "dE_dx": float(gradient_atom_1[0]),
                    "dE_dy": float(gradient_atom_1[1]),
                    "dE_dz": float(gradient_atom_1[2]),
                    "gradient_norm": float(np.linalg.norm(gradient_atom_1)),
                },
                "atom_2_partial_derivatives": {
                    "dE_dx": float(gradient_atom_2[0]),
                    "dE_dy": float(gradient_atom_2[1]),
                    "dE_dz": float(gradient_atom_2[2]),
                    "gradient_norm": float(np.linalg.norm(gradient_atom_2)),
                },
            }
        )

    atom_gradient_records: list[dict[str, object]] = []
    net_gradient_vector = np.zeros(3, dtype=np.float64)
    for atom_id in atom_ids:
        accumulator = atom_gradient_accumulators[int(atom_id)]
        gradient_vector = accumulator["gradient_vector"]
        net_gradient_vector += gradient_vector
        atom_gradient_records.append(
            {
                "atom_id": int(atom_id),
                "atom_symbol": str(accumulator["atom_symbol"]),
                "incident_bond_count": int(accumulator["incident_bond_count"]),
                "dE_dx": float(gradient_vector[0]),
                "dE_dy": float(gradient_vector[1]),
                "dE_dz": float(gradient_vector[2]),
                "gradient_norm": float(np.linalg.norm(gradient_vector)),
            }
        )

    metadata = {
        "bonded_pair_count": int(len(bond_records)),
        "reference_distance_source_counts": {
            str(source): int(count) for source, count in sorted(reference_distance_source_counts.items())
        },
        "net_cartesian_gradient": {
            "dE_dx": float(net_gradient_vector[0]),
            "dE_dy": float(net_gradient_vector[1]),
            "dE_dz": float(net_gradient_vector[2]),
            "gradient_norm": float(np.linalg.norm(net_gradient_vector)),
        },
    }
    return bond_records, atom_gradient_records, metadata


def summarize_spring_bond_partial_derivatives(
    bond_records: list[dict[str, object]],
    atom_gradient_records: list[dict[str, object]],
    pair_metadata: dict[str, object],
) -> dict:
    if not bond_records:
        raise ValueError("Spring bond derivative analysis must contain at least one bonded pair")

    distance_residuals = np.array(
        [float(record["distance_residual_angstrom"]) for record in bond_records],
        dtype=np.float64,
    )
    spring_energies = np.array([float(record["spring_energy"]) for record in bond_records], dtype=np.float64)
    atom_gradient_norms = np.array(
        [float(record["gradient_norm"]) for record in atom_gradient_records],
        dtype=np.float64,
    )

    distance_residual_quantiles = np.quantile(distance_residuals, [0.25, 0.5, 0.75])
    spring_energy_quantiles = np.quantile(spring_energies, [0.25, 0.5, 0.75])
    atom_gradient_quantiles = np.quantile(atom_gradient_norms, [0.25, 0.5, 0.75])
    zero_residual_bond_count = int(np.count_nonzero(np.isclose(distance_residuals, 0.0, atol=1e-12)))

    return {
        "distance_residual_angstrom": {
            "count": int(distance_residuals.size),
            "min": float(distance_residuals.min()),
            "mean": float(distance_residuals.mean()),
            "std": float(distance_residuals.std(ddof=0)),
            "q25": float(distance_residual_quantiles[0]),
            "median": float(distance_residual_quantiles[1]),
            "q75": float(distance_residual_quantiles[2]),
            "max": float(distance_residuals.max()),
            "zero_residual_bond_count": zero_residual_bond_count,
        },
        "spring_energy": {
            "count": int(spring_energies.size),
            "total": float(spring_energies.sum()),
            "min": float(spring_energies.min()),
            "mean": float(spring_energies.mean()),
            "std": float(spring_energies.std(ddof=0)),
            "q25": float(spring_energy_quantiles[0]),
            "median": float(spring_energy_quantiles[1]),
            "q75": float(spring_energy_quantiles[2]),
            "max": float(spring_energies.max()),
        },
        "atom_gradient_norm": {
            "count": int(atom_gradient_norms.size),
            "min": float(atom_gradient_norms.min()),
            "mean": float(atom_gradient_norms.mean()),
            "std": float(atom_gradient_norms.std(ddof=0)),
            "q25": float(atom_gradient_quantiles[0]),
            "median": float(atom_gradient_quantiles[1]),
            "q75": float(atom_gradient_quantiles[2]),
            "max": float(atom_gradient_norms.max()),
        },
        "gradient_balance": pair_metadata["net_cartesian_gradient"],
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


def build_atom_gradient_descent_dataset(
    atom_feature_df: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
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
            "mass_range": [
                float(dataset_df["mass"].min()),
                float(dataset_df["mass"].max()),
            ],
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
    auc_lower_bound_scale: float = DEFAULT_HILL_AUC_LOWER_BOUND_SCALE,
    auc_upper_bound_scale: float = DEFAULT_HILL_AUC_UPPER_BOUND_SCALE,
    auc_grid_size: int = DEFAULT_HILL_AUC_GRID_SIZE,
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
    hill_df["auc_trapezoid_reference_curve"] = compute_hill_reference_auc_trapezoid(
        hill_df["inferred_K_activity_value"].to_numpy(dtype=np.float64),
        hill_coefficient=hill_coefficient,
        lower_bound_scale=auc_lower_bound_scale,
        upper_bound_scale=auc_upper_bound_scale,
        grid_size=auc_grid_size,
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
    concentration: np.ndarray,
    half_maximal_concentration: np.ndarray | float,
    hill_coefficient: float,
) -> np.ndarray:
    concentration_array = np.asarray(concentration, dtype=np.float64)
    half_maximal_array = np.asarray(half_maximal_concentration, dtype=np.float64)
    numerator = concentration_array**hill_coefficient
    denominator = (half_maximal_array**hill_coefficient) + numerator
    return numerator / denominator


def compute_hill_reference_auc_trapezoid(
    inferred_k_values: np.ndarray,
    hill_coefficient: float = DEFAULT_HILL_COEFFICIENT,
    lower_bound_scale: float = DEFAULT_HILL_AUC_LOWER_BOUND_SCALE,
    upper_bound_scale: float = DEFAULT_HILL_AUC_UPPER_BOUND_SCALE,
    grid_size: int = DEFAULT_HILL_AUC_GRID_SIZE,
) -> np.ndarray:
    if hill_coefficient <= 0:
        raise ValueError("Hill coefficient must be positive")
    if lower_bound_scale <= 0 or upper_bound_scale <= 0:
        raise ValueError("AUC concentration-bound scales must be positive")
    if lower_bound_scale >= upper_bound_scale:
        raise ValueError("AUC lower-bound scale must be smaller than the upper-bound scale")
    if grid_size < 2:
        raise ValueError("AUC trapezoidal integration requires at least two grid points")

    k_values = np.asarray(inferred_k_values, dtype=np.float64)
    if k_values.size == 0:
        raise ValueError("AUC trapezoidal integration requires at least one inferred K value")
    if np.any(k_values <= 0):
        raise ValueError("AUC trapezoidal integration requires strictly positive inferred K values")

    relative_concentration_grid = np.geomspace(lower_bound_scale, upper_bound_scale, grid_size, dtype=np.float64)
    concentration_grid = k_values[:, np.newaxis] * relative_concentration_grid[np.newaxis, :]
    response_grid = hill_response(concentration_grid, k_values[:, np.newaxis], hill_coefficient)
    return np.trapezoid(response_grid, concentration_grid, axis=1)


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


def summarize_hill_reference_analysis(
    hill_df: pd.DataFrame,
    counts: dict[str, int],
    hill_coefficient: float,
    auc_lower_bound_scale: float = DEFAULT_HILL_AUC_LOWER_BOUND_SCALE,
    auc_upper_bound_scale: float = DEFAULT_HILL_AUC_UPPER_BOUND_SCALE,
    auc_grid_size: int = DEFAULT_HILL_AUC_GRID_SIZE,
) -> dict:
    inferred_k_values = hill_df["inferred_K_activity_value"].to_numpy(dtype=np.float64)
    midpoint_derivatives = hill_df["midpoint_first_derivative"].to_numpy(dtype=np.float64)
    auc_values = hill_df["auc_trapezoid_reference_curve"].to_numpy(dtype=np.float64)
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
            "auc_trapezoid_reference_curve": {
                "min": float(auc_values.min()),
                "median": float(np.median(auc_values)),
                "max": float(auc_values.max()),
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
            "auc_trapezoid_reference_curve": {
                "integration_method": "trapezoidal_rule",
                "curve_basis": "reference_curve_inferred_from_activity_value",
                "concentration_bounds_definition": f"[{auc_lower_bound_scale:g} * K, {auc_upper_bound_scale:g} * K]",
                "grid_size": int(auc_grid_size),
                "concentration_units": "same units as Activity_Value",
                "interpretation": (
                    "AUC is approximated numerically over an inferred Hill reference curve rather than over raw "
                    "experimental dose-response points."
                ),
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
                    "auc_trapezoid_reference_curve": float(row["auc_trapezoid_reference_curve"]),
                    "log10_midpoint_concentration": float(row["log10_midpoint_concentration"]),
                }
                for _, row in representative_rows.iterrows()
            ],
            "notes": [
                "No nonlinear dose-response fitting was performed because "
                "the CSV does not contain raw per-concentration response series for CID 4.",
                "Rows with positive numeric Activity_Value are modeled as reference Hill curves "
                "using Activity_Value as the inferred half-maximal scale K.",
                "The trapezoidal-rule AUC is computed on those inferred reference curves across a concentration "
                "grid scaled relative to each row's inferred K value.",
            ],
        },
    }


def select_hill_plot_representatives(
    hill_df: pd.DataFrame,
) -> tuple[np.ndarray, list[str]]:
    representative_positions = sorted({0, len(hill_df) // 2, len(hill_df) - 1})
    representative_rows = hill_df.iloc[representative_positions]
    representative_k_values = representative_rows["inferred_K_activity_value"].to_numpy(dtype=np.float64)
    representative_labels = [
        f"AID {int(row['BioAssay_AID'])} | {str(row['Activity_Type'])} | "
        f"K={float(row['inferred_K_activity_value']):.4g}"
        for _, row in representative_rows.iterrows()
    ]
    return representative_k_values, representative_labels


def load_bioactivity_dataframe(filename: str) -> pd.DataFrame:
    return pd.read_csv(resolve_data_path(filename))


def build_activity_posterior_dataframe(
    bioactivity_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    activity = bioactivity_df["Activity"].astype("string").str.strip().str.upper().fillna("UNSPECIFIED")
    active_mask = activity.eq("ACTIVE")
    inactive_mask = activity.eq("INACTIVE")
    unspecified_mask = activity.eq("UNSPECIFIED")
    binary_mask = active_mask | inactive_mask

    posterior_df = bioactivity_df.loc[binary_mask].copy()
    posterior_df["Activity"] = activity.loc[binary_mask].str.title()
    posterior_df["Activity_Type"] = posterior_df["Activity_Type"].astype("string").str.strip().fillna("Unknown")
    posterior_df["Target_Name"] = posterior_df["Target_Name"].astype("string").str.strip().fillna("Unknown")
    posterior_df["BioAssay_Name"] = posterior_df["BioAssay_Name"].astype("string").str.strip().fillna("Unknown")
    posterior_df = posterior_df.sort_values(by=["Activity", "BioAssay_AID", "Bioactivity_ID"]).reset_index(drop=True)

    counts = {
        "total_rows": int(len(bioactivity_df)),
        "active_rows": int(active_mask.sum()),
        "inactive_rows": int(inactive_mask.sum()),
        "unspecified_rows": int(unspecified_mask.sum()),
        "other_activity_rows": int((~(active_mask | inactive_mask | unspecified_mask)).sum()),
        "retained_binary_rows": int(len(posterior_df)),
        "dropped_non_binary_rows": int(len(bioactivity_df) - len(posterior_df)),
        "retained_unique_bioassays": int(posterior_df["BioAssay_AID"].nunique()),
    }

    if posterior_df.empty:
        raise ValueError("No Active/Inactive rows were found in the bioactivity dataset")

    return posterior_df, counts


def summarize_bioactivity_posterior_analysis(
    posterior_df: pd.DataFrame,
    counts: dict[str, int],
    prior_alpha: float = DEFAULT_POSTERIOR_PRIOR_ALPHA,
    prior_beta: float = DEFAULT_POSTERIOR_PRIOR_BETA,
    credible_interval: float = DEFAULT_POSTERIOR_CREDIBLE_INTERVAL,
) -> dict:
    if prior_alpha <= 0 or prior_beta <= 0:
        raise ValueError("Posterior prior parameters must be positive")
    if not 0 < credible_interval < 1:
        raise ValueError("Credible interval mass must be between 0 and 1")

    active_count = counts["active_rows"]
    inactive_count = counts["inactive_rows"]
    retained_count = counts["retained_binary_rows"]
    posterior_alpha = prior_alpha + active_count
    posterior_beta = prior_beta + inactive_count
    tail_probability = (1.0 - credible_interval) / 2.0
    interval_lower, interval_upper = stats.beta.ppf(
        [tail_probability, 1.0 - tail_probability],
        posterior_alpha,
        posterior_beta,
    )
    posterior_mean = posterior_alpha / (posterior_alpha + posterior_beta)
    posterior_variance = (posterior_alpha * posterior_beta) / (
        ((posterior_alpha + posterior_beta) ** 2) * (posterior_alpha + posterior_beta + 1.0)
    )
    posterior_mode = None
    if posterior_alpha > 1.0 and posterior_beta > 1.0:
        posterior_mode = (posterior_alpha - 1.0) / (posterior_alpha + posterior_beta - 2.0)

    representative_positions = sorted({0, len(posterior_df) // 2, len(posterior_df) - 1})
    representative_rows = posterior_df.iloc[representative_positions]

    return {
        "row_counts": counts,
        "posterior": {
            "prior": {
                "family": "beta",
                "alpha": float(prior_alpha),
                "beta": float(prior_beta),
            },
            "likelihood": {
                "family": "binomial",
                "success_label": "Active",
                "failure_label": "Inactive",
            },
            "posterior_distribution": {
                "family": "beta",
                "alpha": float(posterior_alpha),
                "beta": float(posterior_beta),
            },
            "summary": {
                "posterior_mean_probability_active": float(posterior_mean),
                "posterior_median_probability_active": float(stats.beta.median(posterior_alpha, posterior_beta)),
                "posterior_mode_probability_active": None if posterior_mode is None else float(posterior_mode),
                "posterior_variance": float(posterior_variance),
                "credible_interval_probability_active": {
                    "mass": float(credible_interval),
                    "lower": float(interval_lower),
                    "upper": float(interval_upper),
                },
                "posterior_probability_active_gt_0_5": float(
                    1.0 - stats.beta.cdf(0.5, posterior_alpha, posterior_beta)
                ),
                "observed_active_fraction_in_retained_rows": float(active_count / retained_count),
            },
        },
        "analysis": {
            "target_quantity": "P(Active | CID=4)",
            "model": "Beta-Binomial conjugate update",
            "update_equations": {
                "posterior_alpha": "alpha_post = alpha_prior + active_count",
                "posterior_beta": "beta_post = beta_prior + inactive_count",
                "posterior_mean": "E[p | data] = alpha_post / (alpha_post + beta_post)",
            },
            "binary_evidence_definition": {
                "retained_labels": ["Active", "Inactive"],
                "excluded_labels": ["Unspecified"],
                "interpretation": "Unspecified rows are excluded from the binary posterior update "
                "and reported only in row counts.",
            },
            "representative_rows": [
                {
                    "Bioactivity_ID": int(row["Bioactivity_ID"]),
                    "BioAssay_AID": int(row["BioAssay_AID"]),
                    "Activity": str(row["Activity"]),
                    "Activity_Type": str(row["Activity_Type"]),
                    "Target_Name": str(row["Target_Name"]),
                    "BioAssay_Name": str(row["BioAssay_Name"]),
                }
                for _, row in representative_rows.iterrows()
            ],
            "notes": [
                "This posterior is an aggregate CID 4 activity probability across retained binary bioassay outcomes.",
                "The update uses a Beta(1,1) prior and treats Active/Inactive outcomes as exchangeable "
                "Bernoulli evidence. Rows labeled Unspecified are kept out of the posterior update so "
                "they do not contribute artificial failures.",
            ],
        },
    }


def build_activity_aid_type_chi_square_dataframe(
    posterior_df: pd.DataFrame,
    counts: dict[str, int],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    aid_type = posterior_df["Aid_Type"].astype("string").str.strip().fillna("Unknown")
    aid_type = aid_type.mask(aid_type.eq(""), "Unknown")
    contingency_table = pd.crosstab(posterior_df["Activity"], aid_type, dropna=False)
    contingency_table = contingency_table.sort_index().sort_index(axis=1)
    contingency_table.index.name = "Activity"
    contingency_table.columns.name = "Aid_Type"

    contingency_df = (
        contingency_table.stack(future_stack=True)
        .rename("observed_count")
        .reset_index()
        .sort_values(by=["Activity", "Aid_Type"])
        .reset_index(drop=True)
    )

    chi_square_counts = {
        **counts,
        "retained_rows_with_aid_type": int(len(posterior_df)),
        "activity_levels_tested": int(contingency_table.shape[0]),
        "aid_type_levels_tested": int(contingency_table.shape[1]),
    }

    if contingency_table.empty:
        raise ValueError("No Activity/Aid_Type contingency rows were found in the bioactivity dataset")

    return contingency_table, contingency_df, chi_square_counts


def compute_activity_aid_type_chi_square(
    contingency_table: pd.DataFrame,
    min_expected_count_threshold: float = DEFAULT_CHI_SQUARE_EXPECTED_COUNT_THRESHOLD,
) -> tuple[pd.DataFrame, dict[str, float | int | bool | None | str]]:
    if min_expected_count_threshold <= 0:
        raise ValueError("Chi-square expected-count threshold must be positive")

    observed = contingency_table.to_numpy(dtype=np.float64)
    has_minimum_shape = observed.shape[0] >= 2 and observed.shape[1] >= 2
    expected_df = pd.DataFrame(
        index=contingency_table.index,
        columns=contingency_table.columns,
        dtype=np.float64,
    )

    if not has_minimum_shape:
        expected_df.loc[:, :] = np.nan
        return expected_df, {
            "computed": False,
            "reason_not_computed": "Chi-square test requires at least two observed Activity levels "
            "and two Aid_Type levels after binary filtering.",
            "chi2_statistic": None,
            "p_value": None,
            "degrees_of_freedom": None,
            "minimum_expected_count_threshold": float(min_expected_count_threshold),
            "sparse_expected_cell_count": None,
            "sparse_expected_cell_fraction": None,
        }

    chi2_statistic, p_value, degrees_of_freedom, expected = stats.chi2_contingency(observed)
    expected_df = pd.DataFrame(expected, index=contingency_table.index, columns=contingency_table.columns)
    sparse_expected_mask = expected_df.lt(min_expected_count_threshold)
    sparse_expected_cell_count = int(sparse_expected_mask.to_numpy(dtype=np.int64).sum())
    sparse_expected_cell_fraction = sparse_expected_cell_count / float(expected_df.size)

    return expected_df, {
        "computed": True,
        "reason_not_computed": None,
        "chi2_statistic": float(chi2_statistic),
        "p_value": float(p_value),
        "degrees_of_freedom": int(degrees_of_freedom),
        "minimum_expected_count_threshold": float(min_expected_count_threshold),
        "sparse_expected_cell_count": sparse_expected_cell_count,
        "sparse_expected_cell_fraction": float(sparse_expected_cell_fraction),
    }


def summarize_activity_aid_type_chi_square_analysis(
    contingency_table: pd.DataFrame,
    contingency_df: pd.DataFrame,
    expected_df: pd.DataFrame,
    counts: dict[str, int],
    chi_square_metrics: dict[str, float | int | bool | None | str],
) -> dict:
    representative_cells = contingency_df.sort_values(
        by=["observed_count", "Activity", "Aid_Type"], ascending=[False, True, True]
    )
    representative_cells = representative_cells.head(3).reset_index(drop=True)

    observed_counts = {
        str(activity): {str(aid_type): int(value) for aid_type, value in row.items()}
        for activity, row in contingency_table.to_dict(orient="index").items()
    }
    expected_counts = {
        str(activity): {str(aid_type): None if pd.isna(value) else float(value) for aid_type, value in row.items()}
        for activity, row in expected_df.to_dict(orient="index").items()
    }

    return {
        "row_counts": counts,
        "contingency_table": {
            "activity_levels": [str(value) for value in contingency_table.index.tolist()],
            "aid_type_levels": [str(value) for value in contingency_table.columns.tolist()],
            "observed_counts": observed_counts,
            "expected_counts": expected_counts,
        },
        "chi_square_test": {
            "variables": {
                "row": "Activity",
                "column": "Aid_Type",
            },
            "null_hypothesis": "Activity and Aid_Type are statistically independent within "
            "the retained binary bioactivity rows.",
            "alternative_hypothesis": "Activity and Aid_Type are statistically associated within "
            "the retained binary bioactivity rows.",
            "computed": bool(chi_square_metrics["computed"]),
            "reason_not_computed": chi_square_metrics["reason_not_computed"],
            "chi2_statistic": chi_square_metrics["chi2_statistic"],
            "p_value": chi_square_metrics["p_value"],
            "degrees_of_freedom": chi_square_metrics["degrees_of_freedom"],
            "minimum_expected_count_threshold": float(chi_square_metrics["minimum_expected_count_threshold"]),
            "sparse_expected_cell_count": chi_square_metrics["sparse_expected_cell_count"],
            "sparse_expected_cell_fraction": chi_square_metrics["sparse_expected_cell_fraction"],
        },
        "analysis": {
            "target_quantity": "Activity ⟂ Aid_Type",
            "model": "Pearson chi-square test of independence",
            "binary_evidence_definition": {
                "retained_labels": ["Active", "Inactive"],
                "excluded_labels": ["Unspecified"],
                "interpretation": "The chi-square table is built from the same binary Activity evidence "
                "used by the posterior analysis.",
            },
            "representative_cells": [
                {
                    "Activity": str(row["Activity"]),
                    "Aid_Type": str(row["Aid_Type"]),
                    "observed_count": int(row["observed_count"]),
                    "expected_count": None
                    if pd.isna(expected_df.loc[row["Activity"], row["Aid_Type"]])
                    else float(expected_df.loc[row["Activity"], row["Aid_Type"]]),
                }
                for _, row in representative_cells.iterrows()
            ],
            "notes": [
                "Rows with Activity = Unspecified and other non-binary Activity labels are excluded "
                "before the contingency table is built.",
                "Aid_Type values are used as observed in the CSV after trimming whitespace "
                "and filling blanks with Unknown.",
                "If fewer than two observed Activity levels or fewer than two Aid_Type levels remain after filtering, "
                "the summary records that the chi-square test is not statistically identifiable on this dataset slice.",
            ],
        },
    }


def build_assay_activity_binomial_dataframe(
    posterior_df: pd.DataFrame,
    counts: dict[str, int],
) -> tuple[pd.DataFrame, dict[str, int]]:
    assay_df = (
        posterior_df.groupby("BioAssay_AID", dropna=False)
        .agg(
            retained_binary_rows=("Activity", "size"),
            active_rows=("Activity", lambda values: int(values.eq("Active").sum())),
            inactive_rows=("Activity", lambda values: int(values.eq("Inactive").sum())),
            sample_activity_type=("Activity_Type", "first"),
            sample_target_name=("Target_Name", "first"),
            sample_bioassay_name=("BioAssay_Name", "first"),
        )
        .reset_index()
    )
    assay_df["mixed_evidence"] = assay_df["active_rows"].gt(0) & assay_df["inactive_rows"].gt(0)
    assay_df["assay_activity"] = np.where(assay_df["active_rows"].gt(0), "Active", "Inactive")
    assay_df = assay_df.sort_values(by=["assay_activity", "BioAssay_AID"]).reset_index(drop=True)

    assay_counts = {
        **counts,
        "assay_trials": int(len(assay_df)),
        "active_assay_trials": int(assay_df["assay_activity"].eq("Active").sum()),
        "inactive_assay_trials": int(assay_df["assay_activity"].eq("Inactive").sum()),
        "mixed_evidence_assay_trials": int(assay_df["mixed_evidence"].sum()),
        "unanimous_active_assay_trials": int((assay_df["active_rows"] > 0).sum() - assay_df["mixed_evidence"].sum()),
        "unanimous_inactive_assay_trials": int(
            (assay_df["inactive_rows"] > 0).sum() - assay_df["mixed_evidence"].sum()
        ),
    }

    if assay_df.empty:
        raise ValueError("No assay-level Active/Inactive trials were found in the bioactivity dataset")

    return assay_df, assay_counts


def build_bioactivity_binomial_pmf_dataframe(
    assay_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float | int]]:
    assay_trials = int(len(assay_df))
    active_assay_trials = int(assay_df["assay_activity"].eq("Active").sum())
    success_probability = active_assay_trials / assay_trials
    k_values = np.arange(assay_trials + 1, dtype=np.int64)
    pmf_values = stats.binom.pmf(k_values, assay_trials, success_probability)
    cumulative_leq_values = stats.binom.cdf(k_values, assay_trials, success_probability)
    cumulative_geq_values = stats.binom.sf(
        np.maximum(k_values - 1, DEFAULT_BINOMIAL_TAIL_THRESHOLD),
        assay_trials,
        success_probability,
    )
    pmf_df = pd.DataFrame(
        {
            "k_active": k_values,
            "probability": pmf_values,
            "cumulative_probability_leq_k": cumulative_leq_values,
            "cumulative_probability_geq_k": cumulative_geq_values,
        }
    )

    return pmf_df, {
        "assay_trials": assay_trials,
        "active_assay_trials": active_assay_trials,
        "success_probability_active_assay": float(success_probability),
        "observed_pmf_at_active_assay_count": float(pmf_values[active_assay_trials]),
        "observed_cumulative_probability_leq_active_assay_count": float(cumulative_leq_values[active_assay_trials]),
        "observed_cumulative_probability_geq_active_assay_count": float(cumulative_geq_values[active_assay_trials]),
    }


def summarize_bioactivity_binomial_analysis(
    assay_df: pd.DataFrame,
    pmf_df: pd.DataFrame,
    counts: dict[str, int],
    binomial_metrics: dict[str, float | int],
) -> dict:
    assay_trials = int(binomial_metrics["assay_trials"])
    active_assay_trials = int(binomial_metrics["active_assay_trials"])
    success_probability = float(binomial_metrics["success_probability_active_assay"])
    representative_positions = sorted({0, len(assay_df) // 2, len(assay_df) - 1})
    representative_rows = assay_df.iloc[representative_positions]

    return {
        "row_counts": counts,
        "binomial": {
            "trial_definition": {
                "unit": "unique_BioAssay_AID",
                "success_label": "Active assay",
                "failure_label": "Inactive assay",
                "assay_resolution_rule": "Active wins if any retained row for the assay is Active; "
                "otherwise the assay is Inactive.",
            },
            "parameters": {
                "n_assays": assay_trials,
                "observed_active_assays": active_assay_trials,
                "success_probability_active_assay": success_probability,
            },
            "summary": {
                "pmf_at_observed_active_assay_count": float(binomial_metrics["observed_pmf_at_active_assay_count"]),
                "cumulative_probability_leq_observed_active_assay_count": float(
                    binomial_metrics["observed_cumulative_probability_leq_active_assay_count"]
                ),
                "cumulative_probability_geq_observed_active_assay_count": float(
                    binomial_metrics["observed_cumulative_probability_geq_active_assay_count"]
                ),
                "binomial_mean_active_assays": float(assay_trials * success_probability),
                "binomial_variance_active_assays": float(
                    assay_trials * success_probability * (1.0 - success_probability)
                ),
                "pmf_probability_sum": float(pmf_df["probability"].sum()),
            },
        },
        "analysis": {
            "target_quantity": "P(K = k active assays in n assays)",
            "model": "Binomial distribution with plug-in success probability",
            "equation": "P(K = k) = C(n, k) p^k (1-p)^(n-k)",
            "parameter_estimation": "p is estimated as the observed active assay fraction active_assays / n_assays.",
            "representative_assays": [
                {
                    "BioAssay_AID": int(row["BioAssay_AID"]),
                    "assay_activity": str(row["assay_activity"]),
                    "retained_binary_rows": int(row["retained_binary_rows"]),
                    "active_rows": int(row["active_rows"]),
                    "inactive_rows": int(row["inactive_rows"]),
                    "mixed_evidence": bool(row["mixed_evidence"]),
                    "Activity_Type": str(row["sample_activity_type"]),
                    "Target_Name": str(row["sample_target_name"]),
                    "BioAssay_Name": str(row["sample_bioassay_name"]),
                }
                for _, row in representative_rows.iterrows()
            ],
            "notes": [
                "The binomial model operates at the assay level rather than the raw retained-row level.",
                "Rows with Activity = Unspecified are excluded before assay-level collapsing, consistent "
                "with the posterior analysis. This is a frequentist plug-in binomial model using "
                "the observed assay-level active fraction, not a posterior-predictive distribution.",
            ],
        },
    }


def build_pic50_dataframe(
    bioactivity_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
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


def build_activity_value_statistics_dataframe(
    bioactivity_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    activity_value = pd.to_numeric(bioactivity_df["Activity_Value"], errors="coerce")
    numeric_mask = activity_value.notna()
    positive_numeric_mask = numeric_mask & activity_value.gt(0)
    zero_mask = numeric_mask & activity_value.eq(0)
    negative_mask = numeric_mask & activity_value.lt(0)

    selected_columns = [
        "Bioactivity_ID",
        "BioAssay_AID",
        "Activity",
        "Aid_Type",
        "Activity_Type",
        "Target_Name",
        "BioAssay_Name",
        "Activity_Value",
    ]
    activity_value_df = bioactivity_df.loc[positive_numeric_mask, selected_columns].copy()
    activity_value_df["Activity_Value"] = activity_value.loc[positive_numeric_mask]
    activity_value_df["Activity"] = activity_value_df["Activity"].astype("string").str.strip().fillna("Unknown")
    activity_value_df["Aid_Type"] = activity_value_df["Aid_Type"].astype("string").str.strip().fillna("Unknown")
    activity_value_df["Aid_Type"] = activity_value_df["Aid_Type"].mask(activity_value_df["Aid_Type"].eq(""), "Unknown")
    activity_value_df["Activity_Type"] = (
        activity_value_df["Activity_Type"].astype("string").str.strip().fillna("Unknown")
    )
    activity_value_df["Target_Name"] = activity_value_df["Target_Name"].astype("string").str.strip().fillna("Unknown")
    activity_value_df["BioAssay_Name"] = (
        activity_value_df["BioAssay_Name"].astype("string").str.strip().fillna("Unknown")
    )
    activity_value_df = activity_value_df.sort_values(
        by=["Activity_Value", "BioAssay_AID", "Bioactivity_ID"],
        ascending=[False, True, True],
    ).reset_index(drop=True)

    counts = {
        "total_rows": int(len(bioactivity_df)),
        "rows_with_numeric_activity_value": int(numeric_mask.sum()),
        "positive_numeric_rows": int(positive_numeric_mask.sum()),
        "zero_activity_value_rows": int(zero_mask.sum()),
        "negative_activity_value_rows": int(negative_mask.sum()),
        "non_numeric_or_missing_activity_value_rows": int((~numeric_mask).sum()),
        "retained_positive_numeric_rows": int(len(activity_value_df)),
        "dropped_rows": int(len(bioactivity_df) - len(activity_value_df)),
        "retained_unique_bioassays": int(activity_value_df["BioAssay_AID"].nunique()),
    }

    if activity_value_df.empty:
        raise ValueError("No positive numeric Activity_Value rows were found in the bioactivity dataset")

    return activity_value_df, counts


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
            "observed_ic50_domain_uM": [
                float(ic50_values.min()),
                float(ic50_values.max()),
            ],
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


def summarize_activity_value_statistics_analysis(
    activity_value_df: pd.DataFrame,
    counts: dict[str, int],
    shapiro_alpha: float = DEFAULT_SHAPIRO_ALPHA,
    shapiro_max_sample_size: int = DEFAULT_SHAPIRO_MAX_SAMPLE_SIZE,
) -> dict:
    if not 0 < shapiro_alpha < 1:
        raise ValueError("Shapiro-Wilk alpha must be between 0 and 1")
    if shapiro_max_sample_size < 3:
        raise ValueError("Shapiro-Wilk maximum sample size must be at least 3")

    values = activity_value_df["Activity_Value"].to_numpy(dtype=np.float64)
    quantiles = np.quantile(values, [0.25, 0.5, 0.75])
    sample_size = int(values.size)
    mean_value = float(np.mean(values))
    variance_value = float(np.var(values, ddof=1)) if sample_size > 1 else 0.0
    skewness_value = float(stats.skew(values, bias=False)) if sample_size > 2 else None

    shapiro_summary: dict[str, object] = {
        "computed": False,
        "reason_not_computed": None,
        "sample_size": sample_size,
        "alpha": float(shapiro_alpha),
        "statistic": None,
        "p_value": None,
        "reject_normality": None,
        "interpretation": None,
    }
    if sample_size < 3:
        shapiro_summary["reason_not_computed"] = "Shapiro-Wilk requires at least 3 retained observations."
        shapiro_summary["interpretation"] = (
            "Normality was not tested because too few positive numeric rows were retained."
        )
    elif sample_size > shapiro_max_sample_size:
        shapiro_summary["reason_not_computed"] = (
            "Shapiro-Wilk was skipped because SciPy warns that p-values may be inaccurate for samples larger than "
            f"{shapiro_max_sample_size}."
        )
        shapiro_summary["interpretation"] = (
            "Normality was not tested because the retained sample exceeds the configured Shapiro-Wilk limit."
        )
    else:
        statistic, p_value = stats.shapiro(values)
        reject_normality = bool(p_value < shapiro_alpha)
        shapiro_summary.update(
            {
                "computed": True,
                "statistic": float(statistic),
                "p_value": float(p_value),
                "reject_normality": reject_normality,
                "interpretation": (
                    "Reject the null hypothesis of normality at the configured alpha threshold."
                    if reject_normality
                    else "Do not reject the null hypothesis of normality at the configured alpha threshold."
                ),
            }
        )

    representative_positions = sorted({0, len(activity_value_df) // 2, len(activity_value_df) - 1})
    representative_rows = activity_value_df.iloc[representative_positions]

    return {
        "row_counts": counts,
        "statistics": {
            "sample_size": sample_size,
            "mean": mean_value,
            "variance": variance_value,
            "variance_definition": "sample_variance_ddof_1",
            "skewness": skewness_value,
            "min": float(values.min()),
            "q25": float(quantiles[0]),
            "median": float(quantiles[1]),
            "q75": float(quantiles[2]),
            "max": float(values.max()),
        },
        "normality_test": {
            "name": "Shapiro-Wilk",
            **shapiro_summary,
        },
        "analysis": {
            "target_quantity": "Positive numeric Activity_Value distribution",
            "retained_row_definition": {
                "predicate": "Activity_Value is numeric and strictly greater than 0",
                "excluded_rows": [
                    "missing Activity_Value",
                    "non-numeric Activity_Value",
                    "Activity_Value = 0",
                    "Activity_Value < 0",
                ],
            },
            "representative_rows": [
                {
                    "Bioactivity_ID": int(row["Bioactivity_ID"]),
                    "BioAssay_AID": int(row["BioAssay_AID"]),
                    "Activity": str(row["Activity"]),
                    "Aid_Type": str(row["Aid_Type"]),
                    "Activity_Type": str(row["Activity_Type"]),
                    "Activity_Value": float(row["Activity_Value"]),
                }
                for _, row in representative_rows.iterrows()
            ],
            "notes": [
                "The retained distribution aggregates all positive numeric "
                "Activity_Value rows regardless of Activity_Type.",
                "Variance is reported as the sample variance with ddof = 1 "
                "to reflect descriptive statistics over the retained sample.",
                "The diagnostic plot pairs a log-scale histogram with a normal "
                "Q-Q panel when the retained sample supports it.",
            ],
        },
    }


def build_atom_element_entropy_dataframe(
    atom_feature_df: pd.DataFrame,
    required_elements: tuple[str, ...] = REQUIRED_ATOM_ENTROPY_ELEMENTS,
) -> tuple[pd.DataFrame, dict[str, int], dict[str, int]]:
    if "symbol" not in atom_feature_df.columns:
        raise ValueError("Atom feature matrix is missing the required symbol column")

    symbols = atom_feature_df["symbol"].astype("string").str.strip().str.upper()
    symbol_counts = symbols.value_counts(dropna=False).to_dict()
    required_counts = {element: int(symbol_counts.get(element, 0)) for element in required_elements}
    unexpected_counts = {
        str(element): int(count)
        for element, count in symbol_counts.items()
        if element not in required_elements and pd.notna(element) and str(element) != ""
    }

    retained_total = int(sum(required_counts.values()))
    if retained_total <= 0:
        raise ValueError("No required O/N/C/H atom symbols were found in the atom feature matrix")

    entropy_df = pd.DataFrame(
        {
            "element": list(required_elements),
            "count": [required_counts[element] for element in required_elements],
        }
    )
    entropy_df["proportion"] = entropy_df["count"] / retained_total
    entropy_df["log_proportion"] = entropy_df["proportion"].apply(
        lambda value: None if value <= 0 else float(np.log(value))
    )
    entropy_df["shannon_contribution"] = entropy_df["proportion"].apply(
        lambda value: 0.0 if value <= 0 else float(-value * np.log(value))
    )

    counts = {
        "total_atom_rows": int(len(atom_feature_df)),
        "retained_atom_rows": retained_total,
        "required_element_categories": int(len(required_elements)),
        "observed_required_element_categories": int((entropy_df["count"] > 0).sum()),
        "unexpected_element_rows": int(sum(unexpected_counts.values())),
        "unexpected_element_categories": int(len(unexpected_counts)),
    }

    return entropy_df, counts, unexpected_counts


def summarize_atom_element_entropy_analysis(
    entropy_df: pd.DataFrame,
    counts: dict[str, int],
    unexpected_counts: dict[str, int],
) -> dict:
    entropy_value = float(entropy_df["shannon_contribution"].sum())
    unique_retained_elements = int((entropy_df["count"] > 0).sum())
    maximum_entropy = float(np.log(unique_retained_elements)) if unique_retained_elements > 1 else 0.0
    normalized_entropy = float(entropy_value / maximum_entropy) if maximum_entropy > 0 else 0.0
    dominant_row = entropy_df.sort_values(by=["count", "element"], ascending=[False, True]).iloc[0]

    return {
        "row_counts": counts,
        "entropy": {
            "formula": "H = -sum(p_i * log(p_i))",
            "log_base": "natural_log",
            "value": entropy_value,
            "maximum_entropy_for_observed_support": maximum_entropy,
            "normalized_entropy": normalized_entropy,
        },
        "distribution": {
            row["element"]: {
                "count": int(row["count"]),
                "proportion": float(row["proportion"]),
                "log_proportion": None if pd.isna(row["log_proportion"]) else float(row["log_proportion"]),
                "shannon_contribution": float(row["shannon_contribution"]),
            }
            for _, row in entropy_df.iterrows()
        },
        "analysis": {
            "target_quantity": "Atom element entropy over O/N/C/H proportions",
            "required_elements": list(REQUIRED_ATOM_ENTROPY_ELEMENTS),
            "unique_retained_elements": unique_retained_elements,
            "dominant_element": {
                "element": str(dominant_row["element"]),
                "count": int(dominant_row["count"]),
                "proportion": float(dominant_row["proportion"]),
            },
            "unexpected_elements": unexpected_counts,
            "notes": [
                "Entropy is computed only over the required O/N/C/H support requested in the README exercise.",
                "Unexpected atom symbols are excluded from the entropy sum and reported separately for transparency.",
                "Normalized entropy uses the maximum entropy over the observed required-element support rather than "
                "the fixed four-element support.",
            ],
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


def compute_adjacency_spectrum(
    adjacency_matrix: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
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


def compute_laplacian_spectrum(
    laplacian_matrix: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
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


def write_distance_matrix(sdf_filename: str):
    work_directory = env_utils.get_data_dir()
    out_dir = get_output_directory(work_directory)
    molecules = load_sdf_molecules(sdf_filename)

    if not molecules:
        raise ValueError(f"No valid molecules found in {sdf_filename}")

    coordinates = extract_3d_coordinates(molecules[IDX1])
    distance_matrix = build_distance_matrix(coordinates)

    output_path = Path(out_dir) / f"{Path(sdf_filename).stem}.distance_matrix.json"

    with output_path.open("w", encoding=UTF_8) as file:
        json.dump(
            {
                "distance_matrix": distance_matrix.tolist(),
                "metadata": {
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


def write_spring_bond_potential_analysis(sdf_filename: str, json_filename: str):
    work_directory = env_utils.get_data_dir()
    out_dir = get_output_directory(work_directory)
    molecules = load_sdf_molecules(sdf_filename)

    if not molecules:
        raise ValueError(f"No valid molecules found in {sdf_filename}")

    molecule = molecules[IDX1]
    coordinates = extract_3d_coordinates(molecule)
    adjacency_matrix = build_adjacency_matrix(json_filename)
    atom_ids = adjacency_matrix.index.tolist()

    if len(atom_ids) != coordinates.shape[0]:
        raise ValueError(
            f"Expected {len(atom_ids)} atom ids from {json_filename}, found {coordinates.shape[0]} coordinates"
        )

    bond_records, atom_gradient_records, pair_metadata = compute_spring_bond_partial_derivative_records(
        atom_ids,
        coordinates,
        adjacency_matrix,
        molecule,
    )
    statistics = summarize_spring_bond_partial_derivatives(bond_records, atom_gradient_records, pair_metadata)
    output_path = Path(out_dir) / f"{Path(sdf_filename).stem}.spring_bond_potential_analysis.json"

    with output_path.open("w", encoding=UTF_8) as file:
        json.dump(
            {
                "atom_ids": atom_ids,
                "bonded_pair_spring_records": bond_records,
                "atom_gradient_records": atom_gradient_records,
                "statistics": statistics,
                "analysis": {
                    "energy_equation": "E_ij = 0.5 * k_ij * (d_ij - d0_ij)^2",
                    "distance_equation": "d_ij = ||r_i - r_j||",
                    "distance_derivative_equation": "dE_ij/dd_ij = k_ij * (d_ij - d0_ij)",
                    "cartesian_gradient_equation": "dE_ij/dr_i = k_ij * (d_ij - d0_ij) * (r_i - r_j) / d_ij",
                    "reaction_gradient_equation": "dE_ij/dr_j = -dE_ij/dr_i",
                    "reference_distance_policy": (
                        "Chemistry-informed lookup keyed by atom symbols and bond order with a covalent-radius fallback"
                    ),
                    "spring_constant_policy": "Bond-order-specific constants for an educational harmonic bond model",
                    "bond_order_spring_constants": {
                        str(bond_order): float(value)
                        for bond_order, value in sorted(DEFAULT_BOND_ORDER_SPRING_CONSTANTS.items())
                    },
                    "reference_distance_lookup_examples_angstrom": {
                        f"{symbol_1}-{symbol_2}-order-{bond_order}": float(distance)
                        for (symbol_1, symbol_2, bond_order), distance in sorted(
                            DEFAULT_REFERENCE_BOND_LENGTHS_ANGSTROM.items()
                        )
                    },
                    "interpretation": (
                        "Positive and negative Cartesian partial derivatives quantify "
                        "how the spring-bond energy changes under infinitesimal coordinate displacements of "
                        "each bonded atom in the current CID 4 conformer."
                    ),
                },
                "metadata": {
                    "atom_count": len(atom_ids),
                    "bonded_pair_count": int(pair_metadata["bonded_pair_count"]),
                    "source_sdf": sdf_filename,
                    "source_bond_json": json_filename,
                    "distance_units": "angstrom",
                    "reference_distance_units": "angstrom",
                    "spring_constant_units": "relative spring units / angstrom^2",
                    "spring_energy_units": "relative spring units",
                    "coordinate_partial_derivative_units": "relative spring units / angstrom",
                    "reference_distance_source_counts": pair_metadata["reference_distance_source_counts"],
                },
            },
            file,
            indent=2,
        )

    log.info("Spring bond potential analysis written to %s", output_path)


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


def write_activity_value_statistics_analysis(filename: str):
    work_directory = env_utils.get_data_dir()
    out_dir = get_output_directory(work_directory)
    bioactivity_df = load_bioactivity_dataframe(filename)
    activity_value_df, counts = build_activity_value_statistics_dataframe(bioactivity_df)
    summary = summarize_activity_value_statistics_analysis(activity_value_df, counts)
    output_stem = Path(filename).stem
    records_output_path = Path(out_dir) / f"{output_stem}.activity_value_statistics.csv"
    summary_output_path = Path(out_dir) / f"{output_stem}.activity_value_statistics.summary.json"
    plot_output_path = Path(out_dir) / f"{output_stem}.activity_value_statistics.png"

    activity_value_df.to_csv(records_output_path, index=False)

    with summary_output_path.open("w", encoding=UTF_8) as file:
        json.dump(summary, file, indent=2)

    plot_activity_value_statistics(
        activity_value_df["Activity_Value"].to_numpy(dtype=np.float64),
        bool(summary["normality_test"]["computed"]),
        str(plot_output_path),
    )

    log.info("Activity_Value statistics rows written to %s", records_output_path)
    log.info("Activity_Value statistics summary written to %s", summary_output_path)
    log.info("Activity_Value statistics plot written to %s", plot_output_path)


def write_bioactivity_posterior_analysis(
    filename: str,
    prior_alpha: float = DEFAULT_POSTERIOR_PRIOR_ALPHA,
    prior_beta: float = DEFAULT_POSTERIOR_PRIOR_BETA,
    credible_interval: float = DEFAULT_POSTERIOR_CREDIBLE_INTERVAL,
):
    work_directory = env_utils.get_data_dir()
    out_dir = get_output_directory(work_directory)
    bioactivity_df = load_bioactivity_dataframe(filename)
    posterior_df, counts = build_activity_posterior_dataframe(bioactivity_df)
    summary = summarize_bioactivity_posterior_analysis(
        posterior_df,
        counts,
        prior_alpha=prior_alpha,
        prior_beta=prior_beta,
        credible_interval=credible_interval,
    )
    output_stem = Path(filename).stem
    records_output_path = Path(out_dir) / f"{output_stem}.activity_posterior_binary_evidence.csv"
    summary_output_path = Path(out_dir) / f"{output_stem}.activity_posterior.summary.json"

    posterior_df.to_csv(records_output_path, index=False)

    with summary_output_path.open("w", encoding=UTF_8) as file:
        json.dump(summary, file, indent=2)

    log.info("Bioactivity posterior evidence rows written to %s", records_output_path)
    log.info("Bioactivity posterior summary written to %s", summary_output_path)


def write_activity_aid_type_chi_square_analysis(filename: str):
    work_directory = env_utils.get_data_dir()
    out_dir = get_output_directory(work_directory)
    bioactivity_df = load_bioactivity_dataframe(filename)
    posterior_df, posterior_counts = build_activity_posterior_dataframe(bioactivity_df)
    contingency_table, contingency_df, chi_square_counts = build_activity_aid_type_chi_square_dataframe(
        posterior_df,
        posterior_counts,
    )
    expected_df, chi_square_metrics = compute_activity_aid_type_chi_square(contingency_table)
    contingency_output_df = contingency_df.copy()
    contingency_output_df["expected_count"] = contingency_output_df.apply(
        lambda row: expected_df.loc[row["Activity"], row["Aid_Type"]],
        axis=1,
    )
    summary = summarize_activity_aid_type_chi_square_analysis(
        contingency_table,
        contingency_output_df,
        expected_df,
        chi_square_counts,
        chi_square_metrics,
    )
    output_stem = Path(filename).stem
    records_output_path = Path(out_dir) / f"{output_stem}.activity_aid_type_chi_square_contingency.csv"
    summary_output_path = Path(out_dir) / f"{output_stem}.activity_aid_type_chi_square.summary.json"

    contingency_output_df.to_csv(records_output_path, index=False)

    with summary_output_path.open("w", encoding=UTF_8) as file:
        json.dump(summary, file, indent=2)

    log.info(
        "Activity vs Aid_Type chi-square contingency rows written to %s",
        records_output_path,
    )
    log.info("Activity vs Aid_Type chi-square summary written to %s", summary_output_path)


def write_bioactivity_binomial_analysis(filename: str):
    work_directory = env_utils.get_data_dir()
    out_dir = get_output_directory(work_directory)
    bioactivity_df = load_bioactivity_dataframe(filename)
    posterior_df, posterior_counts = build_activity_posterior_dataframe(bioactivity_df)
    assay_df, assay_counts = build_assay_activity_binomial_dataframe(posterior_df, posterior_counts)
    pmf_df, binomial_metrics = build_bioactivity_binomial_pmf_dataframe(assay_df)
    summary = summarize_bioactivity_binomial_analysis(assay_df, pmf_df, assay_counts, binomial_metrics)
    output_stem = Path(filename).stem
    records_output_path = Path(out_dir) / f"{output_stem}.activity_binomial_pmf.csv"
    summary_output_path = Path(out_dir) / f"{output_stem}.activity_binomial.summary.json"

    pmf_df.to_csv(records_output_path, index=False)

    with summary_output_path.open("w", encoding=UTF_8) as file:
        json.dump(summary, file, indent=2)

    log.info("Bioactivity binomial PMF rows written to %s", records_output_path)
    log.info("Bioactivity binomial summary written to %s", summary_output_path)


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


def write_atom_element_entropy_analysis(
    sdf_filename: str,
    atom_feature_df: pd.DataFrame | None = None,
):
    work_directory = env_utils.get_data_dir()
    out_dir = get_output_directory(work_directory)
    feature_df = atom_feature_df if atom_feature_df is not None else process_sdf_file(sdf_filename)
    entropy_df, counts, unexpected_counts = build_atom_element_entropy_dataframe(feature_df)
    summary = summarize_atom_element_entropy_analysis(entropy_df, counts, unexpected_counts)
    output_stem = Path(sdf_filename).stem
    records_output_path = Path(out_dir) / f"{output_stem}.atom_element_entropy_proportions.csv"
    summary_output_path = Path(out_dir) / f"{output_stem}.atom_element_entropy.summary.json"
    plot_output_path = Path(out_dir) / f"{output_stem}.atom_element_entropy.png"

    entropy_df.to_csv(records_output_path, index=False)

    with summary_output_path.open("w", encoding=UTF_8) as file:
        json.dump(summary, file, indent=2)

    plot_atom_element_entropy(
        entropy_df["element"].tolist(),
        entropy_df["proportion"].to_numpy(dtype=np.float64),
        float(summary["entropy"]["value"]),
        str(plot_output_path),
    )

    log.info("Atom element entropy rows written to %s", records_output_path)
    log.info("Atom element entropy summary written to %s", summary_output_path)
    log.info("Atom element entropy plot written to %s", plot_output_path)


def main():
    log_settings.configure_logging()
    sdf_filename = "Conformer3D_COMPOUND_CID_4(1).sdf"
    json_filename = "Conformer3D_COMPOUND_CID_4(1).json"
    bioactivity_filename = "pubchem_cid_4_bioactivity.csv"
    atom_feature_df = process_sdf_file(sdf_filename)
    write_atom_gradient_descent_analysis(sdf_filename, atom_feature_df=atom_feature_df)
    write_atom_element_entropy_analysis(sdf_filename, atom_feature_df=atom_feature_df)
    write_distance_matrix(sdf_filename)
    write_bonded_distance_analysis(sdf_filename, json_filename)
    write_bonded_angle_analysis(sdf_filename, json_filename)
    write_spring_bond_potential_analysis(sdf_filename, json_filename)
    adjacency_matrix = write_adjacency_matrix(json_filename)
    write_adjacency_spectrum(json_filename, adjacency_matrix)
    write_laplacian_analysis(json_filename, adjacency_matrix)
    write_bioactivity_analysis(bioactivity_filename)
    write_hill_dose_response_analysis(bioactivity_filename)
    write_activity_value_statistics_analysis(bioactivity_filename)
    write_bioactivity_posterior_analysis(bioactivity_filename)
    write_activity_aid_type_chi_square_analysis(bioactivity_filename)
    write_bioactivity_binomial_analysis(bioactivity_filename)


if __name__ == "__main__":
    main()
