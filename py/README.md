## Run
```bash
export DATA_DIR="$(pwd)/../data"
export DB_URL='postgresql://chemist:chemist@192.168.64.2:5432/cid4_analysis?options=-csearch_path%3Dcid4,public'

source .venv/bin/activate
uv sync
uv run python src/cid4_analysis.py
```
```bash
uv run jupyter lab --allow-root --ip=0.0.0.0 --NotebookApp.allow_origin='*'
```
http://192.168.64.2:8888/lab?token=<token>

### Ingest pgvector data
```bash
# pwd -> ...<git repo root>/py
uv run python -m debugpy --listen 5678 --wait-for-client src.pgvector.main
# or
uv run python -m src.pgvector.main
```

## Install psql on macOS:
```bash
brew install libpq
brew link --force libpq
```
## Install psql on Ubuntu:
```bash
apt search postgresql-client
sudo apt install -y postgresql-client-common postgresql-client
```
## Format code
```sh
uv tool run ruff format
```

## Quantum conformer ranking
The first quantum slice is optional and only runs when `CID4_ENABLE_QUANTUM=1` is set.
It ranks the six CID 4 conformers by fixed-geometry single-point energy and writes:

- `data/out/cid4.quantum_conformer_ranking.json`
- `data/out/cid4.quantum_conformer_ranking.csv`

Enable it with:

```sh
export CID4_ENABLE_QUANTUM=1
uv run python src/cid4_analysis.py
```

## Apache AGE runner
```bash
# pwd -> ...<git repo root>/py
uv run python -m debugpy --listen 5678 src.age_graph.main
# or
uv run python -m src.age_graph.main
```

Expected output under `data/out`:
- `cid4_age.summary.json`

The current AGE slice covers the main graph families from the README:
- molecular graph from `Conformer3D_COMPOUND_CID_4(1).json`
- canonical 2D fallback graph from `Structure2D_COMPOUND_CID_4.json`
- compound-to-organism graph from `cid_4.dot` and `pubchem_cid_4_consolidatedcompoundtaxonomy.csv`
- pathway-reaction graph from `pubchem_cid_4_pathway.csv` and `pubchem_cid_4_pathwayreaction.csv`
- assay-target graph from `pubchem_cid_4_bioactivity.csv`

## Machine learning runner
```sh
export DATA_DIR="$(pwd)/../data"
uv run python src/cid4_ml.py
```

The runner currently compares these tasks across libraries:
- atom heavy-atom vs hydrogen classification
- atom O/N/C/H element classification
- filtered bioactivity Active vs Inactive classification
- positive `Activity_Value` regression using molecular descriptors plus assay metadata

The summaries are written to `data/out/cid4_ml.xgboost_suite.summary.json`. The boosted-tree features go beyond the constant molecular descriptors and basic assay encodings by adding missingness flags for `Protein_Accession`, `Gene_ID`, `PMID`, and `Activity_Value`, numeric taxonomy IDs, encoded `Bioassay_Data_Source`, and keyword flags derived from `BioAssay_Name`, `Target_Name`, and assay source text.

## NLTK runner
```bash
# pwd -> ...<git repo root>/py
uv run python -m debugpy --listen 5678 src.nltk.main
# or
uv run python -m src.nltk.main
```
