package org.example.analysis.distance

import org.apache.commons.csv.CSVFormat
import org.apache.commons.csv.CSVPrinter
import org.example.model.PcCompound
import org.knowm.xchart.BitmapEncoder
import org.knowm.xchart.BitmapEncoder.BitmapFormat
import org.knowm.xchart.XYChartBuilder
import org.knowm.xchart.style.markers.SeriesMarkers
import org.openscience.cdk.DefaultChemObjectBuilder
import org.openscience.cdk.config.Isotopes
import org.openscience.cdk.io.iterator.IteratingSDFReader

import java.io.FileInputStream
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import scala.jdk.CollectionConverters.*
import scala.math.BigDecimal.RoundingMode

final case class AtomFeatureRow(
    index: Int,
    symbol: String,
    mass: Double,
    atomicNumber: Int
)

final case class GradientDescentTraceRow(
    epoch: Int,
    weight: Double,
    gradient: Double,
    sumSquaredError: Double,
    mse: Double
)

final case class GradientCheck(analytic: Double, finiteDifference: Double)

final case class GradientCheckSummary(
    initialWeight: GradientCheck,
    finalWeight: GradientCheck
)

final case class GradientLossTraceSummary(
    monotonicNonincreasingMse: Boolean,
    bestEpoch: Int
)

final case class GradientDescentDatasetSummary(
    rowCount: Int,
    feature: String,
    target: String,
    featureMatrixShape: Vector[Int],
    massRange: Vector[Double],
    atomicNumberRange: Vector[Int],
    atomRows: Vector[AtomFeatureRow]
)

final case class GradientDescentModelSummary(
    predictionEquation: String,
    objectiveName: String,
    objectiveEquation: String,
    mseEquation: String,
    gradientEquation: String,
    featureName: String,
    targetName: String
)

final case class GradientDescentOptimizationSummary(
    initialWeight: Double,
    finalWeight: Double,
    learningRate: Double,
    epochs: Int,
    closedFormWeight: Double,
    initialSumSquaredError: Double,
    finalSumSquaredError: Double,
    initialMse: Double,
    finalMse: Double,
    weightErrorVsClosedForm: Double,
    gradientChecks: GradientCheckSummary,
    lossTrace: GradientLossTraceSummary
)

final case class GradientDescentSummary(
    dataset: GradientDescentDatasetSummary,
    model: GradientDescentModelSummary,
    optimization: GradientDescentOptimizationSummary
)

final case class GradientDescentAnalysisResult(
    headers: Vector[String],
    traceRows: Vector[GradientDescentTraceRow],
    summary: GradientDescentSummary
)

