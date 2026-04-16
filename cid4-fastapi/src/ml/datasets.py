from __future__ import annotations

from typing import Any

import pandas as pd
from rdkit import Chem

import cid4_analysis
from ml.common import PreparedDataset

ATOM_SDF_FILENAME = "Conformer3D_COMPOUND_CID_4(1).sdf"
BIOACTIVITY_FILENAME = "pubchem_cid_4_bioactivity.csv"
TAXONOMY_FILENAME = "pubchem_cid_4_consolidatedcompoundtaxonomy.csv"

ATOM_FEATURE_COLUMNS = [
    "bondCount",
    "totalHydrogenCount",
    "valency",
    "mass",
    "hybridizationEncoded",
    "isAromaticInt",
    "charge",
]

HEAVY_ATOM_PCA_COLUMNS = [
    "atomicNumber",
    "bondCount",
    "totalHydrogenCount",
    "valency",
    "mass",
    "hybridizationEncoded",
    "isAromaticInt",
]

BIOASSAY_NAME_KEYWORDS = {
    "BioAssay_Name_Has_qHTS": ("qhts",),
    "BioAssay_Name_Has_IC50": ("ic50",),
    "BioAssay_Name_Has_Counter_Screen": ("counter screen",),
    "BioAssay_Name_Has_Estrogen": ("estrogen",),
    "BioAssay_Name_Has_Androgen": ("androgen",),
    "BioAssay_Name_Has_Cytochrome": ("cytochrome",),
    "BioAssay_Name_Has_Plasmodium": ("plasmodium",),
    "BioAssay_Name_Has_Yeast": ("yeast",),
}

TARGET_NAME_KEYWORDS = {
    "Target_Name_Has_Estrogen": ("estrogen",),
    "Target_Name_Has_Androgen": ("androgen",),
    "Target_Name_Has_Cytochrome": ("cytochrome",),
    "Target_Name_Has_Plasmodium": ("plasmodium",),
    "Target_Name_Has_Yeast": ("yeast",),
}

SOURCE_KEYWORDS = {
    "Bioassay_Source_Has_Tox21": ("tox21",),
    "Bioassay_Source_Has_ChEMBL": ("chembl",),
    "Bioassay_Source_Has_DTP_NCI": ("dtp", "nci"),
}


def build_atom_feature_frame(
    filename: str = ATOM_SDF_FILENAME,
) -> tuple[pd.DataFrame, Chem.Mol]:
    molecules = cid4_analysis.load_sdf_molecules(filename)

    if not molecules:
        raise ValueError(f"No valid molecules were loaded from {filename}")

    molecule = molecules[0]
    atom_feature_df = cid4_analysis.extract_atom_feature_matrix([molecule]).copy()
    atom_feature_df["atomId"] = atom_feature_df["index"].astype(int) + 1
    atom_feature_df["hybridizationEncoded"] = encode_categories(
        atom_feature_df["hybridization"]
    )
    atom_feature_df["isAromaticInt"] = atom_feature_df["isAromatic"].astype(int)
    atom_feature_df["isHeavyAtom"] = (
        atom_feature_df["atomicNumber"].astype(int).gt(1).astype(int)
    )
    atom_feature_df["elementLabel"] = atom_feature_df["symbol"].astype(str)
    atom_feature_df["atomLabel"] = atom_feature_df["symbol"].astype(
        str
    ) + atom_feature_df["atomId"].astype(str)
    return atom_feature_df, molecule


def build_atom_heavy_atom_dataset(filename: str = ATOM_SDF_FILENAME) -> PreparedDataset:
    atom_feature_df, _ = build_atom_feature_frame(filename)
    frame = atom_feature_df.loc[
        :, ["atomLabel", *ATOM_FEATURE_COLUMNS, "isHeavyAtom"]
    ].copy()

    return PreparedDataset(
        name="atom-heavy-vs-hydrogen",
        task_type="classification",
        frame=frame,
        feature_columns=ATOM_FEATURE_COLUMNS,
        target_column="isHeavyAtom",
        class_names=["hydrogen", "heavy_atom"],
        description="Atom-level binary classification from conformer-derived RDKit features.",
    )


def build_atom_element_dataset(filename: str = ATOM_SDF_FILENAME) -> PreparedDataset:
    atom_feature_df, _ = build_atom_feature_frame(filename)
    class_names = sorted(atom_feature_df["elementLabel"].astype(str).unique().tolist())
    label_to_index = {label: index for index, label in enumerate(class_names)}
    frame = atom_feature_df.loc[:, ["atomLabel", *ATOM_FEATURE_COLUMNS]].copy()
    frame["elementTarget"] = (
        atom_feature_df["elementLabel"].map(label_to_index).astype(int)
    )

    return PreparedDataset(
        name="atom-element-multiclass",
        task_type="classification",
        frame=frame,
        feature_columns=ATOM_FEATURE_COLUMNS,
        target_column="elementTarget",
        class_names=class_names,
        description="Atom-level multiclass classification over O/N/C/H using non-symbol features.",
    )


