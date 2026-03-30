package org.example.analysis.bioactivity

import org.apache.commons.csv.CSVFormat
import org.apache.commons.csv.CSVParser
import org.apache.commons.csv.CSVPrinter
import org.apache.commons.math3.stat.descriptive.rank.Median
import org.knowm.xchart.BitmapEncoder
import org.knowm.xchart.BitmapEncoder.BitmapFormat
import org.knowm.xchart.XYChartBuilder
import org.knowm.xchart.style.markers.SeriesMarkers

import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import scala.jdk.CollectionConverters.*
import scala.util.Try

final case class BioactivityRowCounts(
    totalRows: Int,
    rowsWithNumericActivityValue: Int,
    rowsWithIc50ActivityType: Int,
    retainedIc50Rows: Int,
    droppedRows: Int
)

final case class BioactivityStatistic(min: Double, median: Double, max: Double)

final case class BioactivityStatistics(ic50Um: BioactivityStatistic, pIC50: BioactivityStatistic)

final case class BioactivityMeasurement(
    bioactivityId: Long,
    bioAssayAid: Long,
    ic50Um: Double,
    pIC50: Double
)

final case class BioactivityAnalysisSummary(
    transform: String,
    interpretation: String,
    observedIc50DomainUm: Vector[Double],
    strongestRetainedMeasurement: BioactivityMeasurement,
    weakestRetainedMeasurement: BioactivityMeasurement
)

final case class BioactivitySummaryResult(
    rowCounts: BioactivityRowCounts,
    statistics: BioactivityStatistics,
    analysis: BioactivityAnalysisSummary
)

final case class BioactivityAnalysisResult(
    headers: Vector[String],
    filteredRows: Vector[Map[String, String]],
    summary: BioactivitySummaryResult
)

