import json
from pathlib import Path
from typing import Any

from src.constants import UTF_8


def write_json(data: dict[str, Any], output_path: Path):
    with output_path.open("w", encoding=UTF_8) as file:
        json.dump(data, file, indent=2)
