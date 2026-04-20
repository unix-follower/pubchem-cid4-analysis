import logging as log
import os


def get_data_dir():
    data_directory = os.environ["DATA_DIR"]
    log.info(f"Data directory: {data_directory}")
    return data_directory
