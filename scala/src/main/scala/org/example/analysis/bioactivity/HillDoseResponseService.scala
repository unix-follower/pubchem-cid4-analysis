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

final case class HillDoseResponseRowCounts(
    totalRows: Int,
    rowsWithNumericActivityValue: Int,
    rowsWithPositiveActivityValue: Int,
    rowsFlaggedHasDoseResponseCurve: Int,
    retainedRows: Int,
    retainedRowsFlaggedHasDoseResponseCurve: Int,
    retainedUniqueBioassays: Int
)

final case class HillDoseResponseStatistic(min: Double, median: Double, max: Double)

final case class HillDoseResponseStatistics(
    activityValueAsInferredK: HillDoseResponseStatistic,
    midpointFirstDerivative: HillDoseResponseStatistic
)

final case class HillDoseResponseActivityTypeCount(activityType: String, count: Int)

final case class HillDoseResponseRepresentativeRow(
    bioactivityId: Long,
    bioAssayAid: Long,
    activityType: String,
    targetName: String,
    activityValue: Double,
    inferredKActivityValue: Double,
    log10MidpointConcentration: Double
)

final case class HillDoseResponseMidpointSummary(condition: String, response: Double, interpretation: String)

final case class HillDoseResponseLinearInflectionSummary(
    formula: String,
    responseFormula: String,
    relativeToK: Double,
    normalizedResponse: Double
)

final case class HillDoseResponseSummary(
    model: String,
    equation: String,
    firstDerivative: String,
    secondDerivative: String,
    referenceHillCoefficientN: Double,
    parameterInterpretation: String,
    midpointInLogConcentrationSpace: HillDoseResponseMidpointSummary,
    linearConcentrationInflection: Option[HillDoseResponseLinearInflectionSummary],
    fitStatus: String,
    representativeRows: Vector[HillDoseResponseRepresentativeRow],
    notes: Vector[String]
)

final case class HillDoseResponseSummaryResult(
    rowCounts: HillDoseResponseRowCounts,
    statistics: HillDoseResponseStatistics,
    activityTypeCounts: Map[String, Int],
    analysis: HillDoseResponseSummary
)

final case class HillDoseResponseAnalysisResult(
    headers: Vector[String],
    rows: Vector[Map[String, String]],
    summary: HillDoseResponseSummaryResult
)

