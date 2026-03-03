import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem, Draw, ValenceType


def write_image(sdf_file_path: str, out_dir: str):
    with Chem.SDMolSupplier(sdf_file_path) as supplier:
        ms = [x for x in supplier if x is not None]

    for m in ms:
        AllChem.Compute2DCoords(m)

    Draw.MolToFile(ms[0], f"{out_dir}/Conformer3D_COMPOUND_CID_4.png")


def main():
    data_directory = env.get_data_dir()
    work_directory = f"{data_directory}/pubchem/cid_4"

    sdf_file_path = f"{work_directory}/Conformer3D_COMPOUND_CID_4.sdf"
    sdf_supplier = Chem.SDMolSupplier(sdf_file_path)

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
    df.to_json(f"{out_dir}/cid4-sdf-extracted.json")

    write_image(sdf_file_path, out_dir)


if __name__ == "__main__":
    main()
