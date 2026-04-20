import json
import logging.config
from pathlib import Path

import constants


def configure_logging():
    src_dir = Path(__file__).resolve().parent
    with (src_dir / "logging.json").open(encoding=constants.UTF_8) as file:
        config = json.load(file)
        logging.config.dictConfig(config)
