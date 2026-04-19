## Run
```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
uv run python src/cid4_analysis.py
```

## Quantum conformer ranking
The first quantum slice is optional and only runs when `CID4_ENABLE_QUANTUM=1` is set.
It ranks the six CID 4 conformers by fixed-geometry single-point energy and writes:

- `data/out/cid4.quantum_conformer_ranking.json`
- `data/out/cid4.quantum_conformer_ranking.csv`

Enable it with:

```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
export CID4_ENABLE_QUANTUM=1
uv run python src/cid4_analysis.py
```

## Format code
```sh
uv tool run ruff format
```
