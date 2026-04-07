## pgvector runner
It normalizes literature, patents, bioactivity rows, pathway records, taxonomy rows, and CPDat rows into a shared document shape, generates deterministic hashed-token embeddings, and writes a JSON summary into `data/out`.

```sh
uv sync
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/main.py
```

Environment variables:
- `PGVECTOR_DSN` - PostgreSQL connection string for a database with the `vector` extension available
- `PGVECTOR_TABLE` - optional target table name, default `cid4_documents`
- `PGVECTOR_EMBED_DIM` - optional hashed embedding dimension, default `96`

Expected output under `data/out`:
- `cid4_pgvector.summary.json`
