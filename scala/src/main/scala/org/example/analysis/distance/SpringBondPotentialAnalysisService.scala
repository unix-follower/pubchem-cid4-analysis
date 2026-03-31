package org.example.analysis.distance

import org.apache.commons.math3.stat.descriptive.rank.Percentile
import org.example.analysis.adjacency.AdjacencyMatrix
import org.example.model.PcCompound
import org.openscience.cdk.config.Isotopes
import org.openscience.cdk.tools.periodictable.PeriodicTable

final case class CartesianPartialDerivatives(
    dEDx: Double,
    dEDy: Double,
    dEDz: Double,
    gradientNorm: Double
)

final case class BondedPairSpringRecord(
    atomId1: Int,
    atomId2: Int,
    atomSymbol1: String,
    atomSymbol2: String,
    bondOrder: Int,
    distanceAngstrom: Double,
    referenceDistanceAngstrom: Double,
    referenceDistanceSource: String,
    distanceResidualAngstrom: Double,
    springConstant: Double,
    springEnergy: Double,
    dEDDistance: Double,
    atom1PartialDerivatives: CartesianPartialDerivatives,
    atom2PartialDerivatives: CartesianPartialDerivatives
)

final case class AtomGradientRecord(
    atomId: Int,
    atomSymbol: String,
    incidentBondCount: Int,
    dEDx: Double,
    dEDy: Double,
    dEDz: Double,
    gradientNorm: Double
)

final case class DistanceResidualStatistics(
    count: Int,
    min: Double,
    mean: Double,
    std: Double,
    q25: Double,
    median: Double,
    q75: Double,
    max: Double,
    zeroResidualBondCount: Int
)

final case class SpringEnergyStatistics(
    count: Int,
    total: Double,
    min: Double,
    mean: Double,
    std: Double,
    q25: Double,
    median: Double,
    q75: Double,
    max: Double
)

final case class AtomGradientNormStatistics(
    count: Int,
    min: Double,
    mean: Double,
    std: Double,
    q25: Double,
    median: Double,
    q75: Double,
    max: Double
)

final case class NetCartesianGradient(
    dEDx: Double,
    dEDy: Double,
    dEDz: Double,
    gradientNorm: Double
)

final case class SpringBondPotentialStatistics(
    distanceResidualAngstrom: DistanceResidualStatistics,
    springEnergy: SpringEnergyStatistics,
    atomGradientNorm: AtomGradientNormStatistics,
    gradientBalance: NetCartesianGradient
)

final case class SpringBondPotentialAnalysisInfo(
    energyEquation: String,
    distanceEquation: String,
    distanceDerivativeEquation: String,
    cartesianGradientEquation: String,
    reactionGradientEquation: String,
    referenceDistancePolicy: String,
    springConstantPolicy: String,
    bondOrderSpringConstants: Map[String, Double],
    referenceDistanceLookupExamplesAngstrom: Map[String, Double],
    interpretation: String
)

final case class SpringBondPotentialMetadata(
    atomCount: Int,
    bondedPairCount: Int,
    sourceDistanceMethod: String,
    sourceAdjacencyMethod: String,
    distanceUnits: String,
    referenceDistanceUnits: String,
    springConstantUnits: String,
    springEnergyUnits: String,
    coordinatePartialDerivativeUnits: String,
    referenceDistanceSourceCounts: Map[String, Int]
)

final case class SpringBondPotentialAnalysisResult(
    atomIds: Vector[Int],
    bondedPairSpringRecords: Vector[BondedPairSpringRecord],
    atomGradientRecords: Vector[AtomGradientRecord],
    statistics: SpringBondPotentialStatistics,
    analysis: SpringBondPotentialAnalysisInfo,
    metadata: SpringBondPotentialMetadata
)

