import json
import logging as log
from functools import reduce
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
from matplotlib_utils import plot_pic50_transform

CONFORMER_ATOM_COUNT = 14
NULL_SPACE_TOLERANCE = 1e-10


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


def process_sdf_file(filename: str):
    work_directory = env_utils.get_data_dir()
    sdf_file_path = resolve_data_path(filename)
    molecules = load_sdf_molecules(filename)

    avg_mol_weights = [Descriptors.MolWt(mol) for mol in molecules]
    log.info(f"Average molecular weight: {reduce_mol_weights(avg_mol_weights)}")
    mol_exact_mass = [Descriptors.ExactMolWt(mol) for mol in molecules]
    log.info(f"Exact molecular mass: {reduce_mol_weights(mol_exact_mass)}")

    out_dir = get_output_directory(work_directory)

    atom_data = []

    for mol in molecules:
        for atom in mol.GetAtoms():
            atom_properties = {
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
            atom_data.append(atom_properties)

    df = pd.DataFrame(atom_data)
    df.to_json(f"{out_dir}/{filename}.json")

    out_img_filepath = f"{out_dir}/{filename.split('.')[IDX1]}.png"
    write_image(str(sdf_file_path), out_img_filepath)


def main():
    log_settings.configure_logging()
    sdf_filename = "Conformer3D_COMPOUND_CID_4(1).sdf"
    json_filename = "Conformer3D_COMPOUND_CID_4(1).json"
    bioactivity_filename = "pubchem_cid_4_bioactivity.csv"
    process_sdf_file(sdf_filename)
    write_distance_matrix(sdf_filename, json_filename)
    write_bonded_distance_analysis(sdf_filename, json_filename)
    adjacency_matrix = write_adjacency_matrix(json_filename)
    write_adjacency_spectrum(json_filename, adjacency_matrix)
    write_laplacian_analysis(json_filename, adjacency_matrix)
    write_bioactivity_analysis(bioactivity_filename)


if __name__ == "__main__":
    main()