def build_bioactivity_binary_classification_dataset(
    bioactivity_filename: str = BIOACTIVITY_FILENAME,
    atom_filename: str = ATOM_SDF_FILENAME,
) -> PreparedDataset:
    bioactivity_df = cid4_analysis.load_bioactivity_dataframe(bioactivity_filename)
    filtered_df, _ = cid4_analysis.build_activity_posterior_dataframe(bioactivity_df)
    atom_feature_df, molecule = build_atom_feature_frame(atom_filename)
    descriptor_map = build_molecular_descriptors(atom_feature_df, molecule)
    frame, feature_columns = build_bioactivity_model_frame(filtered_df, descriptor_map)
    frame["activityBinary"] = (
        frame["Activity"].astype(str).str.upper().eq("ACTIVE").astype(int)
    )

    return PreparedDataset(
        name="bioactivity-active-vs-inactive",
        task_type="classification",
        frame=frame,
        feature_columns=feature_columns,
        target_column="activityBinary",
        class_names=["inactive", "active"],
        description="Filtered Active vs Inactive assay rows using constant molecular descriptors and assay metadata.",
    )


def build_activity_value_regression_dataset(
    bioactivity_filename: str = BIOACTIVITY_FILENAME,
    atom_filename: str = ATOM_SDF_FILENAME,
) -> PreparedDataset:
    bioactivity_df = cid4_analysis.load_bioactivity_dataframe(bioactivity_filename)
    activity_value = pd.to_numeric(bioactivity_df["Activity_Value"], errors="coerce")
    retained_mask = activity_value.notna() & activity_value.gt(0)
    filtered_df = bioactivity_df.loc[retained_mask].copy()
    filtered_df["Activity_Value"] = activity_value.loc[retained_mask]
    atom_feature_df, molecule = build_atom_feature_frame(atom_filename)
    descriptor_map = build_molecular_descriptors(atom_feature_df, molecule)
    frame, feature_columns = build_bioactivity_model_frame(filtered_df, descriptor_map)

    return PreparedDataset(
        name="bioactivity-activity-value-regression",
        task_type="regression",
        frame=frame,
        feature_columns=feature_columns,
        target_column="Activity_Value",
        class_names=None,
        description="Positive numeric Activity_Value regression dataset using "
        "molecular descriptors and assay metadata.",
    )


def build_heavy_atom_pca_dataset(filename: str = ATOM_SDF_FILENAME) -> PreparedDataset:
    atom_feature_df, _ = build_atom_feature_frame(filename)
    heavy_atom_df = atom_feature_df.loc[atom_feature_df["isHeavyAtom"].eq(1)].copy()
    frame = heavy_atom_df.loc[:, ["atomLabel", *HEAVY_ATOM_PCA_COLUMNS]].copy()

    return PreparedDataset(
        name="heavy-atom-pca",
        task_type="embedding",
        frame=frame,
        feature_columns=HEAVY_ATOM_PCA_COLUMNS,
        target_column=None,
        class_names=None,
        description="Heavy-atom feature matrix for PCA and related unsupervised analysis.",
    )


def build_taxonomy_clustering_frame(filename: str = TAXONOMY_FILENAME) -> pd.DataFrame:
    taxonomy_df = pd.read_csv(cid4_analysis.resolve_data_path(filename)).copy()
    taxonomy_df["Taxonomy_ID"] = pd.to_numeric(
        taxonomy_df["Taxonomy_ID"], errors="coerce"
    )
    taxonomy_df = taxonomy_df.dropna(
        subset=["Taxonomy_ID", "Source_Organism"]
    ).reset_index(drop=True)
    taxonomy_df["Taxonomy_ID"] = taxonomy_df["Taxonomy_ID"].astype(int)
    taxonomy_df["animalClass"] = (
        taxonomy_df["Taxonomy"].astype(str).map(infer_taxonomy_class)
    )
    return taxonomy_df.loc[
        :, ["Source_Organism", "Taxonomy", "Taxonomy_ID", "animalClass"]
    ]


def build_molecular_descriptors(
    atom_feature_df: pd.DataFrame, molecule: Chem.Mol
) -> dict[str, Any]:
    element_counts = atom_feature_df["symbol"].astype(str).value_counts().to_dict()
    chiral_centers = Chem.FindMolChiralCenters(molecule, includeUnassigned=True)

    return {
        "C_count": int(element_counts.get("C", 0)),
        "H_count": int(element_counts.get("H", 0)),
        "N_count": int(element_counts.get("N", 0)),
        "O_count": int(element_counts.get("O", 0)),
        "bond_count_total": int(molecule.GetNumBonds()),
        "mol_weight": float(atom_feature_df["mass"].astype(float).sum()),
        "has_chiral_center": int(len(chiral_centers) > 0),
    }


