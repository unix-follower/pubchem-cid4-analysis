import os


def get_data_dir():
    data_directory = os.environ["DATA_DIR"]
    print(f"Data directory: {data_directory}")
    return data_directory
