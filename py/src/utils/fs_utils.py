import os
from pathlib import Path

from src.utils import env_utils


def create_dir_if_doesnt_exist(directory: str):
    if not os.path.exists(directory):
        os.makedirs(directory)


def resolve_output_directory() -> Path:
    data_dir = Path(env_utils.get_data_dir())
    output_directory = data_dir / "out"
    create_dir_if_doesnt_exist(str(output_directory))
    return output_directory


def resolve_data_path(filename: str) -> Path:
    return Path(env_utils.get_data_dir()) / filename
