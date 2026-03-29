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

CONFORMER_ATOM_COUNT = 14
NULL_SPACE_TOLERANCE = 1e-10


def reduce_mol_weights(mol_weights: list[float]) -> float:
    return reduce(lambda prev, next: prev + next, mol_weights, 0.0)


def get_output_directory(work_directory: str) -> str:
    out_dir = f"{work_directory}/out"
    fs.create_dir_if_doesnt_exist(out_dir)
    return out_dir


def get_valid_molecules(sdf_file_path: str) -> list[Chem.Mol]:
    with Chem.SDMolSupplier(sdf_file_path) as supplier:
        return [mol for mol in supplier if mol is not None]


def load_conformer_compound(filename: str) -> dict:
    work_directory = env_utils.get_data_dir()
    json_file_path = Path(work_directory) / filename

    with json_file_path.open(encoding=UTF_8) as file:
        conformer_data = json.load(file)

    return conformer_data["PC_Compounds"][IDX1]


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
    sdf_file_path = f"{work_directory}/{filename}"
    molecules = get_valid_molecules(sdf_file_path)

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
    write_image(sdf_file_path, out_img_filepath)


def main():
    log_settings.configure_logging()
    sdf_filename = "Conformer3D_COMPOUND_CID_4(1).sdf"
    json_filename = "Conformer3D_COMPOUND_CID_4(1).json"
    process_sdf_file(sdf_filename)
    adjacency_matrix = write_adjacency_matrix(json_filename)
    write_adjacency_spectrum(json_filename, adjacency_matrix)
    write_laplacian_analysis(json_filename, adjacency_matrix)


if __name__ == "__main__":
    main()
