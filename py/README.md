## Run
```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
uv run python src/cid4_analysis.py
```

## Format code
```sh
uv tool run ruff format
```
