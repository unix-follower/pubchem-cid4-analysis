package org.example.analysis.adjacency

import org.example.model.PcCompound

final case class WeightedBond(
    sourceAtomId: Int,
    targetAtomId: Int,
    weight: Int,
    sourceIndex: Int,
    targetIndex: Int
)

final case class NormalizedAdjacencyInput(atomIds: Vector[Int], bonds: Vector[WeightedBond]):
  val atomIndexById: Map[Int, Int] = atomIds.zipWithIndex.toMap

  def size: Int = atomIds.size

final case class AdjacencyMatrix(atomIds: Vector[Int], values: Vector[Vector[Int]], method: String)

enum AdjacencyMethod(val value: String):
  case Arrays extends AdjacencyMethod("arrays")
  case Guava extends AdjacencyMethod("guava")
  case TinkerPop extends AdjacencyMethod("tinkerpop")
  case JGraphT extends AdjacencyMethod("jgrapht")
  case ScalaGraph extends AdjacencyMethod("scala-graph")

object AdjacencyMethod:
  private val aliases = Map(
    "arrays" -> AdjacencyMethod.Arrays,
    "array" -> AdjacencyMethod.Arrays,
    "guava" -> AdjacencyMethod.Guava,
    "tinkerpop" -> AdjacencyMethod.TinkerPop,
    "jgrapht" -> AdjacencyMethod.JGraphT,
    "scala-graph" -> AdjacencyMethod.ScalaGraph,
    "scalax.collection.graph" -> AdjacencyMethod.ScalaGraph,
    "scalagraph" -> AdjacencyMethod.ScalaGraph
  )

  def supportedValues: String =
    AdjacencyMethod.values.map(_.value).mkString(", ")

  def parse(method: String): Either[String, AdjacencyMethod] =
    aliases.get(method.trim.toLowerCase) match
      case Some(value) => Right(value)
      case None =>
        Left(s"Unsupported adjacency method '$method'. Supported values: $supportedValues")

object NormalizedAdjacencyInput:
  def fromCompound(compound: PcCompound): NormalizedAdjacencyInput =
    val atomIds = compound.atoms.aid.sorted.toVector

    if atomIds.isEmpty then
      throw IllegalArgumentException("Compound must contain at least one atom")

    if atomIds.distinct.size != atomIds.size then
      throw IllegalArgumentException("Compound contains duplicate atom ids")

    val aid1 = compound.bonds.aid1.toVector
    val aid2 = compound.bonds.aid2.toVector
    val order = compound.bonds.order.toVector

    if aid1.size != aid2.size || aid1.size != order.size then
      throw IllegalArgumentException("Bond arrays aid1, aid2, and order must have the same length")

    val atomIndexById = atomIds.zipWithIndex.toMap
    val bonds = aid1.indices.toVector.map { index =>
      val sourceAtomId = aid1(index)
      val targetAtomId = aid2(index)
      val weight = order(index)
      val sourceIndex = atomIndexById.getOrElse(
        sourceAtomId,
        throw IllegalArgumentException(s"Unknown source atom id in bonds: $sourceAtomId")
      )
      val targetIndex = atomIndexById.getOrElse(
        targetAtomId,
        throw IllegalArgumentException(s"Unknown target atom id in bonds: $targetAtomId")
      )

      WeightedBond(sourceAtomId, targetAtomId, weight, sourceIndex, targetIndex)
    }

    NormalizedAdjacencyInput(atomIds, bonds)

private[adjacency] object MatrixOps:
  def empty(size: Int): Array[Array[Int]] =
    Array.fill(size, size)(0)

  def assignSymmetric(matrix: Array[Array[Int]], rowIndex: Int, columnIndex: Int, weight: Int): Unit =
    matrix(rowIndex)(columnIndex) = weight
    matrix(columnIndex)(rowIndex) = weight

  def freeze(input: NormalizedAdjacencyInput, matrix: Array[Array[Int]], method: AdjacencyMethod): AdjacencyMatrix =
    AdjacencyMatrix(
      atomIds = input.atomIds,
      values = matrix.iterator.map(_.toVector).toVector,
      method = method.value
    )

object AdjacencyMatrixService:
  def build(compound: PcCompound, method: String): AdjacencyMatrix =
    val strategy = AdjacencyMatrixStrategy.resolve(method)
    val input = NormalizedAdjacencyInput.fromCompound(compound)
    strategy.build(input)
