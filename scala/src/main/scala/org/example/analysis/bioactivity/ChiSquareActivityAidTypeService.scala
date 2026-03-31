package org.example.analysis.bioactivity

import org.apache.commons.csv.CSVFormat
import org.apache.commons.csv.CSVParser
import org.apache.commons.csv.CSVPrinter
import org.apache.commons.math3.distribution.ChiSquaredDistribution

import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import scala.jdk.CollectionConverters.*

final case class ChiSquareActivityAidTypeRowCounts(
    totalRows: Int,
    activeRows: Int,
    inactiveRows: Int,
    unspecifiedRows: Int,
    otherActivityRows: Int,
    retainedBinaryRows: Int,
    droppedNonBinaryRows: Int,
    retainedUniqueBioassays: Int,
    retainedRowsWithAidType: Int,
    activityLevelsTested: Int,
    aidTypeLevelsTested: Int
)

final case class ChiSquareContingencyTable(
    activityLevels: Vector[String],
    aidTypeLevels: Vector[String],
    observedCounts: Map[String, Map[String, Int]],
    expectedCounts: Map[String, Map[String, Option[Double]]]
)

final case class ChiSquareVariables(row: String, column: String)

final case class ChiSquareTestMetrics(
    variables: ChiSquareVariables,
    nullHypothesis: String,
    alternativeHypothesis: String,
    computed: Boolean,
    reasonNotComputed: Option[String],
    chi2Statistic: Option[Double],
    pValue: Option[Double],
    degreesOfFreedom: Option[Int],
    minimumExpectedCountThreshold: Double,
    sparseExpectedCellCount: Option[Int],
    sparseExpectedCellFraction: Option[Double]
)

final case class ChiSquareRepresentativeCell(
    activity: String,
    aidType: String,
    observedCount: Int,
    expectedCount: Option[Double]
)

final case class ChiSquareBinaryEvidenceDefinition(
    retainedLabels: Vector[String],
    excludedLabels: Vector[String],
    interpretation: String
)

final case class ChiSquareAnalysis(
    targetQuantity: String,
    model: String,
    binaryEvidenceDefinition: ChiSquareBinaryEvidenceDefinition,
    representativeCells: Vector[ChiSquareRepresentativeCell],
    notes: Vector[String]
)

final case class ChiSquareSummaryResult(
    rowCounts: ChiSquareActivityAidTypeRowCounts,
    contingencyTable: ChiSquareContingencyTable,
    chiSquareTest: ChiSquareTestMetrics,
    analysis: ChiSquareAnalysis
)

final case class ChiSquareActivityAidTypeAnalysisResult(
    headers: Vector[String],
    rows: Vector[Map[String, String]],
    summary: ChiSquareSummaryResult
)

