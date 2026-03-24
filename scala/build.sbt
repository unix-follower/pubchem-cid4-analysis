import sbt.Keys.libraryDependencies

ThisBuild / scalaVersion := "3.8.2"
ThisBuild / version := "1.0.0"
ThisBuild / organization := "org.example"
ThisBuild / organizationName := "pubchem_cid4_analysis"

lazy val root = (project in file("."))
  .settings(
      name := "cid4-analysis",
  )
