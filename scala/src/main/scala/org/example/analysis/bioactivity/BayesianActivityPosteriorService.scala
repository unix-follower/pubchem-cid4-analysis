package org.example.analysis.bioactivity

import org.apache.commons.csv.CSVFormat
import org.apache.commons.csv.CSVParser
import org.apache.commons.csv.CSVPrinter
import org.apache.commons.math3.distribution.BetaDistribution

import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import scala.jdk.CollectionConverters.*

final case class BayesianActivityPosteriorRowCounts(
    totalRows: Int,
    activeRows: Int,
    inactiveRows: Int,
    unspecifiedRows: Int,
    otherActivityRows: Int,
    retainedBinaryRows: Int,
    droppedNonBinaryRows: Int,
    retainedUniqueBioassays: Int
)

final case class BayesianActivityPrior(family: String, alpha: Double, beta: Double)

final case class BayesianActivityLikelihood(family: String, successLabel: String, failureLabel: String)

final case class BayesianActivityPosteriorDistribution(family: String, alpha: Double, beta: Double)

final case class BayesianActivityCredibleInterval(mass: Double, lower: Double, upper: Double)

final case class BayesianActivityPosteriorSummary(
    posteriorMeanProbabilityActive: Double,
    posteriorMedianProbabilityActive: Double,
    posteriorModeProbabilityActive: Option[Double],
    posteriorVariance: Double,
    credibleIntervalProbabilityActive: BayesianActivityCredibleInterval,
    posteriorProbabilityActiveGt0_5: Double,
    observedActiveFractionInRetainedRows: Double
)

final case class BayesianActivityPosteriorSection(
    prior: BayesianActivityPrior,
    likelihood: BayesianActivityLikelihood,
    posteriorDistribution: BayesianActivityPosteriorDistribution,
    summary: BayesianActivityPosteriorSummary
)

final case class BayesianActivityUpdateEquations(
    posteriorAlpha: String,
    posteriorBeta: String,
    posteriorMean: String
)

final case class BayesianActivityBinaryEvidenceDefinition(
    retainedLabels: Vector[String],
    excludedLabels: Vector[String],
    interpretation: String
)

final case class BayesianActivityRepresentativeRow(
    bioactivityId: Long,
    bioAssayAid: Long,
    activity: String,
    activityType: String,
    targetName: String,
    bioAssayName: String
)

final case class BayesianActivityAnalysis(
    targetQuantity: String,
    model: String,
    updateEquations: BayesianActivityUpdateEquations,
    binaryEvidenceDefinition: BayesianActivityBinaryEvidenceDefinition,
    representativeRows: Vector[BayesianActivityRepresentativeRow],
    notes: Vector[String]
)

final case class BayesianActivityPosteriorSummaryResult(
    rowCounts: BayesianActivityPosteriorRowCounts,
    posterior: BayesianActivityPosteriorSection,
    analysis: BayesianActivityAnalysis
)

final case class BayesianActivityPosteriorAnalysisResult(
    headers: Vector[String],
    rows: Vector[Map[String, String]],
    summary: BayesianActivityPosteriorSummaryResult
)

