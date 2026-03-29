package org.example.analysis.spectrum

import org.apache.commons.math3.linear.Array2DRowRealMatrix
import org.apache.commons.math3.linear.EigenDecomposition
import org.example.analysis.adjacency.AdjacencyMatrix

final case class EigendecompositionResult(
    atomIds: Vector[Int],
    eigenvalues: Vector[Double],
    eigenvectors: Vector[Vector[Double]],
    adjacencyMethod: String
)

object EigendecompositionService:
  def compute(adjacencyMatrix: AdjacencyMatrix): EigendecompositionResult =
    val size = adjacencyMatrix.values.size
    val realMatrix = new Array2DRowRealMatrix(
      adjacencyMatrix.values.map(_.map(_.toDouble).toArray).toArray,
      false
    )
    val decomposition = new EigenDecomposition(realMatrix)

    val sortedComponents = Vector.tabulate(size) { index =>
      decomposition.getRealEigenvalue(index) -> decomposition.getEigenvector(index).toArray.toVector
    }.sortBy(_._1)

    val eigenvalues = sortedComponents.map(_._1)
    val eigenvectors =
      Vector.tabulate(size) { rowIndex =>
        sortedComponents.map { case (_, eigenvector) =>
          eigenvector(rowIndex)
        }
      }

    EigendecompositionResult(
      atomIds = adjacencyMatrix.atomIds,
      eigenvalues = eigenvalues,
      eigenvectors = eigenvectors,
      adjacencyMethod = adjacencyMatrix.method
    )
