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
