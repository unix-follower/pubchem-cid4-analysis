package org.example.analysis.distance

import org.apache.commons.math3.stat.descriptive.rank.Percentile
import org.example.analysis.adjacency.AdjacencyMatrix

final case class BondAngleTriplet(
    centralAtomId: Int,
    terminalAtomId1: Int,
    terminalAtomId2: Int
)

final case class BondAngleMeasurement(
    centralAtomId: Int,
    terminalAtomId1: Int,
    terminalAtomId2: Int,
    angleDegrees: Double
)

final case class BondAngleStatistics(
    count: Int,
    minAngleDegrees: Double,
    meanAngleDegrees: Double,
    stdAngleDegrees: Double,
    q25AngleDegrees: Double,
    medianAngleDegrees: Double,
    q75AngleDegrees: Double,
    maxAngleDegrees: Double
)

final case class BondAngleMetadata(
    atomCount: Int,
    bondedAngleTripletCount: Int,
    sourceDistanceMethod: String,
    units: String,
    selectionRule: String
)

final case class BondAngleAnalysisResult(
    atomIds: Vector[Int],
    bondedAngleTriplets: Vector[BondAngleTriplet],
    bondedTripletAngles: Vector[BondAngleMeasurement],
    statistics: BondAngleStatistics,
    metadata: BondAngleMetadata
)

object BondAngleAnalysisService:
  private val AngleVectorTolerance = 1.0e-10

  def analyze(distanceMatrix: DistanceMatrixResult, adjacencyMatrix: AdjacencyMatrix): BondAngleAnalysisResult =
    validateAlignment(distanceMatrix, adjacencyMatrix)

    val angleTriplets = bondedAngleTriplets(adjacencyMatrix)
    val angleMeasurements = computeAngles(distanceMatrix, angleTriplets)
    val statistics = summarizeAngles(angleMeasurements)

    BondAngleAnalysisResult(
      atomIds = distanceMatrix.atomIds,
      bondedAngleTriplets = angleTriplets,
      bondedTripletAngles = angleMeasurements,
      statistics = statistics,
      metadata = BondAngleMetadata(
        atomCount = distanceMatrix.atomIds.size,
        bondedAngleTripletCount = angleMeasurements.size,
        sourceDistanceMethod = distanceMatrix.sourceMethod,
        units = "degrees",
        selectionRule = "angles A-B-C where A-B and B-C are bonded and B is the central atom"
      )
    )

  private def validateAlignment(distanceMatrix: DistanceMatrixResult, adjacencyMatrix: AdjacencyMatrix): Unit =
    require(
      distanceMatrix.atomIds == adjacencyMatrix.atomIds,
      "Distance and adjacency atomIds must be aligned for bond-angle analysis"
    )
    require(
      distanceMatrix.xyzCoordinates.size == adjacencyMatrix.values.size,
      "Distance coordinates and adjacency matrix must have the same size"
    )

  private def bondedAngleTriplets(adjacencyMatrix: AdjacencyMatrix): Vector[BondAngleTriplet] =
    val atomIds = adjacencyMatrix.atomIds

    val triplets = adjacencyMatrix.values.indices.toVector.flatMap { centerIndex =>
      val neighbors = adjacencyMatrix.values(centerIndex).indices.collect {
        case neighborIndex if adjacencyMatrix.values(centerIndex)(neighborIndex) > 0 => atomIds(neighborIndex)
      }.toVector.sorted

      neighbors.combinations(2).map { terminals =>
        BondAngleTriplet(
          centralAtomId = atomIds(centerIndex),
          terminalAtomId1 = terminals.head,
          terminalAtomId2 = terminals(1)
        )
      }.toVector
    }

    require(triplets.nonEmpty, "Expected at least one bonded angle triplet in the adjacency matrix")
    triplets

  private def computeAngles(
      distanceMatrix: DistanceMatrixResult,
      angleTriplets: Vector[BondAngleTriplet]
  ): Vector[BondAngleMeasurement] =
    val atomIndexById = distanceMatrix.atomIds.zipWithIndex.toMap

    angleTriplets.map { triplet =>
      val centerIndex = atomIndexById(triplet.centralAtomId)
      val terminalIndex1 = atomIndexById(triplet.terminalAtomId1)
      val terminalIndex2 = atomIndexById(triplet.terminalAtomId2)
      val firstBondVector = subtractVectors(
        distanceMatrix.xyzCoordinates(terminalIndex1),
        distanceMatrix.xyzCoordinates(centerIndex)
      )
      val secondBondVector = subtractVectors(
        distanceMatrix.xyzCoordinates(terminalIndex2),
        distanceMatrix.xyzCoordinates(centerIndex)
      )

      BondAngleMeasurement(
        centralAtomId = triplet.centralAtomId,
        terminalAtomId1 = triplet.terminalAtomId1,
        terminalAtomId2 = triplet.terminalAtomId2,
        angleDegrees = computeAngleDegrees(firstBondVector, secondBondVector)
      )
    }

  private def subtractVectors(left: Vector[Double], right: Vector[Double]): Vector[Double] =
    left.zip(right).map { (leftValue, rightValue) =>
      leftValue - rightValue
    }

  private def computeAngleDegrees(firstBondVector: Vector[Double], secondBondVector: Vector[Double]): Double =
    val firstNorm = math.sqrt(firstBondVector.map(value => value * value).sum)
    val secondNorm = math.sqrt(secondBondVector.map(value => value * value).sum)
    require(
      firstNorm > AngleVectorTolerance && secondNorm > AngleVectorTolerance,
      "Bond angle computation requires non-zero bond vectors"
    )

    val dotProduct = firstBondVector.zip(secondBondVector).map { (leftValue, rightValue) =>
      leftValue * rightValue
    }.sum
    val cosine = dotProduct / (firstNorm * secondNorm)
    val clampedCosine = math.max(-1.0, math.min(1.0, cosine))
    math.toDegrees(math.acos(clampedCosine))

  private def summarizeAngles(angleMeasurements: Vector[BondAngleMeasurement]): BondAngleStatistics =
    require(angleMeasurements.nonEmpty, "Bond angle analysis must contain at least one angle")

    val angleValues = angleMeasurements.map(_.angleDegrees)
    val meanAngle = angleValues.sum / angleValues.size.toDouble
    val variance = angleValues.map(angle => math.pow(angle - meanAngle, 2)).sum / angleValues.size.toDouble
    val percentile = new Percentile()
    percentile.setData(angleValues.sorted.toArray)

    BondAngleStatistics(
      count = angleValues.size,
      minAngleDegrees = angleValues.min,
      meanAngleDegrees = meanAngle,
      stdAngleDegrees = math.sqrt(variance),
      q25AngleDegrees = percentile.evaluate(25.0),
      medianAngleDegrees = percentile.evaluate(50.0),
      q75AngleDegrees = percentile.evaluate(75.0),
      maxAngleDegrees = angleValues.max
    )