object BayesianActivityPosteriorService:
  private val CsvFormat = CSVFormat.DEFAULT.builder().setHeader().setSkipHeaderRecord(true).build()
  private val RequiredColumns = Vector("Bioactivity_ID", "BioAssay_AID", "Activity")
  private val DefaultPriorAlpha = 1.0
  private val DefaultPriorBeta = 1.0
  private val DefaultCredibleIntervalMass = 0.95

  def analyze(
      csvPath: Path,
      priorAlpha: Double = DefaultPriorAlpha,
      priorBeta: Double = DefaultPriorBeta,
      credibleIntervalMass: Double = DefaultCredibleIntervalMass
  ): BayesianActivityPosteriorAnalysisResult =
    require(priorAlpha > 0.0, "Posterior prior alpha must be positive")
    require(priorBeta > 0.0, "Posterior prior beta must be positive")
    require(credibleIntervalMass > 0.0 && credibleIntervalMass < 1.0, "Credible interval mass must be in (0, 1)")

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
      }.sortBy(row => (row("Activity"), row("BioAssay_AID").toLong, row("Bioactivity_ID").toLong))

      if retainedRows.isEmpty then
        throw IllegalStateException(s"No Active/Inactive rows were found in ${csvPath.getFileName}")

      val counts = BayesianActivityPosteriorRowCounts(
        totalRows = allRows.size,
        activeRows = activeRows,
        inactiveRows = inactiveRows,
        unspecifiedRows = unspecifiedRows,
        otherActivityRows = otherActivityRows,
        retainedBinaryRows = retainedRows.size,
        droppedNonBinaryRows = allRows.size - retainedRows.size,
        retainedUniqueBioassays = retainedRows.map(_("BioAssay_AID").toLong).distinct.size
      )

      val posteriorAlpha = priorAlpha + activeRows.toDouble
      val posteriorBeta = priorBeta + inactiveRows.toDouble
      val betaDistribution = new BetaDistribution(posteriorAlpha, posteriorBeta)
      val tailProbability = (1.0 - credibleIntervalMass) / 2.0
      val posteriorMode =
        if posteriorAlpha > 1.0 && posteriorBeta > 1.0 then Some((posteriorAlpha - 1.0) / (posteriorAlpha + posteriorBeta - 2.0))
        else None
      val representativeRows = selectRepresentativeRows(retainedRows)

      val summary = BayesianActivityPosteriorSummaryResult(
        rowCounts = counts,
        posterior = BayesianActivityPosteriorSection(
          prior = BayesianActivityPrior(
            family = "beta",
            alpha = priorAlpha,
            beta = priorBeta
          ),
          likelihood = BayesianActivityLikelihood(
            family = "binomial",
            successLabel = "Active",
            failureLabel = "Inactive"
          ),
          posteriorDistribution = BayesianActivityPosteriorDistribution(
            family = "beta",
            alpha = posteriorAlpha,
            beta = posteriorBeta
          ),
          summary = BayesianActivityPosteriorSummary(
            posteriorMeanProbabilityActive = posteriorAlpha / (posteriorAlpha + posteriorBeta),
            posteriorMedianProbabilityActive = betaDistribution.inverseCumulativeProbability(0.5),
            posteriorModeProbabilityActive = posteriorMode,
            posteriorVariance =
              (posteriorAlpha * posteriorBeta) /
                (math.pow(posteriorAlpha + posteriorBeta, 2) * (posteriorAlpha + posteriorBeta + 1.0)),
            credibleIntervalProbabilityActive = BayesianActivityCredibleInterval(
              mass = credibleIntervalMass,
              lower = betaDistribution.inverseCumulativeProbability(tailProbability),
              upper = betaDistribution.inverseCumulativeProbability(1.0 - tailProbability)
            ),
            posteriorProbabilityActiveGt0_5 = 1.0 - betaDistribution.cumulativeProbability(0.5),
            observedActiveFractionInRetainedRows = activeRows.toDouble / retainedRows.size.toDouble
          )
        ),
        analysis = BayesianActivityAnalysis(
          targetQuantity = "P(Active | CID=4)",
          model = "Beta-Binomial conjugate update",
          updateEquations = BayesianActivityUpdateEquations(
            posteriorAlpha = "alphaPost = alphaPrior + activeCount",
            posteriorBeta = "betaPost = betaPrior + inactiveCount",
            posteriorMean = "E[p | data] = alphaPost / (alphaPost + betaPost)"
          ),
          binaryEvidenceDefinition = BayesianActivityBinaryEvidenceDefinition(
            retainedLabels = Vector("Active", "Inactive"),
            excludedLabels = Vector("Unspecified"),
            interpretation =
              "Unspecified rows are excluded from the binary posterior update and reported only in row counts."
          ),
          representativeRows = representativeRows.map(toRepresentativeRow),
          notes = Vector(
            "This posterior is an aggregate CID 4 activity probability across retained binary bioassay outcomes.",
            "The update uses a Beta(1,1) prior and treats Active/Inactive outcomes as exchangeable Bernoulli evidence.",
            "Rows labeled Unspecified are kept out of the posterior update so they do not contribute artificial failures."
          )
        )
      )

      BayesianActivityPosteriorAnalysisResult(
        headers = headers,
        rows = retainedRows,
        summary = summary
      )
    finally
      parser.close()

  def writeCsv(result: BayesianActivityPosteriorAnalysisResult, outputPath: Path): Path =
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

  private def toRepresentativeRow(row: Map[String, String]): BayesianActivityRepresentativeRow =
    BayesianActivityRepresentativeRow(
      bioactivityId = row("Bioactivity_ID").toLong,
      bioAssayAid = row("BioAssay_AID").toLong,
      activity = row("Activity"),
      activityType = row.getOrElse("Activity_Type", "Unknown"),
      targetName = row.getOrElse("Target_Name", "Unknown"),
      bioAssayName = row.getOrElse("BioAssay_Name", "Unknown")
    )