object HillDoseResponseService:
  private val CsvFormat = CSVFormat.DEFAULT.builder().setHeader().setSkipHeaderRecord(true).build()
  private val RequiredColumns = Vector("Bioactivity_ID", "BioAssay_AID", "Activity_Type", "Activity_Value")
  private val DefaultHillCoefficient = 1.0

  def analyze(csvPath: Path, hillCoefficient: Double = DefaultHillCoefficient): HillDoseResponseAnalysisResult =
    require(hillCoefficient > 0.0, "Hill coefficient must be positive")

    val parser = CSVParser.parse(csvPath, StandardCharsets.UTF_8, CsvFormat)

    try
      val headers = parser.getHeaderNames.asScala.toVector
      validateHeaders(headers)

      val allRows = parser.iterator().asScala.toVector.map { record =>
        headers.map(header => header -> record.get(header)).toMap
      }

      val numericActivityValues = allRows.map(row => parseDouble(row("Activity_Value")))
      val rowsWithNumericActivityValue = numericActivityValues.count(_.isDefined)
      val rowsWithPositiveActivityValue = numericActivityValues.count(_.exists(_ > 0.0))
      val rowsFlaggedHasDoseResponseCurve = allRows.count(row => parseFlag(row.get("Has_Dose_Response_Curve").orNull))

      val linearInflectionScale = hillLinearInflectionScale(hillCoefficient)

      val retainedRows = allRows.flatMap { row =>
        parsePositiveDouble(row("Activity_Value")).map { activityValue =>
          val inferredK = activityValue
          val midpointConcentration = inferredK
          val midpointFirstDerivative = hillResponseFirstDerivative(midpointConcentration, inferredK, hillCoefficient)
          val baseRow = row ++ Map(
            "Activity_Value" -> activityValue.toString,
            "hill_coefficient_n" -> hillCoefficient.toString,
            "inferred_K_activity_value" -> inferredK.toString,
            "midpoint_concentration" -> midpointConcentration.toString,
            "midpoint_response" -> 0.5.toString,
            "midpoint_first_derivative" -> midpointFirstDerivative.toString,
            "log10_midpoint_concentration" -> math.log10(midpointConcentration).toString,
            "fit_status" -> "reference_curve_inferred_from_activity_value",
            "analysis_mode" -> "reference_curve"
          )

          linearInflectionScale match
            case Some(scale) =>
              val concentration = inferredK * scale
              baseRow ++ Map(
                "linear_inflection_concentration" -> concentration.toString,
                "linear_inflection_response" -> hillResponse(concentration, inferredK, hillCoefficient).toString
              )
            case None =>
              baseRow ++ Map(
                "linear_inflection_concentration" -> "",
                "linear_inflection_response" -> ""
              )
        }
      }.sortBy(row => (row("inferred_K_activity_value").toDouble, row("BioAssay_AID").toLong))

      if retainedRows.isEmpty then
        throw IllegalStateException(s"No positive numeric Activity_Value rows were found in ${csvPath.getFileName}")

      val inferredKValues = retainedRows.map(_("inferred_K_activity_value").toDouble)
      val midpointDerivatives = retainedRows.map(_("midpoint_first_derivative").toDouble)
      val representativeRows = selectRepresentativeRows(retainedRows)
      val activityTypeCounts = retainedRows
        .groupBy(row => normalizeLabel(row("Activity_Type"), fallback = "Unknown"))
        .view
        .mapValues(_.size)
        .toMap

      val summary = HillDoseResponseSummaryResult(
        rowCounts = HillDoseResponseRowCounts(
          totalRows = allRows.size,
          rowsWithNumericActivityValue = rowsWithNumericActivityValue,
          rowsWithPositiveActivityValue = rowsWithPositiveActivityValue,
          rowsFlaggedHasDoseResponseCurve = rowsFlaggedHasDoseResponseCurve,
          retainedRows = retainedRows.size,
          retainedRowsFlaggedHasDoseResponseCurve =
            retainedRows.count(row => parseFlag(row.get("Has_Dose_Response_Curve").orNull)),
          retainedUniqueBioassays = retainedRows.map(_("BioAssay_AID").toLong).distinct.size
        ),
        statistics = HillDoseResponseStatistics(
          activityValueAsInferredK = HillDoseResponseStatistic(
            min = inferredKValues.min,
            median = computeMedian(inferredKValues),
            max = inferredKValues.max
          ),
          midpointFirstDerivative = HillDoseResponseStatistic(
            min = midpointDerivatives.min,
            median = computeMedian(midpointDerivatives),
            max = midpointDerivatives.max
          )
        ),
        activityTypeCounts = activityTypeCounts.toVector
          .sortBy { case (activityType, count) => (-count, activityType) }
          .toMap,
        analysis = HillDoseResponseSummary(
          model = "normalized Hill equation",
          equation = "f(c) = c^n / (K^n + c^n)",
          firstDerivative = "f'(c) = n K^n c^(n-1) / (K^n + c^n)^2",
          secondDerivative = "f''(c) = n K^n c^(n-2) * ((n - 1)K^n - (n + 1)c^n) / (K^n + c^n)^3",
          referenceHillCoefficientN = hillCoefficient,
          parameterInterpretation =
            "Activity_Value is treated as an inferred K parameter because this dataset provides potency-style summary values rather than raw concentration-response observations for CID 4.",
          midpointInLogConcentrationSpace = HillDoseResponseMidpointSummary(
            condition = "c = K",
            response = 0.5,
            interpretation = "The Hill curve is centered at c = K in log-concentration space."
          ),
          linearConcentrationInflection = linearInflectionScale.map { scale =>
            HillDoseResponseLinearInflectionSummary(
              formula = "c* = K * ((n - 1)/(n + 1))^(1/n)",
              responseFormula = "f(c*) = (n - 1)/(2n)",
              relativeToK = scale,
              normalizedResponse = (hillCoefficient - 1.0) / (2.0 * hillCoefficient)
            )
          },
          fitStatus = "reference_curve_inferred_from_activity_value",
          representativeRows = representativeRows.map(toRepresentativeRow),
          notes = Vector(
            "No nonlinear dose-response fitting was performed because the CSV does not contain raw per-concentration response series for CID 4.",
            "Rows with positive numeric Activity_Value are modeled as reference Hill curves using Activity_Value as the inferred half-maximal scale K."
          )
        )
      )

      HillDoseResponseAnalysisResult(
        headers = headers ++ Vector(
          "hill_coefficient_n",
          "inferred_K_activity_value",
          "midpoint_concentration",
          "midpoint_response",
          "midpoint_first_derivative",
          "log10_midpoint_concentration",
          "linear_inflection_concentration",
          "linear_inflection_response",
          "fit_status",
          "analysis_mode"
        ),
        rows = retainedRows,
        summary = summary
      )
    finally
      parser.close()

  def writeCsv(result: HillDoseResponseAnalysisResult, outputPath: Path): Path =
    Files.createDirectories(outputPath.getParent)
    val writer = Files.newBufferedWriter(outputPath, StandardCharsets.UTF_8)
    val printer = new CSVPrinter(writer, CSVFormat.DEFAULT.builder().setHeader(result.headers*).build())

    try
      result.rows.foreach { row =>
        printer.printRecord(result.headers.map(header => row.getOrElse(header, "")).asJava)
      }
    finally
      printer.close(true)

    outputPath

  def writePlot(result: HillDoseResponseAnalysisResult, outputPath: Path): Path =
    Files.createDirectories(outputPath.getParent)

    val representativeRows = result.summary.analysis.representativeRows
    if representativeRows.isEmpty then
      throw IllegalArgumentException("Hill reference-curve plot requires at least one representative row")

    val representativeKValues = representativeRows.map(_.inferredKActivityValue)
    val minK = representativeKValues.min
    val maxK = representativeKValues.max
    val curveX = geometricSpace(math.max(minK / 100.0, 1e-6), maxK * 100.0, 400)

    val chart = new XYChartBuilder()
      .width(1200)
      .height(700)
      .title(
        s"Reference Hill Curves Inferred from Activity_Value (n = ${formatCompact(result.summary.analysis.referenceHillCoefficientN)})"
      )
      .xAxisTitle("Concentration c (same units as Activity_Value)")
      .yAxisTitle("Normalized response f(c)")
      .build()

    chart.getStyler.setXAxisLogarithmic(true)
    chart.getStyler.setMarkerSize(9)
    chart.getStyler.setLegendVisible(true)
    chart.getStyler.setPlotGridLinesVisible(true)
    chart.getStyler.setYAxisMin(-0.02)
    chart.getStyler.setYAxisMax(1.02)

    representativeRows.foreach { row =>
      val curveY = curveX.map(value =>
        hillResponse(value, row.inferredKActivityValue, result.summary.analysis.referenceHillCoefficientN)
      )
      val label = s"AID ${row.bioAssayAid} | ${row.activityType} | K=${formatCompact(row.inferredKActivityValue)}"

      val curveSeries = chart.addSeries(label, curveX.toArray, curveY.toArray)
      curveSeries.setMarker(SeriesMarkers.NONE)

      val midpointSeries =
        chart.addSeries(s"midpoint AID ${row.bioAssayAid}", Array(row.inferredKActivityValue), Array(0.5))
      midpointSeries.setLineStyle(org.knowm.xchart.style.lines.SeriesLines.NONE)
      midpointSeries.setMarker(SeriesMarkers.CIRCLE)
    }

    BitmapEncoder.saveBitmap(chart, outputPath.toString.stripSuffix(".png"), BitmapFormat.PNG)
    outputPath

  private def validateHeaders(headers: Vector[String]): Unit =
    val missing = RequiredColumns.filterNot(headers.contains)
    if missing.nonEmpty then
      throw IllegalArgumentException(s"Bioactivity CSV is missing required columns: ${missing.mkString(", ")}")

  private def parseDouble(value: String): Option[Double] =
    Option(value)
      .map(_.trim)
      .filter(_.nonEmpty)
      .flatMap(raw => Try(raw.toDouble).toOption)

  private def parsePositiveDouble(value: String): Option[Double] =
    parseDouble(value).filter(_ > 0.0)

  private def parseFlag(value: String): Boolean =
    parseDouble(value).exists(number => math.round(number) == 1L)

  private def computeMedian(values: Vector[Double]): Double =
    val median = new Median()
    median.evaluate(values.sorted.toArray)

  private def hillResponse(concentration: Double, halfMaximalConcentration: Double, hillCoefficient: Double): Double =
    val numerator = math.pow(concentration, hillCoefficient)
    val denominator = math.pow(halfMaximalConcentration, hillCoefficient) + numerator
    numerator / denominator

  private def hillResponseFirstDerivative(
      concentration: Double,
      halfMaximalConcentration: Double,
      hillCoefficient: Double
  ): Double =
    val numerator =
      hillCoefficient * math.pow(halfMaximalConcentration, hillCoefficient) * math.pow(
        concentration,
        hillCoefficient - 1.0
      )
    val denominator = math.pow(
      math.pow(halfMaximalConcentration, hillCoefficient) + math.pow(concentration, hillCoefficient),
      2.0
    )
    numerator / denominator

  private def hillLinearInflectionScale(hillCoefficient: Double): Option[Double] =
    if hillCoefficient <= 1.0 then None
    else Some(math.pow((hillCoefficient - 1.0) / (hillCoefficient + 1.0), 1.0 / hillCoefficient))

  private def selectRepresentativeRows(rows: Vector[Map[String, String]]): Vector[Map[String, String]] =
    val indices = Vector(0, rows.size / 2, rows.size - 1).distinct.sorted
    indices.map(rows)

  private def toRepresentativeRow(row: Map[String, String]): HillDoseResponseRepresentativeRow =
    HillDoseResponseRepresentativeRow(
      bioactivityId = row("Bioactivity_ID").toLong,
      bioAssayAid = row("BioAssay_AID").toLong,
      activityType = normalizeLabel(row("Activity_Type"), fallback = "Unknown"),
      targetName = normalizeLabel(row.getOrElse("Target_Name", ""), fallback = "Unknown"),
      activityValue = row("Activity_Value").toDouble,
      inferredKActivityValue = row("inferred_K_activity_value").toDouble,
      log10MidpointConcentration = row("log10_midpoint_concentration").toDouble
    )

  private def normalizeLabel(value: String, fallback: String): String =
    Option(value).map(_.trim).filter(_.nonEmpty).getOrElse(fallback)

  private def geometricSpace(start: Double, end: Double, points: Int): Vector[Double] =
    if points < 2 then Vector(start)
    else
      val logStart = math.log10(start)
      val logEnd = math.log10(end)
      Vector.tabulate(points) { index =>
        val t = index.toDouble / (points - 1).toDouble
        math.pow(10.0, logStart + t * (logEnd - logStart))
      }

  private def formatCompact(value: Double): String =
    f"$value%.4g"
