import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import cid4_quantum  # noqa: E402

HAS_RDKIT = cid4_quantum.rdkit_available()


class Cid4QuantumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data_dir = PROJECT_ROOT.parent / "data"

    @unittest.skipUnless(HAS_RDKIT, "RDKit is required to load SDF conformers")
    def test_discover_conformer_sdf_paths_returns_all_expected_files(self) -> None:
        paths = cid4_quantum.discover_conformer_sdf_paths(self.data_dir)

        self.assertEqual(len(paths), 6)
        self.assertEqual(paths[0].name, "Conformer3D_COMPOUND_CID_4(1).sdf")
        self.assertEqual(paths[-1].name, "Conformer3D_COMPOUND_CID_4(6).sdf")

    @unittest.skipUnless(HAS_RDKIT, "RDKit is required to load SDF conformers")
    def test_load_quantum_conformer_inputs_extracts_atoms_and_hashes(self) -> None:
        conformers = cid4_quantum.load_quantum_conformer_inputs(self.data_dir)

        self.assertEqual(len(conformers), 6)
        self.assertEqual(conformers[0].conformer_index, 1)
        self.assertEqual(len(conformers[0].atom_symbols), 14)
        self.assertEqual(len(conformers[0].coordinates_angstrom), 14)
        self.assertEqual(len(conformers[0].geometry_hash), 64)

    @unittest.skipUnless(HAS_RDKIT, "RDKit is required to load SDF conformers")
    def test_build_psi4_geometry_includes_charge_multiplicity_and_units(self) -> None:
        conformer = cid4_quantum.load_quantum_conformer_inputs(self.data_dir, max_conformer_index=1)[0]
        settings = cid4_quantum.QuantumCalculationSettings(charge=0, multiplicity=1)

        geometry = cid4_quantum.build_psi4_geometry(conformer, settings)

        self.assertTrue(geometry.startswith("0 1\n"))
        self.assertIn("units angstrom", geometry)
        self.assertIn("O ", geometry)

    def test_annotate_relative_energies_ranks_successes_and_keeps_failures_last(self) -> None:
        records = [
            cid4_quantum.QuantumConformerResult(
                conformer_index=2,
                source_filename="Conformer3D_COMPOUND_CID_4(2).sdf",
                status="success",
                geometry_hash="b",
                method="hf",
                basis="sto-3g",
                charge=0,
                multiplicity=1,
                engine="psi4",
                total_energy_hartree=-154.1,
            ),
            cid4_quantum.QuantumConformerResult(
                conformer_index=1,
                source_filename="Conformer3D_COMPOUND_CID_4(1).sdf",
                status="failed",
                geometry_hash="a",
                method="hf",
                basis="sto-3g",
                charge=0,
                multiplicity=1,
                engine="psi4",
                error="SCF did not converge",
            ),
            cid4_quantum.QuantumConformerResult(
                conformer_index=3,
                source_filename="Conformer3D_COMPOUND_CID_4(3).sdf",
                status="success",
                geometry_hash="c",
                method="hf",
                basis="sto-3g",
                charge=0,
                multiplicity=1,
                engine="psi4",
                total_energy_hartree=-154.3,
            ),
        ]

        ranked = cid4_quantum.annotate_relative_energies(records)

        self.assertEqual([record.conformer_index for record in ranked], [3, 2, 1])
        self.assertEqual(ranked[0].rank, 1)
        self.assertEqual(ranked[0].relative_energy_hartree, 0.0)
        self.assertGreater(float(ranked[1].relative_energy_kcal_mol), 0.0)
        self.assertIsNone(ranked[2].rank)

    @unittest.skipUnless(HAS_RDKIT, "RDKit is required to load SDF conformers")
    def test_run_quantum_conformer_ranking_supports_fake_runner(self) -> None:
        settings = cid4_quantum.QuantumCalculationSettings()

        def fake_runner(
            conformer: cid4_quantum.QuantumConformerInput,
            _: cid4_quantum.QuantumCalculationSettings,
        ) -> tuple[float, dict[str, object]]:
            return (-154.0 - conformer.conformer_index * 0.01, {"engine_version": "fake-1.0"})

        payload = cid4_quantum.run_quantum_conformer_ranking(
            self.data_dir,
            settings=settings,
            runner=fake_runner,
        )

        self.assertEqual(payload["summary"]["conformer_count"], 6)
        self.assertEqual(payload["summary"]["successful_count"], 6)
        self.assertEqual(payload["records"][0]["conformer_index"], 6)
        self.assertEqual(payload["records"][0]["rank"], 1)
        self.assertEqual(payload["records"][0]["engine_version"], "fake-1.0")


if __name__ == "__main__":
    unittest.main()