object GradientDescentAnalysisService:
  private val DefaultLearningRate = 5.0e-5
  private val DefaultEpochs = 250
  private val CsvHeaders = Vector("epoch", "weight", "gradient", "sum_squared_error", "mse")

  def analyze(
      compound: PcCompound,
      sdfPath: Path,
      learningRate: Double = DefaultLearningRate,
      epochs: Int = DefaultEpochs
  ): GradientDescentAnalysisResult =
    require(learningRate > 0.0, "Gradient descent learning rate must be positive")
    require(epochs > 0, "Gradient descent epochs must be positive")
    require(
      compound.atoms.aid.size == compound.atoms.element.size,
      "Compound atom ids and atomic numbers must have the same size"
    )

    val dataset = buildAtomFeatureRows(compound, sdfPath)
    val xValues = dataset.map(_.mass)
    val yValues = dataset.map(_.atomicNumber.toDouble)
    val traceRows = runManualGradientDescent(xValues, yValues, learningRate, epochs)
    val finalWeight = traceRows.last.weight
    val initialWeight = traceRows.head.weight
    val closedFormWeight =
      xValues.zip(yValues).map((xValue, yValue) => xValue * yValue).sum / xValues.map(xValue => xValue * xValue).sum

    GradientDescentAnalysisResult(
      headers = CsvHeaders,
      traceRows = traceRows,
      summary = GradientDescentSummary(
        dataset = GradientDescentDatasetSummary(
          rowCount = dataset.size,
          feature = "mass",
          target = "atomicNumber",
          featureMatrixShape = Vector(dataset.size, 1),
          massRange = Vector(dataset.map(_.mass).min, dataset.map(_.mass).max),
          atomicNumberRange = Vector(dataset.map(_.atomicNumber).min, dataset.map(_.atomicNumber).max),
          atomRows = dataset
        ),
        model = GradientDescentModelSummary(
          predictionEquation = "y_hat = w * x",
          objectiveName = "sum_squared_error",
          objectiveEquation = "L(w) = sum_i (y_i - w x_i)^2",
          mseEquation = "MSE(w) = (1 / n) * sum_i (y_i - w x_i)^2",
          gradientEquation = "dL/dw = sum_i -2 x_i (y_i - w x_i) = 2 sum_i x_i (w x_i - y_i)",
          featureName = "atom mass",
          targetName = "atomic number"
        ),
        optimization = GradientDescentOptimizationSummary(
          initialWeight = initialWeight,
          finalWeight = finalWeight,
          learningRate = learningRate,
          epochs = epochs,
          closedFormWeight = closedFormWeight,
          initialSumSquaredError = traceRows.head.sumSquaredError,
          finalSumSquaredError = traceRows.last.sumSquaredError,
          initialMse = traceRows.head.mse,
          finalMse = traceRows.last.mse,
          weightErrorVsClosedForm = finalWeight - closedFormWeight,
          gradientChecks = GradientCheckSummary(
            initialWeight = GradientCheck(
              analytic = computeSumSquaredErrorGradient(xValues, yValues, initialWeight),
              finiteDifference = finiteDifferenceGradient(xValues, yValues, initialWeight)
            ),
            finalWeight = GradientCheck(
              analytic = computeSumSquaredErrorGradient(xValues, yValues, finalWeight),
              finiteDifference = finiteDifferenceGradient(xValues, yValues, finalWeight)
            )
          ),
          lossTrace = GradientLossTraceSummary(
            monotonicNonincreasingMse = traceRows.sliding(2).forall {
              case Vector(left, right) => right.mse <= left.mse + 1.0e-12
              case _                   => true
            },
            bestEpoch = traceRows.minBy(_.mse).epoch
          )
        )
      )
    )

  def writeTraceCsv(result: GradientDescentAnalysisResult, outputPath: Path): Path =
    Files.createDirectories(outputPath.getParent)
    val writer = Files.newBufferedWriter(outputPath, StandardCharsets.UTF_8)
    val printer = new CSVPrinter(writer, CSVFormat.DEFAULT.builder().setHeader(result.headers*).build())

    try
      result.traceRows.foreach { row =>
        printer.printRecord(
          Seq(
            row.epoch.toString,
            row.weight.toString,
            row.gradient.toString,
            row.sumSquaredError.toString,
            row.mse.toString
          ).asJava
        )
      }
    finally
      printer.close(true)

    outputPath

  def writeLossPlot(result: GradientDescentAnalysisResult, outputPath: Path): Path =
    Files.createDirectories(outputPath.getParent)

    val chart = new XYChartBuilder()
      .width(1200)
      .height(700)
      .title("Manual Gradient Descent MSE Trace")
      .xAxisTitle("Epoch")
      .yAxisTitle("MSE")
      .build()

    chart.getStyler.setLegendVisible(false)
    chart.getStyler.setPlotGridLinesVisible(true)
    chart.getStyler.setMarkerSize(6)

    val epochs = result.traceRows.map(_.epoch.toDouble).toArray
    val mseValues = result.traceRows.map(_.mse).toArray
    val series = chart.addSeries("MSE", epochs, mseValues)
    series.setMarker(SeriesMarkers.NONE)

    BitmapEncoder.saveBitmap(chart, outputPath.toString.stripSuffix(".png"), BitmapFormat.PNG)
    outputPath

  def writeFitPlot(result: GradientDescentAnalysisResult, outputPath: Path): Path =
    Files.createDirectories(outputPath.getParent)

    val atomRows = result.summary.dataset.atomRows
    val maxMass = atomRows.map(_.mass).max
    val lineX = Vector.tabulate(200) { index =>
      index.toDouble / 199.0 * maxMass * 1.05
    }
    val lineY = lineX.map(_ * result.summary.optimization.finalWeight)

    val chart = new XYChartBuilder()
      .width(1200)
      .height(700)
      .title("Manual Gradient Descent Fit: Mass to Atomic Number")
      .xAxisTitle("Atom mass")
      .yAxisTitle("Atomic number")
      .build()

    chart.getStyler.setLegendVisible(true)
    chart.getStyler.setPlotGridLinesVisible(true)
    chart.getStyler.setMarkerSize(10)

    val pointSeries = chart.addSeries(
      "Atom feature rows",
      atomRows.map(_.mass).toArray,
      atomRows.map(_.atomicNumber.toDouble).toArray
    )
    pointSeries.setLineStyle(org.knowm.xchart.style.lines.SeriesLines.NONE)
    pointSeries.setMarker(SeriesMarkers.CIRCLE)

    val lineSeries = chart.addSeries(
      s"y_hat = ${formatCompact(result.summary.optimization.finalWeight)}x",
      lineX.toArray,
      lineY.toArray
    )
    lineSeries.setMarker(SeriesMarkers.NONE)

    BitmapEncoder.saveBitmap(chart, outputPath.toString.stripSuffix(".png"), BitmapFormat.PNG)
    outputPath

  private def buildAtomFeatureRows(compound: PcCompound, sdfPath: Path): Vector[AtomFeatureRow] =
    val isotopeFactory = Isotopes.getInstance()
    val reader =
      new IteratingSDFReader(new FileInputStream(sdfPath.toFile), DefaultChemObjectBuilder.getInstance())

    try
      if !reader.hasNext then
        throw IllegalStateException(s"SDF file $sdfPath does not contain any molecules")

      val molecule = reader.next()
      require(
        molecule.getAtomCount == compound.atoms.aid.size,
        s"SDF atom count ${molecule.getAtomCount} does not match compound atom count ${compound.atoms.aid.size}"
      )

      compound.atoms.aid.zip(compound.atoms.element).zipWithIndex.map {
        case ((_, atomicNumber), atomIndex) =>
          val atom = molecule.getAtom(atomIndex)
          val symbol =
            Option(atom.getSymbol).filter(_.nonEmpty).getOrElse(isotopeFactory.getElementSymbol(atomicNumber))
          val mass = roundTo3(isotopeFactory.getNaturalMass(atomicNumber))
          AtomFeatureRow(
            index = atomIndex,
            symbol = symbol,
            mass = mass,
            atomicNumber = atomicNumber
          )
      }.toVector
    finally
      reader.close()

  private def computePredictions(xValues: Vector[Double], weight: Double): Vector[Double] =
    xValues.map(_ * weight)

  private def computeSumSquaredError(xValues: Vector[Double], yValues: Vector[Double], weight: Double): Double =
    yValues.zip(computePredictions(xValues, weight)).map { (yValue, prediction) =>
      val residual = yValue - prediction
      residual * residual
    }.sum

  private def computeMeanSquaredError(xValues: Vector[Double], yValues: Vector[Double], weight: Double): Double =
    computeSumSquaredError(xValues, yValues, weight) / xValues.size.toDouble

  private def computeSumSquaredErrorGradient(
      xValues: Vector[Double],
      yValues: Vector[Double],
      weight: Double
  ): Double =
    2.0 * xValues.zip(yValues).map { (xValue, yValue) =>
      xValue * ((weight * xValue) - yValue)
    }.sum

  private def finiteDifferenceGradient(
      xValues: Vector[Double],
      yValues: Vector[Double],
      weight: Double,
      epsilon: Double = 1.0e-6
  ): Double =
    val forwardLoss = computeSumSquaredError(xValues, yValues, weight + epsilon)
    val backwardLoss = computeSumSquaredError(xValues, yValues, weight - epsilon)
    (forwardLoss - backwardLoss) / (2.0 * epsilon)

  private def runManualGradientDescent(
      xValues: Vector[Double],
      yValues: Vector[Double],
      learningRate: Double,
      epochs: Int,
      initialWeight: Double = 0.0
  ): Vector[GradientDescentTraceRow] =
    var weight = initialWeight

    Vector.tabulate(epochs + 1) { epoch =>
      val sumSquaredError = computeSumSquaredError(xValues, yValues, weight)
      val mse = computeMeanSquaredError(xValues, yValues, weight)
      val gradient = computeSumSquaredErrorGradient(xValues, yValues, weight)
      val row = GradientDescentTraceRow(
        epoch = epoch,
        weight = weight,
        gradient = gradient,
        sumSquaredError = sumSquaredError,
        mse = mse
      )

      if epoch < epochs then
        weight = weight - (learningRate * gradient)

      row
    }

  private def roundTo3(value: Double): Double =
    BigDecimal(value).setScale(3, RoundingMode.HALF_UP).toDouble

  private def formatCompact(value: Double): String =
    f"$value%.4f"
