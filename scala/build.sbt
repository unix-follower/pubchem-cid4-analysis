import sbt.Keys.libraryDependencies

ThisBuild / scalaVersion := "3.8.2"
ThisBuild / version := "1.0.0"
ThisBuild / organization := "org.example"
ThisBuild / organizationName := "pubchem_cid4_analysis"
ThisBuild / semanticdbEnabled := true

val logbackVersion = "1.5.32"

lazy val root = (project in file("."))
  .settings(
      name := "cid4-analysis",
      scalacOptions += "-Wunused:imports",
      libraryDependencies ++= Seq(
        "org.slf4j" % "slf4j-api" % "2.0.17",
        "ch.qos.logback" % "logback-core" % logbackVersion,
        "ch.qos.logback" % "logback-classic" % logbackVersion,
        "org.apache.commons" % "commons-math3" % "3.6.1",
        "org.apache.commons" % "commons-csv" % "1.14.1",
        "org.apache.lucene" % "lucene-core" % "9.12.1",
        "org.apache.lucene" % "lucene-analysis-common" % "9.12.1",
        "org.apache.lucene" % "lucene-queryparser" % "9.12.1",
        "org.apache.lucene" % "lucene-highlighter" % "9.12.1",
        "tools.jackson.module" %% "jackson-module-scala" % "3.1.0",
        "org.openscience.cdk" % "cdk-bundle" % "2.12",
        "com.google.guava" % "guava" % "33.5.0-jre",
        "org.jgrapht" % "jgrapht-core" % "1.5.2",
        "org.apache.tinkerpop" % "gremlin-core" % "3.8.0",
        "org.apache.tinkerpop" % "tinkergraph-gremlin" % "3.8.0",
        "org.scala-graph" %% "graph-core" % "2.0.3",
        "org.knowm.xchart" % "xchart" % "3.8.8"
      )
  )