object BioactivityService:
  private val CsvFormat = CSVFormat.DEFAULT.builder().setHeader().setSkipHeaderRecord(true).build()
  private val RequiredColumns = Vector("Bioactivity_ID", "BioAssay_AID", "Activity_Type", "Activity_Value")

  def analyze(csvPath: Path): BioactivityAnalysisResult =
    val parser = CSVParser.parse(csvPath, StandardCharsets.UTF_8, CsvFormat)

    try
      val headers = parser.getHeaderNames.asScala.toVector
      validateHeaders(headers)

      val allRows = parser.iterator().asScala.toVector.map { record =>
        headers.map(header => header -> record.get(header)).toMap
      }

      val numericValueCount = allRows.count(row => parsePositiveDouble(row("Activity_Value")).isDefined)
      val ic50TypeCount = allRows.count(row => normalizeActivityType(row("Activity_Type")) == "IC50")

      val filteredRows = allRows.flatMap { row =>
        val normalizedType = normalizeActivityType(row("Activity_Type"))
        parsePositiveDouble(row("Activity_Value")).collect {
          case activityValue if normalizedType == "IC50" =>
            row ++ Map(
              "Activity_Value" -> activityValue.toString,
              "IC50_uM" -> activityValue.toString,
              "pIC50" -> (-math.log10(activityValue)).toString
            )
        }
      }.sortBy(row => -row("pIC50").toDouble)

      if filteredRows.isEmpty then
        throw IllegalStateException(s"No positive numeric IC50 rows were found in ${csvPath.getFileName}")

      val ic50Values = filteredRows.map(_("IC50_uM").toDouble)
      val pic50Values = filteredRows.map(_("pIC50").toDouble)

      val counts = BioactivityRowCounts(
        totalRows = allRows.size,
        rowsWithNumericActivityValue = numericValueCount,
        rowsWithIc50ActivityType = ic50TypeCount,
        retainedIc50Rows = filteredRows.size,
        droppedRows = allRows.size - filteredRows.size
      )

      val summary = BioactivitySummaryResult(
        rowCounts = counts,
        statistics = BioactivityStatistics(
          ic50Um = BioactivityStatistic(
            min = ic50Values.min,
            median = computeMedian(ic50Values),
            max = ic50Values.max
          ),
          pIC50 = BioactivityStatistic(
            min = pic50Values.min,
            median = computeMedian(pic50Values),
            max = pic50Values.max
          )
        ),
        analysis = BioactivityAnalysisSummary(
          transform = "pIC50 = -log10(IC50_uM)",
          interpretation = "Lower IC50 values map to higher pIC50 values, so potency increases as the curve rises.",
          observedIc50DomainUm = Vector(ic50Values.min, ic50Values.max),
          strongestRetainedMeasurement = toMeasurement(filteredRows.maxBy(_("pIC50").toDouble)),
          weakestRetainedMeasurement = toMeasurement(filteredRows.minBy(_("pIC50").toDouble))
        )
      )

      BioactivityAnalysisResult(
        headers = headers ++ Vector("IC50_uM", "pIC50"),
        filteredRows = filteredRows,
        summary = summary
      )
    finally
      parser.close()

  def writeFilteredCsv(result: BioactivityAnalysisResult, outputPath: Path): Path =
    Files.createDirectories(outputPath.getParent)
    val writer = Files.newBufferedWriter(outputPath, StandardCharsets.UTF_8)
    val printer = new CSVPrinter(writer, CSVFormat.DEFAULT.builder().setHeader(result.headers*).build())

    try
      result.filteredRows.foreach { row =>
        printer.printRecord(result.headers.map(header => row.getOrElse(header, "")).asJava)
      }
    finally
      printer.close(true)

    outputPath

  def writePlot(result: BioactivityAnalysisResult, outputPath: Path): Path =
    Files.createDirectories(outputPath.getParent)

    val observedIc50 = result.filteredRows.map(_("IC50_uM").toDouble)
    val observedPic50 = result.filteredRows.map(_("pIC50").toDouble)
    val (minIc50, maxIc50) = expandedDomain(observedIc50.min, observedIc50.max)
    val curveX = geometricSpace(minIc50, maxIc50, 200)
    val curveY = curveX.map(value => -math.log10(value))

    val chart = new XYChartBuilder()
      .width(1200)
      .height(700)
      .title("pIC50 Transform Across Observed IC50 Range")
      .xAxisTitle("IC50 (uM)")
      .yAxisTitle("pIC50")
      .build()

    chart.getStyler.setXAxisLogarithmic(true)
    chart.getStyler.setMarkerSize(10)
    chart.getStyler.setLegendVisible(true)
    chart.getStyler.setPlotGridLinesVisible(true)

    val curveSeries = chart.addSeries("y = -log10(x)", curveX.toArray, curveY.toArray)
    curveSeries.setMarker(SeriesMarkers.NONE)

    val pointsSeries = chart.addSeries("Observed IC50 rows", observedIc50.toArray, observedPic50.toArray)
    pointsSeries.setMarker(SeriesMarkers.CIRCLE)
    pointsSeries.setLineStyle(org.knowm.xchart.style.lines.SeriesLines.NONE)

    BitmapEncoder.saveBitmap(chart, outputPath.toString.stripSuffix(".png"), BitmapFormat.PNG)
    outputPath

  private def validateHeaders(headers: Vector[String]): Unit =
    val missing = RequiredColumns.filterNot(headers.contains)
    if missing.nonEmpty then
      throw IllegalArgumentException(s"Bioactivity CSV is missing required columns: ${missing.mkString(", ")}")

  private def normalizeActivityType(value: String): String =
    Option(value).map(_.trim.toUpperCase).getOrElse("")

  private def parsePositiveDouble(value: String): Option[Double] =
    Option(value)
      .map(_.trim)
      .filter(_.nonEmpty)
      .flatMap(raw => Try(raw.toDouble).toOption)
      .filter(_ > 0.0)

  private def computeMedian(values: Vector[Double]): Double =
    val median = new Median()
    median.evaluate(values.sorted.toArray)

  private def toMeasurement(row: Map[String, String]): BioactivityMeasurement =
    BioactivityMeasurement(
      bioactivityId = row("Bioactivity_ID").toLong,
      bioAssayAid = row("BioAssay_AID").toLong,
      ic50Um = row("IC50_uM").toDouble,
      pIC50 = row("pIC50").toDouble
    )

  private def expandedDomain(minValue: Double, maxValue: Double): (Double, Double) =
    if math.abs(minValue - maxValue) < 1e-12 then
      (math.max(minValue / 10.0, 1e-6), maxValue * 10.0)
    else
      (minValue, maxValue)

  private def geometricSpace(start: Double, end: Double, points: Int): Vector[Double] =
    if points < 2 then Vector(start)
    else
      val logStart = math.log10(start)
      val logEnd = math.log10(end)
      Vector.tabulate(points) { index =>
        val t = index.toDouble / (points - 1).toDouble
        math.pow(10.0, logStart + t * (logEnd - logStart))
      }
