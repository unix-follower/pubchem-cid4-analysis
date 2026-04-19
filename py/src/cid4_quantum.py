import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Protocol

import psi4
from rdkit import Chem

HARTREE_TO_KCAL_PER_MOL = 627.509474
DEFAULT_METHOD = "hf"
DEFAULT_BASIS = "sto-3g"
DEFAULT_CHARGE = 0
DEFAULT_MULTIPLICITY = 1
DEFAULT_MAX_CONFORMER_INDEX = 6


@dataclass(frozen=True)
class QuantumCalculationSettings:
    engine: str = "psi4"
    method: str = DEFAULT_METHOD
    basis: str = DEFAULT_BASIS
    charge: int = DEFAULT_CHARGE
    multiplicity: int = DEFAULT_MULTIPLICITY
    scf_type: str = "pk"
    e_convergence: float = 1e-8
    d_convergence: float = 1e-8
    input_units: str = "angstrom"


@dataclass(frozen=True)
class QuantumConformerInput:
    conformer_index: int
    source_filename: str
    atom_symbols: tuple[str, ...]
    coordinates_angstrom: tuple[tuple[float, float, float], ...]
    geometry_hash: str


@dataclass(frozen=True)
class QuantumConformerResult:
    conformer_index: int
    source_filename: str
    status: str
    geometry_hash: str
    method: str
    basis: str
    charge: int
    multiplicity: int
    engine: str
    total_energy_hartree: float | None = None
    relative_energy_hartree: float | None = None
    relative_energy_kcal_mol: float | None = None
    rank: int | None = None
    engine_version: str | None = None
    error: str | None = None


class QuantumEnergyRunner(Protocol):
    def __call__(
        self,
        conformer: QuantumConformerInput,
        settings: QuantumCalculationSettings,
    ) -> tuple[float, dict[str, object]]: ...


def discover_conformer_sdf_paths(
    data_dir: str | Path,
    max_conformer_index: int = DEFAULT_MAX_CONFORMER_INDEX,
) -> list[Path]:
    base_dir = Path(data_dir)
    paths: list[Path] = []

    for index in range(1, max_conformer_index + 1):
        path = base_dir / f"Conformer3D_COMPOUND_CID_4({index}).sdf"
        if not path.is_file():
            raise FileNotFoundError(f"Missing conformer SDF file: {path}")
        paths.append(path)

    return paths


def load_quantum_conformer_inputs(
    data_dir: str | Path,
    max_conformer_index: int = DEFAULT_MAX_CONFORMER_INDEX,
) -> list[QuantumConformerInput]:
    conformers: list[QuantumConformerInput] = []

    for path in discover_conformer_sdf_paths(data_dir, max_conformer_index=max_conformer_index):
        conformer_index = parse_conformer_index(path.name)
        molecule = load_single_sdf_molecule(path)
        conformers.append(build_quantum_conformer_input(conformer_index, path.name, molecule))

    return conformers


def parse_conformer_index(filename: str) -> int:
    start = filename.find("(")
    end = filename.find(")", start + 1)
    if start == -1 or end == -1:
        raise ValueError(f"Filename does not encode a conformer index: {filename}")
    return int(filename[start + 1 : end])


def load_single_sdf_molecule(path: str | Path) -> Any:
    sdf_path = Path(path)
    with Chem.SDMolSupplier(str(sdf_path), removeHs=False) as supplier:
        molecules = [mol for mol in supplier if mol is not None]

    if len(molecules) != 1:
        raise ValueError(f"Expected exactly one molecule in {sdf_path}, found {len(molecules)}")

    return molecules[0]


def build_quantum_conformer_input(
    conformer_index: int,
    source_filename: str,
    molecule: Any,
) -> QuantumConformerInput:
    if molecule.GetNumConformers() == 0:
        raise ValueError(f"Molecule {source_filename} does not contain 3D coordinates")

    conformer = molecule.GetConformer()
    atom_symbols = tuple(atom.GetSymbol() for atom in molecule.GetAtoms())
    coordinates = tuple(
        (
            float(conformer.GetAtomPosition(atom_index).x),
            float(conformer.GetAtomPosition(atom_index).y),
            float(conformer.GetAtomPosition(atom_index).z),
        )
        for atom_index in range(molecule.GetNumAtoms())
    )
    geometry_hash = build_geometry_hash(atom_symbols, coordinates)

    return QuantumConformerInput(
        conformer_index=conformer_index,
        source_filename=source_filename,
        atom_symbols=atom_symbols,
        coordinates_angstrom=coordinates,
        geometry_hash=geometry_hash,
    )


def build_geometry_hash(
    atom_symbols: tuple[str, ...],
    coordinates_angstrom: tuple[tuple[float, float, float], ...],
) -> str:
    normalized_payload = {
        "atom_symbols": atom_symbols,
        "coordinates_angstrom": [
            [round(x_coord, 8), round(y_coord, 8), round(z_coord, 8)]
            for x_coord, y_coord, z_coord in coordinates_angstrom
        ],
    }
    digest = hashlib.sha256(json.dumps(normalized_payload, sort_keys=True).encode("utf-8"))
    return digest.hexdigest()


def build_psi4_geometry(
    conformer: QuantumConformerInput,
    settings: QuantumCalculationSettings,
) -> str:
    lines = [f"{settings.charge} {settings.multiplicity}"]
    for atom_symbol, (x_coord, y_coord, z_coord) in zip(
        conformer.atom_symbols,
        conformer.coordinates_angstrom,
        strict=True,
    ):
        lines.append(f"{atom_symbol} {x_coord:.10f} {y_coord:.10f} {z_coord:.10f}")
    lines.append(f"units {settings.input_units}")
    return "\n".join(lines)


