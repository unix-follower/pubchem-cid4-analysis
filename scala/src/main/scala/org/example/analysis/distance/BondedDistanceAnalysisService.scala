package org.example.analysis.distance

import org.example.analysis.adjacency.AdjacencyMatrix
import org.apache.commons.math3.stat.descriptive.rank.Percentile

final case class BondedDistanceStatistics(
    count: Int,
    minDistanceAngstrom: Double,
    meanDistanceAngstrom: Double,
    stdDistanceAngstrom: Double,
    q25DistanceAngstrom: Double,
    medianDistanceAngstrom: Double,
    q75DistanceAngstrom: Double,
    maxDistanceAngstrom: Double
)

final case class BondedDistanceComparison(
    meanDistanceDifferenceAngstrom: Double,
    nonbondedToBondedMeanRatio: Double
)

final case class BondedAtomPair(atomId1: Int, atomId2: Int)

final case class AtomPairDistance(atomId1: Int, atomId2: Int, distanceAngstrom: Double)

final case class BondedDistanceMetadata(
    atomCount: Int,
    bondedPairCount: Int,
    nonbondedPairCount: Int,
    totalUniquePairCount: Int,
    sourceDistanceMethod: String,
    units: String
)

final case class BondedDistanceAnalysisResult(
    atomIds: Vector[Int],
    bondedAtomPairs: Vector[BondedAtomPair],
    bondedPairDistances: Vector[AtomPairDistance],
    nonbondedPairDistances: Vector[AtomPairDistance],
    bondedDistances: BondedDistanceStatistics,
    nonbondedDistances: BondedDistanceStatistics,
    comparison: BondedDistanceComparison,
    metadata: BondedDistanceMetadata
)

object BondedDistanceAnalysisService:
  def analyze(distanceMatrix: DistanceMatrixResult, adjacencyMatrix: AdjacencyMatrix): BondedDistanceAnalysisResult =
    validateAlignment(distanceMatrix, adjacencyMatrix)

    val bondedPairs = bondedAtomPairs(adjacencyMatrix)
    val partitions = partitionDistances(distanceMatrix, bondedPairs)
    val bondedStats = summarizeDistances(partitions.bondedPairDistances)
    val nonbondedStats = summarizeDistances(partitions.nonbondedPairDistances)

    BondedDistanceAnalysisResult(
      atomIds = distanceMatrix.atomIds,
      bondedAtomPairs = bondedPairs,
      bondedPairDistances = partitions.bondedPairDistances,
      nonbondedPairDistances = partitions.nonbondedPairDistances,
      bondedDistances = bondedStats,
      nonbondedDistances = nonbondedStats,
      comparison = BondedDistanceComparison(
        meanDistanceDifferenceAngstrom =
          nonbondedStats.meanDistanceAngstrom - bondedStats.meanDistanceAngstrom,
        nonbondedToBondedMeanRatio =
          nonbondedStats.meanDistanceAngstrom / bondedStats.meanDistanceAngstrom
      ),
      metadata = BondedDistanceMetadata(
        atomCount = distanceMatrix.atomIds.size,
        bondedPairCount = partitions.bondedPairDistances.size,
        nonbondedPairCount = partitions.nonbondedPairDistances.size,
        totalUniquePairCount = partitions.bondedPairDistances.size + partitions.nonbondedPairDistances.size,
        sourceDistanceMethod = distanceMatrix.sourceMethod,
        units = distanceMatrix.metadata.units
      )
    )

  private final case class DistancePartitions(
      bondedPairDistances: Vector[AtomPairDistance],
      nonbondedPairDistances: Vector[AtomPairDistance]
  )

  private def validateAlignment(distanceMatrix: DistanceMatrixResult, adjacencyMatrix: AdjacencyMatrix): Unit =
    require(
      distanceMatrix.atomIds == adjacencyMatrix.atomIds,
      "Distance and adjacency atomIds must be aligned for bonded-distance analysis"
    )
    require(
      distanceMatrix.distanceMatrix.size == adjacencyMatrix.values.size,
      "Distance matrix and adjacency matrix must have the same size"
    )

  private def bondedAtomPairs(adjacencyMatrix: AdjacencyMatrix): Vector[BondedAtomPair] =
    val atomIds = adjacencyMatrix.atomIds

    val pairs = for {
      rowIndex <- adjacencyMatrix.values.indices.toVector
      columnIndex <- (rowIndex + 1) until adjacencyMatrix.values(rowIndex).size
      if adjacencyMatrix.values(rowIndex)(columnIndex) > 0
    } yield BondedAtomPair(atomIds(rowIndex), atomIds(columnIndex))

    require(pairs.nonEmpty, "Expected at least one bonded atom pair in the adjacency matrix")
    pairs

  private def partitionDistances(
      distanceMatrix: DistanceMatrixResult,
      bondedPairs: Vector[BondedAtomPair]
  ): DistancePartitions =
    val bondedPairSet = bondedPairs.map(pair => (pair.atomId1, pair.atomId2)).toSet

    val allPairs = for {
      rowIndex <- distanceMatrix.atomIds.indices.toVector
      columnIndex <- (rowIndex + 1) until distanceMatrix.atomIds.size
    } yield AtomPairDistance(
      atomId1 = distanceMatrix.atomIds(rowIndex),
      atomId2 = distanceMatrix.atomIds(columnIndex),
      distanceAngstrom = distanceMatrix.distanceMatrix(rowIndex)(columnIndex)
    )

    val (bonded, nonbonded) = allPairs.partition(pair => bondedPairSet.contains((pair.atomId1, pair.atomId2)))
    val expectedTotalPairCount = distanceMatrix.atomIds.size * (distanceMatrix.atomIds.size - 1) / 2
    require(
      bonded.size + nonbonded.size == expectedTotalPairCount,
      s"Expected $expectedTotalPairCount unique atom pairs, partitioned ${bonded.size + nonbonded.size}"
    )

    DistancePartitions(bonded, nonbonded)

  private def summarizeDistances(pairDistances: Vector[AtomPairDistance]): BondedDistanceStatistics =
    require(pairDistances.nonEmpty, "Distance partition must contain at least one pair")

    val distances = pairDistances.map(_.distanceAngstrom)
    val meanDistance = distances.sum / distances.size.toDouble
    val variance = distances.map(distance => math.pow(distance - meanDistance, 2)).sum / distances.size.toDouble
    val percentile = new Percentile()
    percentile.setData(distances.sorted.toArray)

    BondedDistanceStatistics(
      count = distances.size,
      minDistanceAngstrom = distances.min,
      meanDistanceAngstrom = meanDistance,
      stdDistanceAngstrom = math.sqrt(variance),
      q25DistanceAngstrom = percentile.evaluate(25.0),
      medianDistanceAngstrom = percentile.evaluate(50.0),
      q75DistanceAngstrom = percentile.evaluate(75.0),
      maxDistanceAngstrom = distances.max
    )