object SpringBondPotentialAnalysisService:
  private val SpringDistanceTolerance = 1.0e-12
  private val ZeroResidualTolerance = 1.0e-12
  private val DefaultBondOrderSpringConstants = Map(
    1 -> 300.0,
    2 -> 500.0,
    3 -> 700.0
  )
  private val DefaultBondOrderLengthScales = Map(
    1 -> 1.0,
    2 -> 0.9,
    3 -> 0.85
  )
  private val DefaultReferenceBondLengthsAngstrom = Map(
    ("C", "C", 1) -> 1.54,
    ("C", "C", 2) -> 1.34,
    ("C", "C", 3) -> 1.20,
    ("C", "N", 1) -> 1.47,
    ("C", "N", 2) -> 1.28,
    ("C", "N", 3) -> 1.16,
    ("C", "O", 1) -> 1.43,
    ("C", "O", 2) -> 1.23,
    ("C", "H", 1) -> 1.09,
    ("N", "H", 1) -> 1.01,
    ("O", "H", 1) -> 0.96
  )

  def analyze(
      compound: PcCompound,
      distanceMatrix: DistanceMatrixResult,
      adjacencyMatrix: AdjacencyMatrix
  ): SpringBondPotentialAnalysisResult =
    validateAlignment(compound, distanceMatrix, adjacencyMatrix)

    val isotopeFactory = Isotopes.getInstance()
    val atomicNumberByAtomId = compound.atoms.aid.zip(compound.atoms.element).toMap
    val atomSymbolById = distanceMatrix.atomIds.map { atomId =>
      val atomicNumber = atomicNumberByAtomId.getOrElse(
        atomId,
        throw IllegalArgumentException(s"Missing atomic number for atom id $atomId")
      )
      atomId -> isotopeFactory.getElementSymbol(atomicNumber)
    }.toMap
    val atomIndexById = distanceMatrix.atomIds.zipWithIndex.toMap
    val bondedPairs = bondedPairsWithOrder(adjacencyMatrix)

    val zeroGradient = Vector(0.0, 0.0, 0.0)
    val initialAccumulators = distanceMatrix.atomIds.map { atomId =>
      atomId -> AtomGradientAccumulator(
        atomId = atomId,
        atomSymbol = atomSymbolById(atomId),
        incidentBondCount = 0,
        gradientVector = zeroGradient
      )
    }.toMap

    val foldResult = bondedPairs.foldLeft(SpringAccumulator(Vector.empty, initialAccumulators, Map.empty)) {
      case (accumulator, bondedPair) =>
        val atomId1 = bondedPair.atomId1
        val atomId2 = bondedPair.atomId2
        val atomSymbol1 = atomSymbolById(atomId1)
        val atomSymbol2 = atomSymbolById(atomId2)
        val coordinate1 = distanceMatrix.xyzCoordinates(atomIndexById(atomId1))
        val coordinate2 = distanceMatrix.xyzCoordinates(atomIndexById(atomId2))
        val bondVector = subtractVectors(coordinate1, coordinate2)
        val distance = vectorNorm(bondVector)

        require(
          distance > SpringDistanceTolerance,
          s"Spring bond derivative analysis requires non-zero bonded distances, found $distance for pair ($atomId1, $atomId2)"
        )

        val (referenceDistance, referenceDistanceSource) =
          inferReferenceBondLengthAngstrom(atomSymbol1, atomSymbol2, bondedPair.bondOrder)
        val springConstant = resolveSpringConstantForBondOrder(bondedPair.bondOrder)
        val distanceResidual = distance - referenceDistance
        val dEDDistance = springConstant * distanceResidual
        val gradientAtom1 = scaleVector(bondVector, dEDDistance / distance)
        val gradientAtom2 = scaleVector(gradientAtom1, -1.0)
        val springEnergy = 0.5 * springConstant * distanceResidual * distanceResidual

        SpringAccumulator(
          bondRecords = accumulator.bondRecords :+ BondedPairSpringRecord(
            atomId1 = atomId1,
            atomId2 = atomId2,
            atomSymbol1 = atomSymbol1,
            atomSymbol2 = atomSymbol2,
            bondOrder = bondedPair.bondOrder,
            distanceAngstrom = distance,
            referenceDistanceAngstrom = referenceDistance,
            referenceDistanceSource = referenceDistanceSource,
            distanceResidualAngstrom = distanceResidual,
            springConstant = springConstant,
            springEnergy = springEnergy,
            dEDDistance = dEDDistance,
            atom1PartialDerivatives = toPartialDerivatives(gradientAtom1),
            atom2PartialDerivatives = toPartialDerivatives(gradientAtom2)
          ),
          atomGradients = accumulator.atomGradients
            .updated(atomId1, accumulator.atomGradients(atomId1).addGradient(gradientAtom1))
            .updated(atomId2, accumulator.atomGradients(atomId2).addGradient(gradientAtom2)),
          referenceDistanceSourceCounts = accumulator.referenceDistanceSourceCounts.updated(
            referenceDistanceSource,
            accumulator.referenceDistanceSourceCounts.getOrElse(referenceDistanceSource, 0) + 1
          )
        )
    }

    val atomGradientRecords = distanceMatrix.atomIds.map { atomId =>
      val accumulator = foldResult.atomGradients(atomId)
      AtomGradientRecord(
        atomId = accumulator.atomId,
        atomSymbol = accumulator.atomSymbol,
        incidentBondCount = accumulator.incidentBondCount,
        dEDx = accumulator.gradientVector(0),
        dEDy = accumulator.gradientVector(1),
        dEDz = accumulator.gradientVector(2),
        gradientNorm = vectorNorm(accumulator.gradientVector)
      )
    }
    val netGradientVector = atomGradientRecords.foldLeft(zeroGradient) { (current, record) =>
      addVectors(current, Vector(record.dEDx, record.dEDy, record.dEDz))
    }

    SpringBondPotentialAnalysisResult(
      atomIds = distanceMatrix.atomIds,
      bondedPairSpringRecords = foldResult.bondRecords,
      atomGradientRecords = atomGradientRecords,
      statistics = summarize(foldResult.bondRecords, atomGradientRecords, netGradientVector),
      analysis = SpringBondPotentialAnalysisInfo(
        energyEquation = "E_ij = 0.5 * k_ij * (d_ij - d0_ij)^2",
        distanceEquation = "d_ij = ||r_i - r_j||",
        distanceDerivativeEquation = "dE_ij/dd_ij = k_ij * (d_ij - d0_ij)",
        cartesianGradientEquation = "dE_ij/dr_i = k_ij * (d_ij - d0_ij) * (r_i - r_j) / d_ij",
        reactionGradientEquation = "dE_ij/dr_j = -dE_ij/dr_i",
        referenceDistancePolicy =
          "Chemistry-informed lookup keyed by atom symbols and bond order with a covalent-radius fallback",
        springConstantPolicy = "Bond-order-specific constants for an educational harmonic bond model",
        bondOrderSpringConstants = DefaultBondOrderSpringConstants.toVector.sortBy(_._1).map { (bondOrder, value) =>
          bondOrder.toString -> value
        }.toMap,
        referenceDistanceLookupExamplesAngstrom = DefaultReferenceBondLengthsAngstrom.toVector
          .sortBy { case ((symbol1, symbol2, bondOrder), _) => (symbol1, symbol2, bondOrder) }
          .map { case ((symbol1, symbol2, bondOrder), value) =>
            s"$symbol1-$symbol2-order-$bondOrder" -> value
          }
          .toMap,
        interpretation =
          "Positive and negative Cartesian partial derivatives quantify how the spring-bond energy changes under infinitesimal coordinate displacements of each bonded atom in the current CID 4 conformer."
      ),
      metadata = SpringBondPotentialMetadata(
        atomCount = distanceMatrix.atomIds.size,
        bondedPairCount = foldResult.bondRecords.size,
        sourceDistanceMethod = distanceMatrix.sourceMethod,
        sourceAdjacencyMethod = adjacencyMatrix.method,
        distanceUnits = distanceMatrix.metadata.units,
        referenceDistanceUnits = "angstrom",
        springConstantUnits = "relative spring units / angstrom^2",
        springEnergyUnits = "relative spring units",
        coordinatePartialDerivativeUnits = "relative spring units / angstrom",
        referenceDistanceSourceCounts = foldResult.referenceDistanceSourceCounts.toVector.sortBy(_._1).toMap
      )
    )

  private final case class BondedPairWithOrder(atomId1: Int, atomId2: Int, bondOrder: Int)

  private final case class AtomGradientAccumulator(
      atomId: Int,
      atomSymbol: String,
      incidentBondCount: Int,
      gradientVector: Vector[Double]
  ):
    def addGradient(delta: Vector[Double]): AtomGradientAccumulator =
      copy(
        incidentBondCount = incidentBondCount + 1,
        gradientVector = addVectors(gradientVector, delta)
      )

  private final case class SpringAccumulator(
      bondRecords: Vector[BondedPairSpringRecord],
      atomGradients: Map[Int, AtomGradientAccumulator],
      referenceDistanceSourceCounts: Map[String, Int]
  )

  private def validateAlignment(
      compound: PcCompound,
      distanceMatrix: DistanceMatrixResult,
      adjacencyMatrix: AdjacencyMatrix
  ): Unit =
    require(
      distanceMatrix.atomIds == adjacencyMatrix.atomIds,
      "Distance and adjacency atomIds must be aligned for spring-bond analysis"
    )
    require(
      distanceMatrix.xyzCoordinates.size == adjacencyMatrix.values.size,
      "Distance coordinates and adjacency matrix must have the same size for spring-bond analysis"
    )
    require(
      compound.atoms.aid.toSet == distanceMatrix.atomIds.toSet,
      "Compound atom ids must match distance-matrix atom ids for spring-bond analysis"
    )
    require(
      compound.atoms.aid.size == compound.atoms.element.size,
      "Compound atom ids and atomic numbers must have the same size for spring-bond analysis"
    )

  private def bondedPairsWithOrder(adjacencyMatrix: AdjacencyMatrix): Vector[BondedPairWithOrder] =
    val atomIds = adjacencyMatrix.atomIds

    val pairs = for {
      rowIndex <- adjacencyMatrix.values.indices.toVector
      columnIndex <- (rowIndex + 1) until adjacencyMatrix.values(rowIndex).size
      bondOrder = adjacencyMatrix.values(rowIndex)(columnIndex)
      if bondOrder > 0
    } yield BondedPairWithOrder(
      atomId1 = atomIds(rowIndex),
      atomId2 = atomIds(columnIndex),
      bondOrder = bondOrder
    )

    require(pairs.nonEmpty, "Expected at least one bonded atom pair in the adjacency matrix")
    pairs

  private def inferReferenceBondLengthAngstrom(
      symbol1: String,
      symbol2: String,
      bondOrder: Int
  ): (Double, String) =
    require(bondOrder > 0, "Bond order must be positive when inferring a spring reference distance")

    val normalizedPair = Vector(symbol1, symbol2).sorted
    val normalizedKey = (normalizedPair.head, normalizedPair(1), bondOrder)

    DefaultReferenceBondLengthsAngstrom.get(normalizedKey) match
      case Some(value) => (value, "lookupTable")
      case None =>
        val covalentRadius1 = covalentRadius(symbol1)
        val covalentRadius2 = covalentRadius(symbol2)
        val lengthScale = DefaultBondOrderLengthScales.getOrElse(bondOrder, 1.0 / math.sqrt(bondOrder.toDouble))
        ((covalentRadius1 + covalentRadius2) * lengthScale, "covalentRadiusFallback")

  private def resolveSpringConstantForBondOrder(bondOrder: Int): Double =
    require(bondOrder > 0, "Bond order must be positive when resolving a spring constant")
    DefaultBondOrderSpringConstants.getOrElse(
      bondOrder,
      DefaultBondOrderSpringConstants(1) * bondOrder.toDouble
    )

  private def covalentRadius(symbol: String): Double =
    val radius = PeriodicTable.getCovalentRadius(symbol)
    require(
      !radius.isNaN && radius > 0.0,
      s"Could not infer a positive covalent radius for symbol '$symbol'"
    )
    radius

  private def toPartialDerivatives(gradient: Vector[Double]): CartesianPartialDerivatives =
    CartesianPartialDerivatives(
      dEDx = gradient(0),
      dEDy = gradient(1),
      dEDz = gradient(2),
      gradientNorm = vectorNorm(gradient)
    )

  private def summarize(
      bondRecords: Vector[BondedPairSpringRecord],
      atomGradientRecords: Vector[AtomGradientRecord],
      netGradientVector: Vector[Double]
  ): SpringBondPotentialStatistics =
    require(bondRecords.nonEmpty, "Spring bond derivative analysis must contain at least one bonded pair")

    val distanceResiduals = bondRecords.map(_.distanceResidualAngstrom)
    val springEnergies = bondRecords.map(_.springEnergy)
    val atomGradientNorms = atomGradientRecords.map(_.gradientNorm)

    SpringBondPotentialStatistics(
      distanceResidualAngstrom = DistanceResidualStatistics(
        count = distanceResiduals.size,
        min = distanceResiduals.min,
        mean = mean(distanceResiduals),
        std = std(distanceResiduals),
        q25 = percentile(distanceResiduals, 25.0),
        median = percentile(distanceResiduals, 50.0),
        q75 = percentile(distanceResiduals, 75.0),
        max = distanceResiduals.max,
        zeroResidualBondCount = distanceResiduals.count(value => math.abs(value) <= ZeroResidualTolerance)
      ),
      springEnergy = SpringEnergyStatistics(
        count = springEnergies.size,
        total = springEnergies.sum,
        min = springEnergies.min,
        mean = mean(springEnergies),
        std = std(springEnergies),
        q25 = percentile(springEnergies, 25.0),
        median = percentile(springEnergies, 50.0),
        q75 = percentile(springEnergies, 75.0),
        max = springEnergies.max
      ),
      atomGradientNorm = AtomGradientNormStatistics(
        count = atomGradientNorms.size,
        min = atomGradientNorms.min,
        mean = mean(atomGradientNorms),
        std = std(atomGradientNorms),
        q25 = percentile(atomGradientNorms, 25.0),
        median = percentile(atomGradientNorms, 50.0),
        q75 = percentile(atomGradientNorms, 75.0),
        max = atomGradientNorms.max
      ),
      gradientBalance = NetCartesianGradient(
        dEDx = netGradientVector(0),
        dEDy = netGradientVector(1),
        dEDz = netGradientVector(2),
        gradientNorm = vectorNorm(netGradientVector)
      )
    )

  private def mean(values: Vector[Double]): Double =
    values.sum / values.size.toDouble

  private def std(values: Vector[Double]): Double =
    val average = mean(values)
    math.sqrt(values.map(value => math.pow(value - average, 2)).sum / values.size.toDouble)

  private def percentile(values: Vector[Double], percentileValue: Double): Double =
    val estimator = new Percentile()
    estimator.setData(values.sorted.toArray)
    estimator.evaluate(percentileValue)

  private def subtractVectors(left: Vector[Double], right: Vector[Double]): Vector[Double] =
    left.zip(right).map { (leftValue, rightValue) =>
      leftValue - rightValue
    }

  private def addVectors(left: Vector[Double], right: Vector[Double]): Vector[Double] =
    left.zip(right).map { (leftValue, rightValue) =>
      leftValue + rightValue
    }

  private def scaleVector(vector: Vector[Double], factor: Double): Vector[Double] =
    vector.map(_ * factor)

  private def vectorNorm(vector: Vector[Double]): Double =
    math.sqrt(vector.map(value => value * value).sum)
