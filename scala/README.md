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

The same run now also writes a manual gradient-descent analysis from the atom feature matrix of the active CID 4 conformer:
- a CSV trace of per-epoch weight, gradient, summed squared error, and MSE for the no-intercept model $\hat{y} = wx$
- a summary JSON documenting the hand-derived gradient $\frac{\partial}{\partial w}\sum_i(y_i - wx_i)^2 = 2\sum_i x_i(wx_i - y_i)$ with atom mass as the feature and atomic number as the target
- a PNG loss curve across epochs
- a PNG scatter/fit plot for atom mass versus atomic number under the learned weight

This gradient-descent example is intentionally educational rather than general-purpose: it uses the full atom feature matrix of the CID 4 conformer as the dataset, treats `mass` as the single feature, treats `atomicNumber` as the target, optimizes a one-parameter no-intercept regression, and reports the closed-form least-squares solution alongside the iterative result as a numerical check.

The same run now also writes Scala bioactivity artifacts from `pubchem_cid_4_bioactivity.csv` under `DATA_DIR/out`:
- filtered IC50 rows with computed pIC50 as CSV
- summary JSON with row counts and descriptive statistics
- a PNG plot of `y = -log10(x)` across the observed IC50 range

The same run now also writes Hill/sigmoidal dose-response reference artifacts from `pubchem_cid_4_bioactivity.csv` under `DATA_DIR/out`:
- a CSV of positive numeric `Activity_Value` rows interpreted as inferred Hill-scale parameters `K`
- a summary JSON documenting the normalized Hill model `f(c) = c^n / (K^n + c^n)`, its derivatives, and midpoint / inflection interpretation
- a PNG plot of representative reference Hill curves using `Activity_Value` as the inferred half-maximal concentration scale

Because the CID 4 bioactivity CSV contains potency-style summary values rather than raw per-concentration response series, this Hill output is a reference-curve analysis rather than a nonlinear fit to experimental dose-response points. The implementation uses each positive numeric `Activity_Value` as an inferred `K` value and reports that the log-concentration midpoint occurs at `c = K`. For the default reference coefficient `n = 1`, there is no positive linear-concentration inflection point.
