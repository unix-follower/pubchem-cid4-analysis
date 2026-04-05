package org.example.analysis.spectrum

import org.example.analysis.adjacency.AdjacencyMatrix
import org.jgrapht.alg.connectivity.ConnectivityInspector
import org.jgrapht.graph.DefaultWeightedEdge
import org.jgrapht.graph.SimpleWeightedGraph

import scala.jdk.CollectionConverters.*

final case class NullSpaceBasis(
    eigenvalues: Vector[Double],
    eigenvectors: Vector[Vector[Double]],
    tolerance: Double,
    numZeroEigenvalues: Int,
    smallestNonZeroEigenvalue: Double
)

final case class ConnectedComponentsResult(
    labels: Vector[Int],
    numComponents: Int,
    componentAtomIds: Vector[Vector[Int]],
    verificationJGraphTCount: Int
)

final case class LaplacianMetadata(
    atomCount: Int,
    bondCount: Int,
    laplacianRank: Int,
    graphIsConnected: Boolean
)

final case class LaplacianAnalysisResult(
    atomIds: Vector[Int] | Null = null,
    degreeMatrix: Vector[Vector[Double]],
    laplacianMatrix: Vector[Vector[Double]],
    laplacianEigenvalues: Vector[Double],
    laplacianEigenvectors: Vector[Vector[Double]],
    nullSpace: NullSpaceBasis,
    connectedComponents: ConnectedComponentsResult,
    adjacencyMethod: String,
    metadata: LaplacianMetadata
)

object LaplacianService:
  def analyze(
      adjacencyMatrix: AdjacencyMatrix,
      tolerance: Double = SpectralMath.DefaultZeroTolerance
  ): LaplacianAnalysisResult =
    val adjacencyValues = adjacencyMatrix.values.map(_.map(_.toDouble))
    val atomCount = adjacencyValues.size
    val degreeValues = adjacencyValues.map(_.sum)
    val degreeMatrix =
      Vector.tabulate(atomCount) { rowIndex =>
        Vector.tabulate(atomCount) { columnIndex =>
          if rowIndex == columnIndex then degreeValues(rowIndex) else 0.0
        }
      }
    val laplacianMatrix =
      Vector.tabulate(atomCount) { rowIndex =>
        Vector.tabulate(atomCount) { columnIndex =>
          degreeMatrix(rowIndex)(columnIndex) - adjacencyValues(rowIndex)(columnIndex)
        }
      }

    val spectrum = SpectralMath.computeDenseSpectrum(laplacianMatrix)
    val zeroIndices = SpectralMath.zeroEigenIndices(spectrum.eigenvalues, tolerance)
    val nullSpaceEigenvectors =
      Vector.tabulate(atomCount) { rowIndex =>
        zeroIndices.map(columnIndex => spectrum.eigenvectors(rowIndex)(columnIndex))
      }
    val nullSpace = NullSpaceBasis(
      eigenvalues = zeroIndices.map(spectrum.eigenvalues),
      eigenvectors = nullSpaceEigenvectors,
      tolerance = tolerance,
      numZeroEigenvalues = zeroIndices.size,
      smallestNonZeroEigenvalue =
        SpectralMath.smallestNonZeroEigenvalue(spectrum.eigenvalues, tolerance)
    )

    val connectivityGraph =
      new SimpleWeightedGraph[Int, DefaultWeightedEdge](classOf[DefaultWeightedEdge])
    adjacencyMatrix.atomIds.foreach(connectivityGraph.addVertex)
    adjacencyMatrix.atomIds.indices.foreach { rowIndex =>
      ((rowIndex + 1) until atomCount).foreach { columnIndex =>
        val weight = adjacencyValues(rowIndex)(columnIndex)
        if weight > 0.0 then
          val sourceAtomId = adjacencyMatrix.atomIds(rowIndex)
          val targetAtomId = adjacencyMatrix.atomIds(columnIndex)
          val edge = connectivityGraph.addEdge(sourceAtomId, targetAtomId)
          if edge != null then connectivityGraph.setEdgeWeight(edge, weight)
      }
    }

    val connectivityInspector = ConnectivityInspector(connectivityGraph)
    val componentSets = connectivityInspector.connectedSets().asScala.toVector.map(_.asScala.toVector.sorted)
    val componentIndexByAtomId = componentSets.zipWithIndex.flatMap { (componentAtomIds, componentIndex) =>
      componentAtomIds.map(_ -> componentIndex)
    }.toMap
    val labels = adjacencyMatrix.atomIds.map(componentIndexByAtomId)
    val connectedComponents = ConnectedComponentsResult(
      labels = labels,
      numComponents = componentSets.size,
      componentAtomIds = componentSets,
      verificationJGraphTCount = componentSets.size
    )

    if connectedComponents.numComponents != nullSpace.numZeroEigenvalues then
      throw IllegalStateException(
        s"Null-space dimension ${nullSpace.numZeroEigenvalues} does not match connected-components count ${connectedComponents.numComponents}"
      )

    val bondCount = adjacencyValues.indices.map { rowIndex =>
      ((rowIndex + 1) until atomCount).count(columnIndex => adjacencyValues(rowIndex)(columnIndex) > 0.0)
    }.sum

    LaplacianAnalysisResult(
      degreeMatrix = degreeMatrix,
      laplacianMatrix = laplacianMatrix,
      laplacianEigenvalues = spectrum.eigenvalues,
      laplacianEigenvectors = spectrum.eigenvectors,
      nullSpace = nullSpace,
      connectedComponents = connectedComponents,
      adjacencyMethod = adjacencyMatrix.method,
      metadata = LaplacianMetadata(
        atomCount = atomCount,
        bondCount = bondCount,
        laplacianRank = SpectralMath.matrixRank(spectrum.eigenvalues, tolerance),
        graphIsConnected = connectedComponents.numComponents == 1
      )
    )
