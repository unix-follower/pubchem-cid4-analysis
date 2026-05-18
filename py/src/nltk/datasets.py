from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils import env_utils

TOXICOLOGY_FILENAME = "pubchem_sid_134971235_chemidplus.csv"


def load_toxicology_frame(filename: str = TOXICOLOGY_FILENAME) -> pd.DataFrame:
    return _read_csv(filename)


def resolve_data_path(filename: str) -> Path:
    return Path(env_utils.get_data_dir()) / filename


def _read_csv(filename: str) -> pd.DataFrame:
    path = Path(resolve_data_path(filename))
    return pd.read_csv(path)
