import sbt.Keys.libraryDependencies

ThisBuild / scalaVersion := "3.8.2"
ThisBuild / version := "1.0.0"
ThisBuild / organization := "org.example"
ThisBuild / organizationName := "pubchem_cid4_analysis"

val logbackVersion = "1.5.32"

lazy val root = (project in file("."))
  .settings(
      name := "cid4-analysis",
      libraryDependencies ++= Seq(
        "org.slf4j" % "slf4j-api" % "2.0.17",
        "ch.qos.logback" % "logback-core" % logbackVersion,
        "ch.qos.logback" % "logback-classic" % logbackVersion,
        "org.apache.commons" % "commons-math3" % "3.6.1",
        "tools.jackson.module" %% "jackson-module-scala" % "3.1.0",
        "org.openscience.cdk" % "cdk-bundle" % "2.12"
      )
  )
