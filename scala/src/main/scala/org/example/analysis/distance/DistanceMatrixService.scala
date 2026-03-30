package org.example.analysis.distance

import org.example.model.PcCompound
import org.openscience.cdk.DefaultChemObjectBuilder
import org.openscience.cdk.io.iterator.IteratingSDFReader

import java.io.FileInputStream
import java.nio.file.Path

final case class DistanceMatrixMetadata(
    atomCount: Int,
    coordinateDimension: Int,
    sourcePath: String,
    units: String
)

final case class DistanceMatrixResult(
    atomIds: Vector[Int],
    xyzCoordinates: Vector[Vector[Double]],
    distanceMatrix: Vector[Vector[Double]],
    sourceMethod: String,
    metadata: DistanceMatrixMetadata
)

enum DistanceSourceMethod(val value: String):
  case Json extends DistanceSourceMethod("json")
  case Sdf extends DistanceSourceMethod("sdf")

object DistanceSourceMethod:
  private val aliases = Map(
    "json" -> DistanceSourceMethod.Json,
    "dto" -> DistanceSourceMethod.Json,
    "sdf" -> DistanceSourceMethod.Sdf,
    "cdk" -> DistanceSourceMethod.Sdf
  )

  def supportedValues: String =
    DistanceSourceMethod.values.map(_.value).mkString(", ")

  def parse(method: String): Either[String, DistanceSourceMethod] =
    aliases.get(method.trim.toLowerCase) match
      case Some(value) => Right(value)
      case None =>
        Left(s"Unsupported distance source '$method'. Supported values: $supportedValues")

final case class DistanceMatrixInput(compound: PcCompound, jsonPath: Path, sdfPath: Path):
  val atomIds: Vector[Int] = compound.atoms.aid.toVector

  if atomIds.isEmpty then
    throw IllegalArgumentException("Compound must contain at least one atom for distance analysis")

trait DistanceMatrixStrategy:
  def method: DistanceSourceMethod

  def build(input: DistanceMatrixInput): DistanceMatrixResult

object DistanceMatrixStrategy:
  private val implementations = Vector[DistanceMatrixStrategy](
    JsonDistanceMatrixStrategy,
    SdfDistanceMatrixStrategy
  ).map(strategy => strategy.method -> strategy).toMap

  def resolve(method: String): DistanceMatrixStrategy =
    DistanceSourceMethod.parse(method) match
      case Right(value)       => implementations(value)
      case Left(errorMessage) => throw IllegalArgumentException(errorMessage)

private object DistanceMatrixMath:
  private val CoordinateDimension = 3

  def coordinatesFromAxes(x: Seq[Double], y: Seq[Double], z: Seq[Double]): Vector[Vector[Double]] =
    if x.size != y.size || x.size != z.size then
      throw IllegalArgumentException("Coordinate axes x, y, and z must have the same length")

    Vector.tabulate(x.size) { index =>
      Vector(x(index), y(index), z(index))
    }

  def validateAtomCount(atomIds: Vector[Int], coordinates: Vector[Vector[Double]], source: String): Unit =
    if atomIds.size != coordinates.size then
      throw IllegalArgumentException(
        s"Atom ids count ${atomIds.size} does not match coordinate count ${coordinates.size} for $source"
      )

    coordinates.foreach { coordinate =>
      if coordinate.size != CoordinateDimension then
        throw IllegalArgumentException(
          s"Expected $CoordinateDimension coordinate dimensions for $source, found ${coordinate.size}"
        )
    }

  def buildDistanceMatrix(coordinates: Vector[Vector[Double]]): Vector[Vector[Double]] =
    Vector.tabulate(coordinates.size) { rowIndex =>
      Vector.tabulate(coordinates.size) { columnIndex =>
        if rowIndex == columnIndex then 0.0
        else euclideanDistance(coordinates(rowIndex), coordinates(columnIndex))
      }
    }

  def buildResult(
      atomIds: Vector[Int],
      coordinates: Vector[Vector[Double]],
      sourceMethod: DistanceSourceMethod,
      sourcePath: Path
  ): DistanceMatrixResult =
    validateAtomCount(atomIds, coordinates, sourcePath.toString)

    DistanceMatrixResult(
      atomIds = atomIds,
      xyzCoordinates = coordinates,
      distanceMatrix = buildDistanceMatrix(coordinates),
      sourceMethod = sourceMethod.value,
      metadata = DistanceMatrixMetadata(
        atomCount = atomIds.size,
        coordinateDimension = CoordinateDimension,
        sourcePath = sourcePath.toString,
        units = "angstrom"
      )
    )

  private def euclideanDistance(left: Vector[Double], right: Vector[Double]): Double =
    math.sqrt(left.zip(right).map { (leftValue, rightValue) =>
      val delta = leftValue - rightValue
      delta * delta
    }.sum)

object JsonDistanceMatrixStrategy extends DistanceMatrixStrategy:
  override val method: DistanceSourceMethod = DistanceSourceMethod.Json

  override def build(input: DistanceMatrixInput): DistanceMatrixResult =
    val coordinateSet = input.compound.coords.headOption.getOrElse(
      throw IllegalStateException("Compound does not contain coordinate metadata")
    )
    val conformer = coordinateSet.conformers.headOption.getOrElse(
      throw IllegalStateException("Compound coordinates do not contain a conformer")
    )
    val coordinatesByAtomId =
      coordinateSet.aid.zip(DistanceMatrixMath.coordinatesFromAxes(conformer.x, conformer.y, conformer.z)).toMap

    val orderedCoordinates = input.atomIds.map { atomId =>
      coordinatesByAtomId.getOrElse(
        atomId,
        throw IllegalArgumentException(s"Missing JSON coordinates for atom id $atomId")
      )
    }

    DistanceMatrixMath.buildResult(input.atomIds, orderedCoordinates, method, input.jsonPath)

object SdfDistanceMatrixStrategy extends DistanceMatrixStrategy:
  override val method: DistanceSourceMethod = DistanceSourceMethod.Sdf

  override def build(input: DistanceMatrixInput): DistanceMatrixResult =
    val reader =
      new IteratingSDFReader(new FileInputStream(input.sdfPath.toFile), DefaultChemObjectBuilder.getInstance())

    try
      if !reader.hasNext then
        throw IllegalStateException(s"SDF file ${input.sdfPath} does not contain any molecules")

      val molecule = reader.next()
      val coordinates = Vector.tabulate(molecule.getAtomCount) { atomIndex =>
        val point = Option(molecule.getAtom(atomIndex).getPoint3d).getOrElse(
          throw IllegalStateException(
            s"SDF atom index $atomIndex in ${input.sdfPath} does not contain 3D coordinates"
          )
        )
        Vector(point.x, point.y, point.z)
      }

      DistanceMatrixMath.buildResult(input.atomIds, coordinates, method, input.sdfPath)
    finally
      reader.close()

object DistanceMatrixService:
  def analyze(compound: PcCompound, jsonPath: Path, sdfPath: Path, sourceMethod: String): DistanceMatrixResult =
    val strategy = DistanceMatrixStrategy.resolve(sourceMethod)
    val input = DistanceMatrixInput(compound, jsonPath, sdfPath)
    strategy.build(input)
