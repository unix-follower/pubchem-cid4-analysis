## Run
Try this on macOS with Intel CPU
```bash
micromamba create -c conda-forge -p ./.micromamba/cid4_age python=3.12 rdkit
uv venv --python ./.micromamba/cid4_age/bin/python --system-site-packages .venv

source ./.micromamba/cid4_age/bin/activate
source .venv/bin/activate
```
```bash
export DATA_DIR="$(pwd)/../data"
source .venv/bin/activate
uv sync
uv run python src/cid4_analysis.py
```
### Docker Cheat sheet
```bash
uv run jupyter lab

docker run -it --rm pytorch/pytorch:2.11.0-cuda13.0-cudnn9-devel bash

docker build -t cid4-pytorch:latest .
docker run --rm --name cid4-pytorch -p 8888:8888 cid4-pytorch:latest
nc -vz $(minikube ip) 8888

docker image rm cid4-pytorch:latest
```
http://192.168.64.23:8888/lab?token=<token>


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
uv run python -m debugpy --listen 5678 --wait-for-client src.age_graph.main
# or
uv run python -m src.age_graph.main
```

If `AGE_DSN` is not set or Apache AGE is not available on the target PostgreSQL instance, the runner still completes. It falls back to a dry-run summary that reports node and edge counts, sample Cypher statements, and example multi-hop queries.

Environment variables:
- `AGE_DSN` - PostgreSQL connection string for an instance where the Apache AGE extension is installed
- `AGE_GRAPH_NAME` - optional AGE graph name, default `cid4_graph`

Expected output under `data/out`:
- `cid4_age.summary.json`

The current AGE slice covers the main graph families from the README:
- molecular graph from `Conformer3D_COMPOUND_CID_4(1).json`
- canonical 2D fallback graph from `Structure2D_COMPOUND_CID_4.json`
- compound-to-organism graph from `cid_4.dot` and `pubchem_cid_4_consolidatedcompoundtaxonomy.csv`
- pathway-reaction graph from `pubchem_cid_4_pathway.csv` and `pubchem_cid_4_pathwayreaction.csv`
- assay-target graph from `pubchem_cid_4_bioactivity.csv`

## NLTK runner
It writes JSON summaries into `data/out` for:
- literature corpus term and collocation analysis
- literature-versus-patent vocabulary comparison
- bioactivity assay and target vocabulary extraction
- taxonomy name normalization and vocabulary cleanup
- toxicology short-text phrase extraction
- pathway and reaction wording analysis

The runner is chemistry-aware at the token-normalization level. It preserves tokens such as `1-amino-2-propanol`, `NADH`, `IC50`, `ER-alpha`, `PMID`, `DOI`, `AID`, `CID`, and `SID` instead of over-cleaning them as generic English text.

Expected outputs under `data/out`:
- `cid4_nltk.literature.summary.json`
- `cid4_nltk.literature_vs_patent.summary.json`
- `cid4_nltk.bioactivity.summary.json`
- `cid4_nltk.taxonomy.summary.json`
- `cid4_nltk.toxicology.summary.json`
- `cid4_nltk.pathway.summary.json`

```bash
# pwd -> ...<git repo root>/py
uv run python -m debugpy --listen 5678 --wait-for-client src.nltk.main
# or
uv run python -m src.nltk.main
```

## pgvector runner
It normalizes literature, patents, bioactivity rows, pathway records, taxonomy rows, and CPDat rows into a shared document shape, generates deterministic hashed-token embeddings, and writes a JSON summary into `data/out`.

Environment variables:
- `PGVECTOR_DSN` - PostgreSQL connection string for a database with the `vector` extension available
- `PGVECTOR_TABLE` - optional target table name, default `cid4_documents`
- `PGVECTOR_EMBED_DIM` - optional hashed embedding dimension, default `96`

Expected output under `data/out`:
- `cid4_pgvector.summary.json`

```bash
# pwd -> ...<git repo root>/py
uv run python -m debugpy --listen 5678 --wait-for-client src.pgvector.main
# or
uv run python -m src.pgvector.main
```
