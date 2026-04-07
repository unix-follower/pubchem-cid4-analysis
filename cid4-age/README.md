## Apache AGE runner
```sh
micromamba create -c conda-forge -p ./.micromamba/cid4_age python=3.12 rdkit
uv venv --python ./.micromamba/cid4_age/bin/python --system-site-packages .venv

source ./.micromamba/cid4_age/bin/activate
source .venv/bin/activate

uv sync

export DATA_DIR="$(pwd)/../data"
python src/main.py
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
