from __future__ import annotations

from pathlib import Path

import pandas as pd

import cid4_analysis

LITERATURE_FILENAME = "pubchem_cid_4_literature.csv"
PATENT_FILENAME = "pubchem_cid_4_patent.csv"
BIOACTIVITY_FILENAME = "pubchem_cid_4_bioactivity.csv"
PATHWAY_FILENAME = "pubchem_cid_4_pathway.csv"
PATHWAY_REACTION_FILENAME = "pubchem_cid_4_pathwayreaction.csv"
TAXONOMY_FILENAME = "pubchem_cid_4_consolidatedcompoundtaxonomy.csv"
CPDAT_FILENAME = "pubchem_cid_4_cpdat.csv"


def load_literature_frame(filename: str = LITERATURE_FILENAME) -> pd.DataFrame:
    return _read_csv(filename)


def load_patent_frame(filename: str = PATENT_FILENAME) -> pd.DataFrame:
    return _read_csv(filename)


def load_bioactivity_frame(filename: str = BIOACTIVITY_FILENAME) -> pd.DataFrame:
    return _read_csv(filename)


def load_pathway_frame(filename: str = PATHWAY_FILENAME) -> pd.DataFrame:
    return _read_csv(filename)


def load_pathway_reaction_frame(filename: str = PATHWAY_REACTION_FILENAME) -> pd.DataFrame:
    return _read_csv(filename)


def load_taxonomy_frame(filename: str = TAXONOMY_FILENAME) -> pd.DataFrame:
    return _read_csv(filename)


def load_cpdat_frame(filename: str = CPDAT_FILENAME) -> pd.DataFrame:
    return _read_csv(filename)


def _read_csv(filename: str) -> pd.DataFrame:
    path = Path(cid4_analysis.resolve_data_path(filename))
    return pd.read_csv(path, low_memory=False)