def build_bioactivity_model_frame(
    source_frame: pd.DataFrame, descriptor_map: dict[str, Any]
) -> tuple[pd.DataFrame, list[str]]:
    frame = source_frame.copy()
    frame["Aid_Type_Encoded"] = encode_categories(frame["Aid_Type"])
    frame["Activity_Type_Encoded"] = encode_categories(frame["Activity_Type"])
    frame["Bioassay_Data_Source_Encoded"] = encode_categories(
        frame["Bioassay_Data_Source"]
    )
    frame["Has_Dose_Response_Curve"] = pd.to_numeric(
        frame["Has_Dose_Response_Curve"], errors="coerce"
    ).fillna(0)
    frame["RNAi_BioAssay"] = pd.to_numeric(
        frame["RNAi_BioAssay"], errors="coerce"
    ).fillna(0)
    frame["Taxonomy_ID_Numeric"] = pd.to_numeric(
        frame["Taxonomy_ID"], errors="coerce"
    ).fillna(-1)
    frame["Target_Taxonomy_ID_Numeric"] = pd.to_numeric(
        frame["Target_Taxonomy_ID"], errors="coerce"
    ).fillna(-1)
    frame["Has_Protein_Accession"] = has_non_empty_text(frame["Protein_Accession"])
    frame["Has_Gene_ID"] = has_non_empty_text(frame["Gene_ID"])
    frame["Has_PMID"] = has_non_empty_text(frame["PMID"])
    frame["Has_Activity_Value"] = has_non_empty_text(frame["Activity_Value"])

    for key, value in descriptor_map.items():
        frame[key] = value

    add_keyword_flags(frame, "BioAssay_Name", BIOASSAY_NAME_KEYWORDS)
    add_keyword_flags(frame, "Target_Name", TARGET_NAME_KEYWORDS)
    add_keyword_flags(frame, "Bioassay_Data_Source", SOURCE_KEYWORDS)

    feature_columns = [
        "C_count",
        "H_count",
        "N_count",
        "O_count",
        "bond_count_total",
        "mol_weight",
        "has_chiral_center",
        "Aid_Type_Encoded",
        "Activity_Type_Encoded",
        "Bioassay_Data_Source_Encoded",
        "Has_Dose_Response_Curve",
        "RNAi_BioAssay",
        "Taxonomy_ID_Numeric",
        "Target_Taxonomy_ID_Numeric",
        "Has_Protein_Accession",
        "Has_Gene_ID",
        "Has_PMID",
        "Has_Activity_Value",
        *BIOASSAY_NAME_KEYWORDS,
        *TARGET_NAME_KEYWORDS,
        *SOURCE_KEYWORDS,
    ]
    return frame, feature_columns


def add_keyword_flags(
    frame: pd.DataFrame, column_name: str, definitions: dict[str, tuple[str, ...]]
) -> None:
    normalized = frame[column_name].astype("string").fillna("").str.lower()
    for feature_name, keywords in definitions.items():
        pattern = "|".join(keywords)
        frame[feature_name] = normalized.str.contains(pattern, regex=True).astype(int)


def has_non_empty_text(series: pd.Series) -> pd.Series:
    normalized = series.astype("string").fillna("").str.strip()
    return normalized.ne("").astype(int)


def encode_categories(series: pd.Series) -> pd.Series:
    values = series.astype("string").str.strip().fillna("Unknown")
    values = values.mask(values.eq(""), "Unknown")
    category_order = sorted(values.unique().tolist())
    mapping = {value: index for index, value in enumerate(category_order)}
    return values.map(mapping).astype(int)


def infer_taxonomy_class(value: str) -> str:
    lowered = value.lower()
    bird_keywords = {
        "chicken",
        "emu",
        "ostrich",
        "duck",
        "goose",
        "guineafowl",
        "pheasant",
        "pigeon",
        "quail",
        "turkey",
        "waterfowl",
        "ptarmigan",
        "gallus",
        "dromaius",
        "struthio",
        "anas",
        "anser",
        "numida",
        "phasian",
        "columba",
        "meleagris",
        "melanitta",
        "lagopus",
        "anatidae",
        "columbidae",
        "phasianidae",
    }
    mammal_keywords = {
        "sheep",
        "cattle",
        "beefalo",
        "hare",
        "pig",
        "rabbit",
        "buffalo",
        "elk",
        "horse",
        "goat",
        "deer",
        "bison",
        "bos",
        "ovis",
        "sus",
        "lepus",
        "oryctolagus",
        "leporidae",
        "cervus",
        "cervidae",
        "equus",
        "capra",
        "bubalus",
        "odocoileus",
    }

    if any(keyword in lowered for keyword in bird_keywords):
        return "bird"
    if any(keyword in lowered for keyword in mammal_keywords):
        return "mammal"
    return "unknown"