def default_psi4_single_point_runner(
    conformer: QuantumConformerInput,
    settings: QuantumCalculationSettings,
) -> tuple[float, dict[str, object]]:
    psi4.core.be_quiet()
    psi4.core.clean()
    psi4.core.clean_options()
    molecule = psi4.geometry(build_psi4_geometry(conformer, settings))
    psi4.set_options(
        {
            "reference": "rhf",
            "scf_type": settings.scf_type,
            "e_convergence": settings.e_convergence,
            "d_convergence": settings.d_convergence,
        }
    )
    total_energy = float(psi4.energy(f"{settings.method}/{settings.basis}", molecule=molecule))
    return total_energy, {"engine_version": getattr(psi4, "__version__", None)}


def run_quantum_conformer_ranking(
    data_dir: str | Path,
    settings: QuantumCalculationSettings | None = None,
    runner: QuantumEnergyRunner | None = None,
    max_conformer_index: int = DEFAULT_MAX_CONFORMER_INDEX,
) -> dict[str, object]:
    resolved_settings = settings or QuantumCalculationSettings()
    resolved_runner = runner or default_psi4_single_point_runner
    conformers = load_quantum_conformer_inputs(data_dir, max_conformer_index=max_conformer_index)
    records: list[QuantumConformerResult] = []

    for conformer in conformers:
        try:
            total_energy_hartree, metadata = resolved_runner(conformer, resolved_settings)
            records.append(
                QuantumConformerResult(
                    conformer_index=conformer.conformer_index,
                    source_filename=conformer.source_filename,
                    status="success",
                    geometry_hash=conformer.geometry_hash,
                    method=resolved_settings.method,
                    basis=resolved_settings.basis,
                    charge=resolved_settings.charge,
                    multiplicity=resolved_settings.multiplicity,
                    engine=resolved_settings.engine,
                    total_energy_hartree=float(total_energy_hartree),
                    engine_version=_string_or_none(metadata.get("engine_version")),
                )
            )
        except Exception as exc:  # noqa: BLE001
            records.append(
                QuantumConformerResult(
                    conformer_index=conformer.conformer_index,
                    source_filename=conformer.source_filename,
                    status="failed",
                    geometry_hash=conformer.geometry_hash,
                    method=resolved_settings.method,
                    basis=resolved_settings.basis,
                    charge=resolved_settings.charge,
                    multiplicity=resolved_settings.multiplicity,
                    engine=resolved_settings.engine,
                    error=str(exc),
                )
            )

    ranked_records = annotate_relative_energies(records)
    successful_records = [record for record in ranked_records if record.status == "success"]
    if not successful_records:
        raise RuntimeError("Quantum conformer ranking did not complete for any conformer")

    return {
        "settings": asdict(resolved_settings),
        "summary": build_quantum_ranking_summary(ranked_records),
        "records": [asdict(record) for record in ranked_records],
    }


def annotate_relative_energies(records: list[QuantumConformerResult]) -> list[QuantumConformerResult]:
    successful_records = sorted(
        (record for record in records if record.status == "success" and record.total_energy_hartree is not None),
        key=lambda record: (float(record.total_energy_hartree), record.conformer_index),
    )
    failed_records = sorted(
        (record for record in records if record.status != "success" or record.total_energy_hartree is None),
        key=lambda record: record.conformer_index,
    )

    if not successful_records:
        return failed_records

    lowest_energy = float(successful_records[0].total_energy_hartree)
    ranked_successful_records = [
        replace(
            record,
            rank=rank,
            relative_energy_hartree=float(record.total_energy_hartree) - lowest_energy,
            relative_energy_kcal_mol=(float(record.total_energy_hartree) - lowest_energy) * HARTREE_TO_KCAL_PER_MOL,
        )
        for rank, record in enumerate(successful_records, start=1)
    ]

    return ranked_successful_records + failed_records


def build_quantum_ranking_summary(records: list[QuantumConformerResult]) -> dict[str, object]:
    successful_records = [record for record in records if record.status == "success"]
    failed_records = [record for record in records if record.status != "success"]
    lowest_energy_hartree = (
        float(successful_records[0].total_energy_hartree)
        if successful_records and successful_records[0].total_energy_hartree is not None
        else None
    )

    return {
        "conformer_count": len(records),
        "successful_count": len(successful_records),
        "failed_count": len(failed_records),
        "lowest_energy_hartree": lowest_energy_hartree,
        "ranking_complete": len(successful_records) == len(records),
    }


def records_to_rows(records: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "rank": record["rank"],
            "conformer_index": record["conformer_index"],
            "source_filename": record["source_filename"],
            "status": record["status"],
            "method": record["method"],
            "basis": record["basis"],
            "charge": record["charge"],
            "multiplicity": record["multiplicity"],
            "engine": record["engine"],
            "engine_version": record["engine_version"],
            "geometry_hash": record["geometry_hash"],
            "total_energy_hartree": record["total_energy_hartree"],
            "relative_energy_hartree": record["relative_energy_hartree"],
            "relative_energy_kcal_mol": record["relative_energy_kcal_mol"],
            "error": record["error"],
        }
        for record in records
    ]


def _string_or_none(value: object) -> str | None:
    return None if value is None else str(value)
