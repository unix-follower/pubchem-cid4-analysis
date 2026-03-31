package org.example.analysis.bioactivity

import org.apache.commons.csv.CSVFormat
import org.apache.commons.csv.CSVParser
import org.apache.commons.csv.CSVPrinter
import org.apache.commons.math3.distribution.BinomialDistribution

import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import scala.jdk.CollectionConverters.*

final case class BinomialActivityRowCounts(
    totalRows: Int,
    activeRows: Int,
    inactiveRows: Int,
    unspecifiedRows: Int,
    otherActivityRows: Int,
    retainedBinaryRows: Int,
    droppedNonBinaryRows: Int,
    retainedUniqueBioassays: Int,
    assayTrials: Int,
    activeAssayTrials: Int,
    inactiveAssayTrials: Int,
    mixedEvidenceAssayTrials: Int,
    unanimousActiveAssayTrials: Int,
    unanimousInactiveAssayTrials: Int
)

final case class BinomialActivityTrialDefinition(
    unit: String,
    successLabel: String,
    failureLabel: String,
    assayResolutionRule: String
)

final case class BinomialActivityParameters(
    nAssays: Int,
    observedActiveAssays: Int,
    successProbabilityActiveAssay: Double
)

final case class BinomialActivitySummary(
    pmfAtObservedActiveAssayCount: Double,
    cumulativeProbabilityLeqObservedActiveAssayCount: Double,
    cumulativeProbabilityGeqObservedActiveAssayCount: Double,
    binomialMeanActiveAssays: Double,
    binomialVarianceActiveAssays: Double,
    pmfProbabilitySum: Double
)

final case class BinomialActivityRepresentativeAssay(
    bioAssayAid: Long,
    assayActivity: String,
    retainedBinaryRows: Int,
    activeRows: Int,
    inactiveRows: Int,
    mixedEvidence: Boolean,
    activityType: String,
    targetName: String,
    bioAssayName: String
)

final case class BinomialActivityDistributionSection(
    trialDefinition: BinomialActivityTrialDefinition,
    parameters: BinomialActivityParameters,
    summary: BinomialActivitySummary
)

final case class BinomialActivityAnalysis(
    targetQuantity: String,
    model: String,
    equation: String,
    parameterEstimation: String,
    representativeAssays: Vector[BinomialActivityRepresentativeAssay],
    notes: Vector[String]
)

final case class BinomialActivityDistributionSummaryResult(
    rowCounts: BinomialActivityRowCounts,
    binomial: BinomialActivityDistributionSection,
    analysis: BinomialActivityAnalysis
)

final case class BinomialActivityDistributionAnalysisResult(
    headers: Vector[String],
    rows: Vector[Map[String, String]],
    summary: BinomialActivityDistributionSummaryResult
)

