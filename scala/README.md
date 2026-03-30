## Format code
```shell
sbt scalafmt
```

## Run Scalafix
```shell
sbt scalafixAll
```

For consistent results with import rewrites, run Scalafix before Scalafmt.

## Run adjacency matrix generation
```shell
sbt "run arrays json"
sbt "run guava json"
sbt "run tinkerpop json"
sbt "run jgrapht json"
sbt "run scala-graph json"
sbt "run jgrapht sdf"
```

The first argument is the adjacency `method` string parameter. The optional second argument is the distance-source selector and supports `json` and `sdf`.

Each run writes a distance-matrix JSON file, an adjacency-matrix JSON file, a matching eigendecomposition JSON file, and a Laplacian-analysis JSON file under `DATA_DIR/out`.

The same run also writes a bonded-distance comparison JSON artifact for the active conformer:
- bonded vs non-bonded inter-atom distance statistics derived from the 3D distance matrix and PubChem bond list

The same run also writes a bond-angle analysis JSON artifact for the active conformer:
- bonded angles $A$-$B$-$C$ derived from the 3D coordinates using the dot-product formula, where $A$-$B$ and $B$-$C$ are bonded and $B$ is the central atom

The same run now also writes Scala bioactivity artifacts from `pubchem_cid_4_bioactivity.csv` under `DATA_DIR/out`:
- filtered IC50 rows with computed pIC50 as CSV
- summary JSON with row counts and descriptive statistics
- a PNG plot of `y = -log10(x)` across the observed IC50 range
