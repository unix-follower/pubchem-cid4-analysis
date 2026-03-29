package org.example.analysis.spectrum

import org.apache.commons.math3.linear.Array2DRowRealMatrix
import org.apache.commons.math3.linear.EigenDecomposition

private[spectrum] final case class DenseSpectrum(
    eigenvalues: Vector[Double],
    eigenvectors: Vector[Vector[Double]]
)

private[spectrum] object SpectralMath:
  val DefaultZeroTolerance: Double = 1e-10

  def computeDenseSpectrum(matrixValues: Vector[Vector[Double]]): DenseSpectrum =
    val size = matrixValues.size
    val realMatrix = new Array2DRowRealMatrix(matrixValues.map(_.toArray).toArray, false)
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

    DenseSpectrum(eigenvalues = eigenvalues, eigenvectors = eigenvectors)

  def zeroEigenIndices(eigenvalues: Vector[Double], tolerance: Double): Vector[Int] =
    eigenvalues.zipWithIndex.collect { case (value, index) if math.abs(value) < tolerance => index }

  def smallestNonZeroEigenvalue(eigenvalues: Vector[Double], tolerance: Double): Double =
    eigenvalues.find(_ > tolerance).getOrElse(0.0)

  def matrixRank(eigenvalues: Vector[Double], tolerance: Double): Int =
    eigenvalues.count(value => math.abs(value) >= tolerance)
