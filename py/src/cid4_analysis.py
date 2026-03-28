import logging as log
from functools import reduce

import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, Draw, ValenceType

import env_utils
import fs_utils as fs
import log_settings
from constants import ARR_1ST_IDX as IDX1


def write_image(sdf_file_path: str, out_img_filepath: str):
    with Chem.SDMolSupplier(sdf_file_path) as supplier:
        ms = [x for x in supplier if x is not None]

    for m in ms:
        AllChem.Compute2DCoords(m)

    Draw.MolToFile(ms[IDX1], out_img_filepath)


def process_sdf_file(filename: str):
    work_directory = env_utils.get_data_dir()
    sdf_file_path = f"{work_directory}/{filename}"
    sdf_supplier = Chem.SDMolSupplier(sdf_file_path)

    def reduce_mol_weights(mol_weights: list):
        return reduce(lambda prev, next: prev + next, mol_weights)

    avg_mol_weights = [Descriptors.MolWt(mol) for mol in sdf_supplier if mol is not None]
    log.info(f"Average molecular weight: {reduce_mol_weights(avg_mol_weights)}")
    mol_exact_mass = [Descriptors.ExactMolWt(mol) for mol in sdf_supplier if mol is not None]
    log.info(f"Exact molecular mass: {reduce_mol_weights(mol_exact_mass)}")

    out_dir = f"{work_directory}/out"
    fs.create_dir_if_doesnt_exist(out_dir)

    atom_data = []

    for mol in sdf_supplier:
        if mol is not None:
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
    filename = "Conformer3D_COMPOUND_CID_4(1).sdf"
    process_sdf_file(filename)


if __name__ == "__main__":
    main()
