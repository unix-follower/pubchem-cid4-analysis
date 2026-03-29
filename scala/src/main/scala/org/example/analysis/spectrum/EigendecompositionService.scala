package org.example.analysis.spectrum

import org.example.analysis.adjacency.AdjacencyMatrix

final case class EigendecompositionResult(
    atomIds: Vector[Int],
    eigenvalues: Vector[Double],
    eigenvectors: Vector[Vector[Double]],
    adjacencyMethod: String
)

object EigendecompositionService:
  def compute(adjacencyMatrix: AdjacencyMatrix): EigendecompositionResult =
    val spectrum = SpectralMath.computeDenseSpectrum(adjacencyMatrix.values.map(_.map(_.toDouble)))

    EigendecompositionResult(
      atomIds = adjacencyMatrix.atomIds,
      eigenvalues = spectrum.eigenvalues,
      eigenvectors = spectrum.eigenvectors,
      adjacencyMethod = adjacencyMatrix.method
    )
