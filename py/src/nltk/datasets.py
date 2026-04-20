from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils import env_utils

LITERATURE_FILENAME = "pubchem_cid_4_literature.csv"
PATENT_FILENAME = "pubchem_cid_4_patent.csv"
BIOACTIVITY_FILENAME = "pubchem_cid_4_bioactivity.csv"
TAXONOMY_FILENAME = "pubchem_cid_4_consolidatedcompoundtaxonomy.csv"
TOXICOLOGY_FILENAME = "pubchem_sid_134971235_chemidplus.csv"
PATHWAY_REACTION_FILENAME = "pubchem_cid_4_pathwayreaction.csv"


def load_literature_frame(filename: str = LITERATURE_FILENAME) -> pd.DataFrame:
    return _read_csv(filename)


def load_patent_frame(filename: str = PATENT_FILENAME) -> pd.DataFrame:
    return _read_csv(filename)


def load_bioactivity_frame(filename: str = BIOACTIVITY_FILENAME) -> pd.DataFrame:
    return _read_csv(filename)


def load_taxonomy_frame(filename: str = TAXONOMY_FILENAME) -> pd.DataFrame:
    return _read_csv(filename)


def load_toxicology_frame(filename: str = TOXICOLOGY_FILENAME) -> pd.DataFrame:
    return _read_csv(filename)


def load_pathway_reaction_frame(
    filename: str = PATHWAY_REACTION_FILENAME,
) -> pd.DataFrame:
    return _read_csv(filename)


def resolve_data_path(filename: str) -> Path:
    return Path(env_utils.get_data_dir()) / filename


def _read_csv(filename: str) -> pd.DataFrame:
    path = Path(resolve_data_path(filename))
    return pd.read_csv(path)