object ChiSquareActivityAidTypeService:
  private val CsvFormat = CSVFormat.DEFAULT.builder().setHeader().setSkipHeaderRecord(true).build()
  private val RequiredColumns = Vector("Bioactivity_ID", "BioAssay_AID", "Activity", "Aid_Type")
  private val ContingencyHeaders = Vector("Activity", "Aid_Type", "observed_count", "expected_count")
  private val DefaultChiSquareExpectedCountThreshold = 5.0
  private val NotComputedReason =
    "Chi-square test requires at least two observed Activity levels and two Aid_Type levels after binary filtering."

  def analyze(
      csvPath: Path,
      minExpectedCountThreshold: Double = DefaultChiSquareExpectedCountThreshold
  ): ChiSquareActivityAidTypeAnalysisResult =
    require(minExpectedCountThreshold > 0.0, "Chi-square expected-count threshold must be positive")

    val parser = CSVParser.parse(csvPath, StandardCharsets.UTF_8, CsvFormat)

    try
      val headers = parser.getHeaderNames.asScala.toVector
      validateHeaders(headers)

      val allRows = parser.iterator().asScala.toVector.map { record =>
        headers.map(header => header -> record.get(header)).toMap
      }

      val normalizedActivities = allRows.map(row => normalizeActivity(row.getOrElse("Activity", "")))
      val activeRows = normalizedActivities.count(_ == "ACTIVE")
      val inactiveRows = normalizedActivities.count(_ == "INACTIVE")
      val unspecifiedRows = normalizedActivities.count(_ == "UNSPECIFIED")
      val otherActivityRows = normalizedActivities.count(label =>
        label != "ACTIVE" && label != "INACTIVE" && label != "UNSPECIFIED"
      )

      val retainedRows = allRows.zip(normalizedActivities).collect {
        case (row, normalizedActivity) if normalizedActivity == "ACTIVE" || normalizedActivity == "INACTIVE" =>
          row ++ Map(
            "Activity" -> toTitleCase(normalizedActivity),
            "Aid_Type" -> normalizeLabel(row.getOrElse("Aid_Type", ""), fallback = "Unknown")
          )
      }.sortBy(row => (row("Activity"), row("Aid_Type"), row("BioAssay_AID").toLong, row("Bioactivity_ID").toLong))

      if retainedRows.isEmpty then
        throw IllegalStateException(s"No Active/Inactive rows were found in ${csvPath.getFileName}")

      val activityLevels = retainedRows.map(_("Activity")).distinct.sorted
      val aidTypeLevels = retainedRows.map(_("Aid_Type")).distinct.sorted

      val observedCounts = activityLevels.map { activity =>
        val countsByAidType = aidTypeLevels.map { aidType =>
          val count = retainedRows.count(row => row("Activity") == activity && row("Aid_Type") == aidType)
          aidType -> count
        }.toMap
        activity -> countsByAidType
      }.toMap

      val rowCounts = ChiSquareActivityAidTypeRowCounts(
        totalRows = allRows.size,
        activeRows = activeRows,
        inactiveRows = inactiveRows,
        unspecifiedRows = unspecifiedRows,
        otherActivityRows = otherActivityRows,
        retainedBinaryRows = retainedRows.size,
        droppedNonBinaryRows = allRows.size - retainedRows.size,
        retainedUniqueBioassays = retainedRows.map(_("BioAssay_AID").toLong).distinct.size,
        retainedRowsWithAidType = retainedRows.size,
        activityLevelsTested = activityLevels.size,
        aidTypeLevelsTested = aidTypeLevels.size
      )

      val observedMatrix = activityLevels.map { activity =>
        aidTypeLevels.map(aidType => observedCounts(activity)(aidType).toDouble).toArray
      }.toArray

      val hasMinimumShape = activityLevels.size >= 2 && aidTypeLevels.size >= 2
      val expectedMatrix =
        if hasMinimumShape then computeExpectedCounts(observedMatrix)
        else Array.fill(activityLevels.size, aidTypeLevels.size)(Option.empty[Double])

      val expectedCounts = activityLevels.zipWithIndex.map { case (activity, rowIndex) =>
        val countsByAidType = aidTypeLevels.zipWithIndex.map { case (aidType, columnIndex) =>
          aidType -> expectedMatrix(rowIndex)(columnIndex)
        }.toMap
        activity -> countsByAidType
      }.toMap

      val chiSquareMetrics =
        if hasMinimumShape then
          val chi2Statistic = computeChiSquareStatistic(observedMatrix, expectedMatrix)
          val degreesOfFreedom = (activityLevels.size - 1) * (aidTypeLevels.size - 1)
          val distribution = new ChiSquaredDistribution(degreesOfFreedom.toDouble)
          val flattenedExpected = expectedMatrix.flatten.flatten
          val sparseExpectedCellCount = flattenedExpected.count(_ < minExpectedCountThreshold)
          val sparseExpectedCellFraction = sparseExpectedCellCount.toDouble / flattenedExpected.size.toDouble

          ChiSquareTestMetrics(
            variables = ChiSquareVariables(row = "Activity", column = "Aid_Type"),
            nullHypothesis =
              "Activity and Aid_Type are statistically independent within the retained binary bioactivity rows.",
            alternativeHypothesis =
              "Activity and Aid_Type are statistically associated within the retained binary bioactivity rows.",
            computed = true,
            reasonNotComputed = None,
            chi2Statistic = Some(chi2Statistic),
            pValue = Some(1.0 - distribution.cumulativeProbability(chi2Statistic)),
            degreesOfFreedom = Some(degreesOfFreedom),
            minimumExpectedCountThreshold = minExpectedCountThreshold,
            sparseExpectedCellCount = Some(sparseExpectedCellCount),
            sparseExpectedCellFraction = Some(sparseExpectedCellFraction)
          )
        else
          ChiSquareTestMetrics(
            variables = ChiSquareVariables(row = "Activity", column = "Aid_Type"),
            nullHypothesis =
              "Activity and Aid_Type are statistically independent within the retained binary bioactivity rows.",
            alternativeHypothesis =
              "Activity and Aid_Type are statistically associated within the retained binary bioactivity rows.",
            computed = false,
            reasonNotComputed = Some(NotComputedReason),
            chi2Statistic = None,
            pValue = None,
            degreesOfFreedom = None,
            minimumExpectedCountThreshold = minExpectedCountThreshold,
            sparseExpectedCellCount = None,
            sparseExpectedCellFraction = None
          )

      val contingencyRows = activityLevels.flatMap { activity =>
        aidTypeLevels.map { aidType =>
          Map(
            "Activity" -> activity,
            "Aid_Type" -> aidType,
            "observed_count" -> observedCounts(activity)(aidType).toString,
            "expected_count" -> expectedCounts(activity)(aidType).map(_.toString).getOrElse("")
          )
        }
      }

      val representativeCells = activityLevels.flatMap { activity =>
        aidTypeLevels.map { aidType =>
          ChiSquareRepresentativeCell(
            activity = activity,
            aidType = aidType,
            observedCount = observedCounts(activity)(aidType),
            expectedCount = expectedCounts(activity)(aidType)
          )
        }
      }.sortBy(cell => (-cell.observedCount, cell.activity, cell.aidType)).take(3)

      val summary = ChiSquareSummaryResult(
        rowCounts = rowCounts,
        contingencyTable = ChiSquareContingencyTable(
          activityLevels = activityLevels,
          aidTypeLevels = aidTypeLevels,
          observedCounts = observedCounts,
          expectedCounts = expectedCounts
        ),
        chiSquareTest = chiSquareMetrics,
        analysis = ChiSquareAnalysis(
          targetQuantity = "Activity independent of Aid_Type",
          model = "Pearson chi-square test of independence",
          binaryEvidenceDefinition = ChiSquareBinaryEvidenceDefinition(
            retainedLabels = Vector("Active", "Inactive"),
            excludedLabels = Vector("Unspecified"),
            interpretation =
              "The chi-square table is built from the same binary Activity evidence used by the posterior analysis."
          ),
          representativeCells = representativeCells,
          notes = Vector(
            "Rows with Activity = Unspecified and other non-binary Activity labels are excluded before the contingency table is built.",
            "Aid_Type values are used as observed in the CSV after trimming whitespace and filling blanks with Unknown.",
            "If fewer than two observed Activity levels or fewer than two Aid_Type levels remain after filtering, the summary records that the chi-square test is not statistically identifiable on this dataset slice."
          )
        )
      )

      ChiSquareActivityAidTypeAnalysisResult(
        headers = ContingencyHeaders,
        rows = contingencyRows,
        summary = summary
      )
    finally
      parser.close()

  def writeCsv(result: ChiSquareActivityAidTypeAnalysisResult, outputPath: Path): Path =
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

  private def validateHeaders(headers: Vector[String]): Unit =
    val missing = RequiredColumns.filterNot(headers.contains)
    if missing.nonEmpty then
      throw IllegalArgumentException(s"Bioactivity CSV is missing required columns: ${missing.mkString(", ")}")

  private def normalizeActivity(value: String): String =
    val normalized = Option(value).map(_.trim.toUpperCase).getOrElse("")
    if normalized.isEmpty then "UNSPECIFIED" else normalized

  private def normalizeLabel(value: String, fallback: String): String =
    Option(value).map(_.trim).filter(_.nonEmpty).getOrElse(fallback)

  private def toTitleCase(value: String): String =
    value.toLowerCase.capitalize

  private def computeExpectedCounts(observedMatrix: Array[Array[Double]]): Array[Array[Option[Double]]] =
    val rowTotals = observedMatrix.map(_.sum)
    val columnTotals = observedMatrix.transpose.map(_.sum)
    val grandTotal = rowTotals.sum

    observedMatrix.indices.map { rowIndex =>
      observedMatrix(rowIndex).indices.map { columnIndex =>
        Option((rowTotals(rowIndex) * columnTotals(columnIndex)) / grandTotal)
      }.toArray
    }.toArray

  private def computeChiSquareStatistic(
      observedMatrix: Array[Array[Double]],
      expectedMatrix: Array[Array[Option[Double]]]
  ): Double =
    observedMatrix.indices.map { rowIndex =>
      observedMatrix(rowIndex).indices.map { columnIndex =>
        val expected = expectedMatrix(rowIndex)(columnIndex).getOrElse(0.0)
        if expected <= 0.0 then 0.0
        else
          val difference = observedMatrix(rowIndex)(columnIndex) - expected
          (difference * difference) / expected
      }.sum
    }.sum
