import json
from pathlib import Path

from rdkit import Chem

import env_utils
from constants import ARR_1ST_IDX as IDX1
from constants import UTF_8

PERIODIC_TABLE = Chem.GetPeriodicTable()


def resolve_data_path(filename: str) -> Path:
    return Path(env_utils.get_data_dir()) / filename


def load_conformer_compound(filename: str) -> dict:
    json_file_path = resolve_data_path(filename)

    with json_file_path.open(encoding=UTF_8) as file:
        conformer_data = json.load(file)

    return conformer_data["PC_Compounds"][IDX1]
