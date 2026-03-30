## Run
```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/cid4_analysis.py
```

The standard Python run now also writes bioactivity artifacts from `pubchem_cid_4_bioactivity.csv` into `data/out`:
- filtered IC50 rows with computed pIC50
- summary JSON with row counts and descriptive statistics
- a PNG plot of $y = -\log_{10}(x)$ across the observed IC50 range

The same run now also writes Hill/sigmoidal dose-response reference artifacts from `pubchem_cid_4_bioactivity.csv` into `data/out`:
- a CSV of positive numeric `Activity_Value` rows interpreted as inferred Hill-scale parameters $K$
- a summary JSON documenting the normalized Hill model $f(c) = \frac{c^n}{K^n + c^n}$, its derivatives, and midpoint / inflection interpretation
- a PNG plot of representative reference Hill curves using `Activity_Value` as the inferred half-maximal concentration scale

Because the CID 4 bioactivity CSV contains potency-style summary values rather than raw per-concentration response series, this Hill output is a reference-curve analysis rather than a nonlinear fit to experimental dose-response points. The implementation uses each positive numeric `Activity_Value` as an inferred $K$ value and reports that the log-concentration midpoint occurs at $c = K$. For the default reference coefficient $n = 1$, there is no positive linear-concentration inflection point.

The same run also writes a bonded-distance comparison artifact from the CID 4 conformer:
- a JSON report comparing bonded vs non-bonded inter-atom distances derived from the SDF 3D coordinates and PubChem bond list

The same run also writes a bonded-angle analysis artifact from the CID 4 conformer:
- a JSON report of bonded angles $A$-$B$-$C$ computed from 3D coordinates using the dot-product formula, where $A$-$B$ and $B$-$C$ are bonded and $B$ is the central atom

## Format code
```sh
uv tool run ruff format
```
