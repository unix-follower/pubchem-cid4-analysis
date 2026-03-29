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
sbt "run arrays"
sbt "run guava"
sbt "run tinkerpop"
sbt "run jgrapht"
sbt "run scala-graph"
```

The selected method is passed as the `method` string parameter and writes both an adjacency-matrix JSON file and a matching eigendecomposition JSON file under `DATA_DIR/out`.