object BinomialActivityDistributionService:
  private val CsvFormat = CSVFormat.DEFAULT.builder().setHeader().setSkipHeaderRecord(true).build()
  private val RequiredColumns = Vector("Bioactivity_ID", "BioAssay_AID", "Activity")
  private val PmfHeaders = Vector(
    "k_active",
    "probability",
    "cumulative_probability_leq_k",
    "cumulative_probability_geq_k"
  )

  def analyze(csvPath: Path): BinomialActivityDistributionAnalysisResult =
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
            "Activity_Type" -> normalizeLabel(row.getOrElse("Activity_Type", ""), fallback = "Unknown"),
            "Target_Name" -> normalizeLabel(row.getOrElse("Target_Name", ""), fallback = "Unknown"),
            "BioAssay_Name" -> normalizeLabel(row.getOrElse("BioAssay_Name", ""), fallback = "Unknown")
          )
      }

      if retainedRows.isEmpty then
        throw IllegalStateException(s"No Active/Inactive rows were found in ${csvPath.getFileName}")

      val assayRows = retainedRows
        .groupBy(_("BioAssay_AID"))
        .toVector
        .map { case (bioAssayAid, rowsForAssay) =>
          val activeCount = rowsForAssay.count(_("Activity") == "Active")
          val inactiveCount = rowsForAssay.count(_("Activity") == "Inactive")
          val mixedEvidence = activeCount > 0 && inactiveCount > 0
          val assayActivity = if activeCount > 0 then "Active" else "Inactive"
          val sampleRow = rowsForAssay.head

          Map(
            "BioAssay_AID" -> bioAssayAid,
            "assay_activity" -> assayActivity,
            "retained_binary_rows" -> rowsForAssay.size.toString,
            "active_rows" -> activeCount.toString,
            "inactive_rows" -> inactiveCount.toString,
            "mixed_evidence" -> mixedEvidence.toString,
            "Activity_Type" -> sampleRow.getOrElse("Activity_Type", "Unknown"),
            "Target_Name" -> sampleRow.getOrElse("Target_Name", "Unknown"),
            "BioAssay_Name" -> sampleRow.getOrElse("BioAssay_Name", "Unknown")
          )
        }
        .sortBy(row => (row("assay_activity"), row("BioAssay_AID").toLong))

      if assayRows.isEmpty then
        throw IllegalStateException(s"No assay-level Active/Inactive trials were found in ${csvPath.getFileName}")

      val assayTrials = assayRows.size
      val activeAssayTrials = assayRows.count(_("assay_activity") == "Active")
      val inactiveAssayTrials = assayRows.count(_("assay_activity") == "Inactive")
      val mixedEvidenceAssayTrials = assayRows.count(_("mixed_evidence").toBoolean)
      val successProbability = activeAssayTrials.toDouble / assayTrials.toDouble
      val distribution = new BinomialDistribution(assayTrials, successProbability)

      val pmfRows = (0 to assayTrials).toVector.map { k =>
        val cumulativeGeq =
          if k <= 0 then 1.0
          else 1.0 - distribution.cumulativeProbability(k - 1)

        Map(
          "k_active" -> k.toString,
          "probability" -> distribution.probability(k).toString,
          "cumulative_probability_leq_k" -> distribution.cumulativeProbability(k).toString,
          "cumulative_probability_geq_k" -> cumulativeGeq.toString
        )
      }

      val observedPmf = distribution.probability(activeAssayTrials)
      val observedCumulativeLeq = distribution.cumulativeProbability(activeAssayTrials)
      val observedCumulativeGeq =
        if activeAssayTrials <= 0 then 1.0
        else 1.0 - distribution.cumulativeProbability(activeAssayTrials - 1)

      val representativeAssays = selectRepresentativeRows(assayRows).map(toRepresentativeAssay)

      val summary = BinomialActivityDistributionSummaryResult(
        rowCounts = BinomialActivityRowCounts(
          totalRows = allRows.size,
          activeRows = activeRows,
          inactiveRows = inactiveRows,
          unspecifiedRows = unspecifiedRows,
          otherActivityRows = otherActivityRows,
          retainedBinaryRows = retainedRows.size,
          droppedNonBinaryRows = allRows.size - retainedRows.size,
          retainedUniqueBioassays = retainedRows.map(_("BioAssay_AID").toLong).distinct.size,
          assayTrials = assayTrials,
          activeAssayTrials = activeAssayTrials,
          inactiveAssayTrials = inactiveAssayTrials,
          mixedEvidenceAssayTrials = mixedEvidenceAssayTrials,
          unanimousActiveAssayTrials = activeAssayTrials - mixedEvidenceAssayTrials,
          unanimousInactiveAssayTrials = inactiveAssayTrials
        ),
        binomial = BinomialActivityDistributionSection(
          trialDefinition = BinomialActivityTrialDefinition(
            unit = "unique_BioAssay_AID",
            successLabel = "Active assay",
            failureLabel = "Inactive assay",
            assayResolutionRule =
              "Active wins if any retained row for the assay is Active; otherwise the assay is Inactive."
          ),
          parameters = BinomialActivityParameters(
            nAssays = assayTrials,
            observedActiveAssays = activeAssayTrials,
            successProbabilityActiveAssay = successProbability
          ),
          summary = BinomialActivitySummary(
            pmfAtObservedActiveAssayCount = observedPmf,
            cumulativeProbabilityLeqObservedActiveAssayCount = observedCumulativeLeq,
            cumulativeProbabilityGeqObservedActiveAssayCount = observedCumulativeGeq,
            binomialMeanActiveAssays = assayTrials.toDouble * successProbability,
            binomialVarianceActiveAssays = assayTrials.toDouble * successProbability * (1.0 - successProbability),
            pmfProbabilitySum = pmfRows.map(_("probability").toDouble).sum
          )
        ),
        analysis = BinomialActivityAnalysis(
          targetQuantity = "P(K = k active assays in n assays)",
          model = "Binomial distribution with plug-in success probability",
          equation = "P(K = k) = C(n, k) p^k (1-p)^(n-k)",
          parameterEstimation =
            "p is estimated as the observed active assay fraction active_assays / n_assays.",
          representativeAssays = representativeAssays,
          notes = Vector(
            "The binomial model operates at the assay level rather than the raw retained-row level.",
            "Rows with Activity = Unspecified are excluded before assay-level collapsing, consistent with the posterior analysis.",
            "This is a frequentist plug-in binomial model using the observed assay-level active fraction, not a posterior-predictive distribution."
          )
        )
      )

      BinomialActivityDistributionAnalysisResult(
        headers = PmfHeaders,
        rows = pmfRows,
        summary = summary
      )
    finally
      parser.close()

  def writeCsv(result: BinomialActivityDistributionAnalysisResult, outputPath: Path): Path =
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

  private def selectRepresentativeRows(rows: Vector[Map[String, String]]): Vector[Map[String, String]] =
    val positions = Vector(0, rows.size / 2, rows.size - 1).distinct.sorted
    positions.map(rows)

  private def toRepresentativeAssay(row: Map[String, String]): BinomialActivityRepresentativeAssay =
    BinomialActivityRepresentativeAssay(
      bioAssayAid = row("BioAssay_AID").toLong,
      assayActivity = row("assay_activity"),
      retainedBinaryRows = row("retained_binary_rows").toInt,
      activeRows = row("active_rows").toInt,
      inactiveRows = row("inactive_rows").toInt,
      mixedEvidence = row("mixed_evidence").toBoolean,
      activityType = row.getOrElse("Activity_Type", "Unknown"),
      targetName = row.getOrElse("Target_Name", "Unknown"),
      bioAssayName = row.getOrElse("BioAssay_Name", "Unknown")
    )
