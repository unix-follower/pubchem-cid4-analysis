## NLTK runner
It writes JSON summaries into `data/out` for:
- literature corpus term and collocation analysis
- literature-versus-patent vocabulary comparison
- bioactivity assay and target vocabulary extraction
- taxonomy name normalization and vocabulary cleanup
- toxicology short-text phrase extraction
- pathway and reaction wording analysis

```sh
uv sync
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/main.py
```

The runner is chemistry-aware at the token-normalization level. It preserves tokens such as `1-amino-2-propanol`, `NADH`, `IC50`, `ER-alpha`, `PMID`, `DOI`, `AID`, `CID`, and `SID` instead of over-cleaning them as generic English text.

Expected outputs under `data/out`:
- `cid4_nltk.literature.summary.json`
- `cid4_nltk.literature_vs_patent.summary.json`
- `cid4_nltk.bioactivity.summary.json`
- `cid4_nltk.taxonomy.summary.json`
- `cid4_nltk.toxicology.summary.json`
- `cid4_nltk.pathway.summary.json`
